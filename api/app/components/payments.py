from typing import List, Dict, Any, Optional
from fasthtml.core import respond, fh_cfg
from fasthtml.common import *
from app.components.layout import base_layout, STYLES


def Section(content, class_name="section"):
    """Create a section with the specified content."""
    return Div(content, class_=class_name)


def PaymentMethodCard(method: Dict[str, Any]) -> str:
    """Create a payment method card component."""
    print(method)
    print('***********')
    brand = method.get("brand", "").upper()
    last4 = method.get("last4", "")
    exp_month = method.get("exp_month", "")
    exp_year = method.get("exp_year", "")
    is_default = method.get("is_default", False)
    
    card_header = Div(
        Div(f"{brand} •••• {last4}", class_="card-brand"),
        Div(f"Expires {exp_month}/{exp_year}"),
        class_="card-header"
    )
    
    badge = "" if not is_default else Span("Default", class_="badge badge-success")
    
    return Div(
        card_header,
        Div(badge),
        class_="card"
    )


def SubscriptionRow(sub: Dict[str, Any]) -> str:
    """Create a subscription table row component."""
    product_name = sub.get("product_name", "")
    status = sub.get("status", "")
    current_period_start = sub.get("current_period_start", "")
    current_period_end = sub.get("current_period_end", "")
    cancel_at_period_end = sub.get("cancel_at_period_end", False)
    subscription_id = sub.get("id", "")
    
    # Status cell with cancellation indicator
    status_cell = status
    if cancel_at_period_end:
        status_cell = Div(
            status,
            Span("(Cancels at period end)", style="color: #856404; font-size: 0.8em;"),
        )
    
    # Renewal date cell with cancel buttons
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


def PaymentRow(payment: Dict[str, Any]) -> str:
    """Create a payment history table row component."""
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


def SubscriptionTable(subscriptions: List[Dict[str, Any]]) -> str:
    """Create a table of subscriptions."""
    if not subscriptions:
        return Div("You don't have any active subscriptions.", class_="empty-state")
    
    return Table(
        Tr(
            Th("Plan"),
            Th("Status"),
            Th("Started"),
            Th("Renewal Date")
        ),
        *[SubscriptionRow(sub) for sub in subscriptions]
    )


def PaymentHistoryTable(payments: List[Dict[str, Any]]) -> str:
    """Create a table of payment history."""
    if not payments:
        return Div("You don't have any payment history yet.", class_="empty-state")
    
    return Table(
        Tr(
            Th("Date"),
            Th("Amount"),
            Th("Description"),
            Th("Status")
        ),
        *[PaymentRow(payment) for payment in payments]
    )


def PaymentMethodsList(payment_methods: List[Dict[str, Any]]) -> str:
    """Create a list of payment methods."""
    if not payment_methods:
        return Div("You don't have any payment methods yet.", class_="empty-state")
    
    return Div(*[PaymentMethodCard(method) for method in payment_methods])


def payments_page(
    user: Dict[str, Any],
    payment_methods: List[Dict[str, Any]],
    subscriptions: List[Dict[str, Any]],
    payments: List[Dict[str, Any]],
    has_payment_method: bool
) -> str:
    """Create the payments page."""
    # Nav items
    nav_items = [
        {"text": "Home", "href": "/"},
        {"text": "Profile", "href": "/profile"},
        {"text": "2FA", "href": "/2fa"},
        {"text": "Products", "href": "/products"},
        {"text": "Logout", "href": "/logout"}
    ]
    
    # Customer info section
    customer_info = Div(
        *[H3("Payment Account"),
        Div(
            *[Div(
               *[ Strong("Customer ID:"), 
                f" {user.get('stripe_customer_id', 'Not set up yet')}"]
            ),
            Div(
                *[Strong("Status:"),
                Span("Active", class_="badge badge-success") if has_payment_method else Span("No payment method", class_="badge badge-warning")]
            )],
            class_="profile-info"
        )],
        class_="customer-info"
    )
    
    # Payment methods section
    payment_methods_section = Section(
       *Div([ H2("Payment Methods"),
        PaymentMethodsList(payment_methods),
        A(
            "Add Another Payment Method" if payment_methods else "Add Payment Method",
            href="/payments/add-card",
         
            class_="button"
        )])
    )
    
    # Subscriptions section
    subscriptions_section = Section(
       Div(*[ H2("Active Subscriptions"),
        SubscriptionTable(subscriptions),
        A("View Subscription Plans", href="/products", class_="button")])
    )
    
    # Payment history section
    payment_history_section = Section(
       Div(*[ H2("Payment History"),
        PaymentHistoryTable(payments)])
    )
    
    # Combine all sections
    content = Div(
        *[customer_info,
        payment_methods_section,
        subscriptions_section,
        payment_history_section]
    )
    
    return base_layout("Payments", content, nav_items)