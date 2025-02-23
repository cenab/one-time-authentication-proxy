# TextVerified API Integration

This code demonstrates how to use the TextVerified API to obtain a single-use phone number for verification purposes, such as WhatsApp authentication.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your API credentials:
   - Open `textverified_api.py`
   - Replace `YOUR_API_KEY` with your TextVerified API key
   - Replace `your@example.com` with your TextVerified username/email

## Usage

Run the script:
```bash
python textverified_api.py
```

The script will:
1. Authenticate with TextVerified API
2. Get a list of available services
3. Create a verification request
4. Get a phone number
5. Poll for incoming SMS messages

## Important Notes

- This code is for demonstration purposes. Make sure to comply with both TextVerified's and WhatsApp's terms of service.
- The script uses sample area codes (775 and 301). You can modify these in the code.
- The SMS polling has a default timeout of 10 attempts with 10-second delays. You can adjust these parameters in the code.
- Make sure to handle your API credentials securely in a production environment. 