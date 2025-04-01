# API Test Client

This is a test client for the API that allows testing various authentication and payment flows. It uses a simplified login process but maintains real integration with Google Auth and Stripe APIs.

## Features

- Login with email/password
- Login with Google auth
- Update user profile
- Enable/disable two-factor authentication (2FA)
- Manage payment methods (add credit cards)
- Purchase tokens
- Subscribe to subscription plans
- View payment history and active subscriptions

## Requirements

- Python 3.7+
- FastAPI
- Uvicorn
- Jinja2
- httpx
- stripe

## Installation

1. Install dependencies:

```bash
pip install fastapi uvicorn jinja2 httpx stripe
```

2. Set environment variables:

```bash
export STRIPE_PUBLISHABLE_KEY="your_stripe_publishable_key"
```

## Usage

1. Make sure the main API server is running on port 8000 (default):

```bash
uvicorn app.main:app --reload
```

2. Run the test client in a separate terminal:

```bash
cd /path/to/api
python -m app.test_client
```

3. The client will be available at http://localhost:7999

Note: The test client simplifies the email/password login process (any email/password will work), but all other functionality makes real API calls to test Google Auth, 2FA, and Stripe integration.

## Testing Flows

### Authentication

1. Email/Password Login:
   - Visit http://localhost:7999/login
   - Enter credentials and submit

2. Google Authentication:
   - Visit http://localhost:7999/login
   - Click "Login with Google"
   - Complete Google authentication flow

### Profile Management

1. View Profile:
   - Log in first
   - Visit http://localhost:7999/profile

2. Update Profile:
   - On profile page, update your display name
   - Submit the form

### Two-Factor Authentication

1. Enable 2FA:
   - Visit http://localhost:7999/2fa
   - Click "Enable 2FA"
   - Scan QR code with your authenticator app
   - Enter verification code

2. Disable 2FA:
   - Visit http://localhost:7999/2fa
   - Click "Disable 2FA"

### Payments

1. Add Payment Method:
   - Visit http://localhost:7999/payments
   - Click "Add Payment Method"
   - Enter test card information (use Stripe test cards)
   - Submit the form

2. View Payment Methods:
   - Visit http://localhost:7999/payments

3. View Payment History:
   - Visit http://localhost:7999/payments

### Subscriptions and Tokens

1. View Available Plans:
   - Visit http://localhost:7999/products

2. Subscribe to a Plan:
   - Visit http://localhost:7999/products
   - Select a subscription plan
   - Complete payment with test card

3. Purchase Tokens:
   - Visit http://localhost:7999/products
   - Scroll to "Buy Tokens" section
   - Enter token amount
   - Complete payment with test card

## Stripe Test Cards

For testing payments, use Stripe test cards:

- **Test Card Success**: 4242 4242 4242 4242
- **Test Card Requires Authentication**: 4000 0025 0000 3155
- **Test Card Decline**: 4000 0000 0000 0002

Use any future expiration date, any 3-digit CVC, and any postal code.

## API Endpoints Required

The test client expects the following API endpoints to be implemented:

### Authentication
- `POST /auth/token` - Email/password login
- `GET /auth/google/login` - Initiate Google auth flow
- `POST /auth/google/callback` - Handle Google auth callback
- `GET /users/me` - Get current user details
- `PUT /users/me` - Update user profile

### Two-Factor Authentication
- `GET /auth/2fa/status` - Get current 2FA status
- `POST /auth/2fa/setup` - Setup 2FA (returns QR code)
- `POST /auth/2fa/verify` - Verify 2FA setup
- `POST /auth/2fa/disable` - Disable 2FA

### Payments
- `GET /payments/methods` - Get user's payment methods
- `POST /payments/methods` - Add a payment method
- `POST /payments/setup-intent` - Create a setup intent for adding cards
- `GET /payments/subscriptions` - Get user's active subscriptions
- `GET /payments/history` - Get user's payment history
- `GET /payments/products` - Get available products
- `GET /payments/subscription-tiers` - Get subscription tiers
- `POST /payments/checkout/tokens` - Create checkout session for tokens
- `POST /payments/checkout/subscription` - Create checkout session for subscription
- `GET /payments/verify` - Verify payment completion

## Implementation Details

This test client balances simplicity with real API integration:

1. **Authentication**:
   - Email/password login is simplified (any credentials work) to make testing easier
   - Google login uses the real Google OAuth flow via the API

2. **2FA**:
   - Uses real TOTP-based 2FA flow with QR codes
   - Integrates with the API's 2FA implementation
   - Fallback to mock data if API is unavailable

3. **Payments**:
   - Uses real Stripe integration for payment methods, tokens, and subscriptions
   - Redirects to actual Stripe Checkout for payment processing
   - Uses Stripe test cards for testing payments
   - Fallback to simulated payments if API is unavailable

## Notes

This is a simplified test client for demonstration purposes. In a production environment, you would need to implement:

- Proper session handling and security
- Error handling and user feedback
- Form validation
- Responsive design
- CSRF protection
- Integration with real payment providers

## Troubleshooting

### "Subscription tier not found" error

If you encounter a "Subscription tier not found" or "Subscription tier is not properly initialized in Stripe" error when trying to subscribe to a plan:

1. **Cause**: Subscription tiers are defined in the code but need to be initialized in Stripe before they can be used. This creates the necessary Stripe products and price IDs.

2. **Solution**: Run the product initialization script:
   ```bash
   python scripts/initialize_products.py
   ```
   
   This will:
   - Create all subscription tiers in Stripe
   - Generate and store the necessary Stripe price IDs
   - Make the subscription tiers available for purchase

3. **Verification**: After running the script, visit the products page to confirm that subscription tiers are properly displayed with "Subscribe" buttons.

### Other payment integration issues

If you encounter other payment-related issues:

1. **Check Stripe API keys**: Ensure your Stripe API keys are properly set in environment variables.
   ```bash
   export STRIPE_SECRET_KEY="your_stripe_secret_key"
   export STRIPE_PUBLISHABLE_KEY="your_stripe_publishable_key"
   ```

2. **Check Stripe webhook secret** (if using webhooks):
   ```bash
   export STRIPE_WEBHOOK_SECRET="your_stripe_webhook_secret"
   ```

3. **Reset test products** (if products are in a bad state):
   ```bash
   python scripts/reset_stripe_products.py
   ```

4. **Test mode**: If you're having trouble with Stripe integration, you can enable test mode by setting:
   ```bash
   export STRIPE_SECRET_KEY="sk_test_12345"
   ```
   This will use mock payments instead of real Stripe API calls.