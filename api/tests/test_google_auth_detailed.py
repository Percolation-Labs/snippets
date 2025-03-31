import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import status
import json
import os

from app.main import app
from app.controllers import auth_controller

client = TestClient(app)


@pytest.fixture
def mock_google_auth_data():
    """Mock Google auth data for testing"""
    return {
        "user_info": {
            "sub": "123456789",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://example.com/test.jpg",
            "given_name": "Test",
            "family_name": "User",
        },
        "access_token": "mock-access-token",
        "id_token": "mock-id-token",
        "refresh_token": "mock-refresh-token",
    }


def test_google_login_route():
    """Test the Google login route redirects to Google auth URL"""
    # Set a mock Google client ID for the test
    os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
    
    # Test the Google login route
    response = client.get("/auth/google/login", allow_redirects=False)
    
    # It should redirect to Google's auth endpoint
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert "accounts.google.com" in response.headers["location"]
    assert "test-client-id" in response.headers["location"]
    assert "scope=email%20profile" in response.headers["location"]


@patch("app.controllers.auth_controller.exchange_google_code")
def test_google_callback(mock_exchange, mock_google_auth_data):
    """Test the Google callback route processes OAuth response correctly"""
    # Setup the mock to return the test data
    mock_exchange.return_value = (mock_google_auth_data["user_info"], mock_google_auth_data["access_token"])
    
    # Test the callback with a mock code
    response = client.get("/auth/google/callback?code=test-auth-code")
    
    # Check that the response is successful
    assert response.status_code == status.HTTP_200_OK
    
    # Verify the exchange function was called correctly
    mock_exchange.assert_called_once_with("test-auth-code")
    
    # Check the response data
    data = response.json()
    assert data["email"] == mock_google_auth_data["user_info"]["email"]
    assert data["name"] == mock_google_auth_data["user_info"]["name"]
    assert data["avatar"] == mock_google_auth_data["user_info"]["picture"]
    assert data["auth_method"] == "google"
    assert "user_id" in data
    assert "session_id" in data
    
    # Verify that a session cookie was set
    assert "session_id" in response.cookies
    
    # Check that the user was created in the mock database
    assert any(user.email == "test@example.com" for user in auth_controller.users_db.values())


@patch("app.controllers.auth_controller.exchange_google_code")
def test_google_callback_returning_user(mock_exchange, mock_google_auth_data):
    """Test that a returning Google user doesn't create a duplicate record"""
    # First create a user with Google auth
    mock_exchange.return_value = (mock_google_auth_data["user_info"], mock_google_auth_data["access_token"])
    client.get("/auth/google/callback?code=test-auth-code")
    
    # Get the number of users and user ID of the just-created user
    user_count = len(auth_controller.users_db)
    user_id = next(u.id for u in auth_controller.users_db.values() if u.email == "test@example.com")
    
    # Now simulate the same user logging in again
    client.get("/auth/google/callback?code=test-auth-code-2")
    
    # Verify that no new user was created
    assert len(auth_controller.users_db) == user_count
    
    # Verify that the same user ID was returned
    assert any(u.id == user_id for u in auth_controller.users_db.values())