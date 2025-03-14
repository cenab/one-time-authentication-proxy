import requests
import time

# Configuration
API_BASE = "https://www.textverified.com/api/pub/v2"
API_KEY = "UtpiLyzoBnd6AkBfxq0ADBMb34rLhxthXopA7rkk6U4LQ9rQaw2Vc2mXQlrCLr"
API_USERNAME = "batu.bora389@gmail.com"

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

def retrieve_verification_code(token, phone_number, verification_id, service_name, details, max_attempts=20, polling_interval=5):
    """
    Retrieves the verification code by polling the verifications endpoint to check for status updates.
    
    Args:
        token (str): The authentication token for API calls
        phone_number (str): The phone number to receive SMS
        verification_id (str): The ID of the verification
        service_name (str): The name of the service being used
        details (dict): The verification details
        max_attempts (int): Maximum number of polling attempts
        polling_interval (int): Seconds to wait between polling attempts
        
    Returns:
        dict or None: The verification details including code if successful, None otherwise
    """
    try:
        print(f"\nPolling for verification code...")
        print(f"Will check for verification status every {polling_interval} seconds, up to {max_attempts} times.")
        
        # Get specific verification details endpoint
        url = f"{API_BASE}/verifications/{verification_id}"
        headers = {"Authorization": f"Bearer {token}"}
        
        for attempt in range(1, max_attempts + 1):
            print(f"Attempt {attempt}/{max_attempts}: Checking verification status...")
            
            try:
                response = requests.get(url, headers=headers)
                
                # Print response details for debugging
                print(f"Response Status Code: {response.status_code}")
                print(f"Response Headers: {response.headers}")
                print(f"Response Content: {response.text}")
                
                response.raise_for_status()
                verification_data = response.json()
                
                print(f"Verification Status: {verification_data.get('state', 'unknown')}")
                
                # Check if verification has an SMS link
                if verification_data.get('sms') and verification_data['sms'].get('href'):
                    # Use the direct SMS URL provided by the API
                    sms_url = verification_data['sms']['href']
                    print(f"Using SMS URL from API: {sms_url}")
                    
                    # Make request to SMS endpoint
                    sms_response = requests.get(sms_url, headers=headers)
                    sms_response.raise_for_status()
                    sms_data = sms_response.json()
                    
                    print(f"SMS Response: {sms_data}")
                    
                    if sms_data.get("data") and len(sms_data["data"]) > 0:
                        sms = sms_data["data"][0]
                        print("SMS Received:", sms)
                        
                        code = sms.get("parsedCode")
                        if code:
                            print(f"✓ Verification code received: {code}")
                            return {
                                "service": service_name,
                                "phone": phone_number,
                                "code": code,
                                "details": details,
                                "sms": sms,
                                "verification_status": verification_data.get('state')
                            }
                        else:
                            print("⚠️ Received SMS but could not extract a verification code.")
                            # Continue polling as the code might come in a subsequent message
                
                # Check if verification state indicates completion
                if verification_data.get('state') == 'verificationComplete':
                    print("Verification marked as complete, but no code was found.")
                    # Try to extract message from verification data directly if available
                    if verification_data.get('message'):
                        print(f"Message from verification: {verification_data.get('message')}")
                        # Try to extract code from message if possible
                
                # No verification code yet, wait and try again
                if attempt < max_attempts:
                    print(f"Waiting {polling_interval} seconds before next check...")
                    time.sleep(polling_interval)
            except Exception as e:
                print(f"Error during polling attempt {attempt}: {str(e)}")
                # Continue to next attempt despite error
                if attempt < max_attempts:
                    time.sleep(polling_interval)
        
        print("⚠️ Maximum polling attempts reached. No verification code received.")
        return None
            
    except Exception as e:
        print(f"Error in verification code retrieval process: {str(e)}")
        return None

def verify_with_service(token, service):
    """
    Performs verification process with a single specified service.
    
    Args:
        token (str): The authentication token for API calls
        service (dict): The service to use for verification
        
    Returns:
        dict or None: The verification details including code if successful, None otherwise
    """
    try:
        service_name = service["serviceName"]
        print(f"Using Service: {service_name}")
        
        # Create verification (get phone number)
        try:
            verification_location = create_verification(token, service_name, area_codes=["775", "301"])
            if not verification_location:
                print("Error: Failed to create verification.")
                return None
                
            verification_id = verification_location.split("/")[-1]
            print("Verification ID:", verification_id)
        except Exception as e:
            print(f"Error creating verification: {str(e)}")
            return None
    
        # Get verification details
        try:
            details = get_verification_details(token, verification_id)
            phone_number = details.get("number")
            if not phone_number:
                print("Error: Phone number not found in verification details.")
                return None
            print("Phone number for verification:", phone_number)
        except Exception as e:
            print(f"Error retrieving verification details: {str(e)}")
            return None
    
        # Display instructions to user
        print(f"\n===== INSTRUCTIONS =====")
        print(f"1. Use this phone number ({phone_number}) in your {service_name} verification process")
        print(f"2. Wait for the verification SMS to be received")
        print("=======================\n")
    
        # Get verification SMS and code
        return retrieve_verification_code(token, phone_number, verification_id, service_name, details)
            
    except Exception as e:
        print(f"Unexpected error during verification process: {str(e)}")
        return None

def main():
    try:
        # Step 1: Authenticate and get a Bearer token.
        print("Authenticating...")
        token = get_bearer_token()
        if not token:
            print("Error: Failed to obtain authentication token.")
            return
        
        # Step 2: Retrieve available verification services.
        print("Retrieving available services...")
        services = get_service_list(token)
        if not services:
            print("Error: No verification services available.")
            return
        
        # Filter for target services
        target_services = []
        for service in services:
            service_name = service.get("serviceName", "").lower()
            
            # Check capabilities in either format (list or single string)
            has_sms = False
            if "capabilities" in service:
                capabilities = [cap.lower() for cap in service.get("capabilities", [])]
                has_sms = "sms" in capabilities
            elif "capability" in service:
                has_sms = service.get("capability", "").lower() == "sms"
            
            # Check if the service is one of our targets AND has SMS capability
            if ("whatsapp" in service_name or "telegram" in service_name or "signal" in service_name) and has_sms:
                target_services.append(service)
        
        # Just use the first available service that meets our criteria
        selected_service = target_services[1]
        print(f"Selected service: {selected_service['serviceName']}")
        
        # Run the verification process with the selected service
        result = verify_with_service(token, selected_service)
        if result:
            print("\nVerification completed successfully!")
            print(f"Service: {result['service']}")
            print(f"Phone: {result['phone']}")
            print(f"Verification Code: {result['code']}")
    
    except Exception as e:
        print(f"Error in main program: {str(e)}")
    
if __name__ == "__main__":
    main() 