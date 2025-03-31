import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.controllers import auth_controller
from app.utils import mfa

client = TestClient(app)


@pytest.fixture
def test_user_with_session():
    """Create a test user and return user_id and session_id"""
    # Register a user
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
@patch("app.utils.mfa.generate_mfa_qr_code")
def test_mfa_setup(mock_generate_qr, mock_generate_secret, test_user_with_session):
    """Test MFA setup flow"""
    user_id, session_id = test_user_with_session
    
    # Mock MFA secret and QR code
    mock_generate_secret.return_value = "TESTSECRET123456"
    mock_generate_qr.return_value = "data:image/png;base64,mockqrcode"
    
    # Request MFA setup
    response = client.post(
        "/auth/mfa/setup",
        cookies={"session_id": session_id}
    )
    
    assert response.status_code == 200
    mfa_data = response.json()
    
    # Verify the response contains the secret and QR code
    assert mfa_data["secret"] == "TESTSECRET123456"
    assert mfa_data["qr_code"] == "data:image/png;base64,mockqrcode"
    
    # Verify the user has the secret stored
    user = auth_controller.users_db.get(user_id)
    assert user.mfa_secret == "TESTSECRET123456"
    assert user.mfa_enabled is False  # Not enabled yet


@patch("app.utils.mfa.verify_mfa_token")
def test_mfa_verify_and_enable(mock_verify_token, test_user_with_session):
    """Test verifying and enabling MFA"""
    user_id, session_id = test_user_with_session
    
    # First set up MFA
    with patch("app.utils.mfa.generate_mfa_secret") as mock_generate_secret:
        with patch("app.utils.mfa.generate_mfa_qr_code") as mock_generate_qr:
            mock_generate_secret.return_value = "TESTSECRET123456"
            mock_generate_qr.return_value = "data:image/png;base64,mockqrcode"
            
            client.post(
                "/auth/mfa/setup",
                cookies={"session_id": session_id}
            )
    
    # Mock verification success
    mock_verify_token.return_value = True
    
    # Verify and enable MFA
    response = client.post(
        "/auth/mfa/verify",
        json={"code": "123456"},
        cookies={"session_id": session_id}
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "MFA enabled successfully"
    
    # Verify the user has MFA enabled
    user = auth_controller.users_db.get(user_id)
    assert user.mfa_enabled is True
    
    # Mock verification failure
    mock_verify_token.return_value = False
    
    # Try with invalid code
    response = client.post(
        "/auth/mfa/verify",
        json={"code": "999999"},
        cookies={"session_id": session_id}
    )
    
    assert response.status_code == 400  # Bad request
    assert "Invalid MFA code" in response.json()["detail"]


@patch("app.utils.mfa.verify_mfa_token")
def test_mfa_validation(mock_verify_token, test_user_with_session):
    """Test MFA validation for authenticating to protected resources"""
    user_id, session_id = test_user_with_session
    
    # Set up and enable MFA for the user
    user = auth_controller.users_db.get(user_id)
    user.mfa_secret = "TESTSECRET123456"
    user.mfa_enabled = True
    auth_controller.users_db[user_id] = user
    
    # Mock verification success
    mock_verify_token.return_value = True
    
    # Validate MFA code
    response = client.post(
        "/auth/mfa/validate",
        json={"code": "123456"},
        cookies={"session_id": session_id}
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "MFA code is valid"
    
    # Mock verification failure
    mock_verify_token.return_value = False
    
    # Validate with invalid code
    response = client.post(
        "/auth/mfa/validate",
        json={"code": "999999"},
        cookies={"session_id": session_id}
    )
    
    assert response.status_code == 400
    assert "Invalid MFA code" in response.json()["detail"]