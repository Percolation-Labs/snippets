import pytest
from fastapi.testclient import TestClient
import uuid
from app.main import app

client = TestClient(app)


@pytest.fixture
def authenticated_user():
    """Create an authenticated user for testing"""
    # Register a new user
    response = client.post(
        "/auth/register",
        json={
            "email": f"product_test_{uuid.uuid4()}@example.com",
            "name": "Product Test User",
            "password": "password123"
        }
    )
    data = response.json()
    return data["user_id"], data["session_id"]


def test_create_product(authenticated_user):
    """Test creating a product"""
    user_id, session_id = authenticated_user
    
    # Create a product
    product_name = f"Test Product {uuid.uuid4()}"
    response = client.post(
        "/payments/products",
        json={
            "name": product_name,
            "description": "Test product description",
            "price": 19.99,
            "currency": "usd"
        },
        cookies={"session_id": session_id}
    )
    
    # Check the response
    assert response.status_code == 200
    product = response.json()
    assert product["name"] == product_name
    assert product["description"] == "Test product description"
    assert product["price"] == 19.99
    assert product["currency"] == "usd"
    assert product["active"] is True
    
    return product


def test_create_duplicate_product(authenticated_user):
    """Test creating a product with a duplicate name"""
    user_id, session_id = authenticated_user
    
    # Create a product
    product_name = f"Duplicate Product {uuid.uuid4()}"
    response = client.post(
        "/payments/products",
        json={
            "name": product_name,
            "description": "First product",
            "price": 19.99
        },
        cookies={"session_id": session_id}
    )
    
    # Check first creation worked
    assert response.status_code == 200
    
    # Try to create another product with the same name
    response = client.post(
        "/payments/products",
        json={
            "name": product_name,
            "description": "Second product",
            "price": 29.99
        },
        cookies={"session_id": session_id}
    )
    
    # Check that it fails with appropriate error
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_delete_product(authenticated_user):
    """Test deleting a product"""
    user_id, session_id = authenticated_user
    
    # Create a product to delete
    product = test_create_product(authenticated_user)
    product_name = product["name"]
    
    # Delete the product
    response = client.delete(
        f"/payments/products/{product_name}",
        cookies={"session_id": session_id}
    )
    
    # Check the response
    assert response.status_code == 200
    assert response.json()["message"] == f"Product '{product_name}' deleted successfully"
    
    # Make sure the product no longer exists
    response = client.get("/payments/products")
    products = response.json()
    assert not any(p["name"] == product_name for p in products)


def test_delete_nonexistent_product(authenticated_user):
    """Test deleting a product that doesn't exist"""
    user_id, session_id = authenticated_user
    
    # Delete a nonexistent product
    response = client.delete(
        f"/payments/products/NonexistentProduct-{uuid.uuid4()}",
        cookies={"session_id": session_id}
    )
    
    # Check the response
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]