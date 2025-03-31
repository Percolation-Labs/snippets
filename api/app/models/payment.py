from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Product(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    active: bool = True
    price_id: Optional[str] = None
    price: Optional[float] = None
    currency: str = "usd"
    metadata: Optional[Dict[str, Any]] = None


class Subscription(BaseModel):
    id: str
    user_id: str
    product_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    canceled_at: Optional[datetime] = None
    stripe_subscription_id: str


class Payment(BaseModel):
    id: str
    user_id: str
    amount: float
    currency: str = "usd"
    status: str
    created_at: datetime
    payment_method: str
    stripe_payment_id: str
    metadata: Optional[Dict[str, Any]] = None


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