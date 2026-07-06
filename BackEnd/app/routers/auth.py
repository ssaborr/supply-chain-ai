from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import AdminOut, LoginRequest
from app.services.auth_service import get_current_admin
from app.services.face_service import get_face_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Cosine similarity threshold
FACE_MATCH_THRESHOLD = 0.60

class FaceLoginRequest(BaseModel):
    image: str  # Base64 encoded image string
    email: Optional[EmailStr] = None

@router.post("/login")
async def login(login_data: LoginRequest, db = Depends(get_db)):
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection is not initialized"
        )

    email = login_data.email.lower()
    admin = await db["admin"].find_one({"email": email})
    if not admin or not verify_password(login_data.password, admin["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password"
        )
        
    # Force face scan for suppliers
    if admin.get("role") == "supplier":
        enrollments = admin.get("face_enrollments", [])
        if not enrollments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supplier biometric profile not enrolled. Please contact the administrator."
            )
        return {
            "status": "face_verification_required",
            "email": email
        }

    access_token = create_access_token(subject=str(admin["_id"]))
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login-face")
async def login_face(payload: FaceLoginRequest, db = Depends(get_db)):
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection is not initialized"
        )

    # Parse face image
    try:
        face_service = get_face_service()
        img = face_service.decode_base64_image(payload.image)
        query_embedding = face_service.detect_and_extract_face_embedding(img)
    except ValueError as val_err:
        logger.warning(f"Face login image validation failed: {val_err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err)
        )
    except Exception as e:
        logger.error(f"Failed to process face login image: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing face recognition. Please try again."
        )

    matched_user = None

    if payload.email:
        # 1-to-1 verify
        email_clean = payload.email.lower()
        user = await db["admin"].find_one({"email": email_clean})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found."
            )
        
        enrollments = user.get("face_enrollments", [])
        if not enrollments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No face enrollment registered for this account."
            )
            
        best_sim = -1.0
        for enrollment in enrollments:
            sim = face_service.calculate_cosine_similarity(query_embedding, enrollment["embedding"])
            if sim > best_sim:
                best_sim = sim
                
        logger.info(f"1-to-1 Face verification for {email_clean}: best similarity = {best_sim:.4f}")
        if best_sim >= FACE_MATCH_THRESHOLD:
            matched_user = user
    else:
        # 1-to-many match
        best_overall_sim = -1.0
        best_overall_user = None
        
        async for user in db["admin"].find():
            enrollments = user.get("face_enrollments", [])
            for enrollment in enrollments:
                sim = face_service.calculate_cosine_similarity(query_embedding, enrollment["embedding"])
                if sim > best_overall_sim:
                    best_overall_sim = sim
                    best_overall_user = user
                    
        logger.info(f"1-to-many Face identification: best similarity = {best_overall_sim:.4f}")
        if best_overall_sim >= FACE_MATCH_THRESHOLD:
            matched_user = best_overall_user

    if not matched_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Face not recognized or matching enrollment not found."
        )

    # Issue JWT
    access_token = create_access_token(subject=str(matched_user["_id"]))
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=AdminOut)
async def read_admin_me(current_admin: dict = Depends(get_current_admin)):
    # Check face enrollment status
    enrollments = current_admin.get("face_enrollments", [])
    current_admin["has_face_enrolled"] = len(enrollments) > 0
    return current_admin
