import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

import stripe
from fastapi import HTTPException, status

from app.models.payment import Product, Subscription, Payment, SubscriptionTier

# Initialize Stripe
stripe_key = os.getenv("STRIPE_SECRET_KEY")
stripe.api_key = stripe_key
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

# Set to True for testing without real Stripe API calls
TEST_MODE = stripe_key == "sk_test_12345" or not stripe_key

# Base URL for API (used for success/cancel URLs)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Mock database (replace with real DB)
products_db = {}
subscriptions_db = {}
payments_db = {}

# Define subscription tiers
SUBSCRIPTION_TIERS = {
    "Free": SubscriptionTier(
        name="Free",
        price=0.0,
        features=["Basic access", "Limited API calls"],
        credits=5
    ),
    "Individual": SubscriptionTier(
        name="Individual",
        price=9.99,
        features=["Full access", "Priority support", "Unlimited API calls"],
        credits=100
    ),
    "Team": SubscriptionTier(
        name="Team",
        price=49.99,
        features=["Full access", "Priority support", "Unlimited API calls", "Team management"],
        credits=500
    ),
    "Enterprise": SubscriptionTier(
        name="Enterprise",
        price=199.99,
        features=["Full access", "Priority support", "Unlimited API calls", "Team management", "Custom integrations"],
        credits=2000
    )
}

# Create token product for credits
tokens_product = {
    "name": "Tokens",
    "description": "Credits for API usage",
    "price": 0.01,  # $0.01 per token
    "min_purchase": 50,  # Minimum purchase to meet Stripe's $0.50 minimum
    "test_price": 0.55  # Price in test mode, already above minimum
}


def create_stripe_product(name: str, description: Optional[str] = None) -> Dict[str, Any]:
    """Create a product in Stripe
    
    In Stripe's payment model, Products represent the items or services that customers
    can purchase. Products have attributes like name, description, and can have multiple
    Price objects associated with them.
    
    This function creates a Product in Stripe, which is the first step in setting up
    something that can be purchased. After creating a Product, you'll typically create
    one or more Prices for the Product (using create_stripe_price).
    
    Args:
        name: The name of the product (displayed to customers)
        description: Optional description of the product
        
    Returns:
        Dict containing the Stripe Product object
        
    Raises:
        HTTPException: If there's an error communicating with Stripe
        
    Stripe Documentation:
        https://stripe.com/docs/api/products
        https://stripe.com/docs/products-prices/overview
    """
    # If in test mode, return a mock product
    if TEST_MODE:
        return {
            "id": f"prod_test_{uuid.uuid4().hex[:8]}",
            "name": name,
            "description": description,
            "active": True
        }
    
    try:
        product = stripe.Product.create(
            name=name,
            description=description
        )
        return product
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


def create_stripe_price(product_id: str, price: float, currency: str = "usd") -> Dict[str, Any]:
    """Create a one-time price for a product in Stripe
    
    In Stripe, Prices define how much and how often customers pay for a Product.
    This function creates a one-time Price (not recurring) for a Product.
    
    Stripe requires prices to be specified in the smallest currency unit (e.g., cents for USD),
    so this function automatically converts the price from dollars to cents.
    
    Important notes:
    - Stripe has a minimum charge amount (typically $0.50 for USD)
    - Price IDs are used when creating checkout sessions
    - Prices can be set as active/inactive but never truly deleted
    
    Args:
        product_id: The Stripe ID of the product this price belongs to
        price: The price amount in major currency units (e.g., dollars for USD)
        currency: The 3-letter ISO currency code (default: "usd")
        
    Returns:
        Dict containing the Stripe Price object
        
    Raises:
        HTTPException: If there's an error communicating with Stripe
        
    Stripe Documentation:
        https://stripe.com/docs/api/prices
        https://stripe.com/docs/currencies
        https://stripe.com/docs/products-prices/pricing-models
    """
    # If in test mode, return a mock price
    if TEST_MODE:
        return {
            "id": f"price_test_{uuid.uuid4().hex[:8]}",
            "product": product_id,
            "unit_amount": int(price * 100),
            "currency": currency,
            "recurring": None
        }
    
    try:
        # Convert price to smallest currency unit (e.g., cents)
        # Stripe requires prices in the smallest unit of the currency
        unit_amount = int(price * 100)
        
        price_obj = stripe.Price.create(
            product=product_id,
            unit_amount=unit_amount,
            currency=currency,
            recurring=None  # One-time payment
        )
        return price_obj
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


def create_stripe_subscription_price(product_id: str, price: float, currency: str = "usd") -> Dict[str, Any]:
    """Create a subscription price for a product in Stripe
    
    In Stripe, subscription prices differ from one-time prices by including
    recurring payment terms. This function creates a Price object with 
    a monthly recurring billing cycle.
    
    The typical flow for subscriptions in Stripe is:
    1. Create a Product (the service being subscribed to)
    2. Create a Price with recurring parameters (defines how much and how often)
    3. Create a Subscription or Checkout Session using this Price
    
    Important subscription concepts:
    - Billing cycles: This function creates monthly subscriptions
    - Proration: When customers change plans, Stripe can prorate charges
    - Trials: Not implemented here, but can be added with trial_period_days
    - Cancellation: Handled through the Stripe dashboard or API
    
    Args:
        product_id: The Stripe ID of the product this price belongs to
        price: The price amount in major currency units (e.g., dollars for USD)
        currency: The 3-letter ISO currency code (default: "usd")
        
    Returns:
        Dict containing the Stripe Price object with recurring parameters
        
    Raises:
        HTTPException: If there's an error communicating with Stripe
        
    Stripe Documentation:
        https://stripe.com/docs/api/prices/create (see 'recurring' parameter)
        https://stripe.com/docs/billing/subscriptions/overview
        https://stripe.com/docs/billing/subscriptions/build-subscriptions
    """
    # If in test mode, return a mock price
    if TEST_MODE:
        return {
            "id": f"price_sub_test_{uuid.uuid4().hex[:8]}",
            "product": product_id,
            "unit_amount": int(price * 100),
            "currency": currency,
            "recurring": {"interval": "month"}
        }
    
    try:
        price_obj = stripe.Price.create(
            product=product_id,
            unit_amount=int(price * 100),  # Convert to cents
            currency=currency,
            recurring={"interval": "month"}
        )
        return price_obj
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


def product_exists_by_name(name: str) -> bool:
    """Check if a product already exists with the given name"""
    return any(p.name == name for p in products_db.values())


def create_product(name: str, description: Optional[str] = None, price: Optional[float] = None, 
                   currency: str = "usd") -> Product:
    """Create a product in the database and in Stripe"""
    # Check if a product with this name already exists
    if product_exists_by_name(name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A product with the name '{name}' already exists"
        )
    
    # Create in Stripe
    stripe_product = create_stripe_product(name, description)
    
    price_id = None
    if price is not None:
        stripe_price = create_stripe_price(stripe_product["id"], price, currency)
        price_id = stripe_price["id"]
    
    # Create in database
    product_id = str(uuid.uuid4())
    product = Product(
        id=product_id,
        name=name,
        description=description,
        active=True,
        price_id=price_id,
        price=price,
        currency=currency,
        metadata={"stripe_product_id": stripe_product["id"]}
    )
    
    # Save to mock database (replace with real DB operation)
    products_db[product_id] = product
    
    return product


def create_subscription_product(tier: SubscriptionTier) -> Product:
    """Create a subscription product in the database and in Stripe
    
    This function is a higher-level wrapper that handles both the Stripe integration
    and local database operations for creating subscription products.
    
    The function performs these steps:
    1. Creates a Stripe Product representing the subscription tier
    2. Creates a recurring Price for the Product with monthly billing
    3. Saves the product details in the local database with metadata
    
    Subscription tiers typically represent different service levels (Free, Individual, 
    Team, etc.) with varying features, pricing, and credit allocations. The tier
    metadata is stored with the product to allow easy access to subscription benefits.
    
    Args:
        tier: A SubscriptionTier object containing name, price, features, etc.
        
    Returns:
        A Product object representing the subscription tier in the local database
        
    Raises:
        HTTPException: If there's an error creating the product in Stripe
        
    Stripe Documentation:
        https://stripe.com/docs/billing/subscriptions/multiple-products
        https://stripe.com/docs/products-prices/overview#subscription-products
    """
    # Create in Stripe
    stripe_product = create_stripe_product(f"{tier.name} Subscription", f"{tier.name} tier subscription")
    stripe_price = create_stripe_subscription_price(stripe_product["id"], tier.price, tier.currency)
    
    # Update tier with price ID
    tier.stripe_price_id = stripe_price["id"]
    
    # Create in database
    product_id = str(uuid.uuid4())
    product = Product(
        id=product_id,
        name=f"{tier.name} Subscription",
        description=f"{tier.name} tier subscription",
        active=True,
        price_id=stripe_price["id"],
        price=tier.price,
        currency=tier.currency,
        metadata={
            "stripe_product_id": stripe_product["id"],
            "type": "subscription",
            "tier": tier.name,
            "credits": tier.credits
        }
    )
    
    # Save to mock database (replace with real DB operation)
    products_db[product_id] = product
    
    return product


def get_all_products() -> List[Product]:
    """Get all products"""
    return list(products_db.values())


def get_product_by_name(name: str) -> Optional[Product]:
    """Get a product by name"""
    for product in products_db.values():
        if product.name == name:
            return product
    return None


def delete_product_by_name(name: str) -> bool:
    """Delete a product by name from the database and optionally from Stripe"""
    product = get_product_by_name(name)
    
    if not product:
        return False
    
    # Delete from Stripe if not in test mode
    if not TEST_MODE and product.metadata and "stripe_product_id" in product.metadata:
        try:
            stripe_product_id = product.metadata["stripe_product_id"]
            stripe.Product.modify(stripe_product_id, active=False)
        except Exception as e:
            # Log the error but continue with local deletion
            print(f"Error deactivating Stripe product: {str(e)}")
    
    # Delete from local database
    product_id_to_delete = product.id
    if product_id_to_delete in products_db:
        del products_db[product_id_to_delete]
        return True
        
    return False


def get_subscription_tiers() -> List[SubscriptionTier]:
    """Get all subscription tiers"""
    return list(SUBSCRIPTION_TIERS.values())


def create_payment_intent(amount: float, currency: str = "usd", 
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a payment intent in Stripe
    
    PaymentIntents are at the core of Stripe's payment processing system and represent
    the intent to collect payment from a customer. They handle the entire payment lifecycle
    including authentication, authorization, and success/failure handling.
    
    Key benefits of PaymentIntents:
    1. Strong Customer Authentication (SCA) compliance for European payments
    2. Automatic handling of 3D Secure when required
    3. Payment method confirmation and authentication in one step
    4. Support for various payment methods beyond credit cards
    
    The typical flow for using PaymentIntents is:
    1. Create a PaymentIntent on the server (this function)
    2. Pass the client_secret to your frontend
    3. Use Stripe.js to confirm the payment with the customer's payment details
    4. Handle success/failure on your backend via webhooks
    
    Args:
        amount: The amount to charge in major currency units (e.g., dollars for USD)
        currency: The 3-letter ISO currency code (default: "usd")
        metadata: Optional dictionary of metadata to attach to the payment intent
        
    Returns:
        Dict containing the Stripe PaymentIntent object
        
    Raises:
        HTTPException: If there's an error communicating with Stripe
        
    Stripe Documentation:
        https://stripe.com/docs/api/payment_intents
        https://stripe.com/docs/payments/payment-intents
        https://stripe.com/docs/payments/accept-a-payment
    """
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency=currency,
            metadata=metadata or {}
        )
        return intent
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


def create_checkout_session(price_id: str, success_url: str, cancel_url: str, 
                           metadata: Optional[Dict[str, Any]] = None,
                           customer_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a checkout session in Stripe for one-time payments
    
    Stripe Checkout provides a pre-built, hosted payment page optimized for
    conversion. It handles payment method collection, validation, and 
    security concerns like PCI compliance automatically.
    
    Checkout benefits:
    1. Mobile-optimized design that works across devices
    2. Support for 25+ languages and multiple payment methods
    3. Built-in address collection and validation
    4. PCI compliance handled by Stripe
    
    This function creates a one-time payment Checkout session (mode="payment").
    For subscriptions, use create_subscription_checkout_session() instead.
    
    The flow for using Checkout is:
    1. Create a Session on your server (this function)
    2. Redirect the customer to the session.url
    3. Customer completes payment on Stripe's hosted page
    4. Stripe redirects to your success_url or cancel_url
    5. Handle completion via webhooks (most reliable) or success page
    
    Args:
        price_id: The Stripe Price ID to charge the customer for
        success_url: Where to redirect after successful payment
        cancel_url: Where to redirect if payment is canceled
        metadata: Optional dictionary of metadata to attach to the session
        customer_id: Optional Stripe customer ID to associate with the session
        
    Returns:
        Dict containing the Stripe Checkout Session object
        
    Raises:
        HTTPException: If there's an error communicating with Stripe or
                      if the purchase amount is below Stripe's minimum
        
    Stripe Documentation:
        https://stripe.com/docs/api/checkout/sessions
        https://stripe.com/docs/payments/checkout
        https://stripe.com/docs/payments/accept-a-payment?ui=checkout
    """
    # If in test mode, return a mock checkout session
    if TEST_MODE:
        session_id = f"cs_test_{uuid.uuid4().hex[:16]}"
        
        # For token purchase, ensure we're meeting Stripe's minimum
        if metadata and "tokens" in metadata:
            tokens = int(metadata["tokens"])
            price_per_token = tokens_product["price"]
            amount = tokens * price_per_token
            
            if amount < 0.5:  # Stripe minimum is $0.50
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Minimum purchase amount is $0.50. Please purchase at least {50} tokens."
                )
        
        mock_session = {
            "id": session_id,
            "url": f"https://checkout.stripe.com/pay/{session_id}",
            "metadata": metadata or {}
        }
        
        # Add customer info to mock session if provided
        if customer_id:
            mock_session["customer"] = customer_id
            
        return mock_session
    
    try:
        # Create session parameters
        session_params = {
            "payment_method_types": ["card"],
            "line_items": [{
                "price": price_id,
                "quantity": 1
            }],
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata or {}
        }
        
        # Add customer if provided
        if customer_id:
            session_params["customer"] = customer_id
            
            # If the customer exists, use customer mode which will show saved payment methods
            try:
                # Try to retrieve customer to verify it exists
                stripe.Customer.retrieve(customer_id)
                session_params["customer_creation"] = "never"
            except stripe.error.InvalidRequestError:
                # If customer doesn't exist, let Stripe create a new one with the ID we provided
                session_params["customer_creation"] = "always"
        
        # Create the checkout session
        session = stripe.checkout.Session.create(**session_params)
        return session
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


def create_subscription_checkout_session(price_id: str, success_url: str, cancel_url: str, 
                                        metadata: Optional[Dict[str, Any]] = None,
                                        customer_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a subscription checkout session in Stripe
    
    This function creates a Stripe Checkout session specifically for recurring
    subscriptions (mode="subscription"). The primary difference from one-time
    payments is that customers enter a billing agreement for future charges.
    
    Subscription checkout benefits:
    1. All regular Checkout benefits (mobile-optimized, multiple payment methods)
    2. Automatic recurring billing without requiring customer to return
    3. Built-in subscription management through the Customer Portal
    4. Support for trials, prorations, and plan changes
    
    The subscription lifecycle:
    1. Customer subscribes through Checkout (this function creates the session)
    2. Initial payment is collected
    3. Subscription becomes active
    4. Automatic recurring billing based on the Price's interval
    5. Various subscription events (renewal, failure, cancellation) are handled via webhooks
    
    Args:
        price_id: The Stripe Price ID with recurring parameters
        success_url: Where to redirect after successful subscription setup
        cancel_url: Where to redirect if subscription setup is canceled
        metadata: Optional dictionary of metadata to attach to the session
        
    Returns:
        Dict containing the Stripe Checkout Session object
        
    Raises:
        HTTPException: If there's an error communicating with Stripe
        
    Stripe Documentation:
        https://stripe.com/docs/api/checkout/sessions (see mode="subscription")
        https://stripe.com/docs/billing/subscriptions/checkout
        https://stripe.com/docs/billing/subscriptions/integrating-customer-portal
    """
    # If in test mode, return a mock checkout session
    if TEST_MODE:
        session_id = f"cs_sub_test_{uuid.uuid4().hex[:16]}"
        mock_session = {
            "id": session_id,
            "url": f"https://checkout.stripe.com/pay/{session_id}",
            "metadata": metadata or {}
        }
        
        # Add customer info to mock session if provided
        if customer_id:
            mock_session["customer"] = customer_id
            
        return mock_session
    
    try:
        # Create session parameters
        session_params = {
            "payment_method_types": ["card"],
            "line_items": [{
                "price": price_id,
                "quantity": 1
            }],
            "mode": "subscription",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata or {}
        }
        
        # Add customer if provided
        if customer_id:
            session_params["customer"] = customer_id
            
            # If the customer exists, use customer mode which will show saved payment methods
            try:
                # Try to retrieve customer to verify it exists
                stripe.Customer.retrieve(customer_id)
                session_params["customer_creation"] = "never"
            except stripe.error.InvalidRequestError:
                # If customer doesn't exist, let Stripe create a new one with the ID we provided
                session_params["customer_creation"] = "always"
        
        # Create the checkout session
        session = stripe.checkout.Session.create(**session_params)
        return session
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


def record_payment(user_id: str, amount: float, currency: str, payment_method: str, 
                  stripe_payment_id: str, metadata: Optional[Dict[str, Any]] = None) -> Payment:
    """Record a payment in the database after successful Stripe payment
    
    This function creates a local record of a successful payment processed through
    Stripe. This is a critical step in the payment lifecycle as it allows your
    application to track payment history, grant access to purchased content,
    and provide receipts to customers.
    
    Important payment handling concepts:
    1. Dual storage: Payments are stored both in Stripe and your local database
    2. Idempotency: Payment recording should be idempotent to avoid duplicates
    3. Reconciliation: Your local records should match Stripe's records
    4. Non-repudiation: Maintain sufficient information for audit trails
    
    This function is typically called:
    - After receiving a webhook notification of successful payment
    - When a customer returns to the success_url after Checkout
    - After manual verification of payment status
    
    Args:
        user_id: Your application's internal user identifier
        amount: The payment amount in major currency units
        currency: The 3-letter ISO currency code
        payment_method: Description of the payment method used
        stripe_payment_id: The Stripe Payment Intent or Charge ID
        metadata: Additional information about the payment
        
    Returns:
        A Payment object representing the local record of the payment
        
    Stripe Documentation:
        https://stripe.com/docs/payments/handling-payment-events
        https://stripe.com/docs/webhooks
        https://stripe.com/docs/payments/payment-intents/verifying-status
    """
    payment_id = str(uuid.uuid4())
    payment = Payment(
        id=payment_id,
        user_id=user_id,
        amount=amount,
        currency=currency,
        status="completed",
        created_at=datetime.utcnow(),
        payment_method=payment_method,
        stripe_payment_id=stripe_payment_id,
        metadata=metadata or {}
    )
    
    # Save to mock database (replace with real DB operation)
    payments_db[payment_id] = payment
    
    return payment


def record_subscription(user_id: str, product_id: str, stripe_subscription_id: str, 
                       current_period_start: datetime, current_period_end: datetime) -> Subscription:
    """Record a subscription in the database after successful Stripe subscription creation
    
    This function creates a local record of a subscription created through Stripe.
    Tracking subscriptions locally is essential for managing user access to premium
    features, handling renewal logic, and providing subscription status to users.
    
    Subscription lifecycle management involves:
    1. Creation: When a customer first subscribes (handled by this function)
    2. Renewals: When payments automatically recur
    3. Updates: When customers change plans
    4. Cancellations: When customers end their subscription
    5. Failed payments: When renewal payments fail
    
    Your application should listen for webhook events from Stripe to keep
    subscription records in sync, especially for:
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed
    
    Args:
        user_id: Your application's internal user identifier
        product_id: Your application's internal product identifier
        stripe_subscription_id: The Stripe Subscription ID
        current_period_start: When the current billing period begins
        current_period_end: When the current billing period ends
        
    Returns:
        A Subscription object representing the local record of the subscription
        
    Stripe Documentation:
        https://stripe.com/docs/billing/subscriptions/overview
        https://stripe.com/docs/billing/lifecycle
        https://stripe.com/docs/webhooks/subscription-events
    """
    subscription_id = str(uuid.uuid4())
    subscription = Subscription(
        id=subscription_id,
        user_id=user_id,
        product_id=product_id,
        status="active",
        current_period_start=current_period_start,
        current_period_end=current_period_end,
        stripe_subscription_id=stripe_subscription_id
    )
    
    # Save to mock database (replace with real DB operation)
    subscriptions_db[subscription_id] = subscription
    
    return subscription


def update_user_credits(user_id: str, credits: int) -> None:
    """Update a user's credits after a successful purchase or subscription change
    
    This function adds credits to a user's account, typically after they've
    made a purchase or as part of subscription benefits. Credits are often used
    as an in-app currency that users can spend on premium features or services.
    
    The credit system provides several benefits:
    1. Microtransactions: Users can purchase credits in bulk rather than making
       many small payments
    2. Subscription perks: Credits can be granted as part of subscription tiers
    3. Promotions: Credits can be given as rewards or incentives
    4. Usage tracking: Credits provide a clear way to meter service usage
    
    This function should be called:
    - After confirming a successful token purchase payment
    - When a subscription is created or renewed
    - As part of promotional campaigns
    
    Args:
        user_id: Your application's internal user identifier
        credits: The number of credits to add to the user's balance
        
    Raises:
        HTTPException: If the user is not found
        
    Related concepts:
        - Credit balance should be checked before allowing premium operations
        - Consider implementing credit expiration for subscription credits
        - Monitor credit usage patterns for business insights
    """
    # This would use the database to update the user's credits
    # For now, we'll just mock this
    from app.controllers.auth_controller import users_db
    
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.credits += credits
    users_db[user_id] = user


def update_user_subscription_tier(user_id: str, tier: str) -> None:
    """Update a user's subscription tier after subscription creation or change
    
    This function updates the user's subscription tier in your application's database,
    which determines the level of service and features they have access to. This is
    a critical step after processing a subscription through Stripe.
    
    Subscription tier changes affect:
    1. Feature access: Different tiers provide access to different features
    2. Usage limits: Higher tiers typically have higher usage quotas
    3. Support levels: Premium tiers may include priority support
    4. Team sizes: Team/enterprise tiers may allow multiple users
    
    Subscription tier management should handle:
    - Upgrades: Granting additional privileges immediately
    - Downgrades: Adjusting access at the end of the billing period
    - Cancellations: Reverting to free tier at the end of the billing period
    
    Args:
        user_id: Your application's internal user identifier
        tier: The name of the subscription tier (e.g., "Free", "Individual", "Team")
        
    Raises:
        HTTPException: If the user is not found
        
    Stripe Documentation:
        https://stripe.com/docs/billing/subscriptions/upgrade-downgrade
        https://stripe.com/docs/billing/subscriptions/integrating-customer-portal
    """
    # This would use the database to update the user's subscription tier
    # For now, we'll just mock this
    from app.controllers.auth_controller import users_db
    
    user = users_db.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.subscription_tier = tier
    users_db[user_id] = user


def get_user_payments(user_id: str) -> List[Payment]:
    """Get all payments for a user"""
    return [p for p in payments_db.values() if p.user_id == user_id]


def get_user_subscriptions(user_id: str) -> List[Subscription]:
    """Get all subscriptions for a user"""
    return [s for s in subscriptions_db.values() if s.user_id == user_id]


def initialize_subscription_products() -> None:
    """Initialize subscription products in Stripe and the database
    
    This function creates all subscription tiers as Products in Stripe and
    records them in the local database. It's typically run during application
    initialization or as part of deployment scripts.
    
    Proper product initialization is critical for:
    1. Ensuring all subscription tiers are available for purchase
    2. Maintaining consistency between your application and Stripe
    3. Enabling seamless subscription management
    
    Implementation notes:
    - Only non-free tiers are created in Stripe (free tiers don't require payment)
    - Each tier gets a Product and a recurring Price in Stripe
    - The Stripe Product/Price IDs are stored in your database for future reference
    
    This function should be used:
    - During initial application deployment
    - When adding new subscription tiers
    - To refresh products if they get out of sync
    
    Note that once customers have subscribed to products, you should be careful
    about modifying existing products. Consider creating new products instead
    and migrating customers as needed.
    
    Stripe Documentation:
        https://stripe.com/docs/billing/subscriptions/set-up-subscription
        https://stripe.com/docs/billing/subscriptions/multiple-products
    """
    for tier_name, tier in SUBSCRIPTION_TIERS.items():
        if tier.price > 0:  # Don't create Stripe product for free tier
            create_subscription_product(tier)


def initialize_token_product() -> None:
    """Initialize token product in Stripe and the database
    
    This function creates the token/credit product in Stripe and the local database.
    Tokens are a form of in-app currency that users can purchase and spend on
    API calls or premium features.
    
    The token product system offers:
    1. Microtransactions: Allow small purchases without processing many payments
    2. Usage metering: Track and limit API or feature usage with precision
    3. Value perception: Package tokens in bundles for better perceived value
    4. Frictionless experience: Users purchase once and spend gradually
    
    Implementation details:
    - Token prices are typically very small (e.g., $0.01 per token)
    - Stripe has minimum transaction amounts ($0.50 for USD)
    - Therefore, tokens are sold in bundles that meet the minimum
    - Different bundle sizes may offer volume discounts
    
    This function is typically called:
    - During application initialization
    - When resetting test environments
    - When modifying token pricing
    
    Stripe Documentation:
        https://stripe.com/docs/products-prices/pricing-models
        https://stripe.com/docs/billing/prices-guide
    """
    create_product(
        name=tokens_product["name"],
        description=tokens_product["description"],
        price=tokens_product["price"]
    )


def create_stripe_customer(user_id: str, email: str, name: Optional[str] = None) -> Dict[str, Any]:
    """Create a customer in Stripe
    
    This function creates a Stripe Customer object which is required for storing 
    payment methods, creating subscriptions, and tracking payment history.
    
    Stripe Customers are the foundation of the billing system and provide:
    1. A way to save and reuse payment methods securely
    2. A container for subscriptions and payment history
    3. A way to personalize checkout experiences
    4. A single identity for a customer across different products
    
    This function should be called:
    - When a new user signs up
    - When an existing user makes their first purchase
    - If a user's customer ID is missing or invalid
    
    Args:
        user_id: Your application's internal user ID
        email: The customer's email address
        name: The customer's name (optional)
        
    Returns:
        Dict containing the Stripe Customer object
        
    Raises:
        HTTPException: If there's an error communicating with Stripe
        
    Stripe Documentation:
        https://stripe.com/docs/api/customers/create
        https://stripe.com/docs/billing/customer
    """
    # If in test mode, return a mock customer
    if TEST_MODE:
        return {
            "id": f"cus_test_{uuid.uuid4().hex[:8]}",
            "email": email,
            "name": name,
            "metadata": {"user_id": user_id}
        }
    
    try:
        # Create a customer in Stripe
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={"user_id": user_id}
        )
        return customer
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


def get_stripe_customer(customer_id: str) -> Dict[str, Any]:
    """Retrieve a customer from Stripe
    
    This function fetches a Stripe Customer object using its ID.
    
    Use cases for retrieving a customer:
    1. Verifying a customer exists before operations
    2. Getting customer details for display
    3. Checking payment methods and default payment method
    4. Reviewing subscription status
    
    Args:
        customer_id: The Stripe customer ID
        
    Returns:
        Dict containing the Stripe Customer object
        
    Raises:
        HTTPException: If the customer doesn't exist or there's an error
        
    Stripe Documentation:
        https://stripe.com/docs/api/customers/retrieve
    """
    # If in test mode, return a mock customer
    if TEST_MODE:
        if not customer_id.startswith("cus_"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid customer ID format"
            )
        return {
            "id": customer_id,
            "email": "test@example.com",
            "name": "Test Customer",
            "default_source": None,
            "invoice_settings": {"default_payment_method": None}
        }
    
    try:
        # Retrieve the customer from Stripe
        customer = stripe.Customer.retrieve(customer_id)
        
        # Check if the customer has been deleted
        if getattr(customer, "deleted", False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer has been deleted"
            )
            
        return customer
    except stripe.error.InvalidRequestError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


def update_stripe_customer(customer_id: str, **kwargs) -> Dict[str, Any]:
    """Update a customer in Stripe
    
    This function updates an existing Stripe Customer with new information.
    
    Common updates include:
    1. Changing email or name
    2. Setting default payment method
    3. Adding metadata 
    4. Modifying shipping or billing addresses
    
    Args:
        customer_id: The Stripe customer ID
        **kwargs: The fields to update (e.g., email, name, metadata)
        
    Returns:
        Dict containing the updated Stripe Customer object
        
    Raises:
        HTTPException: If there's an error communicating with Stripe
        
    Stripe Documentation:
        https://stripe.com/docs/api/customers/update
    """
    # If in test mode, return a mock updated customer
    if TEST_MODE:
        if not customer_id.startswith("cus_"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid customer ID format"
            )
        mock_customer = {
            "id": customer_id,
            "email": "test@example.com",
            "name": "Test Customer",
        }
        # Update with kwargs
        mock_customer.update(kwargs)
        return mock_customer
    
    try:
        # Update the customer in Stripe
        customer = stripe.Customer.modify(customer_id, **kwargs)
        return customer
    except stripe.error.InvalidRequestError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


def get_customer_payment_methods(customer_id: str, type: str = "card") -> List[Dict[str, Any]]:
    """Get a customer's saved payment methods
    
    This function retrieves a list of payment methods saved to a customer's account.
    
    Payment methods in Stripe represent the stored payment details (cards, bank accounts, etc.)
    that can be used for future payments without requiring the customer to re-enter them.
    
    Common use cases:
    1. Displaying saved cards for the customer to choose from
    2. Selecting a default payment method
    3. Managing payment methods (deleting old ones)
    
    Args:
        customer_id: The Stripe customer ID
        type: The type of payment method (default: "card")
        
    Returns:
        List of payment method objects
        
    Raises:
        HTTPException: If there's an error communicating with Stripe
        
    Stripe Documentation:
        https://stripe.com/docs/api/payment_methods/list
        https://stripe.com/docs/payments/payment-methods/overview
    """
    # If in test mode, return mock payment methods
    if TEST_MODE:
        return [
            {
                "id": f"pm_test_{uuid.uuid4().hex[:8]}",
                "type": "card",
                "card": {
                    "brand": "visa",
                    "last4": "4242",
                    "exp_month": 12,
                    "exp_year": 2025,
                },
                "customer": customer_id,
                "created": int(datetime.utcnow().timestamp())
            }
        ]
    
    try:
        # List payment methods for the customer
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type=type
        )
        return payment_methods.data
    except stripe.error.InvalidRequestError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )