#!/usr/bin/env python3
"""
Script to verify product initialization and check subscription settings
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set default API URL
API_URL = "http://localhost:8000"

def login_test_user():
    """Create a test user and log in to get a session ID"""
    print("Creating test user for admin operations...")
    
    # First try to register a new user
    register_response = requests.post(
        f"{API_URL}/auth/register",
        json={
            "email": "admin@example.com",
            "name": "Admin User",
            "password": "adminpassword123"
        }
    )
    
    # If registration fails (e.g., user already exists), try to login
    if register_response.status_code != 200:
        print("User already exists, logging in...")
        login_response = requests.post(
            f"{API_URL}/auth/login",
            json={
                "email": "admin@example.com",
                "password": "adminpassword123"
            }
        )
        
        if login_response.status_code != 200:
            print(f"ERROR: Failed to login. Status code: {login_response.status_code}")
            print(login_response.text)
            return None
            
        user_data = login_response.json()
        session_id = login_response.cookies.get('session_id')
    else:
        user_data = register_response.json()
        session_id = register_response.cookies.get('session_id')
    
    if not session_id and 'session_id' in user_data:
        session_id = user_data['session_id']
    
    print(f"Logged in as: {user_data['email']}")
    print(f"User ID: {user_data.get('user_id', user_data.get('id'))}")
    
    return session_id

def initialize_products(session_id):
    """Initialize products and verify they're set up correctly"""
    if not session_id:
        print("No session ID provided. Cannot initialize products.")
        return False
    
    print("\nInitializing products...")
    
    # Call the API to initialize products
    response = requests.post(
        f"{API_URL}/payments/initialize-products",
        cookies={"session_id": session_id}
    )
    
    if response.status_code != 200:
        print(f"ERROR: Failed to initialize products. Status code: {response.status_code}")
        print(response.text)
        return False
    
    result = response.json()
    print(f"✓ Successfully initialized products!")
    print(f"Products added: {result.get('products_added', 'unknown')}")
    print(f"Subscription products: {result.get('subscription_products', 'unknown')}")
    print(f"Token product: {'Added' if result.get('token_product', False) else 'Not added'}")
    
    # Print token product details
    token_details = result.get('token_product_details', {})
    if token_details and token_details.get('name'):
        print(f"\nToken Product:")
        print(f"  Name: {token_details.get('name')}")
        print(f"  Price: ${token_details.get('price')}")
        print(f"  Price ID: {token_details.get('price_id')}")
    
    # Print subscription tier details
    subscription_tiers = result.get('subscription_tiers', [])
    if subscription_tiers:
        print(f"\nSubscription Tiers:")
        for tier in subscription_tiers:
            print(f"  {tier.get('name')}: ${tier.get('price')} ({tier.get('recurring')})")
            print(f"    Price ID: {tier.get('price_id')}")
    
    return True

def get_all_products():
    """Get all products from the API"""
    print("\nGetting all products...")
    
    response = requests.get(f"{API_URL}/payments/products")
    
    if response.status_code != 200:
        print(f"ERROR: Failed to get products. Status code: {response.status_code}")
        print(response.text)
        return None
    
    products = response.json()
    print(f"Found {len(products)} products:")
    
    for product in products:
        price_info = f"${product.get('price', 'N/A')}"
        metadata = product.get('metadata', {})
        if metadata.get('type') == 'subscription':
            price_info += " (monthly recurring)"
        
        print(f"- {product.get('name')} ({price_info})")
        print(f"  ID: {product.get('id')}")
        print(f"  Price ID: {product.get('price_id')}")
        print(f"  Active: {product.get('active', False)}")
        if metadata:
            print(f"  Metadata: {json.dumps(metadata, indent=2)}")
        print()
    
    return products

def get_subscription_tiers(session_id):
    """Get all subscription tiers"""
    print("\nGetting subscription tiers...")
    
    response = requests.get(
        f"{API_URL}/payments/subscription-tiers",
        cookies={"session_id": session_id}
    )
    
    if response.status_code != 200:
        print(f"ERROR: Failed to get subscription tiers. Status code: {response.status_code}")
        print(response.text)
        return None
    
    tiers = response.json()
    print(f"Found {len(tiers)} subscription tiers:")
    
    for tier in tiers:
        print(f"- {tier.get('name')}: ${tier.get('price')}")
        print(f"  Credits: {tier.get('credits')}")
        print(f"  Stripe Price ID: {tier.get('stripe_price_id', 'Not set')}")
        print(f"  Features: {', '.join(tier.get('features', []))}")
        print()
    
    return tiers

if __name__ == "__main__":
    print("===== PRODUCT VERIFICATION UTILITY =====")
    print("This will check if products are initialized correctly with proper recurring billing.")
    print("Make sure your API server is running before proceeding.")
    
    # Check if API is running
    try:
        response = requests.get(f"{API_URL}/docs")
        if response.status_code != 200:
            print(f"ERROR: API does not seem to be running at {API_URL}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to API at {API_URL}")
        print("Please make sure the server is running.")
        sys.exit(1)
    
    # Login to get session ID
    session_id = login_test_user()
    if not session_id:
        print("Failed to authenticate. Cannot continue.")
        sys.exit(1)
    
    # Initialize and verify products
    success = initialize_products(session_id)
    
    if success:
        # Get all products to verify
        products = get_all_products()
        
        # Get subscription tiers to verify
        tiers = get_subscription_tiers(session_id)
        
        print("\n✅ Product verification completed!")
        
        if not products or not any(p.get('name') == 'Tokens' for p in products):
            print("⚠️ Warning: Token product may not be properly set up.")
        
        if not tiers or not any(t.get('stripe_price_id') for t in tiers if t.get('price', 0) > 0):
            print("⚠️ Warning: Subscription tiers may not have proper Stripe price IDs.")
    else:
        print("\n❌ Product verification failed.")
        print("Check the logs above for details.")