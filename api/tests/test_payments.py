import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.controllers import payment_controller

client = TestClient(app)


def test_get_subscription_tiers():
    """Test getting subscription tiers"""
    response = client.get("/payments/subscription-tiers")
    assert response.status_code == 200
    tiers = response.json()
    assert len(tiers) > 0
    assert "Free" in [tier["name"] for tier in tiers]
    assert "Individual" in [tier["name"] for tier in tiers]
    assert "Team" in [tier["name"] for tier in tiers]
    assert "Enterprise" in [tier["name"] for tier in tiers]


def test_get_products():
    """Test getting products"""
    # First register the products (this would normally happen at startup)
    payment_controller.initialize_subscription_products()
    payment_controller.initialize_token_product()
    
    response = client.get("/payments/products")
    assert response.status_code == 200
    products = response.json()
    
    # There should be at least one product (Tokens)
    assert len(products) > 0
    
    # Find tokens product
    token_product = None
    for product in products:
        if product["name"] == payment_controller.tokens_product["name"]:
            token_product = product
            break
    
    assert token_product is not None
    assert token_product["price"] == payment_controller.tokens_product["price"]