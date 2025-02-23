import requests
import time

# Configuration
API_BASE = "https://www.textverified.com/api/pub/v2"
API_KEY = "YOUR_API_KEY"          # Replace with your API key
API_USERNAME = "your@example.com"   # Replace with your username/email

def get_bearer_token():
    """Authenticate and get a bearer token."""
    url = f"{API_BASE}/auth"
    headers = {
        "X-API-KEY": API_KEY,
        "X-API-USERNAME": API_USERNAME,
    }
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    token = response.json().get("token")
    print("Obtained Bearer Token:", token)
    return token

def get_service_list(bearer_token):
    """Retrieve a list of supported services for verifications."""
    url = f"{API_BASE}/services"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {
        "numberType": "mobile",            # Options: mobile, voip, landline
        "reservationType": "verification"  # We need a single-use verification
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    services = response.json()
    print("Service List:", services)
    return services

def create_verification(bearer_token, service_name, area_codes=None, carrier_options=None):
    """Create a new verification to rent a single-use number."""
    url = f"{API_BASE}/verifications"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "serviceName": service_name,
        "capability": "sms"
    }
    if area_codes:
        payload["areaCodeSelectOption"] = area_codes
    if carrier_options:
        payload["carrierSelectOption"] = carrier_options

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        # The location header points to the newly created verification resource.
        verification_location = response.headers.get("location")
        print("Verification created. Location:", verification_location)
        return verification_location
    else:
        response.raise_for_status()

def get_verification_details(bearer_token, verification_id):
    """Retrieve details of the verification including the phone number."""
    url = f"{API_BASE}/verifications/{verification_id}"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    details = response.json()
    print("Verification Details:", details)
    return details

def get_sms_for_verification(bearer_token, phone_number, reservation_id, retries=10, delay=10):
    """Poll the SMS endpoint until an SMS is received or retries are exhausted."""
    url = f"{API_BASE}/sms"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {
        "to": phone_number,
        "reservationId": reservation_id,
        "reservationType": "verification"
    }
    for i in range(retries):
        print(f"Polling for SMS... Attempt {i+1}/{retries}")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("data") and len(data["data"]) > 0:
            sms = data["data"][0]
            print("SMS Received:", sms)
            return sms
        time.sleep(delay)
    print("No SMS received within the retry window.")
    return None

def main():
    # Step 1: Authenticate and get a Bearer token.
    token = get_bearer_token()
    
    # Step 2: Retrieve available verification services.
    services = get_service_list(token)
    if not services:
        print("No verification services available.")
        return

    # Choose a service from the list. Here, we take the first available service.
    service_name = services[0]["serviceName"]
    print("Using Service:", service_name)

    # Step 3: Create a new verification (single-use number).
    # Optionally specify area codes or carriers. Here, we're using two sample area codes.
    verification_location = create_verification(token, service_name, area_codes=["775", "301"])
    
    # Extract the verification ID from the location URL.
    # For example, if the location is: /api/pub/v2/verifications/abcd1234, the ID is "abcd1234".
    verification_id = verification_location.split("/")[-1]
    print("Verification ID:", verification_id)

    # Step 4: Get verification details to obtain the phone number.
    details = get_verification_details(token, verification_id)
    phone_number = details.get("number")
    if not phone_number:
        print("Phone number not found in verification details.")
        return
    print("Phone number for verification:", phone_number)

    # For WhatsApp registration, you would now use 'phone_number' to register.
    # WhatsApp sends a verification code to this number.
    # Step 5: Poll for the incoming SMS (which should contain the WhatsApp code).
    reservation_id = details.get("id")  # Assuming the reservation ID is the same as verification ID.
    sms = get_sms_for_verification(token, phone_number, reservation_id)
    if sms:
        # Extract the verification code from the SMS as needed.
        code = sms.get("parsedCode")
        print("Verification code received:", code)
    else:
        print("Failed to retrieve SMS verification code.")

if __name__ == "__main__":
    main() 