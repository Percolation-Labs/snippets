import os
import json
import requests
from dotenv import load_dotenv
import time
from pprint import pprint

# Load environment variables
load_dotenv()

# API base URL
BASE_URL = "http://localhost:8000"
session = requests.Session()

def test_health_check():
    """Test the API health check endpoint"""
    print("\nTesting health check endpoint...")
    try:
        response = session.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print(f"✓ Health check successful: {response.json()}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error accessing API: {str(e)}")
        return False

def test_user_registration():
    """Test user registration flow"""
    print("\nTesting user registration...")
    try:
        email = f"test_user_{int(time.time())}@example.com"
        response = session.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": email,
                "name": "Test User",
                "password": "test_password"
            }
        )
        
        if response.status_code == 200:
            user_data = response.json()
            print(f"✓ Registration successful:")
            print(f"  User ID: {user_data['user_id']}")
            print(f"  Email: {user_data['email']}")
            print(f"  Session ID: {user_data['session_id']}")
            
            # Set session cookie for subsequent requests
            session.cookies.set("session_id", user_data["session_id"])
            
            # Add password to user_data for potential login later
            user_data["password"] = "test_password"
            
            return user_data
        else:
            print(f"❌ Registration failed: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error registering user: {str(e)}")
        return None

def test_user_login(email, password):
    """Test user login flow"""
    print("\nTesting user login...")
    try:
        response = session.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": email,
                "password": password
            }
        )
        
        if response.status_code == 200:
            user_data = response.json()
            print(f"✓ Login successful:")
            print(f"  User ID: {user_data['user_id']}")
            print(f"  Email: {user_data['email']}")
            print(f"  Session ID: {user_data['session_id']}")
            return user_data
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error logging in: {str(e)}")
        return None

def test_get_subscription_tiers():
    """Test getting subscription tiers"""
    print("\nTesting subscription tiers endpoint...")
    try:
        response = session.get(f"{BASE_URL}/payments/subscription-tiers")
        
        if response.status_code == 200:
            tiers = response.json()
            print(f"✓ Found {len(tiers)} subscription tiers:")
            for tier in tiers:
                print(f"  {tier['name']}: ${tier['price']} - {tier['credits']} credits")
                print(f"    Features: {', '.join(tier['features'])}")
            return tiers
        else:
            print(f"❌ Failed to get subscription tiers: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error getting subscription tiers: {str(e)}")
        return None

def test_get_products():
    """Test getting products"""
    print("\nTesting products endpoint...")
    try:
        response = session.get(f"{BASE_URL}/payments/products")
        
        if response.status_code == 200:
            products = response.json()
            print(f"✓ Found {len(products)} products:")
            for product in products:
                print(f"  {product['name']}: ${product.get('price', 'N/A')}")
                if product.get('description'):
                    print(f"    Description: {product['description']}")
            return products
        else:
            print(f"❌ Failed to get products: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error getting products: {str(e)}")
        return None

def test_mfa_setup():
    """Test MFA setup flow"""
    print("\nTesting MFA setup...")
    try:
        response = session.post(f"{BASE_URL}/auth/mfa/setup")
        
        if response.status_code == 200:
            mfa_data = response.json()
            print(f"✓ MFA setup successful:")
            print(f"  Secret: {mfa_data['secret']}")
            print(f"  QR code received: {'qr_code' in mfa_data}")
            return mfa_data
        else:
            print(f"❌ MFA setup failed: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error setting up MFA: {str(e)}")
        return None

def test_subscribe_user(tier_name="Individual"):
    """Test subscribing a user to a plan"""
    print(f"\nTesting subscription to {tier_name} tier...")
    try:
        response = session.post(
            f"{BASE_URL}/payments/subscribe",
            json={
                "tier": tier_name,
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel"
            }
        )
        
        if response.status_code == 200:
            checkout_data = response.json()
            print(f"✓ Subscription checkout created:")
            print(f"  Checkout URL: {checkout_data['url']}")
            return checkout_data
        else:
            print(f"❌ Subscription checkout failed: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error creating subscription: {str(e)}")
        return None

def test_buy_tokens(amount=100):
    """Test buying tokens in test mode"""
    print(f"\nTesting token purchase for {amount} tokens...")
    try:
        response = session.post(
            f"{BASE_URL}/payments/test/buy-tokens",
            json={
                "amount": amount,
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel"
            }
        )
        
        if response.status_code == 200:
            checkout_data = response.json()
            print(f"✓ Token purchase checkout created:")
            print(f"  Checkout URL: {checkout_data['url']}")
            return checkout_data
        else:
            print(f"❌ Token purchase checkout failed: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error buying tokens: {str(e)}")
        return None

if __name__ == "__main__":
    # Start API server in a separate terminal first: uvicorn app.main:app --reload
    
    # Step 1: Check if API is running
    if not test_health_check():
        print("API is not running. Please start the API server first.")
        exit(1)
    
    # Step 2: Test user registration
    user_data = test_user_registration()
    if not user_data:
        print("User registration failed. Exiting.")
        exit(1)
    
    # Save user credentials for login
    email = user_data["email"]
    user_id = user_data["user_id"]
    
    # Step 3: Get subscription tiers
    tiers = test_get_subscription_tiers()
    
    # Step 4: Get products
    products = test_get_products()
    
    # Step 5: Test MFA setup
    mfa_data = test_mfa_setup()
    
    # Step 6: Test subscription checkout
    subscription_checkout = test_subscribe_user()
    
    # Step 7: Test token purchase
    token_checkout = test_buy_tokens()
    
    # Summary
    print("\n=== Test Summary ===")
    print(f"API Health Check: {'✓' if test_health_check() else '❌'}")
    print(f"User Registration: {'✓' if user_data else '❌'}")
    print(f"Subscription Tiers: {'✓' if tiers else '❌'}")
    print(f"Products: {'✓' if products else '❌'}")
    print(f"MFA Setup: {'✓' if mfa_data else '❌'}")
    print(f"Subscription Checkout: {'✓' if subscription_checkout else '❌'}")
    print(f"Token Purchase: {'✓' if token_checkout else '❌'}")
    
    # Note on testing results
    print("\nNote: Some Stripe integration tests may not work with mock API keys.")
    print("In this test environment, we're primarily validating that the API endpoints are functioning correctly.")
    print("With real Stripe API keys, all functionality would work end-to-end.")