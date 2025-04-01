from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid

class Product(BaseModel):
    """Stores our """
    model_config = {'namespace':'public'}
    id: str | uuid.UUID
    name: str
    description: Optional[str] = None
    active: bool = True
    price_id: Optional[str] = None
    price: Optional[float] = None
    currency: str = "usd"
    metadata: Optional[Dict[str, Any]] = None
    features: Optional[List[str]] = Field(default_factory=list, description="Features that we offer")
    product_type: Optional[str] = Field(None,description= "Subscriptions and other product types")
    recurs: Optional[str] = Field(None, description="Monthly, Yearly or not at all")
    stripe_product_id: Optional[str] = Field(None,description="The stipe product id if known")
    stripe_price_id: Optional[str] = Field(None,description="The stipe price id used for stripe transactions")
    
class Subscription(BaseModel):
    """User subscription details"""
    model_config = {'namespace':'public'}
    id: str | uuid.UUID
    user_id: str
    product_id: str | uuid.UUID
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    canceled_at: Optional[datetime] = None
    stripe_subscription_id: str


class Payment(BaseModel):
    id: str | uuid.UUID
    user_id: str | uuid.UUID
    amount: float
    currency: str = "usd"
    status: str
    created_at: datetime
    payment_method: str
    stripe_payment_id: str
    metadata: Optional[Dict[str, Any]] = None

# class PaymentMethod(BaseModel):
#     """this payment is not saved by us but if it was we would add a database uuid - this represents a remote payment method"""
#     stripe_id: str = Field(..., description="Unique identifier for the payment method for example as used in stripe")
#     type: str = Field("card", description="Type of payment method")
#     brand: str = Field(..., description="Brand of the card (e.g., Visa, Mastercard)")
#     last4: str = Field(..., min_length=4, max_length=4, description="Last 4 digits of the card")
#     exp_month: int = Field(..., ge=1, le=12, description="Expiration month (1-12)")
#     exp_year: int = Field(..., ge=2000, description="Expiration year")
#     is_default: bool = Field(False, description="Whether this is the default payment method")


class PaymentCreate(BaseModel):
    amount: float
    currency: str = "usd"
    product_id: Optional[str] = None
    description: Optional[str] = None


class SubscriptionTier(BaseModel):
    name: str
    price: float
    currency: str = "usd"
    features: List[str]
    credits: int = 0
    stripe_price_id: Optional[str] = None
    recurs: str = "monthly"