from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

class FaceEnrollment(BaseModel):
    embedding: List[float]
    enrolled_at: str

class AdminBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: str = "admin"
    supplier_name: Optional[str] = None
    allowed_tabs: Optional[List[str]] = []
    face_enrollments: Optional[List[FaceEnrollment]] = []

class AdminCreate(AdminBase):
    password: str

class AdminUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    allowed_tabs: Optional[List[str]] = None

class AdminOut(AdminBase):
    id: str = Field(..., alias="id")
    has_face_enrolled: Optional[bool] = False

    class Config:
        populate_by_name = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
