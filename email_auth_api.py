import requests
import time
import json
import os
import re
from typing import Dict, Optional, List, Any, Union

class EmailAuthAPI:
    """
    A client for handling email authentication using Mail.tm service.
    Mail.tm provides temporary email addresses that can be used for verification.
    No API key is required as mentioned in the Mail.tm documentation.
    """
    
    def __init__(self):
        """
        Initialize the email authentication client.
        """
        self.base_url = "https://api.mail.tm"
        self.token = None
        self.email_address = None
        self.email_password = "Password123"  # Default password for temp accounts
        self.account_id = None
    
    def get_available_domains(self) -> List[Dict[str, Any]]:
        """
        Get list of available domains from Mail.tm.
        
        Returns:
            List of domain objects
        """
        response = requests.get(f"{self.base_url}/domains")
        
        if response.status_code == 200:
            domains_data = response.json()
            return domains_data.get("hydra:member", [])
        
        return []
    
    def create_account(self) -> Dict[str, Any]:
        """
        Creates a new temporary email address.
        
        Returns:
            Dict containing the email address and account information
        """
        # Get available domains
        domains = self.get_available_domains()
        if not domains:
            return {"success": False, "error": "No domains available"}
        
        # Generate a random username for the email
        import random
        import string
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domain = domains[0].get("domain", "mail.tm")
        
        self.email_address = f"{username}@{domain}"
        
        # Create account
        response = requests.post(
            f"{self.base_url}/accounts",
            json={
                "address": self.email_address,
                "password": self.email_password
            }
        )
        
        if response.status_code == 201:
            account_data = response.json()
            self.account_id = account_data.get("id")
            
            # Get authentication token
            return self.get_token()
        
        return {
            "success": False, 
            "error": f"Failed to create email account. Status code: {response.status_code}",
            "details": response.text
        }
    
    def get_token(self) -> Dict[str, Any]:
        """
        Get authentication token for accessing the API.
        
        Returns:
            Dict containing token and success status
        """
        if not self.email_address:
            return {"success": False, "error": "No email address available"}
            
        auth_response = requests.post(
            f"{self.base_url}/token",
            json={
                "address": self.email_address,
                "password": self.email_password
            }
        )
        
        if auth_response.status_code == 200:
            auth_data = auth_response.json()
            self.token = auth_data.get("token")
            return {
                "success": True,
                "email": self.email_address,
                "account_id": self.account_id,
                "token": self.token
            }
            
        return {
            "success": False, 
            "error": f"Failed to get token. Status code: {auth_response.status_code}",
            "details": auth_response.text
        }
    
    def get_messages(self) -> Dict[str, Any]:
        """
        Get all messages in the inbox.
        
        Returns:
            Dict containing message list or error
        """
        if not self.token:
            return {"success": False, "error": "Not authenticated"}
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(f"{self.base_url}/messages", headers=headers)
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        
        return {"success": False, "error": f"Failed to get messages. Status code: {response.status_code}"}
    
    def get_message_content(self, message_id: str) -> Dict[str, Any]:
        """
        Get the content of a specific message.
        
        Args:
            message_id: ID of the message to retrieve
            
        Returns:
            Message content object
        """
        if not self.token:
            return {"success": False, "error": "Not authenticated"}
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(f"{self.base_url}/messages/{message_id}", headers=headers)
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        
        return {"success": False, "error": f"Failed to get message. Status code: {response.status_code}"}
    
    def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """
        Mark a message as read.
        
        Args:
            message_id: ID of the message to mark as read
            
        Returns:
            Dict with success status
        """
        if not self.token:
            return {"success": False, "error": "Not authenticated"}
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        response = requests.patch(
            f"{self.base_url}/messages/{message_id}", 
            headers=headers,
            json={"seen": True}
        )
        
        if response.status_code == 200:
            return {"success": True}
        
        return {"success": False, "error": f"Failed to mark message as read. Status code: {response.status_code}"}
    
    def wait_for_verification_email(self, 
                                   sender_contains: Optional[str] = None, 
                                   subject_contains: Optional[str] = None,
                                   timeout: int = 120,
                                   check_interval: int = 5) -> Dict[str, Any]:
        """
        Wait for a verification email to arrive and extract the verification code.
        
        Args:
            sender_contains: String that should be in the sender's email
            subject_contains: String that should be in the email subject
            timeout: Maximum time to wait for the email (in seconds)
            check_interval: How often to check for new emails (in seconds)
            
        Returns:
            Dict with verification information including the code if found
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            messages_result = self.get_messages()
            
            if not messages_result.get("success", False):
                return messages_result
                
            messages_data = messages_result.get("data", {})
            
            if "hydra:member" in messages_data:
                for message in messages_data.get("hydra:member", []):
                    sender = message.get("from", {}).get("address", "")
                    subject = message.get("subject", "")
                    
                    # Check if this is the verification email we're looking for
                    sender_match = not sender_contains or sender_contains.lower() in sender.lower()
                    subject_match = not subject_contains or subject_contains.lower() in subject.lower()
                    
                    if sender_match and subject_match:
                        # Get the full message content
                        message_id = message.get("id")
                        message_result = self.get_message_content(message_id)
                        
                        if not message_result.get("success", False):
                            continue
                            
                        message_content = message_result.get("data", {})
                        html_body = message_content.get("html", [""])[0] if isinstance(message_content.get("html"), list) else message_content.get("html", "")
                        text_body = message_content.get("text", "")
                        
                        # Mark as read
                        self.mark_as_read(message_id)
                        
                        # Try to extract verification code
                        verification_code = self._extract_verification_code(html_body) or \
                                          self._extract_verification_code(text_body)
                        
                        if verification_code:
                            return {
                                "success": True,
                                "code": verification_code,
                                "message_id": message_id,
                                "subject": subject,
                                "sender": sender
                            }
            
            # Wait before checking again
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
            
        # Common patterns for verification codes
        patterns = [
            r'verification code is: (\d{4,8})',
            r'verification code: (\d{4,8})',
            r'verification code.*?(\d{4,8})',
            r'code.*?(\d{4,8})',
            r'code.*?([A-Z0-9]{4,8})',
            r'verification code.*?([A-Z0-9]{4,8})',
            r'verification code:?\s*([A-Z0-9]{4,8})',
            r'OTP:?\s*([A-Z0-9]{4,8})',
            r'one-time password:?\s*([A-Z0-9]{4,8})',
            r'confirm.*?([A-Z0-9]{4,8})',
            r'<strong>(\d{4,8})</strong>',
            r'<b>(\d{4,8})</b>'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def delete_account(self) -> Dict[str, Any]:
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


def get_verification_code(sender_contains=None, subject_contains=None, timeout=120):
    """
    High-level function to get a verification code from a new temporary email.
    
    Args:
        sender_contains: String that should be in the sender's email
        subject_contains: String that should be in the email subject
        timeout: Maximum time to wait for the verification email
        
    Returns:
        Dict with verification information or error
    """
    email_api = EmailAuthAPI()
    
    # Create a new email account
    account_info = email_api.create_account()
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
    # Example usage
    result = get_verification_code(
        sender_contains="noreply",
        subject_contains="verification"
    )
    print(result) 