import os
import sys
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_api_key():
    """Check if Stripe API key is available"""
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        print("WARNING: No Stripe API key found. Will only reset local products.")
        return False
    
    return True

def run_script(script_name):
    """Run a Python script and return its exit code"""
    print(f"\nRunning {script_name}...")
    print("-" * 50)
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            check=True
        )
        print("-" * 50)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e}")
        print("-" * 50)
        return False

def main():
    print("===== PRODUCT RESET UTILITY =====")
    print("This will reset ALL products in your database and Stripe account.")
    print("Make sure your API server is running before proceeding.")
    
    confirmation = input("Are you sure you want to proceed? (yes/no): ")
    if confirmation.lower() != "yes":
        print("Operation cancelled.")
        return
    
    has_stripe_key = check_api_key()
    
    success = True
    
    # First reset Stripe products (if key available)
    if has_stripe_key:
        success = run_script("scripts/clear_stripe_products.py") and success
    
    # Then reset local products
    success = run_script("scripts/reset_test_environment.py") and success
    
    if success:
        print("\n✅ Product reset completed successfully!")
        print("To initialize default products, run:")
        print("python scripts/initialize_products.py")
    else:
        print("\n❌ Product reset completed with errors.")
        print("Check the logs above for details.")

if __name__ == "__main__":
    main()