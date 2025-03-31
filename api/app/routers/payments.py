import os
import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Cookie, Path, Body
from pydantic import BaseModel, Field
import stripe

from app.controllers import payment_controller, auth_controller
from app.models.payment import Product, SubscriptionTier, Payment, PaymentCreate, Subscription

router = APIRouter()

# Models for this router
class CheckoutSession(BaseModel):
    url: str


class CheckoutRequest(BaseModel):
    product_id: str
    success_url: str
    cancel_url: str


class SubscriptionCheckoutRequest(BaseModel):
    tier: str
    success_url: str
    cancel_url: str


class TokenPurchase(BaseModel):
    amount: int
    success_url: str
    cancel_url: str
    
    
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: str = "usd"
    
    
class CustomerResponse(BaseModel):
    """Response model for customer information"""
    id: str
    email: str
    name: Optional[str] = None
    default_payment_method: Optional[str] = None


class PaymentMethodResponse(BaseModel):
    """Response model for payment method information"""
    id: str
    type: str
    brand: Optional[str] = None
    last4: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    is_default: bool = False


# Helper function to get current user
def get_current_user_id(session_id: str = Cookie(None)):
    """Get the current user ID from session"""
    if not session_id or session_id not in auth_controller.sessions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    session = auth_controller.sessions[session_id]
    return session["user_id"]


# Payment endpoints
@router.get("/products", response_model=List[Product])
async def get_products():
    """Get all products"""
    return payment_controller.get_all_products()


@router.post("/products", response_model=Product)
async def create_product(product_data: ProductCreate, session_id: str = Cookie(None)):
    """Create a new product"""
    # Make sure user is authenticated
    user_id = get_current_user_id(session_id)
    
    try:
        # Create product
        product = payment_controller.create_product(
            name=product_data.name,
            description=product_data.description,
            price=product_data.price,
            currency=product_data.currency
        )
        return product
    except HTTPException as e:
        # Pass through HTTP exceptions
        raise e
    except Exception as e:
        # Handle other exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create product: {str(e)}"
        )


@router.delete("/products/{name}")
async def delete_product(name: str, session_id: str = Cookie(None)):
    """Delete a product by name"""
    # Make sure user is authenticated
    user_id = get_current_user_id(session_id)
    
    # Delete product
    success = payment_controller.delete_product_by_name(name)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with name '{name}' not found"
        )
    
    return {"message": f"Product '{name}' deleted successfully"}


@router.get("/subscription-tiers", response_model=List[SubscriptionTier])
async def get_subscription_tiers():
    """Get all subscription tiers"""
    return payment_controller.get_subscription_tiers()


@router.post("/checkout", response_model=CheckoutSession)
async def create_checkout(request: CheckoutRequest, session_id: str = Cookie(None)):
    """Create a checkout session for a product"""
    user_id = get_current_user_id(session_id)
    
    # Get product
    product = None
    for p in payment_controller.products_db.values():
        if p.id == request.product_id:
            product = p
            break
    
    if not product or not product.price_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or has no price"
        )
    
    # Create checkout session
    checkout = payment_controller.create_checkout_session(
        price_id=product.price_id,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        metadata={"user_id": user_id, "product_id": product.id}
    )
    
    return CheckoutSession(url=checkout["url"])


@router.post("/subscribe", response_model=CheckoutSession)
async def create_subscription(request: SubscriptionCheckoutRequest, session_id: str = Cookie(None)):
    """Create a subscription checkout session"""
    user_id = get_current_user_id(session_id)
    
    # Get subscription tier
    tier = payment_controller.SUBSCRIPTION_TIERS.get(request.tier)
    if not tier or not tier.stripe_price_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription tier not found"
        )
    
    # Ensure the user has a Stripe customer ID
    customer_id = auth_controller.ensure_stripe_customer(user_id)
    
    # Create checkout session
    checkout = payment_controller.create_subscription_checkout_session(
        price_id=tier.stripe_price_id,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        metadata={"user_id": user_id, "tier": tier.name},
        customer_id=customer_id
    )
    
    return CheckoutSession(url=checkout["url"])


@router.post("/buy-tokens", response_model=CheckoutSession)
async def buy_tokens(request: TokenPurchase, session_id: str = Cookie(None)):
    """Buy tokens/credits using real Stripe integration"""
    user_id = get_current_user_id(session_id)
    
    # Find tokens product
    token_product = None
    for p in payment_controller.products_db.values():
        if p.name == payment_controller.tokens_product["name"]:
            token_product = p
            break
    
    if not token_product or not token_product.price_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token product not found"
        )
    
    # Ensure minimum purchase amount for Stripe ($0.50)
    token_price = payment_controller.tokens_product.get("price", 0.01)
    min_tokens = max(50, int(0.5 / token_price) + 1)  # At least 50 or enough to meet $0.50+
    
    if request.amount < min_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum token purchase is {min_tokens} tokens (${min_tokens * token_price:.2f})"
        )
    
    # Ensure the user has a Stripe customer ID
    customer_id = auth_controller.ensure_stripe_customer(user_id)
    
    # Create checkout session with saved price and customer ID
    checkout = payment_controller.create_checkout_session(
        price_id=token_product.price_id,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        metadata={"user_id": user_id, "tokens": request.amount},
        customer_id=customer_id
    )
    
    return CheckoutSession(url=checkout["url"])


@router.post("/test/buy-tokens", response_model=CheckoutSession)
async def test_buy_tokens(request: TokenPurchase, session_id: str = Cookie(None)):
    """Buy tokens/credits (test mode version that doesn't interact with Stripe)"""
    user_id = get_current_user_id(session_id)
    
    # Validate amount
    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token amount must be positive"
        )
    
    # Create a fake checkout URL
    session_id = f"test_session_{uuid.uuid4().hex[:16]}"
    checkout_url = f"https://example.com/test-checkout/{session_id}"
    
    # Simulate adding credits to the user immediately in test mode
    from app.controllers.auth_controller import users_db
    user = users_db.get(user_id)
    if user:
        user.credits += request.amount
        users_db[user_id] = user
    
    return CheckoutSession(url=checkout_url)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    # Get the webhook data
    payload = await request.body()
    payload_str = payload.decode("utf-8")
    sig_header = request.headers.get("stripe-signature")
    
    # Get the webhook secret
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    # Test mode detection
    is_test_mode = payment_controller.TEST_MODE or not webhook_secret
    
    try:
        # If we have a webhook secret and signature header, verify the webhook
        if webhook_secret and sig_header:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        # For testing, allow direct JSON payload with no signature verification
        else:
            print("WARNING: Processing webhook without signature verification (test mode)")
            event = json.loads(payload_str)
            
            # For Stripe CLI webhooks or testing clients, if there's a typo in the structure, try to fix it
            if not isinstance(event, dict) or ("type" not in event and "id" not in event):
                # Try to extract the event from common test client structures
                if isinstance(event, dict) and "body" in event and isinstance(event["body"], dict):
                    event = event["body"]
                elif isinstance(event, list) and len(event) > 0 and isinstance(event[0], dict):
                    event = event[0]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        # Get metadata
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        
        if not user_id:
            return {"success": False, "error": "No user ID in metadata"}
        
        # Handle payment
        if session["mode"] == "payment":
            # Record payment
            payment = payment_controller.record_payment(
                user_id=user_id,
                amount=session["amount_total"] / 100,  # Convert from cents
                currency=session["currency"],
                payment_method="stripe",
                stripe_payment_id=session["id"],
                metadata=metadata
            )
            
            # If tokens purchase, add credits
            if "tokens" in metadata:
                tokens = int(metadata["tokens"])
                payment_controller.update_user_credits(user_id, tokens)
        
        # Handle subscription
        elif session["mode"] == "subscription":
            # Get subscription data
            subscription_id = session["subscription"]
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Get product
            tier = metadata.get("tier")
            
            if tier:
                # Update user subscription tier
                payment_controller.update_user_subscription_tier(user_id, tier)
                
                # Add subscription credits
                tier_obj = payment_controller.SUBSCRIPTION_TIERS.get(tier)
                if tier_obj:
                    payment_controller.update_user_credits(user_id, tier_obj.credits)
                
                # Record subscription
                product_id = None
                for p in payment_controller.products_db.values():
                    if p.metadata and p.metadata.get("tier") == tier:
                        product_id = p.id
                        break
                
                if product_id:
                    payment_controller.record_subscription(
                        user_id=user_id,
                        product_id=product_id,
                        stripe_subscription_id=subscription_id,
                        current_period_start=datetime.fromtimestamp(subscription["current_period_start"]),
                        current_period_end=datetime.fromtimestamp(subscription["current_period_end"])
                    )
    
    return {"success": True}


@router.get("/my/payments", response_model=List[Payment])
async def get_my_payments(session_id: str = Cookie(None)):
    """Get the current user's payments"""
    user_id = get_current_user_id(session_id)
    return payment_controller.get_user_payments(user_id)


@router.get("/my/subscriptions", response_model=List[Subscription])
async def get_my_subscriptions(session_id: str = Cookie(None)):
    """Get the current user's subscriptions"""
    user_id = get_current_user_id(session_id)
    return payment_controller.get_user_subscriptions(user_id)


@router.get("/customer", response_model=CustomerResponse)
async def get_customer(session_id: str = Cookie(None)):
    """
    Get the current user's Stripe customer information
    
    This endpoint ensures the user has a Stripe customer record and returns
    information about their customer account.
    """
    # Get user ID
    user_id = get_current_user_id(session_id)
    
    # Get user from database
    user = auth_controller.users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Ensure the user has a Stripe customer
    customer_id = auth_controller.ensure_stripe_customer(user_id)
    
    # Get the customer from Stripe
    customer = payment_controller.get_stripe_customer(customer_id)
    
    # Determine the default payment method
    default_payment_method = None
    if "invoice_settings" in customer and customer["invoice_settings"]:
        default_payment_method = customer["invoice_settings"].get("default_payment_method")
    
    return CustomerResponse(
        id=customer["id"],
        email=customer.get("email", user.email),
        name=customer.get("name", user.name),
        default_payment_method=default_payment_method
    )


@router.get("/methods", response_model=List[PaymentMethodResponse])
async def get_payment_methods(session_id: str = Cookie(None)):
    """
    Get the current user's payment methods
    
    This endpoint returns all payment methods associated with the user's 
    Stripe customer account.
    """
    # Get user ID
    user_id = get_current_user_id(session_id)
    
    # Get user from database
    user = auth_controller.users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # If user has no Stripe customer ID, return empty list
    if not user.stripe_customer_id:
        return []
    
    try:
        # Get payment methods from Stripe
        payment_methods = payment_controller.get_customer_payment_methods(user.stripe_customer_id)
        
        # Get the customer to determine default payment method
        customer = payment_controller.get_stripe_customer(user.stripe_customer_id)
        default_pm_id = None
        if "invoice_settings" in customer and customer["invoice_settings"]:
            default_pm_id = customer["invoice_settings"].get("default_payment_method")
        
        # Format the payment methods
        result = []
        for pm in payment_methods:
            pm_data = PaymentMethodResponse(
                id=pm["id"],
                type=pm["type"],
                is_default=pm["id"] == default_pm_id
            )
            
            # Add card-specific fields if this is a card
            if pm["type"] == "card" and "card" in pm:
                pm_data.brand = pm["card"]["brand"]
                pm_data.last4 = pm["card"]["last4"]
                pm_data.exp_month = pm["card"]["exp_month"]
                pm_data.exp_year = pm["card"]["exp_year"]
            
            result.append(pm_data)
        
        return result
    except HTTPException as e:
        # If we get a 404 (customer not found), return empty list
        if e.status_code == 404:
            return []
        # Otherwise re-raise
        raise e


@router.post("/methods")
async def add_payment_method(
    payment_method_id: str = Body(..., embed=True),
    session_id: str = Cookie(None)
):
    """
    Add a payment method to the user's account
    
    This endpoint attaches a payment method to the user's Stripe customer account.
    The payment_method_id should be obtained from Stripe Elements on the client side.
    """
    # Get user ID
    user_id = get_current_user_id(session_id)
    
    try:
        # Ensure the user has a Stripe customer
        customer_id = auth_controller.ensure_stripe_customer(user_id)
        
        # Attach the payment method to the customer
        stripe_instance = payment_controller.stripe
        payment_method = stripe_instance.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id
        )
        
        # If this is the first payment method, make it the default
        payment_methods = payment_controller.get_customer_payment_methods(customer_id)
        if len(payment_methods) == 1:
            stripe_instance.Customer.modify(
                customer_id,
                invoice_settings={"default_payment_method": payment_method_id}
            )
        
        return {"status": "success", "payment_method_id": payment_method_id}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/methods/default/{payment_method_id}")
async def set_default_payment_method(
    payment_method_id: str,
    session_id: str = Cookie(None)
):
    """
    Set a payment method as the default for the user
    
    This endpoint sets the specified payment method as the default for the user's
    Stripe customer account. All future payments and subscriptions will use this
    payment method by default.
    """
    # Get user ID
    user_id = get_current_user_id(session_id)
    
    try:
        # Get user from database
        user = auth_controller.users_db.get(user_id)
        if not user or not user.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has no Stripe customer ID"
            )
        
        # Verify the payment method exists and belongs to this customer
        payment_methods = payment_controller.get_customer_payment_methods(user.stripe_customer_id)
        if not any(pm["id"] == payment_method_id for pm in payment_methods):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment method not found for this customer"
            )
        
        # Set as default
        stripe_instance = payment_controller.stripe
        stripe_instance.Customer.modify(
            user.stripe_customer_id,
            invoice_settings={"default_payment_method": payment_method_id}
        )
        
        return {"status": "success", "default_payment_method": payment_method_id}
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/methods/{payment_method_id}")
async def delete_payment_method(
    payment_method_id: str,
    session_id: str = Cookie(None)
):
    """
    Delete a payment method
    
    This endpoint detaches a payment method from the user's Stripe customer account.
    If the payment method is the default, it will be removed as the default.
    """
    # Get user ID
    user_id = get_current_user_id(session_id)
    
    try:
        # Get user from database
        user = auth_controller.users_db.get(user_id)
        if not user or not user.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has no Stripe customer ID"
            )
            
        # Verify the payment method exists and belongs to this customer
        payment_methods = payment_controller.get_customer_payment_methods(user.stripe_customer_id)
        if not any(pm["id"] == payment_method_id for pm in payment_methods):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment method not found for this customer"
            )
        
        # Get customer information
        customer = payment_controller.get_stripe_customer(user.stripe_customer_id)
        default_pm_id = None
        if "invoice_settings" in customer and customer["invoice_settings"]:
            default_pm_id = customer["invoice_settings"].get("default_payment_method")
        
        # If this is the default payment method, clear the default
        if default_pm_id == payment_method_id:
            stripe_instance = payment_controller.stripe
            stripe_instance.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={"default_payment_method": None}
            )
        
        # Detach the payment method
        stripe_instance = payment_controller.stripe
        stripe_instance.PaymentMethod.detach(payment_method_id)
        
        return {"status": "success", "deleted_payment_method": payment_method_id}
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/setup-intent")
async def create_setup_intent(session_id: str = Cookie(None)):
    """
    Create a setup intent for adding a payment method
    
    This endpoint creates a SetupIntent, which is used by Stripe Elements to
    securely collect payment method details without creating a payment.
    """
    # Get user ID
    user_id = get_current_user_id(session_id)
    
    try:
        # Ensure the user has a Stripe customer
        customer_id = auth_controller.ensure_stripe_customer(user_id)
        
        # Create a setup intent
        stripe_instance = payment_controller.stripe
        setup_intent = stripe_instance.SetupIntent.create(
            customer=customer_id,
            usage="off_session"  # Allow using this payment method for future payments
        )
        
        return {
            "client_secret": setup_intent.client_secret,
            "id": setup_intent.id
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Endpoint to initialize default products
@router.post("/initialize-products")
async def initialize_products(session_id: str = Cookie(None)):
    """Initialize all default products (subscription tiers and tokens)"""
    # Authenticate the user
    user_id = get_current_user_id(session_id)
    
    # Count products before initialization
    products_before = len(payment_controller.products_db)
    
    # Initialize subscription products
    subscription_products = []
    try:
        payment_controller.initialize_subscription_products()
        subscription_products = [p for p in payment_controller.products_db.values() 
                                if p.metadata and p.metadata.get("type") == "subscription"]
    except Exception as e:
        # Log error but continue
        print(f"Error initializing subscription products: {str(e)}")
    
    # Initialize token product
    token_product = None
    try:
        payment_controller.initialize_token_product()
        token_product = next((p for p in payment_controller.products_db.values() 
                            if p.name == payment_controller.tokens_product["name"]), None)
    except Exception as e:
        # Log error but continue
        print(f"Error initializing token product: {str(e)}")
    
    # Count products after initialization
    products_after = len(payment_controller.products_db)
    products_added = products_after - products_before
    
    return {
        "success": True,
        "products_added": products_added,
        "subscription_products": len(subscription_products),
        "token_product": token_product is not None
    }