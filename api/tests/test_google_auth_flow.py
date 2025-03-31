import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.controllers import auth_controller

client = TestClient(app)


@pytest.fixture
def mock_google_client_id():
    """Set a mock Google client ID for tests"""
    original = os.environ.get("GOOGLE_CLIENT_ID")
    os.environ["GOOGLE_CLIENT_ID"] = "mock-google-client-id"
    yield
    if original is not None:
        os.environ["GOOGLE_CLIENT_ID"] = original
    else:
        del os.environ["GOOGLE_CLIENT_ID"]


@pytest.fixture
def mock_google_response():
    """Mock response from Google"""
    return {
        "email": "test@example.com",
        "name": "Test User",
        "picture": "https://example.com/avatar.jpg",
        "sub": "google-user-id-123"
    }


def test_google_login_redirect(mock_google_client_id):
    """Test Google login redirect"""
    response = client.get("/auth/google/login", allow_redirects=False)
    assert response.status_code == 307  # Temporary redirect
    assert "accounts.google.com" in response.headers["location"]
    assert "mock-google-client-id" in response.headers["location"]


@patch("app.controllers.auth_controller.exchange_google_code")
def test_google_callback(mock_exchange, mock_google_response):
    """Test Google OAuth callback"""
    # Mock the exchange_google_code function
    mock_exchange.return_value = (mock_google_response, "mock-access-token")
    
    response = client.get("/auth/google/callback?code=mock-code")
    assert response.status_code == 200
    
    # Check that the response contains user profile data
    user_profile = response.json()
    assert user_profile["email"] == "test@example.com"
    assert user_profile["name"] == "Test User"
    assert user_profile["avatar"] == "https://example.com/avatar.jpg"
    assert user_profile["auth_method"] == "google"
    assert "session_id" in user_profile
    
    # Check that a session cookie was set
    assert "session_id" in response.cookies
    
    # Verify the user was created in the mock database
    assert any(u.email == "test@example.com" for u in auth_controller.users_db.values())


def test_access_protected_resource():
    """Test accessing a protected resource with session cookie"""
    # First login to get a session
    with patch("app.controllers.auth_controller.exchange_google_code") as mock_exchange:
        mock_exchange.return_value = ({
            "email": "protected@example.com",
            "name": "Protected User",
            "picture": "https://example.com/avatar.jpg",
            "sub": "google-user-id-456"
        }, "mock-access-token")
        
        login_response = client.get("/auth/google/callback?code=mock-code")
        session_cookie = login_response.cookies.get("session_id")
    
    # Now try to access a protected endpoint with the session cookie
    response = client.get("/auth/me", cookies={"session_id": session_cookie})
    assert response.status_code == 200
    user_profile = response.json()
    assert user_profile["email"] == "protected@example.com"
    
    # Try to access without the cookie
    response = client.get("/auth/me")
    assert response.status_code == 401  # Unauthorized