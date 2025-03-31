import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.controllers import payment_controller

client = TestClient(app)


@patch("stripe.Product.create")
@patch("stripe.Price.create")
def test_product_creation(mock_price_create, mock_product_create):
    """Test product creation in Stripe and the database"""
    # Mock Stripe API responses
    mock_product_create.return_value = {
        "id": "prod_test123",
        "name": "Test Product",
        "description": "A test product",
        "active": True
    }
    
    mock_price_create.return_value = {
        "id": "price_test123",
        "product": "prod_test123",
        "unit_amount": 1000,  # $10.00
        "currency": "usd"
    }
    
    # Create a product
    product = payment_controller.create_product(
        name="Test Product",
        description="A test product",
        price=10.0,
        currency="usd"
    )
    
    # Verify product was created correctly
    assert product.name == "Test Product"
    assert product.description == "A test product"
    assert product.price == 10.0
    assert product.currency == "usd"
    assert product.price_id == "price_test123"
    assert product.metadata["stripe_product_id"] == "prod_test123"
    
    # Verify it was added to the products database
    assert product.id in payment_controller.products_db
    assert payment_controller.products_db[product.id] == product
    
    # Verify Stripe API was called correctly
    mock_product_create.assert_called_once_with(
        name="Test Product",
        description="A test product"
    )
    
    mock_price_create.assert_called_once_with(
        product="prod_test123",
        unit_amount=1000,  # $10.00
        currency="usd",
        recurring=None
    )


@patch("stripe.Product.create")
@patch("stripe.Price.create")
def test_subscription_product_creation(mock_price_create, mock_product_create):
    """Test subscription product creation in Stripe and the database"""
    # Mock Stripe API responses
    mock_product_create.return_value = {
        "id": "prod_sub123",
        "name": "Team Subscription",
        "description": "Team tier subscription",
        "active": True
    }
    
    mock_price_create.return_value = {
        "id": "price_sub123",
        "product": "prod_sub123",
        "unit_amount": 4999,  # $49.99
        "currency": "usd",
        "recurring": {"interval": "month"}
    }
    
    # Get the Team tier
    team_tier = payment_controller.SUBSCRIPTION_TIERS["Team"]
    
    # Create a subscription product
    product = payment_controller.create_subscription_product(team_tier)
    
    # Verify product was created correctly
    assert product.name == "Team Subscription"
    assert "Team tier subscription" in product.description
    assert product.price == 49.99
    assert product.currency == "usd"
    assert product.price_id == "price_sub123"
    assert product.metadata["stripe_product_id"] == "prod_sub123"
    assert product.metadata["tier"] == "Team"
    assert product.metadata["type"] == "subscription"
    assert int(product.metadata["credits"]) == 500
    
    # Verify it was added to the products database
    assert product.id in payment_controller.products_db
    
    # Verify Stripe API was called correctly
    mock_product_create.assert_called_once_with(
        name="Team Subscription",
        description="Team tier subscription"
    )
    
    mock_price_create.assert_called_once_with(
        product="prod_sub123",
        unit_amount=4999,  # $49.99
        currency="usd",
        recurring={"interval": "month"}
    )
    
    # Verify the tier price ID was updated
    assert team_tier.stripe_price_id == "price_sub123"


@patch("stripe.Product.create")
@patch("stripe.Price.create")
def test_initialize_products(mock_price_create, mock_product_create):
    """Test initializing all products on startup"""
    # Clear the products database
    payment_controller.products_db.clear()
    
    # Mock Stripe API responses
    mock_product_create.return_value = {
        "id": "prod_test",
        "name": "Test",
        "active": True
    }
    
    mock_price_create.return_value = {
        "id": "price_test",
        "product": "prod_test",
        "unit_amount": 100,
        "currency": "usd"
    }
    
    # Initialize products
    payment_controller.initialize_subscription_products()
    payment_controller.initialize_token_product()
    
    # Verify that products were created
    
    # Should have 4 products (3 subscription tiers + tokens)
    # Note: Free tier doesn't get a Stripe product
    assert len(payment_controller.products_db) == 4
    
    # Verify token product exists
    token_product = next((p for p in payment_controller.products_db.values() 
                        if p.name == payment_controller.tokens_product["name"]), None)
    assert token_product is not None
    
    # Verify subscription products exist
    individual_product = next((p for p in payment_controller.products_db.values() 
                             if p.metadata and p.metadata.get("tier") == "Individual"), None)
    assert individual_product is not None
    
    team_product = next((p for p in payment_controller.products_db.values() 
                        if p.metadata and p.metadata.get("tier") == "Team"), None)
    assert team_product is not None
    
    enterprise_product = next((p for p in payment_controller.products_db.values() 
                              if p.metadata and p.metadata.get("tier") == "Enterprise"), None)
    assert enterprise_product is not None