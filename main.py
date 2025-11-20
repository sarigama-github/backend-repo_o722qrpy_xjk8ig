import os
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import ContactSubmission

app = FastAPI(title="Smart Krishi API", version="1.0.0")

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

# --- API placeholders matching planned frontend ---

# Image upload for disease detection (mock inference for now)
class DiseaseDetectionResponse(BaseModel):
    disease: str
    confidence: float
    recommendation: str

@app.post("/api/upload", response_model=DiseaseDetectionResponse)
async def upload_disease_image(file: UploadFile = File(...)):
    # In production, run ML model here. For now, return mock response.
    filename = file.filename or "image.jpg"
    return DiseaseDetectionResponse(
        disease="Leaf Blight (example)",
        confidence=0.87,
        recommendation="Apply Mancozeb 2g/L water, remove infected leaves, avoid overhead irrigation."
    )

# Weather endpoint (mock sample; integrate OpenWeather later)
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

# Mandi prices (mock list)
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

# Contact form submission - persisted in MongoDB
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
