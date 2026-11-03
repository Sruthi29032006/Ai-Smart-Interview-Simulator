import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import User, Profile
from ..security import hash_password, verify_password, create_token, new_reset_token

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("auth")


class Register(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class Login(BaseModel):
    email: EmailStr
    password: str


class Forgot(BaseModel):
    email: EmailStr


class Reset(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


def user_out(u: User):
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role}


@router.post("/register", status_code=201)
def register(body: Register, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Email already registered")
    u = User(email=email, full_name=body.full_name.strip(), password_hash=hash_password(body.password),
             role="admin" if settings.admin_email and email == settings.admin_email else "candidate")
    u.profile = Profile()
    db.add(u); db.commit()
    return {"token": create_token(u.id), "user": user_out(u)}


@router.post("/login")
def login(body: Login, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=body.email.lower()).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"token": create_token(u.id), "user": user_out(u)}


@router.get("/me")
def me(u: User = Depends(current_user)):
    return user_out(u)


@router.post("/forgot")
def forgot(body: Forgot, db: Session = Depends(get_db)):
    """Local setup has no email server: the reset link is printed in the backend console."""
    u = db.query(User).filter_by(email=body.email.lower()).first()
    if u:
        u.reset_token = new_reset_token(); u.reset_expires = datetime.utcnow() + timedelta(minutes=30)
        db.commit()
        log.warning("PASSWORD RESET for %s -> http://localhost:5173/reset?token=%s", u.email, u.reset_token)
    return {"detail": "If the account exists, a reset link has been written to the backend console (no email server is configured)."}


@router.post("/reset")
def reset(body: Reset, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(reset_token=body.token).first()
    if not u or not u.reset_expires or u.reset_expires < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired reset token")
    u.password_hash = hash_password(body.password); u.reset_token = None; u.reset_expires = None
    db.commit()
    return {"detail": "Password updated"}
