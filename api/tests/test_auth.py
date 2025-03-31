import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_register():
    """Test user registration"""
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "password": "testpassword"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert "user_id" in data
    assert "session_id" in data


def test_login():
    """Test user login"""
    # First register a user
    client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "name": "Login User",
            "password": "loginpassword"
        }
    )
    
    # Then login
    response = client.post(
        "/auth/login",
        json={
            "email": "login@example.com",
            "password": "loginpassword"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "login@example.com"
    assert data["name"] == "Login User"
    assert "user_id" in data
    assert "session_id" in data


def test_login_failure():
    """Test login failure with wrong credentials"""
    response = client.post(
        "/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401