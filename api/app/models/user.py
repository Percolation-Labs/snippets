from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    avatar: Optional[str] = None


class UserCreate(UserBase):
    password: Optional[str] = None
    auth_provider: Optional[str] = None
    provider_user_id: Optional[str] = None


class UserProfile(UserBase):
    user_id: str
    session_id: str
    auth_method: str
    session_expiry: datetime | str
    mfa_enabled: bool = False
    
    
class TokenData(BaseModel):
    user_id: str
    expires: datetime


class UserInDB(UserBase):
    id: str
    hashed_password: Optional[str] = None
    auth_provider: Optional[str] = None
    provider_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    mfa_secret: Optional[str] = None
    mfa_enabled: bool = False
    subscription_tier: str = "Free"
    credits: int = 0
    stripe_customer_id: Optional[str] = None


class MFASetup(BaseModel):
    secret: str
    qr_code: str


class MFAVerify(BaseModel):
    code: str