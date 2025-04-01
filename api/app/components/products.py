from typing import List, Optional, Dict, Any
from fasthtml.core import Div, H2, A, P, Form, Input, Button, Span, Ul, Li, Strong
from app.components.layout import base_layout, STYLES


def PlanFeatures(features: List[str], credits: int) -> str:
    """Create a list of plan features with credits."""
    feature_items = [Li(feature) for feature in features]
    feature_items.append(Li(Strong(str(credits)), " credits per month"))
    
    return Ul(*feature_items)


def PlanCard(tier: Dict[str, Any], user_subscription_tier: str, has_customer: bool) -> str:
    """Create a subscription plan card."""
    is_current = user_subscription_tier == tier.get("name")
    price = tier.get("price", 0)
    features = tier.get("features", [])
    credits = tier.get("credits", 0)
    name = tier.get("name", "")
    
    # Create the price display
    if price == 0:
        price_display = "Free"
    else:
        price_display = f"${price}<span class=\"period\">/month</span>"
    
    # Create the action button
    if is_current:
        action_button = Button("Current Plan", class_="button current", disabled=True)
    elif price == 0:
        action_button = Form(
            Input(type="hidden", name="tier_id", value=name),
            Button("Switch to Free", type="submit", class_="button"),
            method="post",
            action="/products/subscribe"
        )
    else:
        button_attrs = {"type": "submit", "class": "button"}
        if not has_customer:
            button_attrs["title"] = "You need to add a payment method first"
            
        action_button = Form(
            Input(type="hidden", name="tier_id", value=name),
            Button("Subscribe", **button_attrs),
            method="post",
            action="/products/subscribe"
        )
    
    # Create the plan card
    return Div(
        Div(
            Div(name, class_="plan-name"),
            Div(price_display, class_="plan-price"),
            class_="plan-header"
        ),
        Div(
            PlanFeatures(features, credits),
            class_="plan-features"
        ),
        Div(
            action_button,
            class_="plan-action"
        ),
        class_=f"plan{' current' if is_current else ''}"
    )


def TokenPurchaseForm(token_price: float, has_customer: bool) -> str:
    """Create a token purchase form component."""
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
        
    purchase_form = Form(
        Div(
            Div(
                "Number of tokens to purchase:",
                class_="label"
            ),
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
    )
    
    return Div(
        H2("Buy Tokens"),
        Div(
            P(f"Tokens are used for API calls and other premium features. Each token costs ${token_price}."),
            warning,
            purchase_form,
            class_="token-purchase"
        ),
        class_="section tokens-section"
    )


def products_page(
    user: Dict[str, Any], 
    products: List[Dict[str, Any]], 
    tiers: List[Dict[str, Any]], 
    has_customer: bool,
    has_paid_tiers: bool
) -> str:
    """Create the products page."""
    # Nav items
    nav_items = [
        {"text": "Home", "href": "/"},
        {"text": "Profile", "href": "/profile"},
        {"text": "Payments", "href": "/payments"},
        {"text": "Logout", "href": "/logout"}
    ]
    
    # Check if there are any paid tiers that need a payment method
    payment_method_warning = ""
    if not has_customer and has_paid_tiers:
        payment_method_warning = Div(
            Strong("Note:"),
            " You need to add a payment method before you can subscribe to a paid plan.",
            A("Add Payment Method", href="/payments/add-card", style="margin-left: 10px; text-decoration: underline;"),
            style="margin-bottom: 15px; padding: 10px; background-color: #fff3cd; border-radius: 4px; border-left: 4px solid #856404; color: #856404;"
        )
    
    # Create the subscription plans section
    plan_cards = [
        PlanCard(tier, user.get("subscription_tier", "Free"), has_customer) 
        for tier in tiers
    ]
    
    subscription_section = Div(
        H2("Subscription Plans"),
        payment_method_warning,
        Div(*plan_cards, class_="plans"),
        class_="section"
    )
    
    # Token purchase section
    token_price = products[0].get("price", 0.01) if products and len(products) > 0 else 0.01
    token_section = TokenPurchaseForm(token_price, has_customer)
    
    # Combine everything
    content = Div(
        subscription_section,
        token_section
    )
    
    return base_layout("Products & Subscriptions", content, nav_items)