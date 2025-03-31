#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_requirements():
    """Check if Stripe CLI is installed"""
    try:
        result = subprocess.run(
            ["stripe", "--version"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            print(f"Stripe CLI detected: {result.stdout.strip()}")
            return True
        else:
            print("Stripe CLI is not properly installed or configured.")
            return False
    except FileNotFoundError:
        print("Stripe CLI is not installed. Please install it first:")
        print("https://stripe.com/docs/stripe-cli")
        return False

def check_stripe_auth():
    """Check if Stripe CLI is authenticated"""
    try:
        result = subprocess.run(
            ["stripe", "config", "--list"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if "No user credentials found" in result.stderr:
            print("Stripe CLI is not logged in. Please run 'stripe login' first.")
            return False
            
        if result.returncode == 0:
            print("Stripe CLI is authenticated.")
            return True
        else:
            print("Stripe CLI authentication check failed.")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"Error checking Stripe CLI authentication: {str(e)}")
        return False
        
def create_test_clock():
    """Create a new test clock in Stripe"""
    # Set clock to current time
    now = datetime.now()
    timestamp = int(now.timestamp())
    
    print(f"Creating new test clock at current time ({now.strftime('%Y-%m-%d %H:%M:%S')})...")
    
    try:
        result = subprocess.run(
            ["stripe", "test", "clocks", "create", f"--frozen-time={timestamp}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the output to get the clock ID
        output_lines = result.stdout.strip().split("\n")
        clock_id = None
        
        for line in output_lines:
            if line.startswith("ID:"):
                clock_id = line.split("ID:")[1].strip()
                break
        
        if clock_id:
            print(f"Created new test clock with ID: {clock_id}")
            return clock_id
        else:
            print("Failed to extract test clock ID from output:")
            print(result.stdout)
            return None
    except subprocess.CalledProcessError as e:
        print(f"Error creating test clock: {e}")
        print(e.stderr)
        return None

def simulate_time_passing(clock_id, days=0, hours=0, minutes=0):
    """Advance the test clock by a specified duration"""
    if not clock_id:
        return False
        
    total_minutes = days * 24 * 60 + hours * 60 + minutes
    if total_minutes <= 0:
        return True
        
    print(f"Advancing test clock by {days} days, {hours} hours, and {minutes} minutes...")
    
    try:
        result = subprocess.run(
            ["stripe", "test", "clocks", "advance", clock_id, f"--minutes={total_minutes}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"Advanced test clock successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error advancing test clock: {e}")
        print(e.stderr)
        return False

def main():
    print("===== STRIPE TEST ACCOUNT RESET UTILITY =====")
    print("This utility creates a new test clock in your Stripe test account.")
    print("This effectively gives you a fresh test environment.")
    
    # Check requirements
    if not check_requirements() or not check_stripe_auth():
        print("\nPlease install and configure Stripe CLI first.")
        print("See: https://stripe.com/docs/stripe-cli")
        sys.exit(1)
    
    # Ask for confirmation
    confirmation = input("\nAre you sure you want to create a new test clock? This will give you a fresh test environment. (yes/no): ")
    if confirmation.lower() != "yes":
        print("Operation cancelled.")
        return
    
    # Create new test clock
    clock_id = create_test_clock()
    if not clock_id:
        print("Failed to create test clock. Exiting.")
        sys.exit(1)
    
    # Ask if user wants to advance time
    advance_time = input("\nDo you want to advance the test clock to simulate time passing? (yes/no): ")
    if advance_time.lower() == "yes":
        try:
            days = int(input("Days to advance (0-30): "))
            hours = int(input("Hours to advance (0-23): "))
            minutes = int(input("Minutes to advance (0-59): "))
            
            simulate_time_passing(clock_id, days, hours, minutes)
        except ValueError:
            print("Invalid input. Using default time (now).")
    
    print("\n✅ Stripe test environment has been reset with a new test clock.")
    print(f"Test Clock ID: {clock_id}")
    print("\nNotes:")
    print("1. You may need to run your product initialization script again")
    print("2. All operations in Stripe will now use this test clock")
    print("3. For subsequent tests, you can advance this clock as needed:")
    print(f"   stripe test clocks advance {clock_id} --minutes=1440  # advance by 1 day")

if __name__ == "__main__":
    main()