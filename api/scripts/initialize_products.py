import os
import sys
import requests
from dotenv import load_dotenv
import json

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
    else:
        user_data = register_response.json()
    
    print(f"Logged in as: {user_data['email']}")
    print(f"User ID: {user_data['user_id']}")
    
    return user_data['session_id']

def get_all_products():
    """Get all products from the API"""
    response = requests.get(f"{API_URL}/payments/products")
    
    if response.status_code != 200:
        print(f"ERROR: Failed to get products. Status code: {response.status_code}")
        print(response.text)
        return []
    
    return response.json()

def initialize_products(session_id):
    """Initialize default products"""
    print("Initializing default products...")
    
    # First check if products already exist
    existing_products = get_all_products()
    print(f"Found {len(existing_products)} existing products.")
    
    # Check if user wants to proceed
    if existing_products:
        confirmation = input("Products already exist. Do you want to add more products? (yes/no): ")
        if confirmation.lower() != "yes":
            print("Initialization cancelled.")
            return False
    
    # Initialize products
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
    print(f"  Products created: {result.get('products_created', 0)}")
    print(f"  Products updated: {result.get('products_updated', 0)}")
    print(f"  Subscription products: {result['subscription_products']}")
    print(f"  Token product: {'Added' if result['token_product'] else 'Failed to add'}")
    
    # Get all products to display
    all_products = get_all_products()
    print("\nCurrent products:")
    for product in all_products:
        print(f"- {product['name']} (${product.get('price', 'N/A')})")
    
    return True

if __name__ == "__main__":
    print("===== PRODUCT INITIALIZATION UTILITY =====")
    print("This will initialize default products in your database and Stripe account.")
    print("Make sure your API server is running before proceeding.")
    
    # Check if API is running
    try:
        health_check = requests.get(f"{API_URL}/health")
        if health_check.status_code != 200:
            print(f"ERROR: API is not healthy. Status code: {health_check.status_code}")
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
    
    # Initialize products
    success = initialize_products(session_id)
    
    if success:
        print("\n✅ Product initialization completed successfully!")
    else:
        print("\n❌ Product initialization failed.")
        print("Check the logs above for details.")