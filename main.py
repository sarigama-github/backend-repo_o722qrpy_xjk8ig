import os
import io
import random
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import requests
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import ContactSubmission

app = FastAPI(title="Smart Krishi API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Smart Krishi Backend Running"}

# --- Health + DB test ---
@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', None) or "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# -----------------------
# Disease detection upload
# -----------------------
class DiseaseDetectionResult(BaseModel):
    disease: str
    accuracy: float
    recommended_pesticide: str
    cost_estimate: str
    preventive_tips: List[str]

@app.post("/api/detect-disease", response_model=DiseaseDetectionResult)
async def detect_disease(
    image: UploadFile = File(...),
    crop: str = Form(...),
    userId: Optional[str] = Form(None),
):
    # NOTE: In production, forward image to ML microservice. Here we mock.
    _ = await image.read()  # read to ensure upload works
    mock_diseases = [
        ("Leaf Blight", "Mancozeb 2g/L", [
            "Remove infected leaves",
            "Avoid overhead irrigation",
            "Use disease-free seeds",
        ]),
        ("Powdery Mildew", "Sulfur Dust 25kg/ha", [
            "Improve air circulation",
            "Apply fungicide at dusk",
            "Avoid excess nitrogen",
        ]),
        ("Rust", "Propiconazole 1ml/L", [
            "Rotate crops",
            "Resistant varieties",
            "Destroy crop residues",
        ]),
    ]
    disease, pesticide, tips = random.choice(mock_diseases)
    accuracy = round(random.uniform(0.78, 0.97), 2)
    cost_estimate = f"₹{random.randint(280, 850)}/acre"

    return DiseaseDetectionResult(
        disease=f"{crop} {disease}",
        accuracy=accuracy,
        recommended_pesticide=pesticide,
        cost_estimate=cost_estimate,
        preventive_tips=tips,
    )

# Legacy placeholder kept for compatibility
class DiseaseDetectionResponse(BaseModel):
    disease: str
    confidence: float
    recommendation: str

@app.post("/api/upload", response_model=DiseaseDetectionResponse)
async def upload_disease_image(file: UploadFile = File(...)):
    return DiseaseDetectionResponse(
        disease="Leaf Blight (example)",
        confidence=0.87,
        recommendation="Apply Mancozeb 2g/L water, remove infected leaves, avoid overhead irrigation.",
    )

# -----------------------
# Weather API (OpenWeather)
# -----------------------
class WeatherResponse(BaseModel):
    temperature_c: float
    rain_probability: int
    humidity: int
    wind_speed: float
    recommendation: str


def _recommend_irrigation(temp_c: float, rain_prob: int, humidity: int, wind_speed: float) -> str:
    if rain_prob >= 60:
        return "High rain chance – postpone irrigation and ensure drainage."
    if temp_c >= 34 and humidity < 40:
        return "Hot and dry – irrigate in early morning/evening, consider mulching."
    if wind_speed > 20:
        return "Windy – avoid spraying; irrigate lightly to reduce stress."
    if humidity > 80:
        return "Humid – reduce irrigation to prevent fungal diseases."
    return "Normal conditions – maintain regular irrigation schedule."

@app.get("/api/weather/{lat}/{lon}", response_model=WeatherResponse)
def get_weather_coords(lat: float, lon: float):
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        # Fallback mock if key isn't set
        temp = round(random.uniform(24, 35), 1)
        rain = random.randint(0, 90)
        humidity = random.randint(35, 88)
        wind = round(random.uniform(2, 18), 1)
        return WeatherResponse(
            temperature_c=temp,
            rain_probability=rain,
            humidity=humidity,
            wind_speed=wind,
            recommendation=_recommend_irrigation(temp, rain, humidity, wind),
        )
    try:
        # OpenWeather One Call 3.0 or current weather + forecast
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        temp = data.get("main", {}).get("temp", 30.0)
        humidity = int(data.get("main", {}).get("humidity", 60))
        wind = float(data.get("wind", {}).get("speed", 4.0))
        rain_prob = 0
        # try to get probability from precipitation or weather
        if "rain" in data and "1h" in data["rain"]:
            rain_prob = min(90, int(data["rain"]["1h"] * 50))
        return WeatherResponse(
            temperature_c=float(temp),
            rain_probability=int(rain_prob),
            humidity=humidity,
            wind_speed=wind,
            recommendation=_recommend_irrigation(float(temp), int(rain_prob), humidity, wind),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenWeather error: {str(e)[:120]}")

# Weather alerts subscription (toggle ON)
class WeatherSubscribeRequest(BaseModel):
    userId: str
    lat: float
    lon: float

class WeatherSubscribeResponse(BaseModel):
    success: bool

@app.post("/api/weather/subscribe", response_model=WeatherSubscribeResponse)
def subscribe_weather(payload: WeatherSubscribeRequest):
    try:
        doc = {
            "userId": payload.userId,
            "lat": payload.lat,
            "lon": payload.lon,
            "createdAt": datetime.utcnow(),
            "active": True,
        }
        _id = create_document("weatheralert", doc)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------
# Mandi Prices
# -----------------------
class MandiItem(BaseModel):
    crop: str
    price: int

class MandiTrendPoint(BaseModel):
    date: str
    crop: str
    price: int

class MandiResponse(BaseModel):
    district: str
    items: List[MandiItem]
    trend: List[MandiTrendPoint]
    best_mandi: str
    best_crop: str
    best_price: int

@app.get("/api/mandi/{district}", response_model=MandiResponse)
def get_mandi_district(district: str):
    # In production fetch govt API + cache. Here we mock.
    crops = ["Wheat", "Soyabean", "Maize", "Rice"]
    base_prices = {"Wheat": 2140, "Soyabean": 4400, "Maize": 1860, "Rice": 2500}
    items = []
    for c in crops:
        p = base_prices[c] + random.randint(-120, 150)
        items.append({"crop": c, "price": p})

    # generate 7-day trend for the best crop
    best = max(items, key=lambda x: x["price"])
    trend: List[Dict[str, Any]] = []
    for i in range(7):
        date = (datetime.utcnow() - timedelta(days=6 - i)).strftime("%b %d")
        for c in crops:
            base = base_prices[c]
            price = base + random.randint(-180, 180)
            trend.append({"date": date, "crop": c, "price": price})

    return {
        "district": district.title(),
        "items": items,
        "trend": trend,
        "best_mandi": f"{district.title()} Central",
        "best_crop": best["crop"],
        "best_price": best["price"],
    }

# -----------------------
# Demo endpoints
# -----------------------
@app.get("/api/demo/weather", response_model=WeatherResponse)
def demo_weather():
    return WeatherResponse(
        temperature_c=31.5,
        rain_probability=70,
        humidity=78,
        wind_speed=6.2,
        recommendation=_recommend_irrigation(31.5, 70, 78, 6.2),
    )

class DemoMandiResponse(BaseModel):
    district: str
    items: List[MandiItem]

@app.get("/api/demo/mandi", response_model=DemoMandiResponse)
def demo_mandi():
    return DemoMandiResponse(
        district="Bhopal",
        items=[
            {"crop": "Wheat", "price": 2140},
            {"crop": "Soyabean", "price": 4400},
            {"crop": "Maize", "price": 1860},
        ],
    )

@app.post("/api/demo/detect-disease", response_model=DiseaseDetectionResult)
async def demo_detect_disease(image: UploadFile = File(None), crop: str = Form("Wheat")):
    tips = [
        "Remove infected leaves",
        "Use copper-based fungicide",
        "Improve field sanitation",
    ]
    return DiseaseDetectionResult(
        disease=f"{crop} Leaf Spot",
        accuracy=0.91,
        recommended_pesticide="Copper oxychloride 2g/L",
        cost_estimate="₹450/acre",
        preventive_tips=tips,
    )

class FertilizerPlanItem(BaseModel):
    stage: str
    recommendation: str

class FertilizerDemoResponse(BaseModel):
    crop: str
    plan: List[FertilizerPlanItem]

@app.get("/api/demo/fertilizer", response_model=FertilizerDemoResponse)
def demo_fertilizer(crop: str = "Wheat"):
    plans = {
        "Wheat": [
            {"stage": "Basal", "recommendation": "DAP 100kg/acre + MOP 20kg/acre"},
            {"stage": "Tillering", "recommendation": "Urea 45kg/acre"},
            {"stage": "Heading", "recommendation": "Urea 20kg/acre + Micronutrients"},
        ],
        "Rice": [
            {"stage": "Basal", "recommendation": "NPK 17:17:17 at 80kg/acre"},
            {"stage": "Active tillering", "recommendation": "Urea 25kg/acre"},
            {"stage": "Panicle initiation", "recommendation": "Urea 15kg/acre + ZnSO4 5kg/acre"},
        ],
    }
    plan = plans.get(crop, plans["Wheat"])
    return FertilizerDemoResponse(crop=crop, plan=plan)

# -----------------------
# Contact form (persisted)
# -----------------------
class ContactCreate(BaseModel):
    name: str
    phone: str
    village: Optional[str] = None
    district: Optional[str] = None
    message: Optional[str] = None

class ContactCreateResponse(BaseModel):
    id: str

@app.post("/api/contact", response_model=ContactCreateResponse)
def submit_contact(payload: ContactCreate):
    submission = ContactSubmission(
        name=payload.name,
        phone=payload.phone,
        village=payload.village,
        district=payload.district,
        message=payload.message,
        source="web",
    )
    try:
        inserted_id = create_document("contactsubmission", submission)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------
# Legacy mocks (kept)
# -----------------------
class WeatherItem(BaseModel):
    time: str
    temperature_c: float
    rainfall_mm: float
    tip: str

@app.get("/api/weather", response_model=List[WeatherItem])
def get_weather(location: Optional[str] = None):
    return [
        {"time": "Now", "temperature_c": 29.5, "rainfall_mm": 0.0, "tip": "Irrigate in evening"},
        {"time": "+3h", "temperature_c": 27.8, "rainfall_mm": 0.0, "tip": "Mulch to retain moisture"},
        {"time": "+6h", "temperature_c": 25.1, "rainfall_mm": 2.4, "tip": "Light showers expected"},
        {"time": "+24h", "temperature_c": 31.2, "rainfall_mm": 0.0, "tip": "Avoid midday irrigation"},
    ]

class MandiPrice(BaseModel):
    crop: str
    location: str
    price_per_quintal: int

@app.get("/api/mandi", response_model=List[MandiPrice])
def get_mandi_prices(crop: Optional[str] = None, district: Optional[str] = None):
    data = [
        {"crop": "Wheat", "location": "Kanpur", "price_per_quintal": 2150},
        {"crop": "Rice", "location": "Raipur", "price_per_quintal": 2400},
        {"crop": "Cotton", "location": "Nagpur", "price_per_quintal": 6100},
        {"crop": "Soybean", "location": "Indore", "price_per_quintal": 4900},
    ]
    if crop:
        data = [d for d in data if d["crop"].lower() == crop.lower()]
    if district:
        data = [d for d in data if d["location"].lower() == district.lower()]
    return data

# Simple OTP login mock
class LoginRequest(BaseModel):
    phone: str

class LoginResponse(BaseModel):
    success: bool
    message: str

@app.post("/api/login", response_model=LoginResponse)
def otp_login(payload: LoginRequest):
    if not payload.phone or len(payload.phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    return LoginResponse(success=True, message="OTP sent to your number")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
