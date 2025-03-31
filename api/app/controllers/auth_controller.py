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

from app.models.user import UserCreate, UserProfile, UserInDB, MFASetup

# Password hashing context
try:
    # Try to use bcrypt
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    # Fall back to pbkdf2_sha256 if bcrypt is not available
    print("Warning: bcrypt not available, falling back to pbkdf2_sha256")
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# JWT settings
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# OAuth providers
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

# App name for MFA
API_APP_NAME = os.getenv("API_APP_NAME", "API")

# Mock database for users (replace with real DB)
users_db = {}
sessions = {}


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


def register_user(user_data: UserCreate) -> UserInDB:
    """Register a new user"""
    if user_data.email in [user.email for user in users_db.values()]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user_data.password) if user_data.password else None
    
    user_db = UserInDB(
        id=user_id,
        email=user_data.email,
        name=user_data.name,
        avatar=user_data.avatar,
        hashed_password=hashed_password,
        auth_provider=user_data.auth_provider,
        provider_user_id=user_data.provider_user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        mfa_secret=None,
        mfa_enabled=False,
        stripe_customer_id=None  # Initialize with no Stripe customer
    )
    
    # Save to mock database (replace with real DB operation)
    users_db[user_id] = user_db
    
    return user_db


def authenticate_user(email: str, password: str) -> Optional[UserInDB]:
    """Authenticate user with email and password"""
    user = next((u for u in users_db.values() if u.email == email), None)
    
    if not user or not user.hashed_password:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    return user


def generate_mfa_setup(user_id: str) -> MFASetup:
    """Generate MFA setup for a user"""
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Generate secret
    secret = mfa.generate_mfa_secret()
    
    # Save to user (replace with real DB operation)
    user.mfa_secret = secret
    users_db[user_id] = user
    
    # Generate QR code
    qr_code = mfa.generate_mfa_qr_code(user.email, secret)
    
    return MFASetup(secret=secret, qr_code=qr_code)


def verify_mfa_token(user_id: str, token: str) -> bool:
    """Verify a MFA token"""
    user = users_db.get(user_id)
    if not user or not user.mfa_secret:
        return False
    
    return mfa.verify_mfa_token(user.mfa_secret, token)


def enable_mfa(user_id: str) -> None:
    """Enable MFA for a user"""
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA not set up for this user"
        )
    
    user.mfa_enabled = True
    users_db[user_id] = user


def create_session(user_id: str) -> str:
    """Create a new session for a user"""
    session_id = secrets.token_hex(32)
    expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Save to sessions (replace with real DB operation)
    sessions[session_id] = {
        "user_id": user_id,
        "expires": expires
    }
    
    return session_id


def get_user_profile(user_id: str, session_id: str, auth_method: str) -> UserProfile:
    """Get user profile with session information"""
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    session = sessions.get(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
    
    return UserProfile(
        user_id=user.id,
        email=user.email,
        name=user.name,
        avatar=user.avatar,
        session_id=session_id,
        auth_method=auth_method,
        session_expiry=session["expires"],
        mfa_enabled=user.mfa_enabled
    )


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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange Google authorization code"
            )
        
        data = response.json()
        access_token = data.get("access_token")
        
        user_info = await get_google_user_info(access_token)
        return user_info, access_token


def ensure_stripe_customer(user_id: str) -> str:
    """
    Ensure the user has a Stripe customer ID
    
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
    
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # If user already has a Stripe customer ID, return it
    if user.stripe_customer_id:
        return user.stripe_customer_id
    
    # Otherwise, create a new Stripe customer
    try:
        # Create Stripe customer using user data
        stripe_customer = create_stripe_customer(
            user_id=user_id,
            email=user.email,
            name=user.name
        )
        
        # Update user with Stripe customer ID
        user.stripe_customer_id = stripe_customer["id"]
        users_db[user_id] = user
        
        return user.stripe_customer_id
    except HTTPException as e:
        # Re-raise the HTTP exception
        raise e
    except Exception as e:
        # Handle any other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Stripe customer: {str(e)}"
        )


def update_user(user_id: str, **update_data) -> UserInDB:
    """
    Update a user's information
    
    This function updates a user's information in the database.
    
    Args:
        user_id: User ID to update
        **update_data: Fields to update
        
    Returns:
        Updated user object
        
    Raises:
        HTTPException: If the user is not found
    """
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user fields
    for field, value in update_data.items():
        if hasattr(user, field):
            setattr(user, field, value)
    
    # Update the timestamp
    user.updated_at = datetime.utcnow()
    
    # Save to database
    users_db[user_id] = user
    
    return user