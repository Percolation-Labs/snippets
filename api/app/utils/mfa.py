import os
import io
import base64
from typing import Tuple

try:
    import pyotp
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    # For testing purposes, provide mock implementations
    QRCODE_AVAILABLE = False
    
    # Mock pyotp
    class MockPyOTP:
        class totp:
            class TOTP:
                def __init__(self, secret):
                    self.secret = secret
                    
                def provisioning_uri(self, email, issuer_name=None):
                    return f"otpauth://totp/{issuer_name}:{email}?secret={self.secret}&issuer={issuer_name}"
                    
                def verify(self, token):
                    return token == "123456"  # Test token
                    
        def random_base32(self):
            return "TESTSECRET123456"
            
    pyotp = MockPyOTP()

# App name from environment
API_APP_NAME = os.getenv("API_APP_NAME", "API")


def generate_mfa_secret() -> str:
    """Generate a new MFA secret"""
    return pyotp.random_base32()


def generate_mfa_qr_code(email: str, secret: str) -> str:
    """Generate a QR code for MFA setup"""
    # Create TOTP object
    totp = pyotp.totp.TOTP(secret)
    uri = totp.provisioning_uri(email, issuer_name=API_APP_NAME)
    
    if not QRCODE_AVAILABLE:
        # For testing, return a mock QR code
        return "data:image/png;base64,mockQRcodeBase64Data"
    
    # Create QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffered = io.BytesIO()
    img.save(buffered)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"


def verify_mfa_token(secret: str, token: str) -> bool:
    """Verify a MFA token"""
    totp = pyotp.TOTP(secret)
    return totp.verify(token)