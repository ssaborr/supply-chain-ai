import datetime
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import AdminCreate, AdminOut
from app.services.auth_service import get_current_admin
from app.services.face_service import get_face_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admins", tags=["Admins"])

class FaceEnrollRequest(BaseModel):
    image: str  # Base64 encoded image string

@router.get("/", response_model=List[AdminOut])
async def list_admins(db = Depends(get_db), current_admin: dict = Depends(get_current_admin)):
    admins = []
    async for admin in db["admin"].find():
        admin_id = str(admin.pop("_id"))
        enrollments = admin.get("face_enrollments", [])
        has_face_enrolled = len(enrollments) > 0
        admins.append({
            **admin,
            "id": admin_id,
            "has_face_enrolled": has_face_enrolled
        })
    return admins

@router.post("/", response_model=AdminOut, status_code=status.HTTP_201_CREATED)
async def create_admin(
    admin_in: AdminCreate,
    db = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    if current_admin.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage users and permissions."
        )

    # Check duplicate email
    email_clean = admin_in.email.lower()
    existing = await db["admin"].find_one({"email": email_clean})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    admin_dict = admin_in.dict()
    password = admin_dict.pop("password")
    admin_dict["hashed_password"] = get_password_hash(password)
    admin_dict["email"] = email_clean
    admin_dict["face_enrollments"] = []

    result = await db["admin"].insert_one(admin_dict)
    new_admin = await db["admin"].find_one({"_id": result.inserted_id})
    
    admin_id = str(new_admin.pop("_id"))
    return {
        **new_admin,
        "id": admin_id,
        "has_face_enrolled": False
    }

@router.delete("/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin(
    admin_id: str,
    db = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    if current_admin.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage users and permissions."
        )

    if admin_id == current_admin.get("id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own admin account."
        )

    try:
        oid = ObjectId(admin_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format."
        )

    result = await db["admin"].delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
#enroll face
@router.post("/{admin_id}/enroll-face", response_model=AdminOut)
async def enroll_user_face(
    admin_id: str,
    payload: FaceEnrollRequest,
    db = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    # Enforce admin or self enrollment
    if current_admin.get("role") != "admin" and current_admin.get("id") != admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to enroll face for this user."
        )

    try:
        oid = ObjectId(admin_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format."
        )

    user = await db["admin"].find_one({"_id": oid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    # Parse face image
    try:
        face_service = get_face_service()
        img = face_service.decode_base64_image(payload.image)
        embedding = face_service.detect_and_extract_face_embedding(img)
    except ValueError as val_err:
        logger.warning(f"Face enrollment validation failed: {val_err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err)
        )
    except Exception as e:
        logger.error(f"Failed to process face enrollment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing face recognition model. Please try again."
        )

    enrollment = {
        "embedding": embedding.tolist(),
        "enrolled_at": datetime.datetime.utcnow().isoformat() + "Z"
    }

    # Store face enrollment
    await db["admin"].update_one(
        {"_id": oid},
        {"$push": {"face_enrollments": enrollment}}
    )

    updated_user = await db["admin"].find_one({"_id": oid})
    uid = str(updated_user.pop("_id"))
    enrollments = updated_user.get("face_enrollments", [])
    has_face_enrolled = len(enrollments) > 0
    return {
        **updated_user,
        "id": uid,
        "has_face_enrolled": has_face_enrolled
    }

@router.delete("/{admin_id}/enroll-face", response_model=AdminOut)
async def delete_user_face(
    admin_id: str,
    db = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    if current_admin.get("role") != "admin" and current_admin.get("id") != admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify face enrollments for this user."
        )

    try:
        oid = ObjectId(admin_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format."
        )

    user = await db["admin"].find_one({"_id": oid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    await db["admin"].update_one(
        {"_id": oid},
        {"$set": {"face_enrollments": []}}
    )

    updated_user = await db["admin"].find_one({"_id": oid})
    uid = str(updated_user.pop("_id"))
    return {
        **updated_user,
        "id": uid,
        "has_face_enrolled": False
    }
