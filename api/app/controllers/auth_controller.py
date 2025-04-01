import os
import secrets
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import httpx
import jwt as pyjwt  # Use PyJWT
from app.utils import mfa
from fastapi import HTTPException, status
from passlib.context import CryptContext
import percolate as p8
from app.models.user import UserCreate, UserProfile, Users, MFASetup
from percolate.utils import make_uuid
from app.models.user import TokenData

try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# JWT settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# OAuth providers
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

"""used for MFA context"""
API_APP_NAME = os.getenv("API_APP_NAME", "API")

def get_password_hash(password: str) -> str:
    """Generate a hashed password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = pyjwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode a JWT access token"""
    try:
        payload = pyjwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except pyjwt.exceptions.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def update_user(user_data: dict) -> Users:
    """Update a user state - register new or merge"""
    
    hashed_password = get_password_hash(user_data.get('password')) if user_data.get('password') else None
    """if the id exists we are ok otherwise hash the email as convention"""
    user_data['hashed_password'] = hashed_password
    user_data['id'] = user_data.get('id') or make_uuid(user_data['email'])
    user = Users( **user_data  )
    
    p8.repository(Users).update_records(user)
    
    return user


def authenticate_user(email: str, password: str) -> Optional[Users]:
    """Authenticate user with email and password
    We match the user by email in the database and match the hashed password
    """
    
    users = p8.repository(Users).select(email=email)
    if not users:
        return None
    
    if not verify_password(password, users[0]['hashed_password']):
        return None
    
    return Users(**users[0])

def get_user(user_id:str)->dict:
    """
    The Percolate reference here could be switched with other providers    
    """
    user =  p8.repository(Users).get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    """back compat - repo should return singular by id"""
    if isinstance(user, list):
        user = user[0]
 
    return user

def get_user_model(user_id:str)-> Optional[Users]:
    """
    ensure we are strongly typed
    """
    user = get_user(user_id)
    if user:
        return Users(**user)

def generate_mfa_setup(user_id: str|uuid.UUID) -> MFASetup:
    """Generate MFA setup for a user - save the secret and fetch"""
    user =  get_user(user_id)
    user['mfa_secret'] = mfa.generate_mfa_secret()
    update_user(user)
    qr_code = mfa.generate_mfa_qr_code(user['email'], user['mfa_secret'])
    return MFASetup(secret= user['mfa_secret'], qr_code=qr_code)


def verify_mfa_token(user_id: str, token: str) -> bool:
    """Verify a MFA token"""
    user = get_user_model(user_id)
    if not user or not user.mfa_secret:
        return False
    return mfa.verify_mfa_token(user.mfa_secret, token)


def enable_mfa(user_id: str) -> None:
    """Enable MFA for a user - should verify its setup first - this just shows intent and not that its setup"""
    user:Users = get_user(user_id)
    user['mfa_enabled'] = True
    update_user(user)

def create_session_object() -> TokenData:
    """Create a new session for a user - we can add this to the user object"""
    
    session_id = secrets.token_hex(32)
    expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return TokenData(session_id=session_id, session_expiry=expires.isoformat())

def get_user_profile(user_id: str, session_id: str, auth_method: str) -> UserProfile:
    """Get user profile with session information
    
    For now its single auth but in future users could log in with multiple providers
    """
    return UserProfile(
        **get_user(user_id)
    )
    
def get_user_profile_from_valid_session(session_id:str):
    """
    if the user matches a session that is not expired
    """

    users = p8.repository(Users).select(session_id=session_id)
    if users:
        u  = Users(**users[0])
        print(u)
        if not u.is_expired():
            return u
    return None


def logout(session_id):
    """logout by expiring the session in the database for subsequent calls"""
    
    Q = """UPDATE public."Users" set session_expiry=% where session_id=%"""
    
    result = p8.repository(Users).execute(Q, data=(session_id, datetime.utcnow().isoformat()))
    
    return result
    
async def get_google_user_info(access_token: str) -> Dict[str, Any]:
    """Get user information from Google"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate Google credentials"
            )
        
        return response.json()


async def exchange_google_code(code: str) -> Tuple[Dict[str, Any], str]:
    """Exchange authorization code for tokens with Google"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
            )
            
            if response.status_code != 200:
                print(f"Google token exchange failed: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to exchange Google authorization code"
                )
            
            data = response.json()
            access_token = data.get("access_token")
            
            user_info = await get_google_user_info(access_token)
            return user_info, access_token
    except Exception as e:
        print(f"Exception in exchange_google_code: {str(e)}")
        raise


def ensure_stripe_customer(user_id: str) -> str:
    """
    Ensure the user has a Stripe customer ID and save one if not in DB
    
    This function checks if a user already has a Stripe customer ID.
    If not, it creates a new Stripe customer and updates the user record.
    
    Args:
        user_id: User ID to check/create Stripe customer for
        
    Returns:
        Stripe customer ID
        
    Raises:
        HTTPException: If the user is not found or there's a Stripe error
    """
    # Import here to avoid circular imports
    from app.controllers.payment_controller import create_stripe_customer
    
    user = get_user_model(user_id)
   
    if user.stripe_customer_id:
        return user.stripe_customer_id
    
    try:
        stripe_customer = create_stripe_customer(
            user_id=user_id,
            email=user.email,
            name=user.name
        )
        
        sid = stripe_customer["id"]
        user_data = user.model_dump()
        user_data['stripe_customer_id'] = sid
        update_user(user_data)
        return sid
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Stripe customer: {str(e)}"
        )


 