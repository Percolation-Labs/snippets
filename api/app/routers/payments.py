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
from app.models.user import UserProfile

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


 
def get_current_user_id(session_id: str = Cookie(None)):
    """"""
    return auth_controller.get_user_profile_from_valid_session(session_id).id


# Payment endpoints
@router.get("/products", response_model=List[Product])
async def get_products():
    """Get all products"""
    return payment_controller.get_all_db_products()


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



@router.post("/subscribe-checkout", response_model=CheckoutSession)
async def create_subscription_checkout(request: SubscriptionCheckoutRequest, session_id: str = Cookie(None)):
    """Create a subscription checkout session with an external payment page
    
    This endpoint creates a Stripe Checkout session for subscription payments.
    The user will be redirected to Stripe's hosted checkout page to complete payment.
    """
    user_id = get_current_user_id(session_id)
    
    # Get subscription tier
    tier = payment_controller.SUBSCRIPTION_TIERS.get(request.tier)
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription tier not found. Available tiers: " + ", ".join(payment_controller.SUBSCRIPTION_TIERS.keys())
        )
    
    if not tier.stripe_price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription tier is not properly initialized in Stripe. Please run the initialize products script first."
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


class DirectSubscriptionRequest(BaseModel):
    """Request model for direct subscription creation using saved payment method"""
    tier: str


class SubscriptionResponse(BaseModel):
    """Response model for subscription operations"""
    id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    customer_id: str
    tier_name: str


@router.post("/subscribe", response_model=SubscriptionResponse)
async def create_direct_subscription(request: DirectSubscriptionRequest, session_id: str = Cookie(None)):
    """Create a subscription using the customer's saved payment method
    
    This endpoint creates a subscription directly without redirecting to a checkout page.
    It uses the customer's default payment method (or first available method) to
    immediately process the subscription.
    
    The customer must have at least one valid payment method saved to their account.
    """
    user_id = get_current_user_id(session_id)
    
    tier:Product = payment_controller.get_product_by_name(request.tier)
    # # Get subscription tier - this should be from the database but 
    # tier = payment_controller.SUBSCRIPTION_TIERS.get(request.tier)
    # if not tier:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail="Subscription tier not found. Available tiers: " + ", ".join(payment_controller.SUBSCRIPTION_TIERS.keys())
    #     )
    
    # if not tier.stripe_price_id:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Subscription tier is not properly initialized in Stripe. Please run the initialize products script first."
    #     )
    
    # Ensure the user has a Stripe customer ID
    customer_id = auth_controller.ensure_stripe_customer(user_id)
    
    # Create direct subscription using saved payment method
    # The create_direct_subscription function will handle cancelling existing subscriptions
    try:
        subscription = payment_controller.create_direct_subscription(
            customer_id=customer_id,
            price_id=tier.stripe_price_id,
            metadata={"user_id": user_id, "tier": tier.name},
            cancel_existing=True  # Cancel existing subscriptions in Stripe before creating new one
        )
     
        #do this in the webhook maybe   
        # # Process subscription creation (similar to webhook handling)
        # if subscription["status"] == "active":
        #     # Find product for this tier to get its ID
        #     product_id = None
        #     for p in payment_controller.products_db.values():
        #         if p.metadata and p.metadata.get("tier") == tier.name:
        #             product_id = p.id
        #             break
            
        #     if product_id:
        #         # Record subscription in our database
        #         payment_controller.record_subscription(
        #             user_id=user_id,
        #             product_id=tier.id,
        #             stripe_subscription_id=subscription["id"],
        #             current_period_start=datetime.fromtimestamp(subscription["current_period_start"]),
        #             current_period_end=datetime.fromtimestamp(subscription["current_period_end"])
        #         )
                
        #         # Update user subscription tier
        #         payment_controller.update_user_subscription_tier(user_id, tier.name)
                
        #         # Add subscription credits
        #         #payment_controller.update_user_credits(user_id, tier.credits)
        
        return SubscriptionResponse(
            id=subscription["id"],
            status=subscription["status"],
            current_period_start=datetime.fromtimestamp(subscription["current_period_start"]),
            current_period_end=datetime.fromtimestamp(subscription["current_period_end"]),
            customer_id=customer_id,
            tier_name=tier.name
        )
    
    except HTTPException:
        # Pass through HTTP exceptions
        raise
    except Exception as e:
        # Handle other exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create subscription: {str(e)}"
        )


@router.post("/buy-tokens-checkout", response_model=CheckoutSession)
async def buy_tokens_checkout(request: TokenPurchase, session_id: str = Cookie(None)):
    """Buy tokens/credits using a Stripe external checkout flow
    
    This endpoint creates a Stripe Checkout session for token purchases.
    The user will be redirected to Stripe's hosted checkout page to complete payment.
    """
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
    # We need to use the amount for the quantity in the checkout session
    checkout = payment_controller.create_checkout_session(
        price_id=token_product.price_id,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        metadata={"user_id": user_id, "tokens": request.amount},
        customer_id=customer_id,
        quantity=request.amount  # Pass quantity to create_checkout_session
    )
    
    return CheckoutSession(url=checkout["url"])


class DirectTokenPurchaseRequest(BaseModel):
    """Request model for direct token purchase using saved payment method"""
    amount: int
    name: str = 'Tokens' #Default vanilla tokens

class TokenPurchaseResponse(BaseModel):
    """Response model for token purchase operations"""
    payment_id: str
    amount: int
    status: str
    customer_id: str


@router.post("/buy-tokens", response_model=TokenPurchaseResponse)
async def buy_tokens_direct(request: DirectTokenPurchaseRequest, session_id: str = Cookie(None)):
    """Buy tokens/credits using the customer's saved payment method
    
    This endpoint purchases tokens directly without redirecting to a checkout page.
    It uses the customer's default payment method (or first available method) to
    immediately process the payment.
    
    The customer must have at least one valid payment method saved to their account.
    """
    user_id = get_current_user_id(session_id)
    
    # Find tokens product
    token_product = payment_controller.get_product_by_name(request.name)
 
    if not token_product :
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Token product {request.name} not found in the database"
        )
    
    print("Purchasing the token product", token_product)
    # Ensure minimum purchase amount for Stripe ($0.50)
    token_price = token_product.price
    min_tokens = max(50, int(0.5 / token_price) + 1)  # At least 50 or enough to meet $0.50+
    
    if request.amount < min_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum token purchase is {min_tokens} tokens (${min_tokens * token_price:.2f})"
        )
    
    # Ensure the user has a Stripe customer ID
    customer_id = auth_controller.ensure_stripe_customer(user_id)
    
    try:
        # Create direct payment using saved payment method
        payment_intent = payment_controller.create_direct_payment(
            customer_id=customer_id,
            price_id=token_product.stripe_price_id,
            quantity=request.amount,
            metadata={"user_id": user_id, "tokens": request.amount}
        )
        
        # Process successful payment (similar to webhook handling)
        if payment_intent["status"] == "succeeded":
            # Record payment
            #TODO record payments
            # payment = payment_controller.record_payment(
            #     user_id=user_id,
            #     amount=payment_intent["amount"] / 100,  # Convert from cents
            #     currency=payment_intent["currency"],
            #     payment_method="stripe",
            #     stripe_payment_id=payment_intent["id"],
            #     metadata={"tokens": request.amount}
            # )
            
            # # Add credits to the user's account
            # payment_controller.update_user_credits(user_id, request.amount)
            
            return TokenPurchaseResponse(
                payment_id=payment_intent["id"],
                amount=request.amount,
                status=payment_intent["status"],
                customer_id=customer_id
            )
        else:
            # Payment not succeeded
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Payment failed with status: {payment_intent['status']}"
            )
    
    except HTTPException:
        # Pass through HTTP exceptions
        raise
    except Exception as e:
        # Handle other exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to purchase tokens: {str(e)}"
        )


 
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
                # Find the user's Stripe customer ID and cancel existing subscriptions
                user = auth_controller.users_db.get(user_id)
                if user and user.stripe_customer_id:
                    # Cancel existing subscriptions in Stripe to avoid multiple active subscriptions
                    try:
                        # This will cancel all active subscriptions for the customer in Stripe
                        # We exclude the newly created subscription to avoid cancelling it
                        cancelled_subs = payment_controller.cancel_user_stripe_subscriptions(
                            customer_id=user.stripe_customer_id,
                            exclude_subscription_id=subscription_id,  # Exclude the new subscription
                            cancel_immediately=True
                        )
                        if cancelled_subs:
                            print(f"Cancelled existing Stripe subscriptions: {cancelled_subs}")
                    except Exception as e:
                        # Log error but continue processing the new subscription
                        print(f"Error canceling existing Stripe subscriptions: {str(e)}")
                else:
                    print(f"Warning: Could not find Stripe customer ID for user {user_id} to cancel existing subscriptions")
                
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
                    new_subscription = payment_controller.record_subscription(
                        user_id=user_id,
                        product_id=product_id,
                        stripe_subscription_id=subscription_id,
                        current_period_start=datetime.fromtimestamp(subscription["current_period_start"]),
                        current_period_end=datetime.fromtimestamp(subscription["current_period_end"])
                    )
                    
    # Handle subscription cancellation event
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        
        # Find subscription in our database by Stripe subscription ID
        local_subscription = None
        subscription_id = None
        
        for sub_id, sub in payment_controller.subscriptions_db.items():
            if sub.stripe_subscription_id == subscription["id"]:
                local_subscription = sub
                subscription_id = sub_id
                break
        
        if local_subscription:
            # Update subscription status and dates
            local_subscription.status = "canceled"
            local_subscription.cancel_at_period_end = False
            local_subscription.canceled_at = datetime.utcnow()
            
            # Save updated subscription back to database
            payment_controller.subscriptions_db[subscription_id] = local_subscription
            
            # Reset user subscription tier to Free if this was their active subscription
            user_id = local_subscription.user_id
            user = auth_controller.users_db.get(user_id)
            
            if user:
                # Find the product associated with this subscription
                product = None
                for p in payment_controller.products_db.values():
                    if p.id == local_subscription.product_id:
                        product = p
                        break
                
                # If the product has a tier in its metadata and it matches the user's current tier,
                # reset to Free
                if (product and product.metadata and 
                    product.metadata.get("tier") == user.subscription_tier):
                    payment_controller.update_user_subscription_tier(user_id, "Free")
    
    # Handle subscription renewal event
    elif event["type"] == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        
        # Only process subscription invoices
        if invoice.get("subscription"):
            # Get subscription details
            subscription_id = invoice["subscription"]
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Find subscription in our database by Stripe subscription ID
            local_subscription = None
            local_subscription_id = None
            
            for sub_id, sub in payment_controller.subscriptions_db.items():
                if sub.stripe_subscription_id == subscription_id:
                    local_subscription = sub
                    local_subscription_id = sub_id
                    break
            
            if local_subscription:
                # Update subscription period dates
                local_subscription.current_period_start = datetime.fromtimestamp(subscription["current_period_start"])
                local_subscription.current_period_end = datetime.fromtimestamp(subscription["current_period_end"])
                local_subscription.status = subscription["status"]
                
                # Save updated subscription back to database
                payment_controller.subscriptions_db[local_subscription_id] = local_subscription
                
                # Add subscription credits for the new period
                user_id = local_subscription.user_id
                
                # Find the product associated with this subscription
                product = None
                for p in payment_controller.products_db.values():
                    if p.id == local_subscription.product_id:
                        product = p
                        break
                
                # If the product has a tier in its metadata, add the credits
                if product and product.metadata and product.metadata.get("tier"):
                    tier = product.metadata.get("tier")
                    tier_obj = payment_controller.SUBSCRIPTION_TIERS.get(tier)
                    
                    if tier_obj:
                        payment_controller.update_user_credits(user_id, tier_obj.credits)
    
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


class CancelSubscriptionRequest(BaseModel):
    """Request model for subscription cancellation"""
    cancel_immediately: bool = False


@router.post("/subscriptions/{subscription_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_subscription(
    subscription_id: str,
    request: CancelSubscriptionRequest,
    session_id: str = Cookie(None)
):
    """Cancel a subscription
    
    By default, the subscription will remain active until the end of the billing period.
    If cancel_immediately is True, the subscription will be canceled immediately.
    """
    # Authenticate user
    user_id = get_current_user_id(session_id)
    
    # Get user's subscriptions
    user_subscriptions = payment_controller.get_user_subscriptions(user_id)
    
    # Check if the subscription belongs to the user
    if not any(sub.id == subscription_id for sub in user_subscriptions):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found or doesn't belong to you"
        )
    
    # Cancel the subscription
    result = payment_controller.cancel_subscription(
        subscription_id=subscription_id,
        cancel_immediately=request.cancel_immediately
    )
    
    return {
        "success": True,
        "subscription_id": subscription_id,
        "status": result["status"],
        "cancelled_at_period_end": result["cancel_at_period_end"]
    }


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
    
    """determine the user ud from session and load"""
    user_id = get_current_user_id(session_id)
    user = auth_controller.get_user_model(user_id)
    
    """the user normally should have a customer id but we can make sure"""
    if not user.stripe_customer_id:
        auth_controller.ensure_stripe_customer(user_id)
    
    try:
        payment_methods = payment_controller.get_customer_payment_methods(user.stripe_customer_id)
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
        if e.status_code == 404:
            return []
        raise e


@router.post("/methods")
async def add_payment_method(
    payment_method_id: str = Body(..., embed=True),
    session_id: str = Cookie(None)
):
    """
    Add a payment method to the user's account (callback from stripe elements)
    
    This endpoint attaches a payment method to the user's Stripe customer account.
    The payment_method_id should be obtained from Stripe Elements on the client side.
    
    It also ensures the user has a Stripe customer and returns the customer ID
    in the response, which can be used to update the user's profile.
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
        
        """we dont necessarily need to get save the payment methods in our database - we could in future"""
        
        return {
            "status": "success", 
            "payment_method_id": payment_method_id,
            "customer_id": customer_id
        }
    
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
    Set a payment method as the default for the user (on stripe)
    
    This endpoint sets the specified payment method as the default for the user's
    Stripe customer account. All future payments and subscriptions will use this
    payment method by default.
    """

    try:
        user_id = get_current_user_id(session_id)
        user = auth_controller.get_user_model(user_id)
        
        # Verify the payment method exists and belongs to this customer
        payment_methods = payment_controller.get_customer_payment_methods(user.stripe_customer_id)
        if not any(pm["id"] == payment_method_id for pm in payment_methods):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment method not found for this customer"
            )
        
        stripe_instance = payment_controller.stripe
        stripe_instance.Customer.modify(
            user.stripe_customer_id,
            invoice_settings={"default_payment_method": payment_method_id}
        )
        
        return {"status": "success", "default_payment_method": payment_method_id}
    
    except HTTPException:
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
    
    It also ensures the user has a Stripe customer and returns the customer ID
    in the response, which can be used to update the user's profile.
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
        
        # Return both the setup intent and customer ID
        return {
            "client_secret": setup_intent.client_secret,
            "id": setup_intent.id,
            "customer_id": customer_id
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Endpoint to initialize default products
@router.get("/verify")
async def verify_payment(session_id: str, cookie_session_id: str = Cookie(None)):
    """Verify a payment after the customer returns from Stripe checkout
    
    This endpoint is called when the customer is redirected back to your
    site after completing a Stripe checkout. It verifies the payment was
    successful by checking the checkout session status.
    """
    # Authenticate user
    user_id = get_current_user_id(cookie_session_id)
    
    # Get session information from Stripe
    if not payment_controller.TEST_MODE:
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
            
            # Verify payment was successful
            if checkout.payment_status != "paid":
                return {"success": False, "error": "Payment not completed"}
            
            # Get metadata to see what was purchased
            metadata = checkout.get("metadata", {})
            
            # Handle token purchase completion
            if "tokens" in metadata:
                token_amount = int(metadata.get("tokens", 0))
                if token_amount > 0:
                    payment_controller.update_user_credits(user_id, token_amount)
            
            return {"success": True, "session_id": session_id}
        except stripe.error.StripeError:
            return {"success": False, "error": "Invalid checkout session"}
    else:
        # In test mode, just return success
        return {"success": True, "session_id": session_id}


@router.get("/customer-by-email")
async def find_customer_by_email(email: str, session_id: str = Cookie(None)):
    """
    Find a Stripe customer by email address
    
    This endpoint searches for a Stripe customer with the specified email address.
    If found, it returns the customer details. If not found, it returns an empty response.
    
    This is useful for retrieving a customer ID when only the email is known.
    """
    # Get user ID for authentication
    user_id = get_current_user_id(session_id)
    
    try:
        # Find the customer by email
        customer = payment_controller.find_customer_by_email(email)
        
        if not customer:
            return {"found": False, "message": "No customer found with this email"}
        
        # Extract relevant customer information
        return {
            "found": True,
            "customer_id": customer["id"],
            "email": customer.get("email"),
            "name": customer.get("name"),
            "created": customer.get("created")
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/initialize-products")
async def initialize_products(session_id: str = Cookie(None))->List[Product]:
    """Initialize all default products (subscription tiers and tokens)"""

    products = payment_controller.initialize_subscription_products()
    token = payment_controller.initialize_token_product()
    return products + [token]
 
 