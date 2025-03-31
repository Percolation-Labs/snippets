#!/usr/bin/env python3
import os
import sys
import json
import argparse
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set default API URL
API_URL = "http://localhost:8000"

def generate_webhook_payload(event_type="checkout.session.completed", mode="payment", user_id=None, tokens=None, tier=None):
    """Generate a webhook payload for testing"""
    if event_type == "checkout.session.completed":
        metadata = {}
        if user_id:
            metadata["user_id"] = user_id
        if tokens and mode == "payment":
            metadata["tokens"] = str(tokens)
        if tier and mode == "subscription":
            metadata["tier"] = tier
            
        payload = {
            "type": event_type,
            "data": {
                "object": {
                    "id": "cs_test_" + os.urandom(8).hex(),
                    "mode": mode,
                    "amount_total": 1000, # $10.00
                    "currency": "usd",
                    "metadata": metadata
                }
            }
        }
        
        # Add subscription ID if it's a subscription
        if mode == "subscription":
            payload["data"]["object"]["subscription"] = "sub_test_" + os.urandom(8).hex()
            
        return payload
    else:
        # For other event types, return a simple payload
        return {
            "type": event_type,
            "data": {
                "object": {
                    "id": "evt_test_" + os.urandom(8).hex()
                }
            }
        }

def send_webhook(payload):
    """Send a webhook to the API"""
    url = f"{API_URL}/payments/webhook"
    
    print(f"Sending webhook to {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json"
            }
        )
        
        print(f"\nResponse status code: {response.status_code}")
        try:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except:
            print(f"Response: {response.text}")
            
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending webhook: {str(e)}")
        return False

def get_user_id():
    """Create a test user and get their ID"""
    print("Creating test user for webhook test...")
    
    # First try to register a new user
    register_response = requests.post(
        f"{API_URL}/auth/register",
        json={
            "email": "webhook_test@example.com",
            "name": "Webhook Test User",
            "password": "webhook123"
        }
    )
    
    # If registration fails (e.g., user already exists), try to login
    if register_response.status_code != 200:
        print("User already exists, logging in...")
        login_response = requests.post(
            f"{API_URL}/auth/login",
            json={
                "email": "webhook_test@example.com",
                "password": "webhook123"
            }
        )
        
        if login_response.status_code != 200:
            print(f"ERROR: Failed to login. Status code: {login_response.status_code}")
            print(login_response.text)
            return None
            
        user_data = login_response.json()
    else:
        user_data = register_response.json()
    
    print(f"Using test user: {user_data['email']}")
    print(f"User ID: {user_data['user_id']}")
    
    return user_data['user_id']

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Send a test webhook to the API.')
    parser.add_argument('--type', choices=['payment', 'subscription'], default='payment',
                      help='Type of webhook to send (payment or subscription)')
    parser.add_argument('--tokens', type=int, default=100,
                      help='Number of tokens to add (for payment webhooks)')
    parser.add_argument('--tier', choices=['Individual', 'Team', 'Enterprise'], default='Individual',
                      help='Subscription tier (for subscription webhooks)')
    parser.add_argument('--user-id', type=str,
                      help='User ID to use (if not provided, will create a test user)')
    
    args = parser.parse_args()
    
    print("===== WEBHOOK TEST UTILITY =====")
    print(f"Testing {'subscription' if args.type == 'subscription' else 'payment'} webhook")
    
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
    
    # Get user ID
    user_id = args.user_id or get_user_id()
    if not user_id:
        print("Failed to get a user ID. Cannot continue.")
        sys.exit(1)
    
    # Generate and send webhook payload
    if args.type == 'payment':
        print(f"\nSending payment webhook for {args.tokens} tokens...")
        payload = generate_webhook_payload(
            mode="payment",
            user_id=user_id,
            tokens=args.tokens
        )
    else:
        print(f"\nSending subscription webhook for {args.tier} tier...")
        payload = generate_webhook_payload(
            mode="subscription",
            user_id=user_id,
            tier=args.tier
        )
    
    success = send_webhook(payload)
    
    if success:
        print("\n✅ Webhook sent and processed successfully!")
        if args.type == 'payment':
            print(f"User should now have {args.tokens} more tokens.")
        else:
            print(f"User should now be subscribed to the {args.tier} tier.")
        
        # Verify the changes
        print("\nYou can verify the changes by:")
        print(f"1. Logging in with email: webhook_test@example.com, password: webhook123")
        print(f"2. Checking your profile at: http://localhost:8000/auth/me")
    else:
        print("\n❌ Webhook processing failed.")
        print("Check the server logs for more details.")

if __name__ == "__main__":
    main()