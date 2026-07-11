from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from bson import ObjectId
from app.core.config import settings
from app.core.database import get_db

security_scheme = HTTPBearer()

async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db = Depends(get_db)
) -> dict:
    
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        admin_id: str = payload.get("sub")
        if admin_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection is not initialized"
        )

    try:
        admin = await db["admin"].find_one({"_id": ObjectId(admin_id)})
    except Exception:
        raise credentials_exception
        
    if admin is None:
        raise credentials_exception
        
    # cast ObjectID to string for token encoding
    admin["id"] = str(admin["_id"])
    return admin


def _require_role(current_admin: dict, allowed_roles: set[str]) -> dict:
    if current_admin.get("role") not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource."
        )
    return current_admin


async def require_admin(current_admin: dict = Depends(get_current_admin)) -> dict:
    return _require_role(current_admin, {"admin"})


async def require_admin_role(current_admin: dict = Depends(get_current_admin)) -> dict:
    return _require_role(current_admin, {"admin", "sub_admin", "manager"})


async def require_supplier(current_admin: dict = Depends(get_current_admin)) -> dict:
    return _require_role(current_admin, {"supplier"})
