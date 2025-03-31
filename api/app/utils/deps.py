from fastapi import Depends, HTTPException, status, Cookie
from typing import Optional

from app.controllers import auth_controller


def get_current_user_id(session_id: str = Cookie(None)) -> str:
    """Get the current user ID from session cookie"""
    if not session_id or session_id not in auth_controller.sessions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    session = auth_controller.sessions[session_id]
    return session["user_id"]


def require_mfa(user_id: str, mfa_token: Optional[str] = None) -> bool:
    """Check if the user has MFA enabled and validate MFA token if provided"""
    user = auth_controller.users_db.get(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # If user doesn't have MFA enabled, no validation needed
    if not user.mfa_enabled:
        return True
    
    # If user has MFA enabled but no token provided, require MFA
    if not mfa_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA token required",
            headers={"X-MFA-Required": "true"},
        )
    
    # Verify MFA token
    if not auth_controller.verify_mfa_token(user_id, mfa_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA token"
        )
    
    return True