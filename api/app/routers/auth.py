import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, EmailStr

from app.controllers import auth_controller
from app.models.user import UserCreate, UserProfile, MFAVerify, MFASetup

router = APIRouter()

# Models for this router
class LoginCredentials(BaseModel):
    email: EmailStr
    password: str


class RegisterCredentials(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    password: str


# Auth endpoints
@router.post("/register", response_model=UserProfile)
async def register(credentials: RegisterCredentials):
    """Register a new user with email and password"""
    user_data = UserCreate(
        email=credentials.email,
        name=credentials.name,
        password=credentials.password
    )
    
    user = auth_controller.register_user(user_data)
    session_id = auth_controller.create_session(user.id)
    
    return auth_controller.get_user_profile(user.id, session_id, "password")


@router.post("/login", response_model=UserProfile)
async def login(credentials: LoginCredentials):
    """Login with email and password"""
    user = auth_controller.authenticate_user(credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    session_id = auth_controller.create_session(user.id)
    
    return auth_controller.get_user_profile(user.id, session_id, "password")


@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth flow"""
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    
    if not google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured"
        )
    
    scope = "email profile"
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={google_client_id}&redirect_uri={redirect_uri}&scope={scope}"
    
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_callback(code: str, request: Request):
    """Handle Google OAuth callback"""
    try:
        user_info, access_token = await auth_controller.exchange_google_code(code)
        
        # Check if user exists, if not register
        email = user_info.get("email")
        name = user_info.get("name")
        picture = user_info.get("picture")
        google_id = user_info.get("sub")
        
        # Try to find user by email or provider_user_id
        user = next((u for u in auth_controller.users_db.values() 
                    if u.email == email or 
                    (u.auth_provider == "google" and u.provider_user_id == google_id)), None)
        
        if not user:
            # Register new user
            user_data = UserCreate(
                email=email,
                name=name,
                avatar=picture,
                auth_provider="google",
                provider_user_id=google_id
            )
            user = auth_controller.register_user(user_data)
        
        session_id = auth_controller.create_session(user.id)
        user_profile = auth_controller.get_user_profile(user.id, session_id, "google")
        
        # In a real application, you might set cookies and redirect to a frontend
        response = JSONResponse(content=user_profile.dict())
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=3600 * 24,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with Google: {str(e)}"
        )


@router.get("/me", response_model=UserProfile)
async def get_current_user(session_id: str = Cookie(None)):
    """Get the current user profile"""
    if not session_id or session_id not in auth_controller.sessions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    session = auth_controller.sessions[session_id]
    user_id = session["user_id"]
    
    user = auth_controller.users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Determine auth method
    auth_method = "password"
    if user.auth_provider:
        auth_method = user.auth_provider
    
    return auth_controller.get_user_profile(user_id, session_id, auth_method)


@router.post("/logout")
async def logout(response: Response, session_id: str = Cookie(None)):
    """Logout the current user"""
    if session_id and session_id in auth_controller.sessions:
        # Remove session from database
        auth_controller.sessions.pop(session_id, None)
    
    # Clear cookies
    response.delete_cookie(key="session_id")
    
    return {"message": "Logged out successfully"}


@router.post("/mfa/setup", response_model=MFASetup)
async def setup_mfa(session_id: str = Cookie(None)):
    """Set up MFA for the current user"""
    if not session_id or session_id not in auth_controller.sessions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    session = auth_controller.sessions[session_id]
    user_id = session["user_id"]
    
    # Generate MFA setup
    return auth_controller.generate_mfa_setup(user_id)


@router.post("/mfa/verify")
async def verify_mfa(verification: MFAVerify, session_id: str = Cookie(None)):
    """Verify MFA code and enable MFA for the user"""
    if not session_id or session_id not in auth_controller.sessions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    session = auth_controller.sessions[session_id]
    user_id = session["user_id"]
    
    # Verify MFA code
    if not auth_controller.verify_mfa_token(user_id, verification.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code"
        )
    
    # Enable MFA for the user
    auth_controller.enable_mfa(user_id)
    
    return {"message": "MFA enabled successfully"}


@router.post("/mfa/validate")
async def validate_mfa(verification: MFAVerify, session_id: str = Cookie(None)):
    """Validate MFA code for existing session"""
    if not session_id or session_id not in auth_controller.sessions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    session = auth_controller.sessions[session_id]
    user_id = session["user_id"]
    
    # Verify MFA code
    if not auth_controller.verify_mfa_token(user_id, verification.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code"
        )
    
    return {"message": "MFA code is valid"}