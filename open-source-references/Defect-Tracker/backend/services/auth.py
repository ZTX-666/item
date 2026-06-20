import os
from datetime import datetime, timedelta, timezone
from jose import jwt 
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_ALG = "HS256"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(subject: str) -> str:
    secret = os.getenv("JWT_SECRET", "dev-secret-change-me")
    expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    exp = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {"sub": subject, "exp": exp}
    return jwt.encode(payload, secret, algorithm=JWT_ALG)