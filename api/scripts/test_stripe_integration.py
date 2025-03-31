import os
import json
from dotenv import load_dotenv
import stripe
from pprint import pprint

# Load environment variables
load_dotenv()

# Setup Stripe with the test API key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def test_stripe_connection():
    """Test basic Stripe connection"""
    try:
        print("Testing Stripe connection...")
        account = stripe.Account.retrieve()
        print(f"✓ Connected to Stripe account: {account.id}")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Stripe: {str(e)}")
        return False

def list_stripe_products():
    """List all products in the Stripe account"""
    try:
        print("\nListing Stripe products...")
        products = stripe.Product.list(limit=100, active=True)
        
        if not products.data:
            print("No products found in Stripe account")
        else:
            print(f"Found {len(products.data)} products:")
            for i, product in enumerate(products.data, 1):
                print(f"{i}. {product.name} (ID: {product.id})")
                if hasattr(product, 'description') and product.description:
                    print(f"   Description: {product.description}")
                
                # Get prices for this product
                prices = stripe.Price.list(product=product.id, active=True)
                if prices.data:
                    for price in prices.data:
                        amount = price.unit_amount / 100  # Convert from cents
                        if price.type == 'recurring':
                            recurring = price.recurring
                            interval = recurring.get('interval', 'unknown')
                            print(f"   Price: ${amount:.2f}/{interval} (ID: {price.id})")
                        else:
                            print(f"   Price: ${amount:.2f} (ID: {price.id})")
        
        return products.data
    except Exception as e:
        print(f"❌ Failed to list products: {str(e)}")
        return []

def create_test_product():
    """Create a test product in Stripe"""
    try:
        print("\nCreating test product...")
        product = stripe.Product.create(
            name="Test Product",
            description="A test product created from our API",
            active=True
        )
        
        price = stripe.Price.create(
            product=product.id,
            unit_amount=1000,  # $10.00
            currency="usd"
        )
        
        print(f"✓ Created product: {product.name} (ID: {product.id})")
        print(f"✓ Created price: ${price.unit_amount/100:.2f} (ID: {price.id})")
        
        return product, price
    except Exception as e:
        print(f"❌ Failed to create product: {str(e)}")
        return None, None

def create_test_customer():
    """Create a test customer in Stripe"""
    try:
        print("\nCreating test customer...")
        customer = stripe.Customer.create(
            email="test@example.com",
            name="Test Customer",
            description="Test customer for API testing"
        )
        
        print(f"✓ Created customer: {customer.name} (ID: {customer.id})")
        return customer
    except Exception as e:
        print(f"❌ Failed to create customer: {str(e)}")
        return None

def create_test_subscription(customer_id, price_id):
    """Create a test subscription for a customer"""
    try:
        print("\nCreating test subscription...")
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[
                {"price": price_id},
            ],
        )
        
        print(f"✓ Created subscription (ID: {subscription.id})")
        print(f"  Status: {subscription.status}")
        print(f"  Current period: {subscription.current_period_start} to {subscription.current_period_end}")
        
        return subscription
    except Exception as e:
        print(f"❌ Failed to create subscription: {str(e)}")
        return None

if __name__ == "__main__":
    # Test connection
    if not test_stripe_connection():
        print("Exiting due to connection failure.")
        exit(1)
    
    # List existing products
    existing_products = list_stripe_products()
    
    # Create a test product
    test_product, test_price = create_test_product()
    
    if test_product and test_price:
        # Create a test customer
        test_customer = create_test_customer()
        
        if test_customer:
            # Create a test subscription
            test_subscription = create_test_subscription(test_customer.id, test_price.id)
            
            if test_subscription:
                print("\n✓ Successfully tested all Stripe integration functions!")
            else:
                print("\n❌ Subscription creation failed.")
        else:
            print("\n❌ Customer creation failed.")
    else:
        print("\n❌ Product creation failed.")