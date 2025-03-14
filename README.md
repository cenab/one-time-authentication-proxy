# Email Authentication API

A Python client for generating temporary email addresses and retrieving verification codes sent to those emails. This tool is useful for automating account creation and verification processes that require email verification.

## Features

- Create temporary email addresses on demand using Mail.tm service
- Wait for and retrieve verification emails
- Extract verification codes from email content
- Clean up by deleting temporary email accounts when done

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from email_auth_api import get_verification_code

# Get a verification code from an email that matches certain criteria
result = get_verification_code(
    sender_contains="noreply@example.com",  # Optional: filter by sender
    subject_contains="verification",        # Optional: filter by subject
    timeout=120                            # Optional: maximum wait time in seconds
)

# The result contains the temporary email address and verification code
if result["success"]:
    print(f"Email: {result['email']}")
    print(f"Verification Code: {result['code']}")
else:
    print(f"Error: {result['error']}")
```

### Advanced Usage

For more control over the process, you can use the `EmailAuthAPI` class directly:

```python
from email_auth_api import EmailAuthAPI

# Initialize the API client
email_api = EmailAuthAPI()

# Create a new temporary email account
account_info = email_api.create_account()

if account_info["success"]:
    email_address = account_info["email"]
    print(f"Created temporary email: {email_address}")

    # Use this email address in your application for registration

    # Wait for the verification email and extract the code
    verification_result = email_api.wait_for_verification_email(
        sender_contains="noreply",
        subject_contains="verify",
        timeout=120
    )

    if verification_result["success"]:
        print(f"Verification code: {verification_result['code']}")

    # Clean up by deleting the temporary account
    email_api.delete_account()
else:
    print(f"Error creating account: {account_info['error']}")
```

## Configuration

The API uses the Mail.tm service for creating temporary email addresses. **No API key is required** as explicitly mentioned in the Mail.tm documentation. The service is free to use with a rate limit of 8 queries per second per IP address.

The authentication works by:
1. Creating a temporary email account
2. Getting a bearer token for that account
3. Using that token for subsequent API calls

## Customization

The verification code extraction patterns may need to be customized based on the specific format of verification emails you're dealing with. You can modify the `_extract_verification_code` method in the `EmailAuthAPI` class to handle different patterns.

## Requirements

See `requirements.txt` for dependencies. 