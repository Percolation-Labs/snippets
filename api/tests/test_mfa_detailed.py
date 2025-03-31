import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import status
import json
import os
import re
import base64

from app.main import app
from app.controllers import auth_controller
from app.utils import mfa

client = TestClient(app)


@pytest.fixture
def authenticated_user():
    """Create an authenticated user for testing MFA flows"""
    # Register a new user
    response = client.post(
        "/auth/register",
        json={
            "email": "mfa_test@example.com",
            "name": "MFA Test User",
            "password": "password123"
        }
    )
    data = response.json()
    return data["user_id"], data["session_id"]


@patch("app.utils.mfa.generate_mfa_secret")
def test_mfa_setup(mock_generate_secret, authenticated_user):
    """Test the MFA setup endpoint generates a valid secret and QR code"""
    user_id, session_id = authenticated_user
    
    # Mock the MFA secret generation
    mock_secret = "THISISAFAKETESTSECRET"
    mock_generate_secret.return_value = mock_secret
    
    # Call the MFA setup endpoint
    response = client.post(
        "/auth/mfa/setup",
        cookies={"session_id": session_id}
    )
    
    # Check the response
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Verify the secret matches our mock
    assert data["secret"] == mock_secret
    
    # Verify QR code is returned and is base64 encoded
    assert "qr_code" in data
    qr_code = data["qr_code"]
    assert qr_code.startswith("data:image/png;base64,")
    
    # Try to decode the base64 data to verify it's valid
    try:
        # Extract the base64 part (after the comma)
        base64_data = qr_code.split(",")[1]
        decoded = base64.b64decode(base64_data)
        assert len(decoded) > 0  # Should decode to something
    except Exception as e:
        pytest.fail(f"QR code is not valid base64: {str(e)}")
    
    # Verify the user now has a secret stored
    user = auth_controller.users_db[user_id]
    assert user.mfa_secret == mock_secret
    assert user.mfa_enabled is False  # Not enabled yet


@patch("app.utils.mfa.verify_mfa_token")
def test_mfa_verify_and_enable(mock_verify, authenticated_user):
    """Test that MFA verification and enabling works correctly"""
    user_id, session_id = authenticated_user
    
    # First set up MFA for the user
    with patch("app.utils.mfa.generate_mfa_secret") as mock_secret:
        mock_secret.return_value = "TESTSECRET123456"
        client.post("/auth/mfa/setup", cookies={"session_id": session_id})
    
    # Verify the user has MFA secret but not enabled
    user = auth_controller.users_db[user_id]
    assert user.mfa_secret == "TESTSECRET123456"
    assert user.mfa_enabled is False
    
    # Mock the MFA verification to succeed
    mock_verify.return_value = True
    
    # Verify MFA with mock code
    response = client.post(
        "/auth/mfa/verify",
        json={"code": "123456"},
        cookies={"session_id": session_id}
    )
    
    # Check that verification succeeded
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "MFA enabled successfully"
    
    # Verify the user now has MFA enabled
    user = auth_controller.users_db[user_id]
    assert user.mfa_enabled is True
    
    # Test failed verification
    mock_verify.return_value = False
    
    response = client.post(
        "/auth/mfa/verify",
        json={"code": "wrong-code"},
        cookies={"session_id": session_id}
    )
    
    # Should return error
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid MFA code" in response.json()["detail"]


@patch("app.utils.mfa.verify_mfa_token")
def test_mfa_validation_for_session(mock_verify, authenticated_user):
    """Test that MFA validation works for a session"""
    user_id, session_id = authenticated_user
    
    # Set up the user with MFA already enabled
    user = auth_controller.users_db[user_id]
    user.mfa_secret = "TESTSECRET123456"
    user.mfa_enabled = True
    auth_controller.users_db[user_id] = user
    
    # Test successful validation
    mock_verify.return_value = True
    
    response = client.post(
        "/auth/mfa/validate",
        json={"code": "123456"},
        cookies={"session_id": session_id}
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "MFA code is valid"
    
    # Test failed validation
    mock_verify.return_value = False
    
    response = client.post(
        "/auth/mfa/validate",
        json={"code": "wrong-code"},
        cookies={"session_id": session_id}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid MFA code" in response.json()["detail"]