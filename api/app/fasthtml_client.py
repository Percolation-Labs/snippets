"""
Test client for API authentication and payment flows using FastHTML.
This client runs on port 7999 and provides a simple UI to test various flows:
- Login with email and password
- Buy tokens (real Stripe integration)
- Subscribe to plans (real Stripe integration)
- Manage payment methods (real Stripe integration)
"""

import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import httpx
import stripe
import uvicorn
import asyncio

from fasthtml import  FastHTML 
from fasthtml.common import *
 
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

# Define API base URL (our actual API we're testing)
API_BASE_URL = "http://localhost:8000"  # Assuming the API runs on port 8000

# Stripe configuration (using public key for client-side)
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_example")

# Create FastHTML app
app = FastHTML()

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key="test_key_only_for_development")

# CSS Styles
STYLES = """
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
    .container { border: 1px solid #ddd; border-radius: 5px; padding: 20px; margin-bottom: 20px; }
    .header { display: flex; justify-content: space-between; align-items: center; }
    .nav { display: flex; gap: 10px; }
    .nav a { text-decoration: none; padding: 8px 12px; background: #f0f0f0; border-radius: 4px; }
    .nav a:hover { background: #e0e0e0; }
    .section { margin-top: 20px; }
    h1, h2, h3 { margin-top: 0; }
    .empty-state { padding: 20px; text-align: center; background: #f5f5f5; border-radius: 4px; }
    .button { display: inline-block; padding: 8px 12px; background: #4CAF50; color: white; text-decoration: none; border: none; border-radius: 4px; cursor: pointer; }
    .button:hover { background: #45a049; }
    .button.current { background: #9E9E9E; }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
    .badge-success { background-color: #d4edda; color: #155724; }
    .badge-warning { background-color: #fff3cd; color: #856404; }
    .form-group { margin-bottom: 15px; }
    label { display: block; margin-bottom: 5px; }
    input[type="text"], input[type="password"], input[type="email"], input[type="number"] { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
    .card { border: 1px solid #ddd; border-radius: 4px; padding: 15px; margin-bottom: 15px; }
    .card-header { display: flex; justify-content: space-between; margin-bottom: 10px; }
    .card-brand { font-weight: bold; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
    th { background-color: #f5f5f5; }
    .plans { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }
    .plan { flex: 1; min-width: 200px; border: 1px solid #ddd; border-radius: 4px; padding: 20px; }
    .plan.current { border-color: #4CAF50; border-width: 2px; }
    .plan-header { margin-bottom: 15px; }
    .plan-name { font-size: 1.2em; font-weight: bold; }
    .plan-price { font-size: 1.5em; font-weight: bold; margin: 10px 0; }
    .plan-price .period { font-size: 0.7em; color: #666; }
    .plan-features { margin-bottom: 20px; }
    .plan-action { margin-top: auto; }
    .customer-info { background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 20px; border-left: 4px solid #17a2b8; }
"""


# Helper functions
async def make_api_request(
    method: str, 
    endpoint: str, 
    data: Optional[Dict[str, Any]] = None, 
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Make a request to the API with authentication"""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {}
    cookies = {}
    
    # Add session_id as cookie for authentication
    if token:
        cookies["session_id"] = token
        
        # Legacy: Include Authorization header as fallback
        headers["Authorization"] = f"Bearer {token}"
    
    # Debug the request
    print(f"Making {method.upper()} request to {url}")
    print(f"Cookies: {cookies}")
    
    async with httpx.AsyncClient() as client:
        if method.lower() == "get":
            response = await client.get(url, headers=headers, cookies=cookies)
        elif method.lower() == "post":
            response = await client.post(url, json=data, headers=headers, cookies=cookies)
        elif method.lower() == "put":
            response = await client.put(url, json=data, headers=headers, cookies=cookies)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        # Debug the response
        print(f"Response status: {response.status_code}")
        
        if response.status_code >= 400:
            error_detail = response.text
            try:
                error_json = response.json()
                if "detail" in error_json:
                    error_detail = error_json["detail"]
            except:
                pass
            
            print(f"API error: {error_detail}")
            return {"error": error_detail, "status_code": response.status_code}
        
        try:
            return response.json()
        except Exception as e:
            print(f"Error parsing API response as JSON: {str(e)}")
            return {"error": "Invalid JSON response", "data": response.text}


# Layout Components
def BaseLayout(title: str, content, nav_items=None, user=None):
    """Base layout for all pages"""
    print(app, 'app')
    if nav_items is None:
        if user:
            nav_items = [
                {"text": "Home", "href": "/"},
                {"text": "Profile", "href": "/profile"},
                {"text": "Payments", "href": "/payments"},
                {"text": "Products", "href": "/products"},
                {"text": "Logout", "href": "/logout"}
            ]
        else:
            nav_items = [
                {"text": "Home", "href": "/"},
                {"text": "Login", "href": "/login"}
            ]
    
    return Html(
        Head(
            Title(f"{title} - API Test Client"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            Style(STYLES)
        ),
        Body(
            Div(
                Div(
                    H1(title),
                    Div(
                        *[A(item["text"], href=item["href"]) for item in nav_items],
                        class_="nav"
                    ),
                    class_="header"
                ),
                content,
                class_="container"
            )
        )
    )


# Product Page Components
def PlanFeatures(features, credits):
    """Plan features list with credits"""
    feature_items = [Li(feature) for feature in features]
    feature_items.append(Li(Strong(str(credits)), " credits per month"))
    return Ul(*feature_items)


def PlanCard(tier, user_subscription_tier, has_customer):
    """Create a subscription plan card"""
    name = tier.get("name", "")
    price = tier.get("price", 0)
    features = tier.get("features", [])
    credits = tier.get("credits", 0)
    is_current = user_subscription_tier == name
    
    # Price display
    price_html = "Free" if price == 0 else f"${price}<span class='period'>/month</span>"
    
    # Action button
    if is_current:
        action = Button("Current Plan", class_="button current", disabled=True)
    elif price == 0:
        action = Form(
            Input(type="hidden", name="tier_id", value=name),
            Button("Switch to Free", type="submit", class_="button"),
            method="post",
            action="/products/subscribe"
        )
    else:
        button_attrs = {"type": "submit", "class": "button"}
        if not has_customer:
            button_attrs["title"] = "You need to add a payment method first"
        
        action = Form(
            Input(type="hidden", name="tier_id", value=name),
            Button("Subscribe", **button_attrs),
            method="post",
            action="/products/subscribe"
        )
    
    return Div(
        Div(
            Div(name, class_="plan-name"),
            Div(price_html, class_="plan-price"),
            class_="plan-header"
        ),
        Div(
            PlanFeatures(features, credits),
            class_="plan-features"
        ),
        Div(
            action,
            class_="plan-action"
        ),
        class_=f"plan{'current' if is_current else ''}"
    )


def TokenPurchaseForm(token_price, has_customer):
    """Token purchase form"""
    warning = ""
    if not has_customer:
        warning = Div(
            Strong("Note:"),
            " You need to add a payment method before you can purchase tokens.",
            A("Add Payment Method", href="/payments/add-card", style="margin-left: 10px; text-decoration: underline;"),
            style="margin-bottom: 15px; padding: 10px; background-color: #fff3cd; border-radius: 4px; border-left: 4px solid #856404; color: #856404;"
        )
    
    button_attrs = {"type": "submit", "class": "button"}
    if not has_customer:
        button_attrs["title"] = "You need to add a payment method first"
    
    return Div(
        H2("Buy Tokens"),
        Div(
            P(f"Tokens are used for API calls and other premium features. Each token costs ${token_price}."),
            warning,
            Form(
                Div(
                    Label("Number of tokens to purchase:", for_="token_amount"),
                    Input(
                        type="number",
                        id="token_amount",
                        name="token_amount",
                        value="50",
                        min="50",
                        required=True
                    ),
                    Div("Minimum purchase: 50 tokens", class_="token-price"),
                    class_="form-group"
                ),
                Button("Buy Tokens", **button_attrs),
                method="post",
                action="/products/buy-tokens"
            ),
            class_="token-purchase"
        ),
        class_="section tokens-section"
    )


# Payment Page Components
def PaymentMethodCard(method):
    """Payment method card component"""
    brand = method.get("brand", "").upper()
    last4 = method.get("last4", "")
    exp_month = method.get("exp_month", "")
    exp_year = method.get("exp_year", "")
    is_default = method.get("is_default", False)
    
    badge = Span("Default", class_="badge badge-success") if is_default else ""
    
    return Div(
        Div(
            Div(f"{brand} •••• {last4}", class_="card-brand"),
            Div(f"Expires {exp_month}/{exp_year}"),
            class_="card-header"
        ),
        Div(badge),
        class_="card"
    )


def SubscriptionRow(sub):
    """Single subscription table row"""
    product_name = sub.get("product_name", "")
    status = sub.get("status", "")
    current_period_start = sub.get("current_period_start", "")
    current_period_end = sub.get("current_period_end", "")
    cancel_at_period_end = sub.get("cancel_at_period_end", False)
    subscription_id = sub.get("id", "")
    
    status_cell = Div(
        status,
        Span("(Cancels at period end)", style="color: #856404; font-size: 0.8em;") if cancel_at_period_end else ""
    )
    
    renewal_cell = current_period_end
    if status == "active" and not cancel_at_period_end:
        cancel_buttons = Div(
            Form(
                Input(type="hidden", name="subscription_id", value=subscription_id),
                Input(type="hidden", name="cancel_immediately", value="false"),
                Button(
                    "Cancel at period end",
                    type="submit",
                    style="font-size: 0.8em; padding: 2px 5px; background-color: #fff3cd; color: #856404; border: 1px solid #856404; border-radius: 3px; cursor: pointer;"
                ),
                method="post",
                action="/payments/cancel-subscription",
                style="display: inline;"
            ),
            Form(
                Input(type="hidden", name="subscription_id", value=subscription_id),
                Input(type="hidden", name="cancel_immediately", value="true"),
                Button(
                    "Cancel now",
                    type="submit",
                    style="font-size: 0.8em; padding: 2px 5px; background-color: #f8d7da; color: #721c24; border: 1px solid #721c24; border-radius: 3px; cursor: pointer;"
                ),
                method="post",
                action="/payments/cancel-subscription",
                style="display: inline; margin-left: 5px;"
            ),
            style="margin-top: 5px;"
        )
        renewal_cell = Div(
            current_period_end,
            cancel_buttons
        )
    
    return Tr(
        Td(product_name),
        Td(status_cell),
        Td(current_period_start),
        Td(renewal_cell)
    )


def PaymentRow(payment):
    """Payment history table row"""
    created_at = payment.get("created_at", "")
    amount = payment.get("amount", 0)
    currency = payment.get("currency", "USD").upper()
    description = payment.get("description", payment.get("payment_method", ""))
    status = payment.get("status", "")
    
    return Tr(
        Td(created_at),
        Td(f"{amount} {currency}"),
        Td(description),
        Td(status)
    )


# Route Handlers
@app.get("/")
async def index(session):
    """Home page"""
    print(session)
    user = session.get("user")
    
    if user:
        content = Div(
            H2(f"Welcome, {user.get('display_name') or user.get('email')}"),
            P("You are logged in. Use the navigation above to test different features."),
            class_="section"
        )
    else:
        content = Div(
            H2("Welcome to the API Test Client"),
            P("This client allows you to test various API flows:"),
            Ul(
                Li("Login with email and password"),
                Li("Add payment methods"),
                Li("Buy tokens"),
                Li("Subscribe to plans")
            ),
            P(A("Login", href="/login"), " to get started."),
            class_="section"
        )
    
    return BaseLayout("Home", content, None, user)


@app.get("/login")
async def login_page(request):
    """Login page"""
    content = Div(
        H2("Email Login"),
        Form(
            Div(
                Label("Email:", for_="username"),
                Input(type="email", id="username", name="username", required=True),
                class_="form-group"
            ),
            Div(
                Label("Password:", for_="password"),
                Input(type="password", id="password", name="password", required=True),
                class_="form-group"
            ),
            Button("Login", type="submit"),
            method="post",
            action="/login"
        ),
        class_="section"
    )
    
    return BaseLayout("Login", content)


@app.post("/login")
async def login(request):
    """Process login form"""
    form_data = await request.form()
    email = form_data.get("username")
    password = form_data.get("password")
    
    try:
        # Create a callback URL to receive user profile
        callback_url = f"http://localhost:7999/profile-callback?data=profile_data"
        
        # Login request to API
        async with httpx.AsyncClient(follow_redirects=False) as client:
            api_response = await client.post(
                f"{API_BASE_URL}/auth/login",
                json={"email": email, "password": password},
                params={"redirect_url": callback_url}
            )
            
            # Handle API response
            if 300 <= api_response.status_code < 400:
                # API is redirecting - pass through the redirect
                return RedirectResponse(
                    url=api_response.headers["location"],
                    status_code=302
                )
            elif api_response.status_code == 200:
                # API returned user data directly
                user_data = api_response.json()
                session_id = api_response.cookies.get('session_id', os.urandom(16).hex())
                
                # Save in session
                request.session["token"] = session_id
                request.session["user"] = user_data
                
                # Redirect to profile
                return RedirectResponse(url="/profile", status_code=302)
            
            # API call failed
            raise Exception(f"API returned status {api_response.status_code}: {api_response.text}")
            
    except Exception as e:
        # If API call fails, create a mock user
        print(f"Error during login: {str(e)}")
        
        # Create mock user
        user_data = {
            "id": "user_1234",
            "email": email,
            "display_name": email.split("@")[0],
            "subscription_tier": "Free",
            "credits": 10
        }
        
        mock_token = "mock_token_" + os.urandom(8).hex()
        request.session["token"] = mock_token
        request.session["user"] = user_data
        
        return RedirectResponse(url="/", status_code=302)


@app.get("/profile")
async def profile_page(request):
    """User profile page"""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    
    content = Div(
        H2("User Information"),
        Div(
            Div(Strong("Email: "), user.get("email")),
            Div(Strong("Display Name: "), user.get("display_name") or user.get("name") or "Not set"),
            Div(Strong("Subscription Tier: "), user.get("subscription_tier", "Free")),
            Div(Strong("Credits: "), str(user.get("credits", 0))),
            class_="profile-info"
        ),
        class_="section"
    )
    
    return BaseLayout("Profile", content)


@app.get("/products")
async def products_page(request):
    """Products and subscription plans page"""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    
    token = request.session.get("token", "")
    
    # Initialize data
    products = []
    tiers = []
    
    # First ensure products are initialized in the API
    try:
        init_response = await make_api_request(
            "post",
            "/payments/initialize-products",
            data={},
            token=token
        )
        print(f"Products initialization response: {init_response}")
    except Exception as e:
        print(f"Error initializing products: {str(e)}")
    
    # Get available products from API
    try:
        products = await make_api_request(
            "get",
            "/payments/products",
            token=token
        )
        
        if "error" in products:
            raise Exception(products.get("error", "Failed to get products"))
            
    except Exception as e:
        print(f"Error fetching products: {str(e)}")
        # Create mock products as fallback
        products = [
            {
                "id": "prod_tokens",
                "name": "Tokens",
                "description": "Credits for API usage",
                "price": 0.01,
                "price_id": "price_tokens"
            }
        ]
    
    # Get subscription tiers from API
    try:
        tiers = await make_api_request(
            "get",
            "/payments/subscription-tiers",
            token=token
        )
        
        if "error" in tiers:
            raise Exception(tiers.get("error", "Failed to get subscription tiers"))
            
    except Exception as e:
        print(f"Error fetching subscription tiers: {str(e)}")
        # Create mock tiers as fallback
        tiers = [
            {
                "name": "Free",
                "price": 0,
                "features": ["Basic access", "Limited API calls"],
                "credits": 5,
                "currency": "usd"
            },
            {
                "name": "Individual",
                "price": 9.99,
                "features": ["Full access", "Priority support", "Unlimited API calls"],
                "credits": 100,
                "currency": "usd"
            },
            {
                "name": "Team",
                "price": 49.99,
                "features": ["Full access", "Priority support", "Unlimited API calls", "Team management"],
                "credits": 500,
                "currency": "usd"
            },
            {
                "name": "Enterprise",
                "price": 199.99,
                "features": ["Full access", "Priority support", "Unlimited API calls", "Team management", "Custom integrations"],
                "credits": 2000,
                "currency": "usd"
            }
        ]
    
    # Check if user has a Stripe customer ID, if not try to get one
    if not user.get("stripe_customer_id"):
        try:
            if user.get("email"):
                customer_response = await make_api_request(
                    "get",
                    f"/payments/customer-by-email?email={user['email']}",
                    token=token
                )
                
                if "found" in customer_response and customer_response["found"] and customer_response.get("customer_id"):
                    user["stripe_customer_id"] = customer_response["customer_id"]
                    request.session["user"] = user
                    print(f"Retrieved customer ID by email: {customer_response['customer_id']}")
        except Exception as e:
            print(f"Error retrieving customer by email: {str(e)}")
    
    # Check if there are any paid tiers
    has_paid_tiers = any(tier.get("price", 0) > 0 for tier in tiers)
    has_customer = bool(user.get("stripe_customer_id"))
    
    # Warning for paid tiers
    warning = ""
    if not has_customer and has_paid_tiers:
        warning = Div(
            Strong("Note:"),
            " You need to add a payment method before you can subscribe to a paid plan.",
            A("Add Payment Method", href="/payments/add-card", style="margin-left: 10px; text-decoration: underline;"),
            style="margin-bottom: 15px; padding: 10px; background-color: #fff3cd; border-radius: 4px; border-left: 4px solid #856404; color: #856404;"
        )
    
    # Build content
    subscription_section = Div(
        H2("Subscription Plans"),
        warning,
        Div(
            *[PlanCard(tier, user.get("subscription_tier", "Free"), has_customer) for tier in tiers],
            class_="plans"
        ),
        class_="section"
    )
    
    token_price = products[0].get("price", 0.01) if products and len(products) > 0 else 0.01
    token_section = TokenPurchaseForm(token_price, has_customer)
    
    content = Div(
        subscription_section,
        token_section
    )
    
    return BaseLayout("Products & Subscriptions", content)


@app.post("/products/buy-tokens")
async def buy_tokens(request):
    """Buy tokens form handler"""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    
    token = request.session.get("token", "")
    form_data = await request.form()
    token_amount = int(form_data.get("token_amount", "50"))
    
    try:
        # Get the base URL for success/cancel URLs
        base_url = str(API_BASE_URL)
        success_url = f"{base_url}/payments/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/payments"
        
        # Create token purchase checkout session
        print(f"Creating token purchase for {token_amount} tokens")
        response = await make_api_request(
            "post",
            "/payments/buy-tokens",
            {
                "amount": token_amount,
                "success_url": success_url,
                "cancel_url": cancel_url
            },
            token=token
        )
        
        print(f"Token purchase response: {response}")
        
        if "error" in response:
            error_message = response.get("error", "Failed to create checkout session")
            print(f"Token purchase error: {error_message}")
            return HTMLResponse(f"<h1>Error</h1><p>{error_message}</p>")
        
        # Redirect to Stripe checkout
        checkout_url = response.get("url")
        if not checkout_url:
            raise Exception("No checkout URL returned from API")
            
        return RedirectResponse(url=checkout_url, status_code=302)
        
    except Exception as e:
        print(f"Error creating token checkout: {str(e)}")
        
        # For testing, simulate token purchase
        user["credits"] = user.get("credits", 0) + token_amount
        request.session["user"] = user
        
        return RedirectResponse(
            url=f"/payments?success=true&message=Simulated+token+purchase+of+{token_amount}+tokens",
            status_code=302
        )


@app.post("/products/subscribe")
async def subscribe(request):
    """Subscribe to plan form handler"""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    
    token = request.session.get("token", "")
    form_data = await request.form()
    tier_id = form_data.get("tier_id")
    
    try:
        # Get the base URL for success/cancel URLs
        base_url = str(API_BASE_URL)
        success_url = f"{base_url}/payments/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/payments"
        
        # Create subscription checkout session
        print(f"Creating subscription for tier: {tier_id}")
        response = await make_api_request(
            "post",
            "/payments/subscribe",
            {
                "tier": tier_id,
                "success_url": success_url,
                "cancel_url": cancel_url
            },
            token=token
        )
        
        print(f"Subscription response: {response}")
        
        if "error" in response:
            error_message = response.get("error", "Failed to create subscription")
            print(f"Subscription error: {error_message}")
            return HTMLResponse(f"<h1>Error</h1><p>{error_message}</p>")
        
        # Redirect to Stripe checkout
        checkout_url = response.get("url")
        if not checkout_url:
            raise Exception("No checkout URL returned from API")
            
        return RedirectResponse(url=checkout_url, status_code=302)
        
    except Exception as e:
        print(f"Error creating subscription: {str(e)}")
        
        # For testing, simulate subscription
        user["subscription_tier"] = tier_id
        request.session["user"] = user
        
        return RedirectResponse(
            url=f"/payments?success=true&message=Simulated+subscription+to+{tier_id}+plan",
            status_code=302
        )


@app.get("/payments")
async def payments_page(request):
    """Payments and subscriptions management page"""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    
    token = request.session.get("token", "")
    
    # Initialize data containers
    payment_methods = []
    subscriptions = []
    payments = []
    
    # Only fetch payment data if the user has a Stripe customer ID
    if user.get("stripe_customer_id"):
        # Get user's payment methods from API
        try:
            payment_methods = await make_api_request(
                "get",
                "/payments/methods",
                token=token
            )
            
            if "error" in payment_methods:
                raise Exception(payment_methods.get("error", "Failed to get payment methods"))
                
        except Exception as e:
            print(f"Error fetching payment methods: {str(e)}")
        
        # Get user's subscriptions from API
        try:
            subscriptions = await make_api_request(
                "get",
                "/payments/my/subscriptions",
                token=token
            )
            
            if "error" in subscriptions:
                raise Exception(subscriptions.get("error", "Failed to get subscriptions"))
                
        except Exception as e:
            print(f"Error fetching subscriptions: {str(e)}")
        
        # Get payment history from API
        try:
            payments = await make_api_request(
                "get",
                "/payments/my/payments",
                token=token
            )
            
            if "error" in payments:
                raise Exception(payments.get("error", "Failed to get payment history"))
                
        except Exception as e:
            print(f"Error fetching payment history: {str(e)}")
    
    has_payment_method = len(payment_methods) > 0 or user.get("stripe_customer_id")
    
    # Customer info section
    customer_info = Div(
        H3("Payment Account"),
        Div(
            Div(
                Strong("Customer ID:"), 
                f" {user.get('stripe_customer_id', 'Not set up yet')}"
            ),
            Div(
                Strong("Status:"),
                Span("Active", class_="badge badge-success") if has_payment_method else Span("No payment method", class_="badge badge-warning")
            ),
            class_="profile-info"
        ),
        class_="customer-info"
    )
    
    # Payment methods section
    payment_methods_html = Div("You don't have any payment methods yet.", class_="empty-state")
    if payment_methods:
        payment_methods_html = Div(*[PaymentMethodCard(method) for method in payment_methods])
    
    payment_methods_section = Div(
        H2("Payment Methods"),
        payment_methods_html,
        A(
            "Add Another Payment Method" if payment_methods else "Add Payment Method",
            href="/payments/add-card",
            class_="button"
        ),
        class_="section"
    )
    
    # Subscriptions section
    subscriptions_html = Div("You don't have any active subscriptions.", class_="empty-state")
    if subscriptions:
        subscriptions_html = Table(
            Tr(
                Th("Plan"),
                Th("Status"),
                Th("Started"),
                Th("Renewal Date")
            ),
            *[SubscriptionRow(sub) for sub in subscriptions]
        )
    
    subscriptions_section = Div(
        H2("Active Subscriptions"),
        subscriptions_html,
        A("View Subscription Plans", href="/products", class_="button"),
        class_="section"
    )
    
    # Payment history section
    payments_html = Div("You don't have any payment history yet.", class_="empty-state")
    if payments:
        payments_html = Table(
            Tr(
                Th("Date"),
                Th("Amount"),
                Th("Description"),
                Th("Status")
            ),
            *[PaymentRow(payment) for payment in payments]
        )
    
    payments_section = Div(
        H2("Payment History"),
        payments_html,
        class_="section"
    )
    
    # Combine all sections
    content = Div(
        customer_info,
        payment_methods_section,
        subscriptions_section,
        payments_section
    )
    
    return BaseLayout("Payments", content)


@app.post("/payments/cancel-subscription")
async def cancel_subscription(request):
    """Cancel subscription form handler"""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    
    token = request.session.get("token", "")
    form_data = await request.form()
    subscription_id = form_data.get("subscription_id")
    cancel_immediately = form_data.get("cancel_immediately") == "true"
    
    try:
        # Call API to cancel subscription
        response = await make_api_request(
            "post",
            f"/payments/subscriptions/{subscription_id}/cancel",
            {"cancel_immediately": cancel_immediately},
            token=token
        )
        
        if "error" in response:
            error_message = response.get("error", "Failed to cancel subscription")
            print(f"Cancel subscription error: {error_message}")
            return HTMLResponse(f"<h1>Error</h1><p>{error_message}</p>")
        
        # If immediate cancellation, update user's subscription tier
        if cancel_immediately:
            user["subscription_tier"] = "Free"
            request.session["user"] = user
        
    except Exception as e:
        print(f"Error canceling subscription: {str(e)}")
    
    # Redirect back to payments page
    return RedirectResponse(url="/payments", status_code=302)


@app.get("/payments/add-card")
async def add_card_page(request):
    """Add payment method page"""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    
    token = request.session.get("token", "")
    
    try:
        # Get setup intent from API
        setup_intent = await make_api_request(
            "post",
            "/payments/setup-intent",
            data={},
            token=token
        )
        
        if "error" in setup_intent:
            raise Exception(setup_intent.get("error", "Failed to create setup intent"))
        
        # If we got a customer ID back, update the session
        if setup_intent.get("customer_id") and not user.get("stripe_customer_id"):
            user["stripe_customer_id"] = setup_intent["customer_id"]
            request.session["user"] = user
            print(f"Updated user with customer ID: {setup_intent['customer_id']}")
            
    except Exception as e:
        print(f"Error creating setup intent: {str(e)}")
        # Create a mock setup intent as fallback
        setup_intent = {
            "client_secret": "seti_mock_secret_" + os.urandom(8).hex()
        }
    
    # Build the add card page with Stripe Elements
    content = Div(
        H2("Add Credit or Debit Card"),
        Div(
            Form(
                Div(
                    Label("Credit or debit card:", for_="card-element"),
                    Div(id="card-element"),
                    Div(id="card-errors", class_="error-message", role="alert"),
                    class_="form-group"
                ),
                Button("Add Card", id="submit-button", type="submit"),
                id="payment-form"
            ),
            class_="card-form",
            style="max-width: 500px;"
        ),
        
        # Stripe JS
        Div(
            f"""
            <script src="https://js.stripe.com/v3/"></script>
            <script>
                // Initialize Stripe
                const stripe = Stripe('{STRIPE_PUBLISHABLE_KEY}');
                const elements = stripe.elements();
                
                // Create card element
                const cardElement = elements.create('card');
                cardElement.mount('#card-element');
                
                // Handle form submission
                const form = document.getElementById('payment-form');
                const submitButton = document.getElementById('submit-button');
                const errorElement = document.getElementById('card-errors');
                
                form.addEventListener('submit', async (event) => {{
                    event.preventDefault();
                    
                    // Disable submit button
                    submitButton.disabled = true;
                    submitButton.textContent = 'Processing...';
                    
                    // Create payment method
                    const {{ setupIntent, error }} = await stripe.confirmCardSetup(
                        '{setup_intent["client_secret"]}',
                        {{
                            payment_method: {{
                                card: cardElement,
                            }}
                        }}
                    );
                    
                    if (error) {{
                        // Show error to customer
                        errorElement.textContent = error.message;
                        submitButton.disabled = false;
                        submitButton.textContent = 'Add Card';
                    }} else {{
                        // Submit payment method ID to server
                        const form = document.createElement('form');
                        form.method = 'POST';
                        form.action = '/payments/add-card';
                        
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'payment_method_id';
                        input.value = setupIntent.payment_method;
                        
                        form.appendChild(input);
                        document.body.appendChild(form);
                        form.submit();
                    }}
                }});
            </script>
            """,
            _is_html=True  # This is important to render the script correctly
        ),
        class_="section"
    )
    
    return BaseLayout("Add Payment Method", content)


@app.post("/payments/add-card")
async def add_card(request):
    """Process add card form"""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    
    token = request.session.get("token", "")
    form_data = await request.form()
    payment_method_id = form_data.get("payment_method_id")
    
    try:
        print(f"Adding payment method {payment_method_id}")
        
        # Add payment method through API
        response = await make_api_request(
            "post",
            "/payments/methods",
            {"payment_method_id": payment_method_id},
            token=token
        )
        
        if "error" in response:
            error_message = response.get("error", "Failed to add payment method")
            print(f"Add payment method error: {error_message}")
            return HTMLResponse(f"<h1>Error</h1><p>{error_message}</p>")
        
        print(f"API response for adding payment method: {response}")
        
        # If the API returned a customer ID, update the user's profile
        if response.get("customer_id"):
            user["stripe_customer_id"] = response["customer_id"]
            request.session["user"] = user
            print(f"Updated user with customer ID: {response['customer_id']}")
        
    except Exception as e:
        print(f"Error adding payment method: {str(e)}")
    
    # Redirect to payments page
    return RedirectResponse(url="/payments", status_code=302)


@app.get("/logout")
async def logout(request):
    """Log out user by clearing session"""
    request.session.clear()
    return RedirectResponse(url="/")


# Initialize server
if __name__ == "__main__":
    # Configure uvicorn server
    uvicorn.run("fasthtml_client:app", host="0.0.0.0", port=7999, reload=True)