import pytest
import json
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.controllers import payment_controller, auth_controller

client = TestClient(app)


@pytest.fixture
def authenticated_user():
    """Create an authenticated user and return user_id and session cookie"""
    response = client.post(
        "/auth/register",
        json={
            "email": "payment_test@example.com",
            "name": "Payment Test User",
            "password": "password123"
        }
    )
    data = response.json()
    return data["user_id"], {"session_id": data["session_id"]}


@pytest.fixture
def stripe_product_setup():
    """Setup stripe products and subscription tiers"""
    # Initialize products in mock database
    payment_controller.initialize_subscription_products()
    payment_controller.initialize_token_product()


def test_list_products(stripe_product_setup):
    """Test listing products"""
    response = client.get("/payments/products")
    assert response.status_code == 200
    
    products = response.json()
    assert len(products) > 0
    
    # Check that token product exists
    token_product = next((p for p in products if p["name"] == payment_controller.tokens_product["name"]), None)
    assert token_product is not None
    
    # Check that subscription products exist
    subscription_products = [p for p in products if "Subscription" in p["name"]]
    assert len(subscription_products) > 0


def test_list_subscription_tiers():
    """Test listing subscription tiers"""
    response = client.get("/payments/subscription-tiers")
    assert response.status_code == 200
    
    tiers = response.json()
    assert len(tiers) == 4  # Free, Individual, Team, Enterprise
    
    # Check all tiers exist
    tier_names = [tier["name"] for tier in tiers]
    assert "Free" in tier_names
    assert "Individual" in tier_names
    assert "Team" in tier_names
    assert "Enterprise" in tier_names


@patch("stripe.checkout.Session.create")
def test_create_subscription_checkout(mock_checkout_create, authenticated_user, stripe_product_setup):
    """Test creating a subscription checkout session"""
    user_id, cookies = authenticated_user
    
    # Mock Stripe checkout session response
    mock_checkout_create.return_value = {
        "id": "cs_test_123",
        "url": "https://checkout.stripe.com/pay/cs_test_123"
    }
    
    # Create checkout session
    response = client.post(
        "/payments/subscribe",
        cookies=cookies,
        json={
            "tier": "Individual",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://checkout.stripe.com/pay/cs_test_123"
    
    # Verify the checkout was created with the correct parameters
    call_args = mock_checkout_create.call_args[1]
    assert call_args["mode"] == "subscription"
    assert "Individual" in call_args["metadata"]["tier"]
    assert call_args["metadata"]["user_id"] == user_id


@patch("stripe.checkout.Session.create")
def test_buy_tokens(mock_checkout_create, authenticated_user, stripe_product_setup):
    """Test buying tokens"""
    user_id, cookies = authenticated_user
    
    # Mock Stripe checkout session response
    mock_checkout_create.return_value = {
        "id": "cs_test_456",
        "url": "https://checkout.stripe.com/pay/cs_test_456"
    }
    
    # Buy tokens
    response = client.post(
        "/payments/buy-tokens",
        cookies=cookies,
        json={
            "amount": 100,
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://checkout.stripe.com/pay/cs_test_456"
    
    # Verify the checkout was created with the correct parameters
    call_args = mock_checkout_create.call_args[1]
    assert call_args["mode"] == "payment"
    assert call_args["metadata"]["tokens"] == 100
    assert call_args["metadata"]["user_id"] == user_id


@patch("stripe.Webhook.construct_event")
@patch("stripe.Subscription.retrieve")
def test_webhook_subscription_completed(mock_subscription_retrieve, mock_construct_event, authenticated_user):
    """Test webhook handling for completed subscription"""
    user_id, _ = authenticated_user
    
    # Create a subscription product in the database
    individual_tier = payment_controller.SUBSCRIPTION_TIERS["Individual"]
    product = payment_controller.create_subscription_product(individual_tier)
    
    # Mock Stripe subscription
    mock_subscription_retrieve.return_value = {
        "id": "sub_123",
        "current_period_start": 1609459200,  # 2021-01-01
        "current_period_end": 1612137600,    # 2021-02-01
        "status": "active"
    }
    
    # Mock Stripe event
    mock_construct_event.return_value = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "mode": "subscription",
                "subscription": "sub_123",
                "amount_total": 999,  # $9.99
                "currency": "usd",
                "metadata": {
                    "user_id": user_id,
                    "tier": "Individual"
                }
            }
        }
    }
    
    # Send webhook
    response = client.post(
        "/payments/webhook",
        headers={"stripe-signature": "test_signature"},
        content=json.dumps({})  # Content doesn't matter as we're mocking construct_event
    )
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Verify the user's subscription tier was updated
    user = auth_controller.users_db.get(user_id)
    assert user.subscription_tier == "Individual"
    
    # Verify credits were added
    assert user.credits == individual_tier.credits
    
    # Verify subscription was recorded
    user_subscriptions = payment_controller.get_user_subscriptions(user_id)
    assert len(user_subscriptions) > 0
    assert user_subscriptions[0].status == "active"
    assert user_subscriptions[0].stripe_subscription_id == "sub_123"


@patch("stripe.Webhook.construct_event")
def test_webhook_payment_completed(mock_construct_event, authenticated_user):
    """Test webhook handling for completed token payment"""
    user_id, _ = authenticated_user
    
    # Get user's initial credits
    user = auth_controller.users_db.get(user_id)
    initial_credits = user.credits
    
    # Mock Stripe event
    mock_construct_event.return_value = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_456",
                "mode": "payment",
                "amount_total": 100,  # $1.00 (100 tokens at $0.01 each)
                "currency": "usd",
                "metadata": {
                    "user_id": user_id,
                    "tokens": "100"
                }
            }
        }
    }
    
    # Send webhook
    response = client.post(
        "/payments/webhook",
        headers={"stripe-signature": "test_signature"},
        content=json.dumps({})  # Content doesn't matter as we're mocking construct_event
    )
    
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Verify credits were added
    user = auth_controller.users_db.get(user_id)
    assert user.credits == initial_credits + 100
    
    # Verify payment was recorded
    user_payments = payment_controller.get_user_payments(user_id)
    assert len(user_payments) > 0
    assert user_payments[0].stripe_payment_id == "cs_test_456"
    assert user_payments[0].amount == 1.0  # $1.00


def test_get_user_payments_and_subscriptions(authenticated_user):
    """Test getting user's payments and subscriptions"""
    user_id, cookies = authenticated_user
    
    # Add a payment to the user
    payment_controller.record_payment(
        user_id=user_id,
        amount=10.0,
        currency="usd",
        payment_method="stripe",
        stripe_payment_id="pi_test_123",
        metadata={"test": "payment"}
    )
    
    # Add a subscription to the user
    payment_controller.record_subscription(
        user_id=user_id,
        product_id=str(uuid.uuid4()),  # Random product ID
        stripe_subscription_id="sub_test_123",
        current_period_start=payment_controller.datetime.utcnow(),
        current_period_end=payment_controller.datetime.utcnow()
    )
    
    # Get payments
    response = client.get("/payments/my/payments", cookies=cookies)
    assert response.status_code == 200
    payments = response.json()
    assert len(payments) > 0
    assert payments[0]["user_id"] == user_id
    assert payments[0]["amount"] == 10.0
    
    # Get subscriptions
    response = client.get("/payments/my/subscriptions", cookies=cookies)
    assert response.status_code == 200
    subscriptions = response.json()
    assert len(subscriptions) > 0
    assert subscriptions[0]["user_id"] == user_id
    assert subscriptions[0]["stripe_subscription_id"] == "sub_test_123"