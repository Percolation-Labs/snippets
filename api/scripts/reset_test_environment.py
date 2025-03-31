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

def get_all_products(session_id):
    """Get all products from the API"""
    response = requests.get(f"{API_URL}/payments/products")
    
    if response.status_code != 200:
        print(f"ERROR: Failed to get products. Status code: {response.status_code}")
        print(response.text)
        return []
    
    return response.json()

def delete_product(product_name, session_id):
    """Delete a product by name"""
    response = requests.delete(
        f"{API_URL}/payments/products/{product_name}",
        cookies={"session_id": session_id}
    )
    
    if response.status_code == 200:
        print(f"Deleted product: {product_name}")
        return True
    else:
        print(f"Failed to delete product: {product_name}")
        print(f"Status code: {response.status_code}")
        print(response.text)
        return False

def clear_all_local_products():
    """Clear all products in the local database"""
    # Login to get session ID
    session_id = login_test_user()
    if not session_id:
        print("Failed to authenticate. Cannot continue.")
        return
    
    # Get all products
    products = get_all_products(session_id)
    if not products:
        print("No products found.")
        return
    
    print(f"Found {len(products)} products:")
    for product in products:
        print(f"- {product['name']} (${product.get('price', 'N/A')})")
    
    # Ask for confirmation
    confirmation = input(f"Are you sure you want to delete all {len(products)} products? (yes/no): ")
    if confirmation.lower() != "yes":
        print("Operation cancelled.")
        return
    
    # Delete all products
    deleted_count = 0
    for product in products:
        if delete_product(product['name'], session_id):
            deleted_count += 1
    
    print(f"\nDeleted {deleted_count} out of {len(products)} products.")

if __name__ == "__main__":
    print("WARNING: This script will delete ALL products in your local database.")
    print(f"API URL: {API_URL}")
    
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
    
    clear_all_local_products()