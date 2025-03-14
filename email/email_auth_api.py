import requests
import time
import json
import os
import re
from typing import Dict, Optional, List, Any, Union
import argparse

class EmailAuthAPI:
    """
    A client for handling email authentication using temporary email services.
    Currently supports Mail.tm API for temporary email creation and verification.
    """
    
    def __init__(self, api_key: Optional[str] = None, use_alternative: bool = False):
        """
        Initialize the email authentication client.
        
        Args:
            api_key: Optional API key for the email service (if required)
            use_alternative: Use an alternative email provider if True
        """
        self.api_key = api_key or os.environ.get("EMAIL_AUTH_API_KEY")
        
        # Choose the provider based on parameter
        if use_alternative:
            self.base_url = "https://api.internal.temp-mail.io/api/v3"  # Alternative provider
            self.provider = "temp-mail"
        else:
        self.base_url = "https://api.mail.tm"  # Using Mail.tm as the default provider
            self.provider = "mail.tm"
            
        self.token = None
        self.email_address = None
        self.email_password = "Password123"  # Default password for temp accounts
        self.account_id = None
    
    def login_or_create_account(self) -> Dict[str, Any]:
        """
        Creates a new temporary email address or logs into an existing one.
        
        Returns:
            Dict containing the email address and other account information
        """
        if self.provider == "mail.tm":
            return self._create_mailTm_account()
        else:
            return self._create_tempMail_account()
    
    def _create_mailTm_account(self) -> Dict[str, Any]:
        """
        Creates an account using the Mail.tm service
        """
        # Generate a random username for the email
        import random
        import string
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        print(f"DEBUG: Generated username: {username}")
        
        # Get available domains from the API
        try:
            print(f"DEBUG: Requesting available domains from {self.base_url}/domains")
            domains = self.get_available_domains()
            print(f"DEBUG: Available domains: {domains}")
            if not domains:
                print("WARNING: No domains available from API, using fallback domains")
                domains = ["indigobook.com", "zetmail.com", "zeroe.ml"]
        except Exception as e:
            print(f"ERROR: Failed to get domains: {str(e)}")
            import traceback
            traceback.print_exc()
            domains = ["indigobook.com", "zetmail.com", "zeroe.ml"]
        
        # Try each domain until one works
        for domain in domains:
            self.email_address = f"{username}@{domain}"
            print(f"DEBUG: Attempting to create account with email: {self.email_address}")
        
        # Create account
            try:
                print(f"DEBUG: Sending POST to {self.base_url}/accounts")
        response = requests.post(
            f"{self.base_url}/accounts",
            json={
                "address": self.email_address,
                "password": self.email_password
                    },
                    timeout=10  # Add timeout to prevent hanging
        )
        
                print(f"DEBUG: Account creation response: {response.status_code}")
                # If successful, proceed with getting token
        if response.status_code == 201:
            account_data = response.json()
            self.account_id = account_data.get("id")
                    print(f"DEBUG: Account created successfully with ID: {self.account_id}")
            
            # Get authentication token
                    print(f"DEBUG: Requesting auth token for {self.email_address}")
            auth_response = requests.post(
                f"{self.base_url}/token",
                json={
                    "address": self.email_address,
                    "password": self.email_password
                        },
                        timeout=10
            )
            
                    print(f"DEBUG: Auth token response: {auth_response.status_code}")
            if auth_response.status_code == 200:
                auth_data = auth_response.json()
                self.token = auth_data.get("token")
                        print(f"DEBUG: Got token: {self.token[:10]}...")
                return {
                    "success": True,
                    "email": self.email_address,
                    "account_id": self.account_id,
                            "token": self.token,
                            "provider": self.provider
                        }
                    else:
                        print(f"ERROR: Auth token request failed with status {auth_response.status_code}")
                        print(f"DEBUG: Auth response body: {auth_response.text[:200]}")
                
                # If we reached here, this domain didn't work, try to extract error message
                try:
                    error_detail = "Unknown error"
                    if response.text:
                        print(f"DEBUG: Error response body: {response.text[:200]}")
                        error_json = response.json()
                        if "hydra:description" in error_json:
                            error_detail = error_json["hydra:description"]
                        elif "detail" in error_json:
                            error_detail = error_json["detail"]
                except Exception as e:
                    print(f"DEBUG: Could not parse error response: {str(e)}")
                    error_detail = response.text if response.text else f"Status code: {response.status_code}"
                
                print(f"ERROR: Failed with domain {domain}: {error_detail}")
            except requests.exceptions.RequestException as e:
                print(f"ERROR: Network error with domain {domain}: {str(e)}")
                print(f"DEBUG: Request exception details: {type(e)}")
                import traceback
                traceback.print_exc()
        
        # If we tried all domains and none worked
        print("ERROR: All domains failed, could not create account")
        return {
            "success": False,
            "error": f"Failed to create email account with any available domain. Try --alternative flag.",
            "provider": self.provider
        }
        
    def _create_tempMail_account(self) -> Dict[str, Any]:
        """
        Creates an account using the temp-mail.io service
        """
        # For temp-mail.io, we need to use their format
        import random
        import string
        
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        
        # temp-mail.io typically has domains like these
        domains = ["bluebasket.site", "promail1.net", "nextmail.info", "tempmail.us"]
        
        for domain in domains:
            self.email_address = f"{username}@{domain}"
            
            # With temp-mail.io, just creating the object is enough - no authentication needed
            self.token = "dummy_token"  # Not used but needed for API structure
            self.account_id = username
            
            # Test if we can access the inbox
            try:
                # Just a simple check to see if we can access messages
                test_result = self.get_messages()
                if "hydra:member" in test_result:
                    return {
                        "success": True,
                        "email": self.email_address,
                        "account_id": self.account_id,
                        "token": self.token,
                        "provider": self.provider
                    }
            except Exception as e:
                print(f"Failed with temp-mail domain {domain}: {str(e)}")
        
        return {
            "success": False,
            "error": "Failed to create account with alternative provider",
            "provider": self.provider
        }
    
    def get_messages(self) -> Dict[str, Any]:
        """
        Get all messages in the inbox.
        
        Returns:
            Dict with messages or error information
        """
        if self.provider == "mail.tm":
            return self._get_messages_mailTm()
        else:
            return self._get_messages_tempMail()
    
    def _get_messages_mailTm(self) -> Dict[str, Any]:
        """Get messages from Mail.tm"""
        if not self.token:
            print(f"DEBUG: No authentication token available for {self.email_address}")
            return {"success": False, "error": "Not authenticated", "hydra:member": []}
        
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            print(f"DEBUG: Requesting messages from {self.base_url}/messages with token: {self.token[:10]}...")
            response = requests.get(
                f"{self.base_url}/messages", 
                headers=headers,
                timeout=15  # Increased timeout
            )
            
            print(f"DEBUG: Message response status: {response.status_code}")
            if response.status_code == 200:
                # The API might return an object with hydra:member or an empty array
                data = response.json()
                print(f"DEBUG: Message response data type: {type(data)}")
                if isinstance(data, dict):
                    print(f"DEBUG: Message response keys: {data.keys()}")
                
                if isinstance(data, dict) and "hydra:member" in data:
                    return data
                elif isinstance(data, list):
                    # Convert empty list to expected format
                    print(f"DEBUG: Got list response, converting to hydra:member format")
                    return {"hydra:member": data}
                else:
                    # Some other unexpected format, but still a valid response
                    print(f"DEBUG: Unexpected response format: {data}")
                    return {"hydra:member": []}
            elif response.status_code == 401:
                # Token expired, try to refresh
                print(f"DEBUG: Authentication failure (401), attempting to refresh token")
                refresh_result = self.refresh_token()
                if refresh_result.get("success"):
                    # Try again with new token
                    print(f"DEBUG: Token refresh successful, retrying message fetch")
                    return self.get_messages()
                else:
                    print(f"DEBUG: Token refresh failed: {refresh_result.get('error')}")
                    return {"success": False, "error": "Authentication failed", "hydra:member": []}
            else:
                print(f"DEBUG: Unexpected status code {response.status_code}")
                # Try to get more details from the response
                try:
                    response_body = response.text
                    print(f"DEBUG: Response body: {response_body[:200]}")
                except:
                    response_body = "Could not read response body"
                
                return {"success": False, "error": f"Failed to get messages: {response.status_code}, Response: {response_body[:100]}", "hydra:member": []}
        except Exception as e:
            print(f"DEBUG: Exception in get_messages: {str(e)}, {type(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"Error getting messages: {str(e)}", "hydra:member": []}
            
    def _get_messages_tempMail(self) -> Dict[str, Any]:
        """Get messages from temp-mail.io"""
        if not self.email_address:
            return {"success": False, "error": "No email address", "hydra:member": []}
            
        # Extract email info
        parts = self.email_address.split('@')
        if len(parts) != 2:
            return {"success": False, "error": "Invalid email format", "hydra:member": []}
        
        login, domain = parts
        
        try:
            # For temp-mail.io API
            response = requests.get(
                f"{self.base_url}/email/{login}/{domain}/messages",
                timeout=15
            )
        
        if response.status_code == 200:
                messages = response.json()
                # Convert to our standard format
                hydra_members = []
                for msg in messages:
                    hydra_members.append({
                        "id": msg.get("_id", {}).get("$oid", "unknown"),
                        "from": {"address": msg.get("from", "unknown")},
                        "subject": msg.get("subject", "No subject"),
                        "intro": msg.get("body_text", "")[:100]
                    })
                return {"hydra:member": hydra_members}
            else:
                return {"success": False, "error": f"Failed to get messages from temp-mail: {response.status_code}", "hydra:member": []}
        except Exception as e:
            return {"success": False, "error": f"Error getting messages from temp-mail: {str(e)}", "hydra:member": []}
    
    def refresh_token(self) -> Dict[str, Any]:
        """
        Refresh the authentication token if it's expired.
        
        Returns:
            Dict with success/failure information
        """
        if not self.email_address or not self.email_password:
            print(f"ERROR: Cannot refresh token - no email or password available")
            return {"success": False, "error": "No email or password available"}
        
        print(f"DEBUG: Attempting to refresh token for {self.email_address}")
        try:
            print(f"DEBUG: Sending POST to {self.base_url}/token")
            auth_response = requests.post(
                f"{self.base_url}/token",
                json={
                    "address": self.email_address,
                    "password": self.email_password
                },
                timeout=10
            )
            
            print(f"DEBUG: Token refresh response status: {auth_response.status_code}")
            if auth_response.status_code == 200:
                auth_data = auth_response.json()
                self.token = auth_data.get("token")
                print(f"DEBUG: Token refreshed successfully. New token: {self.token[:10]}...")
                return {
                    "success": True,
                    "token": self.token
                }
            else:
                print(f"ERROR: Token refresh failed with status {auth_response.status_code}")
                print(f"DEBUG: Response body: {auth_response.text[:200]}")
                return {
                    "success": False,
                    "error": f"Failed to refresh token: {auth_response.status_code}"
                }
        except Exception as e:
            print(f"ERROR: Exception during token refresh: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"Error refreshing token: {str(e)}"}
    
    def get_message_content(self, message_id: str) -> Dict[str, Any]:
        """
        Get the content of a specific message.
        
        Args:
            message_id: ID of the message to retrieve
            
        Returns:
            Message content object
        """
        if not self.token:
            print(f"ERROR: Cannot get message content - not authenticated")
            return {"success": False, "error": "Not authenticated"}
        
        print(f"DEBUG: Getting content for message ID: {message_id}")
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            print(f"DEBUG: Sending GET to {self.base_url}/messages/{message_id}")
            response = requests.get(
                f"{self.base_url}/messages/{message_id}", 
                headers=headers,
                timeout=15
            )
            
            print(f"DEBUG: Message content response status: {response.status_code}")
        if response.status_code == 200:
                content = response.json()
                print(f"DEBUG: Message content retrieved successfully. HTML length: {len(content.get('html', ''))}, Text length: {len(content.get('text', ''))}")
                return content
            else:
                print(f"ERROR: Failed to get message content. Status: {response.status_code}")
                print(f"DEBUG: Response body: {response.text[:200]}")
        except Exception as e:
            print(f"ERROR: Exception getting message content: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return {"success": False, "error": f"Failed to get message. Status code: {response.status_code}"}
    
    def wait_for_verification_email(self, 
                                   sender_contains: Optional[str] = None, 
                                   subject_contains: Optional[str] = None,
                                   timeout: int = 120,
                                   check_interval: int = 5,
                                   verbose: bool = False,
                                   facebook_mode: bool = False) -> Dict[str, Any]:
        """
        Wait for a verification email to arrive and extract the verification code.
        
        Args:
            sender_contains: String that should be in the sender's email
            subject_contains: String that should be in the email subject
            timeout: Maximum time to wait for the email (in seconds)
            check_interval: How often to check for new emails (in seconds)
            verbose: Whether to show detailed output
            facebook_mode: If True, just look for 'facebook' in the content
            
        Returns:
            Dict with verification information including the code if found
        """
        start_time = time.time()
        check_count = 0
        consecutive_errors = 0
        
        while time.time() - start_time < timeout:
            check_count += 1
            if verbose:
                print(f"Checking for emails (attempt {check_count})...")
                
            messages = self.get_messages()
            
            # Reset error counter if successful
            if not messages.get("error"):
                consecutive_errors = 0
            else:
                consecutive_errors += 1
                if verbose:
                    print(f"Error retrieving messages: {messages.get('error')}")
                
                # If we've had too many consecutive errors, try to refresh the token
                if consecutive_errors >= 3 and consecutive_errors % 3 == 0:
                    if verbose:
                        print("Too many consecutive errors, attempting to refresh token...")
                    refresh_result = self.refresh_token()
                    if verbose:
                        if refresh_result.get("success"):
                            print("Token refreshed successfully")
                        else:
                            print(f"Failed to refresh token: {refresh_result.get('error')}")
            
            # Debug: Print raw message data
            if verbose:
                member_list = messages.get("hydra:member", [])
                num_messages = len(member_list)
                print(f"Found {num_messages} messages in mailbox")
                
                # Show basic info about each message
                for idx, message in enumerate(member_list):
                    sender = message.get("from", {}).get("address", "unknown")
                    subject = message.get("subject", "No subject")
                    print(f"  {idx+1}. From: {sender}, Subject: {subject}")
            
            member_list = messages.get("hydra:member", [])
            for message in member_list:
                    sender = message.get("from", {}).get("address", "")
                    subject = message.get("subject", "")
                    
                    # Check if this is the verification email we're looking for
                    sender_match = not sender_contains or sender_contains.lower() in sender.lower()
                    subject_match = not subject_contains or subject_contains.lower() in subject.lower()
                    
                # If in Facebook mode, check if "facebook" is in the subject
                if facebook_mode and "facebook" in subject.lower():
                    subject_match = True
                    
                if verbose:
                    print(f"  Checking message: Sender '{sender}' {'✓' if sender_match else '✗'}, Subject '{subject}' {'✓' if subject_match else '✗'}")
                
                    if sender_match and subject_match:
                        # Get the full message content
                        message_content = self.get_message_content(message.get("id"))
                        html_body = message_content.get("html", "")
                        text_body = message_content.get("text", "")
                        
                    # In Facebook mode, just check if "facebook" is in the content
                    if facebook_mode:
                        content_match = False
                        if "facebook" in html_body.lower() or "facebook" in text_body.lower():
                            content_match = True
                            if verbose:
                                print(f"  Found Facebook content in message")
                            return {
                                "success": True,
                                "facebook_email": True,  # Mark this as a Facebook email for manual entry
                                "message_id": message.get("id"),
                                "subject": subject,
                                "sender": sender,
                                "content": text_body or html_body  # Include content for viewing
                            }
                    else:
                        # Use normal pattern matching for other services
                        if verbose:
                            print(f"  Analyzing message content (length: HTML {len(html_body)}, Text {len(text_body)})")
                            # Print a sample of the text content
                            if text_body:
                                print(f"  Text preview: {text_body[:100]}...")
                            elif html_body:
                                print(f"  HTML preview: {html_body[:100]}...")
                        
                        # Try to extract verification code
                        verification_code = self._extract_verification_code(html_body) or \
                                          self._extract_verification_code(text_body)
                        
                        if verification_code:
                            return {
                                "success": True,
                                "code": verification_code,
                                "message_id": message.get("id"),
                                "subject": subject,
                                "sender": sender
                            }
            
            # Wait before checking again
            remaining = timeout - (time.time() - start_time)
            if verbose and remaining > 0:
                print(f"Waiting {check_interval}s before checking again. {int(remaining)}s remaining...")
            time.sleep(check_interval)
        
        return {"success": False, "error": "Verification email not received within timeout period"}
    
    def _extract_verification_code(self, content: str) -> Optional[str]:
        """
        Extract verification code from email content.
        This method needs to be customized based on the specific format of verification emails.
        
        Args:
            content: Email content (HTML or text)
            
        Returns:
            Extracted verification code or None if not found
        """
        if not content:
            return None
            
        # First, try direct search for Facebook's format
        if "FB-" in content:
            # Direct extract of FB-123456 format
            fb_code_match = re.search(r'FB-\d+', content)
            if fb_code_match:
                return fb_code_match.group(0)
        
        # Common patterns for verification codes
        patterns = [
            # Facebook specific patterns
            r'FB-(\d+)',  # FB-123456 format
            r'FB[- ](\d+)',  # Handle potential space after FB
            r'(FB-\d+)',  # Return the whole FB-123456 code
            r'code is (FB-\d+)',
            r'code.*?(\d{6})',  # Facebook often uses 6-digit codes
            r'code.*?(\d{5})',  # 5-digit codes
            r'code.*?(\d{5,8})',  # Flexible digit length
            # Generic patterns
            r'verification code is: (\d{4,8})',
            r'verification code: (\d{4,8})',
            r'verification code.*?(\d{4,8})',
            r'code.*?(\d{4,8})',
            r'code.*?([A-Z0-9]{4,8})',
            r'verification code.*?([A-Z0-9]{4,8})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                code = match.group(1)
                # If this is a Facebook code pattern and doesn't include "FB-", add it
                if re.match(r'^\d+$', code) and "FB-" in content:
                    return f"FB-{code}"
                return code
        
        # Advanced extraction - try harder for Facebook codes by looking at smaller chunks
        if "facebook" in content.lower():
            # Look for numbers near keywords
            number_matches = re.finditer(r'\d{5,8}', content)
            for match in number_matches:
                # Get surrounding text (20 chars before and after)
                start = max(0, match.start() - 20)
                end = min(len(content), match.end() + 20)
                context = content[start:end]
                
                # Check if context includes verification keywords
                if any(keyword in context.lower() for keyword in ['code', 'verif', 'confirm']):
                    return match.group(0)
        
        return None
    
    def delete_account(self) -> Dict[str, bool]:
        """
        Delete the temporary email account.
        
        Returns:
            Dict indicating success or failure
        """
        if not self.token or not self.account_id:
            return {"success": False, "error": "Not authenticated or no account ID"}
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.delete(f"{self.base_url}/accounts/{self.account_id}", headers=headers)
        
        if response.status_code == 204:
            self.email_address = None
            self.token = None
            self.account_id = None
            return {"success": True}
        
        return {"success": False, "error": f"Failed to delete account. Status code: {response.status_code}"}

    def get_available_domains(self) -> List[str]:
        """
        Get list of domains available for creating email addresses.
        
        Returns:
            List of domain strings
        """
        print("DEBUG: Fetching available domains...")
        try:
            print(f"DEBUG: Sending GET to {self.base_url}/domains")
            response = requests.get(f"{self.base_url}/domains", timeout=10)
            
            print(f"DEBUG: Domains response status: {response.status_code}")
            if response.status_code == 200:
                domains_data = response.json()
                print(f"DEBUG: Domains response keys: {domains_data.keys() if isinstance(domains_data, dict) else 'not a dict'}")
                
                if "hydra:member" in domains_data:
                    domains = [domain.get("domain", "") for domain in domains_data["hydra:member"]]
                    valid_domains = [d for d in domains if d]  # Filter out empty domain names
                    
                    print(f"DEBUG: Found {len(valid_domains)} valid domains: {valid_domains}")
                    if valid_domains:
                        return valid_domains
                else:
                    print(f"DEBUG: Expected 'hydra:member' not found in response: {str(domains_data)[:200]}")
                        
            # If we get here, either the API call failed or no domains were found
            print(f"WARNING: API response for domains: Status code {response.status_code}")
            if response.text:
                print(f"DEBUG: API response content: {response.text[:200]}...")
        except Exception as e:
            print(f"ERROR: Exception fetching domains: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Fallback to default domains if API request fails
        print("DEBUG: Using fallback domains")
        return ["indigobook.com", "yogare.xyz", "zeroe.ml", "mail.gw"]


def get_verification_code(sender_contains=None, subject_contains=None, timeout=120):
    """
    High-level function to get a verification code from a new temporary email.
    
    Args:
        sender_contains: String that should be in the sender's email (None or empty string matches all senders)
        subject_contains: String that should be in the email subject (None or empty string matches all subjects)
        timeout: Maximum time to wait for the verification email
        
    Returns:
        Dict with verification information or error
    """
    email_api = EmailAuthAPI()
    
    # Create a new email account
    account_info = email_api.login_or_create_account()
    if not account_info.get("success", False):
        return account_info
    
    # Get the verification email and extract code
    verification_result = email_api.wait_for_verification_email(
        sender_contains=sender_contains,
        subject_contains=subject_contains,
        timeout=timeout
    )
    
    # Clean up by deleting the temporary account
    email_api.delete_account()
    
    if verification_result.get("success", False):
        return {
            "success": True,
            "email": account_info.get("email"),
            "code": verification_result.get("code")
        }
    
    return verification_result


if __name__ == "__main__":
    # Set up command line arguments for testing
    parser = argparse.ArgumentParser(description="Test email verification code retrieval")
    parser.add_argument("--sender", default="", help="String to match in sender email (leave empty to match all senders)")
    parser.add_argument("--subject", default="", help="String to match in email subject (leave empty to match all subjects)")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout in seconds")
    parser.add_argument("--verbose", action="store_true", help="Show detailed progress")
    parser.add_argument("--dump-content", action="store_true", help="Dump full content of all received emails")
    parser.add_argument("--facebook", action="store_true", help="Simple Facebook mode - just find emails with 'facebook'")
    parser.add_argument("--alternative", action="store_true", help="Use alternative email provider if mail.tm fails")
    parser.add_argument("--debug", action="store_true", help="Show extensive debug logs")
    parser.add_argument("--real-email", action="store_true", help="Prompt for a real email address to use instead")
    args = parser.parse_args()
    
    # Enable debug logging based on command line flag
    debug_mode = args.debug or args.verbose
    
    # Configure logging
    if debug_mode:
        print("==== DETAILED DEBUG LOGGING ENABLED ====")
        # Show Python and requests versions for debugging
        import sys
        print(f"Python version: {sys.version}")
        print(f"Requests version: {requests.__version__}")
    
    # Use Facebook-specific settings if requested
    facebook_mode = False
    if args.facebook:
        args.sender = ""  # Don't filter by sender in Facebook mode
        args.subject = ""  # Don't filter by subject in Facebook mode
        facebook_mode = True
        print("Simple Facebook verification mode enabled - looking for any email with 'facebook' in it")
        
        # Show warning about Facebook blocking temporary email domains
        print("\n⚠️ IMPORTANT: Facebook typically blocks temporary email domains.")
        print("This script might not work with Facebook as they require accounts to use legitimate email domains.")
        print("Options:")
        print("1. Use a real email address you own (see --help for --real-email option)")
        print("2. Test this script with services that don't block temporary emails")
        print("")
        
        # Prompt for confirmation
        try:
            proceed = input("Do you still want to proceed with a temporary email? (y/n): ")
            if proceed.lower() != 'y':
                print("Exiting at user request.")
                exit(0)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            exit(0)
    
    print("Starting email verification test...")
    
    # If real-email flag is provided, prompt for a real email address
    if args.real_email:
        try:
            print("\nℹ️ You've chosen to use a real email address.")
            print("This option requires you to have access to the inbox to retrieve the verification code.")
            real_email = input("Enter your real email address: ")
            
            print(f"\n✓ Using email: {real_email}")
            print(f"⏳ Waiting for verification email matching:")
            if facebook_mode:
                print(f"   - Any email containing 'facebook'")
            else:
                if args.sender:
                    print(f"   - Sender contains: '{args.sender}'")
                if args.subject:
                    print(f"   - Subject contains: '{args.subject}'")
            print(f"")
            print(f"NOTE: You should now trigger a verification email to be sent to your address.")
            
            # Manual code entry for real email
            print("\nWhen you receive the verification email, check your inbox and enter the code:")
            try:
                manual_code = input("\nEnter the verification code: ")
                if manual_code.strip():
                    print(f"✓ Verification Code: {manual_code.strip()}")
                    print(f"✓ Email: {real_email}")
                    exit(0)
            except KeyboardInterrupt:
                print("\nOperation cancelled by user.")
                exit(0)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            exit(0)
    
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            print(f"\nRetrying with a new email account (attempt {attempt}/{max_attempts})...")
            
        # If this is the second attempt, try alternative provider
        use_alternative = args.alternative or attempt > 1
        if use_alternative:
            print("Using alternative email provider...")
        
        # Initialize the API
        print(f"DEBUG: Initializing EmailAuthAPI with alternative={use_alternative}")
        email_api = EmailAuthAPI(use_alternative=use_alternative)
        
        # Create a new email account
        print("Creating temporary email account...")
        account_info = email_api.login_or_create_account()
        if not account_info.get("success", False):
            print(f"ERROR: Failed to create email account: {account_info.get('error')}")
            if attempt < max_attempts:
                print("Will retry with another provider/account")
                continue
            else:
                print("Maximum attempts reached. Unable to create a working email account.")
                exit(1)
        
        print(f"✓ Created temporary email: {account_info.get('email')} (provider: {account_info.get('provider')})")
        if debug_mode:
            print(f"DEBUG: Account info: {account_info}")
            
        print(f"⏳ Waiting for verification email matching:")
        if facebook_mode:
            print(f"   - Any email containing 'facebook'")
        else:
            if args.sender:
                print(f"   - Sender contains: '{args.sender}'")
            else:
                print(f"   - Sender: Any")
            if args.subject:
                print(f"   - Subject contains: '{args.subject}'")
            else:
                print(f"   - Subject: Any")
        print(f"   - Timeout: {args.timeout} seconds")
        print(f"")
        print(f"NOTE: You should now trigger a verification email to be sent to the address above.")
        
        # Extra warning for Facebook mode
        if facebook_mode:
            print("\n⚠️ NOTE: If you see 'Invalid Email Domain' or similar errors when using this email,")
            print("it means the service is blocking temporary email domains. Try using --real-email instead.")
        
        # Get the verification email and extract code
        start_time = time.time()
        
        # Create a flag to track if we detected authentication failures
        auth_failure = False
        
        # Monitor for an initial period to detect authentication issues early
        print("Testing email account access...")
        
        for i in range(3):  # Test a few times to ensure account is working
            print(f"DEBUG: Testing email account access (attempt {i+1}/3)")
            test_messages = email_api.get_messages()
            if test_messages.get("error"):
                print(f"DEBUG: Error during test: {test_messages.get('error')}")
                if "authentication" in test_messages.get("error", "").lower():
                    auth_failure = True
                    print(f"ERROR: Authentication issue detected: {test_messages.get('error')}")
                    break
            else:
                print(f"DEBUG: Email account access test successful")
            time.sleep(2)
        
        if auth_failure:
            print("⚠️ Authentication issues detected with this email account.")
            if attempt < max_attempts:
                print("Will retry with a new account/provider")
                continue  # Try a new account
            else:
                print("Maximum attempts reached. The email service may be experiencing issues.")
                
                # Provide alternative instructions
                print("\nAlternative options:")
                print("1. Try again later when the service may be more stable")
                print("2. Use a different email verification service")
                print("3. Manual verification - check for your code at the service's website")
                print("\nFor additional debugging, run with the --debug flag")
                exit(1)
        
        # Everything looks good, wait for the verification email
        print(f"DEBUG: Account validated, now waiting for verification email...")
        verification_result = email_api.wait_for_verification_email(
            sender_contains=args.sender,
            subject_contains=args.subject,
            timeout=args.timeout,
            check_interval=5,
            verbose=args.verbose or args.debug,
            facebook_mode=facebook_mode
        )
        
        elapsed_time = time.time() - start_time
        
        # In Facebook mode, or if we got a Facebook email, always prompt for manual code entry
        if facebook_mode or verification_result.get("facebook_email", False):
            if verification_result.get("success", False):
                print("\n✓ Found Facebook verification email!")
                if verification_result.get("subject"):
                    print(f"Subject: {verification_result.get('subject')}")
                if verification_result.get("sender"):
                    print(f"From: {verification_result.get('sender')}")
                
                # Show a preview of the content
                content = verification_result.get("content", "")
                if content:
                    print("\nEmail content preview:")
                    print("-" * 40)
                    print(content[:300])
                    if len(content) > 300:
                        print("...")
            else:
                print("\nNo Facebook verification email found automatically.")
                if debug_mode:
                    print(f"DEBUG: Verification result: {verification_result}")
            
            # Provide instructions for manual check
            if account_info.get("provider") == "mail.tm":
                print(f"\nCheck the inbox for {account_info.get('email')} at https://mail.tm/en/")
            else:
                print(f"\nCheck the inbox for {account_info.get('email')} at a temporary email service")
                print("Suggested services: temp-mail.org, 10minutemail.com")
                
            print("Enter the verification code you see in the email")
            
            try:
                manual_code = input("\nEnter the verification code (FB-XXXXXX format): ")
                if manual_code.strip():
                    verification_result = {
                        "success": True,
                        "code": manual_code.strip(),
                        "message_id": "manual",
                        "subject": "Manual Entry",
                        "sender": "Manual Entry"
                    }
                    print(f"DEBUG: Manually entered code: {manual_code.strip()}")
            except KeyboardInterrupt:
                print("\nOperation cancelled by user.")
                exit(1)
        
        # If no verification code found and dump-content is enabled, show all messages
        if not verification_result.get("success") and args.dump_content:
            print("\nDumping all messages in inbox:")
            messages = email_api.get_messages()
            if "hydra:member" in messages:
                member_list = messages.get("hydra:member", [])
                if not member_list:
                    print("No messages found in inbox.")
                else:
                    for idx, message in enumerate(member_list):
                        msg_id = message.get("id")
                        sender = message.get("from", {}).get("address", "unknown")
                        subject = message.get("subject", "No subject")
                        print(f"\nMessage {idx+1}:")
                        print(f"From: {sender}")
                        print(f"Subject: {subject}")
                        
                        content = email_api.get_message_content(msg_id)
                        if "text" in content and content["text"]:
                            print("\nText Content:")
                            print("-" * 40)
                            print(content["text"][:500])
                            if len(content["text"]) > 500:
                                print("...")
                        
                        if "html" in content and content["html"]:
                            print("\nHTML Content (first 200 chars):")
                            print("-" * 40)
                            print(content["html"][:200])
                            if len(content["html"]) > 200:
                                print("...")
            else:
                print(f"Unexpected response format: {messages}")
        
        # Try to clean up by deleting the temporary account
        try:
            print("Deleting temporary account...")
            deletion_result = email_api.delete_account()
            
            if deletion_result.get("success", False):
                print("✓ Temporary account deleted successfully")
            else:
                print(f"✗ Failed to delete temporary account: {deletion_result.get('error')}")
        except Exception as e:
            print(f"Error during account deletion: {str(e)}")
        
        # Show results
        if verification_result.get("success", False):
            print(f"✓ Verification Code: {verification_result.get('code')}")
            print(f"✓ Email: {account_info.get('email')}")
            if not facebook_mode and verification_result.get("message_id") != "manual":
                print(f"✓ Subject: {verification_result.get('subject')}")
                print(f"✓ Sender: {verification_result.get('sender')}")
            break  # Success - exit the retry loop
        else:
            print(f"✗ Failed to receive verification email within {args.timeout} seconds")
            print(f"  Error: {verification_result.get('error')}")
            
            # Suggest possible issues
            print("\nPossible issues:")
            print("1. The email service might be blocking temporary email domains")
            print("2. The verification email may be delayed")
            
            if attempt < max_attempts:
                print("\nRetrying with a new email account...")
            else:
                print("\nMaximum retry attempts reached.") 