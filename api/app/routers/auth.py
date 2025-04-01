import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, EmailStr
import traceback
from app.controllers import auth_controller
from app.models.user import UserCreate, UserProfile, MFAVerify, MFASetup,TokenData
import json

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
@router.post("/register")
async def register(credentials: RegisterCredentials, redirect_url: Optional[str] = None):
    """Register a new user with email and password with optional redirect"""
    user_data = UserCreate(
        email=credentials.email,
        name=credentials.name,
        password=credentials.password
    )
    
    user = auth_controller.update_user(user_data)
    session_id = auth_controller.create_session_object(user.id)
    user_profile = auth_controller.get_user_profile(user.id, session_id, "password")
    
    # If a redirect URL was provided, send the user there
    if redirect_url:
        # If the URL contains a special placeholder for profile data, replace it
        if "profile_data" in redirect_url:
            import urllib.parse
            user_json = urllib.parse.quote(json.dumps(user_profile.model_dump()))
            redirect_url = redirect_url.replace("profile_data", user_json)
        
        # Create response with redirect
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
        
        # Set cookie if it's not a data transfer redirect
        if "profile_data" not in redirect_url:
            response.set_cookie(
                key="session_id",
                value=session_id,
                httponly=True,
                max_age=3600 * 24,
                samesite="lax"
            )
    else:
        # No redirect - return user profile as JSON
        response = JSONResponse(content=user_profile.model_dump())
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=3600 * 24,
            samesite="lax"
        )
    
    return response


@router.post("/login")
async def login(credentials: LoginCredentials, redirect_url: Optional[str] = None):
    """Login with email and password with optional redirect"""
    user = auth_controller.authenticate_user(credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    session_id = auth_controller.create_session_object(user.id)
    user_profile = auth_controller.get_user_profile(user.id, session_id, "password")
    
    # If a redirect URL was provided, send the user there
    if redirect_url:
        # If the URL contains a special placeholder for profile data, replace it
        if "profile_data" in redirect_url:
            import urllib.parse
            user_json = urllib.parse.quote(json.dumps(user_profile.model_dump()))
            redirect_url = redirect_url.replace("profile_data", user_json)
        
        # Create response with redirect
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
        
        # Set cookie if it's not a data transfer redirect
        if "profile_data" not in redirect_url:
            response.set_cookie(
                key="session_id",
                value=session_id,
                httponly=True,
                max_age=3600 * 24,
                samesite="lax"
            )
    else:
        # No redirect - return user profile as JSON
        response = JSONResponse(content=user_profile.model_dump())
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=3600 * 24,
            samesite="lax"
        )
    
    return response


@router.get("/google/login")
async def google_login(redirect_url: Optional[str] = None):
    """Initiate Google OAuth flow with optional redirect URL"""
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    
    if not google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured"
        )
    
    scope = "email profile"
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={google_client_id}&redirect_uri={redirect_uri}&scope={scope}"
    
    # Add state parameter with redirect URL if provided
    if redirect_url:
        import base64
        encoded_redirect = base64.urlsafe_b64encode(redirect_url.encode()).decode()
        google_auth_url += f"&state={encoded_redirect}"
    
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_callback(code: str, state: Optional[str] = None, request: Request = None):
    """Handle Google OAuth callback with redirect support"""
    try:
  
        
        user_info, access_token = await auth_controller.exchange_google_code(code)
    
       
        """get provider info"""
        user_info['avatar'] = user_info.get("picture")
        user_info['provider_user_id'] = user_info.get("sub")
        user_info['auth_method'] = 'google'
        
        token = auth_controller.create_session_object()
        """merge it into the user data"""
        user_info.update(token.model_dump())
        print('HANDLING CALLBACK', user_info)
                
        user = auth_controller.update_user(user_info)
        
        # Check if there's a redirect URL in the state parameter
        redirect_url = None
        if state:
            try:
                import base64
                decoded_redirect = base64.urlsafe_b64decode(state.encode()).decode()
                if decoded_redirect:
                    redirect_url = decoded_redirect
            except Exception as e:
                print(f"Error decoding redirect URL: {str(e)}")
        
        # If a redirect URL was provided, send the user there
        if redirect_url:
            # If the URL contains a special placeholder for profile data, replace it
            if "profile_data" in redirect_url:
                import urllib.parse
                user_json = urllib.parse.quote(json.dumps(user.model_dump()))
                redirect_url = redirect_url.replace("profile_data", user_json)
            
            # Create response with redirect
            response = RedirectResponse(url=redirect_url)
            
            # Set cookie if it's a same-site redirect (optional)
            if redirect_url.startswith(str(request.base_url)[:str(request.base_url).rfind(":")]):
                response.set_cookie(
                    key="session_id",
                    value=user.session_id,
                    httponly=True,
                    max_age=3600 * 24,
                    samesite="lax"
                )
        else:
            # No redirect - return user profile as JSON
            response = JSONResponse(content=user.model_dump())
            response.set_cookie(
                key="session_id",
                value=user.session_id,
                httponly=True,
                max_age=3600 * 24,
                samesite="lax"
            )
        
        return response
        
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with Google: {str(e)}"
        )


@router.get("/me", response_model=UserProfile)
async def get_current_user(session_id: str = Cookie(None)):
    """Get the current user profile from the session if it has not expired
    Will raise 401 not authenticated if a valid session cannot be found
    """
    profile = auth_controller.get_user_profile_from_valid_session(session_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return profile


@router.put("/ensure-stripe-customer", response_model=UserProfile)
async def ensure_stripe_customer(session_id: str = Cookie(None)):
    """
    stripe customers can be created implicitly or we can specifically request to attach a stripe customer with this endpoint
    """
    try:
        profile = auth_controller.get_user_profile_from_valid_session(session_id)
        
        print(f'Ensure profile in stripe - {profile}')
        """we can create the stripe user and save it - the customer id is returned but we reload from the database as sanity check"""
        customer_id = auth_controller.ensure_stripe_customer(profile.id)
        
        """reload check"""
        return auth_controller.get_user_profile_from_valid_session(session_id)
    except Exception as ex:
        print(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(ex))

@router.post("/logout")
async def logout(response: Response, session_id: str = Cookie(None)):
    """Logout the current user"""
  
    auth_controller.logout(session_id)
    
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