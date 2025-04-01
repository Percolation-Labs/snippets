from datetime import datetime,timezone
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
import uuid



def parse_utc(date_str:str):
    """"""  
    utc_time = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
    utc_time = utc_time.replace(tzinfo=timezone.utc)
    return utc_time
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    avatar: Optional[str] = None


class UserCreate(UserBase):
    password: Optional[str] = None
    auth_provider: Optional[str] = None
    provider_user_id: Optional[str] = None


class UserProfile(UserBase):
    """User Session and Profile for public consumption"""
   
    auth_method: str
    session_expiry: datetime | str = Field(default=None, description="The users current session expiry")
    mfa_enabled: bool = Field(False,description= "2FA is not needed for all endpoints but for those that are protected the user can opt in or out")
    stripe_customer_id: Optional[str] = Field(None,description= "When the user is login in they may already have a customer id but we should assigned it before payment transactions and update the database")
class TokenData(BaseModel):
    session_id: str | uuid.UUID = Field("This is our session id generated automatically")
    session_expiry: datetime | str = Field(default=None, description="The users current session expiry")

class Users(UserProfile):
    """User will be stored in the database - it will have system fields like updated at created at when saved
    The user is authenticated with a provider like google and stripe customer can be assigned an updated in the database
    To update use the percolate repository - see repository guidelines
    We do not show User data outside the API but the UserProfile is the visible and non sensitive subset
    """
    model_config = {'namespace':'public'}
      
    id: str | uuid.UUID = Field("This is our system user id and can be a simple MD5 hash of the email")
    session_id: str = Field(default=None, description="The current user session id")
    hashed_password: Optional[str] = Field(None, description="For username:password login we can store the hashed password")
    auth_provider: Optional[str] = Field(None, description="When the user logs in, track the current auth provider e.g. google")
    provider_user_id: Optional[str] = None
    subscription_tier: str = Field(default="Free", description="The Tier name the user is added to - these relate to Stripe Tiers by name")
    credits: int = Field(default=0, description="For testing only, we should track credits in a history table")
    mfa_secret: Optional[str] = Field(None, description="2FA secret if set")

    def is_expired(self):
        """check if the expired date is passed"""
        ed = self.session_expiry if not isinstance(self.session_expiry, str) else  parse_utc(self.session_expiry)
        if ed < datetime.utcnow():
            return True
        return False
    
class MFASetup(BaseModel):
    secret: str
    qr_code: str


class MFAVerify(BaseModel):
    code: str