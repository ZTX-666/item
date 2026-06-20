from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.db.session import get_db
from app.db.models import User, UserRole, Role, RoleScope, Scope
from schemas.auth import LoginRequest, TokenResponse, MeResponse
from services.auth import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)

@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    roles = db.query(Role.name).join(UserRole, UserRole.role_id == Role.id).filter(UserRole.user_id == current_user.id).all()
    scopes = db.query(Scope.name).join(RoleScope, RoleScope.scope_id == Scope.id).join(UserRole, UserRole.role_id == RoleScope.role_id).filter(UserRole.user_id == current_user.id).all()
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        roles=sorted(set(role[0] for role in roles)),
        scopes=sorted(set(scope[0] for scope in scopes))
    )