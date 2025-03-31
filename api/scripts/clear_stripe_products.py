import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import stripe

# Load environment variables
load_dotenv()

# Get Stripe API key from environment
stripe_key = os.getenv("STRIPE_SECRET_KEY")
if not stripe_key:
    print("ERROR: No Stripe API key found. Please set STRIPE_SECRET_KEY in your .env file.")
    sys.exit(1)

# Set Stripe API key
stripe.api_key = stripe_key

def is_stripe_test_key(key):
    """Check if the key is a Stripe test key (starts with sk_test_)"""
    return key.startswith("sk_test_")

# Safety check to ensure we're using a test key
if not is_stripe_test_key(stripe_key):
    print("ERROR: This script can only be used with Stripe test keys for safety.")
    print("Your API key does not appear to be a test key (doesn't start with sk_test_).")
    sys.exit(1)

def clear_all_stripe_products():
    print("Fetching all Stripe products...")
    products = stripe.Product.list(limit=100, active=True)
    
    if not products.data:
        print("No active products found in Stripe account.")
        return
    
    print(f"Found {len(products.data)} active products.")
    
    # Ask for confirmation
    confirmation = input(f"Are you sure you want to clean up all {len(products.data)} products? (yes/no): ")
    if confirmation.lower() != "yes":
        print("Operation cancelled.")
        return
    
    # Option to completely reset test data
    if is_stripe_test_key(stripe.api_key):
        reset_option = input("Do you want to ARCHIVE products instead of just deactivating them? (yes/no): ")
        should_archive = reset_option.lower() == "yes"
    else:
        should_archive = False
    
    # Process all products
    for product in products.data:
        try:
            if should_archive:
                print(f"Archiving product: {product.name} (ID: {product.id})")
                # Archive the product (this is more thorough than just deactivating)
                stripe.Product.modify(
                    product.id, 
                    active=False,
                    metadata={"archived": "true", "archived_at": str(datetime.now())}
                )
            else:
                print(f"Deactivating product: {product.name} (ID: {product.id})")
                # Just deactivate the product
                stripe.Product.modify(product.id, active=False)
        except Exception as e:
            print(f"Error processing product {product.id}: {str(e)}")
    
    print("\nAll products have been processed.")
    
    if should_archive:
        print("Products have been archived with metadata for easier cleanup.")
        
        # Fetch prices and deactivate them too
        try:
            prices = stripe.Price.list(limit=100, active=True)
            if prices.data:
                print(f"\nFound {len(prices.data)} active prices.")
                for price in prices.data:
                    print(f"Deactivating price: {price.id}")
                    stripe.Price.modify(price.id, active=False)
                print("All prices have been deactivated.")
        except Exception as e:
            print(f"Error deactivating prices: {str(e)}")
            
    else:
        print("Note: Products in Stripe are never fully deleted, only deactivated.")
        
    # For test accounts, suggest using the test clock reset if there are still issues
    if is_stripe_test_key(stripe.api_key):
        print("\nTIP: For test accounts, if you want to completely reset all data,")
        print("you can use the Stripe Dashboard and create a new test clock.")
        print("This will give you a completely fresh test environment.")

if __name__ == "__main__":
    print("WARNING: This script will deactivate ALL products in your Stripe test account.")
    print(f"Using Stripe API key: {stripe_key[:4]}...{stripe_key[-4:]}")
    
    clear_all_stripe_products()