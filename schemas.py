"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal

# Example schemas (kept for reference/testing)
class User(BaseModel):
    """
    Example Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Example Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Smart Krishi specific schemas
class ContactSubmission(BaseModel):
    """
    Contact form submissions from website
    Collection name: "contactsubmission"
    """
    name: str = Field(..., description="Farmer name")
    phone: str = Field(..., description="Phone number")
    village: Optional[str] = Field(None, description="Village")
    district: Optional[str] = Field(None, description="District")
    message: Optional[str] = Field(None, description="Message from user")
    source: str = Field("web", description="Submission source: web/app")

class AppUser(BaseModel):
    """Registered users (OTP-based) -> collection: "appuser""" 
    userId: Optional[str] = Field(None, description="External user id (string version of ObjectId)")
    name: str
    phone: str
    village: Optional[str] = None
    district: Optional[str] = None
    crops: List[str] = []

class CropDiagnosis(BaseModel):
    """AI diagnosis records -> collection: "cropdiagnosis"""
    diagnosisId: Optional[str] = None
    userId: Optional[str] = None
    crop: Optional[str] = None
    imageURL: Optional[str] = None
    diseaseName: str
    probability: float
    recommendation: str
    pesticide: Optional[str] = None

class WeatherAlert(BaseModel):
    """User weather alert tracking -> collection: "weatheralert"""
    userId: str
    location: str
    lastAlertSent: Optional[str] = None

class MandiPriceRecord(BaseModel):
    """Mandi price cache -> collection: "mandipricerecord"""
    mandiId: Optional[str] = None
    district: str
    crop: str
    price: float

class Notification(BaseModel):
    """User notifications -> collection: "notification"""
    userId: str
    type: Literal["weather", "mandi", "fertilizer"]
    message: str
