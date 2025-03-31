# About

This snippet is an API starter for FastAPI with auth and stripe payment support. It provides a generic starting point for any API backend. You can vibe over it.

## Fast API
- We use the `uv` package manager
- We use uvicorn to launch the app with reload: `uvicorn app.main:app --reload`
- We use routers to separate functionality for auth, payment etc.
- We use Pydantic objects for models
- We use models and controller folders -> pydantic objects are in models and controllers wrap business logic to keep api routes thin and just handling errors etc.
- Controllers for now may not be implemented and have comments to add repositories to save data and read data from a database.

## Installation and Setup

1. **Dependencies Installation:**
   ```
   pip install -r requirements.txt
   ```
   
   Make sure `bcrypt` is properly installed for password hashing. If you encounter errors like:
   ```
   bcrypt: no backends available
   ```
   Try installing it separately:
   ```
   pip install bcrypt --no-binary bcrypt
   ```
   
2. **Environment Setup:**
   Create a `.env` file with the following variables:
   ```
   API_APP_NAME=YourAppName
   JWT_SECRET_KEY=your_jwt_secret_key
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
   STRIPE_SECRET_KEY=your_stripe_secret_key
   STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key
   ```

3. **Start the Server:**
   ```
   uvicorn app.main:app --reload
   ```

4. **Access the API:**
   - API base URL: http://localhost:8000
   - API documentation: http://localhost:8000/docs

## Test scripts
- We add test scripts to test all endpoints and flows: `pytest`
- Run a specific test: `pytest tests/test_file.py::test_function -v`
- Trigger auth login and launch browsers for user for each provider

## Utility Scripts

The `scripts/` directory contains various utility scripts:

1. **API Flow Testing**:
   ```
   python scripts/test_api_flows.py
   ```
   Tests the complete API flow including registration, MFA setup, subscriptions, and token purchase.

2. **Stripe Integration Testing**:
   ```
   python scripts/test_stripe_integration.py
   ```
   Tests Stripe API connection and product management.

3. **Product Management**:
   ```
   python scripts/initialize_products.py
   ```
   Initializes default products (subscription tiers and tokens) in the database.

   ```
   python scripts/reset_all_products.py
   ```
   Resets all products both in Stripe and in the local database.

   Individual reset scripts:
   - `scripts/clear_stripe_products.py` - Deactivates/archives products in Stripe
   - `scripts/reset_test_environment.py` - Clears products in the local database
   - `scripts/reset_stripe_test_account.py` - Creates a new test clock for a completely fresh Stripe test environment
   
   **Note**: Products are no longer automatically initialized on server startup.
   You must explicitly run the initialization script or use the API endpoint.
   
   **Cleaning Stripe Test Account**:
   For a thorough cleanup of your Stripe test account, you have two options:
   
   1. Archive products (using `clear_stripe_products.py`)
   2. Create a new test clock (using `reset_stripe_test_account.py`) which gives you a completely fresh environment
   
   Option 2 requires the Stripe CLI to be installed (`brew install stripe/stripe-cli/stripe`).

## Auth

- Three OAuth providers are added without any third-party libraries. Google, Microsoft and Github. Email and password is also supported.
- The auth route contains `/auth/{provider}/login` and `/auth/{provider}/callback/`
- We store all provider details in environment variables e.g., google or github client id and secret
- We add any necessary scopes for each provider to get user profile information
- For sensitive endpoints we also add two factor authentication. The auth route also allows for codes to be generated and it also provides a QR code that can be scanned with an authenticator app. The app name is in an env variable `API_APP_NAME`
- Normally endpoints can use a session id but if the dependency is added for 2FA, then the caller must supply this in API requests.
- At login we return a generic UserProfile object with session_id, user_id, email, name, avatar, auth-method and session expiry. The client should store this in a cookie for subsequent requests.

## Payments
- There is a payments module that manages Stripe payments and products
- We can list products on the provider
- We can add products
- We can add payments
- We have scripts to add and use basic subscriptions - there are four assumed plans: Free, Individual, Team and Enterprise. 
- We can buy credits from the general 'tokens' product
- Stripe keys are stored in environment variables: `STRIPE_PUBLISHABLE_KEY` and `STRIPE_SECRET_KEY`

### Testing Stripe Integration

#### Required Scaffolding

To test Stripe payments, the following components are needed:

1. **Stripe Account:**
   - Create a free Stripe account at https://stripe.com
   - Access your API keys from the dashboard

2. **Environment Configuration:**
   - `.env` file with your Stripe API keys
   - Set up webhook endpoints in Stripe dashboard

3. **Payment Components:**
   - Products and prices defined in Stripe (created automatically by our app)
   - Checkout sessions for processing payments
   - Webhook handler for completed payments
   - User credits/subscription tracking

4. **Code Structure:**
   - `payment_controller.py`: Contains Stripe API interactions
   - `payments.py` router: Exposes payment endpoints
   - `payment.py` models: Defines data structures
   - Test endpoints for non-Stripe testing

The implementation handles all of this for you, but understanding the structure helps when extending functionality.

#### Setting Up for Testing

1. **Stripe API Keys**:
   - For development/testing, set `STRIPE_SECRET_KEY` to a Stripe test key (`sk_test_...`)
   - Test keys allow you to simulate payments without real charges
   - Get test keys from the Stripe dashboard (https://dashboard.stripe.com/test/apikeys)

2. **Test Environment Variables**:
   ```
   STRIPE_SECRET_KEY=sk_test_your_test_key
   STRIPE_PUBLISHABLE_KEY=pk_test_your_test_key
   STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
   ```

3. **Webhook Testing**:
   - For local development, use Stripe CLI to forward webhook events
   - Install Stripe CLI (https://stripe.com/docs/stripe-cli)
   - Run: `stripe listen --forward-to http://localhost:8000/payments/webhook`
   - This provides a webhook secret to set in your environment variables

#### Testing Token Purchases

Two options for testing token purchases:

1. **Using Test Mode Endpoint** (simplified testing without Stripe):
   ```
   POST /payments/test/buy-tokens
   {
     "amount": 100,
     "success_url": "https://example.com/success",
     "cancel_url": "https://example.com/cancel"
   }
   ```
   - Credits are added directly to the user
   - No Stripe interaction occurs
   - Useful for end-to-end testing of your application logic

2. **Using Stripe Test Mode** (complete Stripe flow):
   ```
   POST /payments/buy-tokens
   {
     "amount": 100,
     "success_url": "https://example.com/success",
     "cancel_url": "https://example.com/cancel"
   }
   ```
   - Returns a Stripe Checkout URL
   - Open the URL in a browser
   - Use Stripe test card numbers:
     - Success: `4242 4242 4242 4242`
     - Decline: `4000 0000 0000 0002`
   - Webhook will add credits to user account when payment completes

#### Testing Subscriptions

1. **Create Subscription Checkout**:
   ```
   POST /payments/subscribe
   {
     "tier": "Individual",
     "success_url": "https://example.com/success",
     "cancel_url": "https://example.com/cancel"
   }
   ```
   - Returns a Stripe Checkout URL for subscription

2. **Complete Test Subscription**:
   - Open checkout URL
   - Use Stripe test card: `4242 4242 4242 4242`
   - Enter any future expiration date, any CVC
   - Fill in any name and email address
   - Complete checkout

3. **Verification**:
   - Stripe sends a webhook event (subscription.created)
   - Server updates user's subscription tier
   - Credits are added based on the subscription tier
   - Check user's subscriptions:
     ```
     GET /payments/my/subscriptions
     ```

#### Automated Testing

- Use `test_api_flows.py` to test the API endpoints
- This script tests token purchase with the test endpoint
- For complete Stripe flow testing, manually use the checkout URLs with test cards
- To run automated tests: `python test_api_flows.py`

#### Testing Webhook Events

For testing webhook events without completing actual checkouts:

1. **Using the Test Script** (easiest approach):
   ```
   # For payment webhooks (adding tokens)
   python scripts/test_webhook.py --type payment --tokens 100

   # For subscription webhooks
   python scripts/test_webhook.py --type subscription --tier Team
   ```
   This script:
   - Creates a test user (or reuses an existing one)
   - Generates the proper webhook payload
   - Sends it to your API
   - Reports the results
   
   Run with `--help` to see all options.

2. **Using Stripe CLI**:
   ```
   stripe trigger checkout.session.completed
   ```
   This simulates a completed checkout event.

3. **Using Stripe Dashboard**:
   - Create a test webhook in the Stripe dashboard
   - Select events to send (e.g., `checkout.session.completed`)
   - Send to your endpoint URL

4. **Manually Triggering with cURL**:
   ```
   curl -X POST http://localhost:8000/payments/webhook \
     -H "Content-Type: application/json" \
     -d '{"type":"checkout.session.completed","data":{"object":{"id":"cs_test_123","mode":"payment","amount_total":1000,"currency":"usd","metadata":{"user_id":"YOUR_USER_ID","tokens":"100"}}}}'
   ```

#### Webhook Troubleshooting

**Missing Webhook Secret Issue**:

If you encounter errors related to webhook signature verification, there are two solutions:

1. **Set the Webhook Secret** (recommended for production):
   - Add `STRIPE_WEBHOOK_SECRET` to your .env file
   - Get this value from the Stripe Dashboard or when running `stripe listen`
   - This allows secure verification of webhook events

2. **Test Mode** (for development only):
   - The API now detects when no webhook secret is present and falls back to test mode
   - In test mode, webhook payloads are accepted without signature verification
   - Various payload formats are supported for testing clients
   - You'll see a warning in the logs when running in this mode

**Example Webhook Payload for Testing**:

```json
{
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "id": "cs_test_123",
      "mode": "payment",
      "amount_total": 1000,
      "currency": "usd",
      "metadata": {
        "user_id": "YOUR_USER_ID",
        "tokens": "100"
      }
    }
  }
}
```

For subscription events, use `"mode": "subscription"` and include `"subscription": "sub_123"` in the object.

#### Step-by-Step Example

Here's a complete testing flow:

1. Start the API server:
   ```
   uvicorn app.main:app --reload
   ```

2. Register a user:
   ```
   curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","name":"Test User","password":"password123"}'
   ```
   Note the `user_id` and `session_id` from the response.

3. Test token purchase (test mode):
   ```
   curl -X POST http://localhost:8000/payments/test/buy-tokens \
     -H "Content-Type: application/json" \
     -H "Cookie: session_id=YOUR_SESSION_ID" \
     -d '{"amount":100,"success_url":"https://example.com/success","cancel_url":"https://example.com/cancel"}'
   ```
   This adds tokens directly to the user in test mode.

4. Check user's profile to verify credits:
   ```
   curl -X GET http://localhost:8000/auth/me \
     -H "Cookie: session_id=YOUR_SESSION_ID"
   ```

For subscription testing with real Stripe checkout, follow a similar flow but open the checkout URL in a browser and use test card numbers to complete the transaction.

## Flows and Examples

### 1. Google OAuth Login Flow

The Google OAuth login process follows this flow:

1. **Initiate Login**: Redirect user to the Google login URL
   ```
   GET /auth/google/login
   ```

2. **Handle Callback**: Google redirects to our callback URL with an authorization code
   ```
   GET /auth/google/callback?code={authorization_code}
   ```

3. **Server Processing**:
   - Exchange the authorization code for tokens
   - Retrieve user info from Google
   - Create or retrieve user account
   - Create session
   - Return user profile with session cookie

4. **Access Protected Resources**: Use the session cookie for authenticated requests
   ```
   GET /auth/me
   ```

### 2. Two-Factor Authentication (2FA) Flow

1. **Setup 2FA**: After login, request 2FA setup
   ```
   POST /auth/mfa/setup
   ```
   This returns a QR code to scan with authenticator app (e.g., Google Authenticator)

2. **Verify 2FA**: Verify and enable 2FA with a code from authenticator app
   ```
   POST /auth/mfa/verify
   {
     "code": "123456"
   }
   ```

3. **Login with 2FA**: For subsequent logins, after normal authentication, validate MFA
   ```
   POST /auth/mfa/validate
   {
     "code": "123456"
   }
   ```

### 3. Product Management Flow

1. **List Products**: View all available products
   ```
   GET /payments/products
   ```

2. **Create Product**: Add a new product
   ```
   POST /payments/products
   {
     "name": "Premium Widget",
     "description": "A high-quality widget",
     "price": 29.99,
     "currency": "usd"
   }
   ```
   This checks if a product with the same name already exists before creating it.

3. **Delete Product**: Remove a product by name
   ```
   DELETE /payments/products/{name}
   ```
   This marks the product as inactive in Stripe and removes it from the local database.

4. **List Subscription Tiers**: View all subscription tiers
   ```
   GET /payments/subscription-tiers
   ```

5. **Initialize Products**: Initialize default products
   ```
   POST /payments/initialize-products
   ```
   This endpoint requires authentication and initializes the default subscription tiers and tokens product.

### 4. Subscription Flow

1. **Create Subscription Checkout Session**: Create a checkout session for a subscription tier
   ```
   POST /payments/subscribe
   {
     "tier": "Individual",
     "success_url": "https://yourapp.com/success",
     "cancel_url": "https://yourapp.com/cancel"
   }
   ```
   Returns a checkout URL to redirect the user to Stripe's payment page

2. **Handle Webhook**: Stripe sends a webhook event when payment is complete
   ```
   POST /payments/webhook
   ```
   Server processes the webhook, updates user subscription, and adds credits

3. **View Subscriptions**: View user's active subscriptions
   ```
   GET /payments/my/subscriptions
   ```

### 5. Token/Credit Purchase Flow

1. **Create Token Purchase Checkout Session**: Create checkout for token purchase
   ```
   POST /payments/buy-tokens
   {
     "amount": 100,
     "success_url": "https://yourapp.com/success",
     "cancel_url": "https://yourapp.com/cancel"
   }
   ```
   Returns checkout URL to redirect to Stripe
   
   **Note:** In test environments, use the test endpoint:
   ```
   POST /payments/test/buy-tokens
   {
     "amount": 100,
     "success_url": "https://yourapp.com/success",
     "cancel_url": "https://yourapp.com/cancel"
   }
   ```
   This test endpoint adds credits directly without requiring Stripe payment.

2. **Handle Webhook**: Stripe sends webhook when payment completes
   ```
   POST /payments/webhook
   ```
   Server processes the webhook and adds credits to user account

3. **View Payment History**: View payment history
   ```
   GET /payments/my/payments
   ```