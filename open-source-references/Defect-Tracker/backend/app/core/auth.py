import os
from fastapi import HTTPException, Security, Depends, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi.security.api_key import APIKeyHeader
from fastapi.security import OAuth2PasswordBearer
from app.db.session import get_db
from app.db.models import User, UserRole, Role, RoleScope, Scope

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_api_key(api_key: str = Security(api_key_header)):
    if api_key is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    elif api_key == os.getenv("DEFECT_TRACKER_API_KEY"):
        return "Demo User"  # In a real application, you would look up the user associated with the API key
    else:
        raise HTTPException(status_code=401, detail="Could not validate API key")
    
JWT_ALG = "HS256"

def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
) -> User:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not set")
    
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALG])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = UUID(sub)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

def require_scopes(required_scopes: list[str]):
    def _dep(
            user: User = Depends(get_current_user),
            db: Session = Depends(get_db)
    ) -> User:
        # Get all scopes for this via joins
        rows = (
            db.query(Scope.name)
            .join(RoleScope, RoleScope.scope_id == Scope.id)
            .join(Role, Role.id == RoleScope.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user.id)
            .all()
        )

        user_scopes = {row[0] for row in rows}

        missing ={s for s in required_scopes if s not in user_scopes}
        if missing:
            raise HTTPException(status_code=403, detail=f"Missing scopes: {missing}")
        
        return user
    
    return _dep
    

    
