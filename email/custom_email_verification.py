import os
import time
import uuid
import json
import hashlib
import hmac
import base64
import argparse
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Union, Tuple

# Email sending dependencies
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, TemplateId, Substitution

# Web server for verification (optional)
from flask import Flask, request, jsonify, redirect

# Database simulation
# In a real application, use a proper database like PostgreSQL, MongoDB, etc.
class SimpleDatabase:
    def __init__(self, db_file: str = "users_db.json"):
        self.db_file = db_file
        self._load_db()
    
    def _load_db(self):
        """Load database from file"""
        try:
            with open(self.db_file, 'r') as f:
                self.data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Initialize empty database
            self.data = {"users": {}, "tokens": {}}
            self._save_db()
    
    def _save_db(self):
        """Save database to file"""
        with open(self.db_file, 'w') as f:
            json.dump(self.data, f, indent=4)
    
    def add_user(self, email: str, user_data: Dict) -> bool:
        """Add a new user to the database"""
        if email in self.data["users"]:
            return False  # User already exists
        
        self.data["users"][email] = user_data
        self._save_db()
        return True
    
    def update_user(self, email: str, user_data: Dict) -> bool:
        """Update user data"""
        if email not in self.data["users"]:
            return False  # User doesn't exist
        
        self.data["users"][email].update(user_data)
        self._save_db()
        return True
    
    def get_user(self, email: str) -> Optional[Dict]:
        """Get user data by email"""
        return self.data["users"].get(email)
    
    def add_token(self, token: str, email: str, expiry: datetime) -> None:
        """Store verification token"""
        self.data["tokens"][token] = {
            "email": email,
            "expiry": expiry.isoformat(),
            "used": False
        }
        self._save_db()
    
    def get_token_data(self, token: str) -> Optional[Dict]:
        """Get token data"""
        return self.data["tokens"].get(token)
    
    def mark_token_used(self, token: str) -> bool:
        """Mark token as used"""
        if token not in self.data["tokens"]:
            return False
        
        self.data["tokens"][token]["used"] = True
        self._save_db()
        return True


class EmailVerificationService:
    """
    A service for handling email verification using your own domain and email provider.
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 from_email: str = "verification@yourdomain.com",
                 from_name: str = "Your Application",
                 verification_url: str = "https://yourdomain.com/verify",
                 token_expiry_hours: int = 24,
                 db: Optional[SimpleDatabase] = None,
                 hmac_secret: Optional[str] = None):
        """
        Initialize the email verification service.
        
        Args:
            api_key: SendGrid API key
            from_email: Email address to send verification emails from
            from_name: Name to display as the sender
            verification_url: Base URL for verification links
            token_expiry_hours: How long tokens are valid for
            db: Database instance for storing users and tokens
            hmac_secret: Secret key for token signing
        """
        self.api_key = api_key or os.environ.get("SENDGRID_API_KEY")
        
        if not self.api_key:
            print("WARNING: No SendGrid API key provided. Email sending will be simulated.")
        
        self.from_email = from_email
        self.from_name = from_name
        self.verification_url = verification_url
        self.token_expiry_hours = token_expiry_hours
        
        # Initialize database
        self.db = db or SimpleDatabase()
        
        # Secret for token signing
        self.hmac_secret = hmac_secret or os.environ.get("HMAC_SECRET", "your-secret-key")
    
    def register_user(self, email: str, password: str, name: str = "") -> Dict[str, Any]:
        """
        Register a new user and send verification email.
        
        Args:
            email: User's email address
            password: User's password (should be hashed before storage in production)
            name: User's name
            
        Returns:
            Dict with registration result
        """
        # Check if user already exists
        if self.db.get_user(email):
            return {
                "success": False,
                "error": "User with this email already exists"
            }
        
        # In production, you should hash the password
        # For demo purposes, we're using a simple hash
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Create user record with unverified status
        user_data = {
            "email": email,
            "name": name,
            "password_hash": password_hash,
            "verified": False,
            "created_at": datetime.now().isoformat(),
            "last_login": None
        }
        
        # Add user to database
        self.db.add_user(email, user_data)
        
        # Generate and send verification token
        token, expiry = self._generate_verification_token(email)
        
        # Store token
        self.db.add_token(token, email, expiry)
        
        # Send verification email
        email_result = self.send_verification_email(email, token, name)
        
        return {
            "success": True,
            "message": "User registered successfully. Verification email sent.",
            "email_sent": email_result.get("success", False),
            "email_error": email_result.get("error")
        }
    
    def _generate_verification_token(self, email: str) -> Tuple[str, datetime]:
        """
        Generate a secure verification token for the user.
        
        Args:
            email: User's email address
            
        Returns:
            Tuple of (token, expiry datetime)
        """
        # Generate a random token
        random_token = uuid.uuid4().hex
        
        # Current timestamp for expiry calculation
        now = datetime.now()
        expiry = now + timedelta(hours=self.token_expiry_hours)
        
        # Create a signed token by combining the random token with a HMAC
        # This prevents token forgery
        timestamp = str(int(now.timestamp()))
        message = f"{email}:{random_token}:{timestamp}"
        
        # Sign the message with HMAC
        signature = hmac.new(
            self.hmac_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Combine all parts into the final token
        token = f"{random_token}.{timestamp}.{signature}"
        
        return token, expiry
    
    def verify_email_token(self, token: str) -> Dict[str, Any]:
        """
        Verify an email verification token.
        
        Args:
            token: The verification token
            
        Returns:
            Dict with verification result
        """
        # Get token data from database
        token_data = self.db.get_token_data(token)
        
        if not token_data:
            return {
                "success": False,
                "error": "Invalid verification token"
            }
        
        # Check if token has already been used
        if token_data.get("used", False):
            return {
                "success": False,
                "error": "Token has already been used"
            }
        
        # Check if token has expired
        expiry = datetime.fromisoformat(token_data["expiry"])
        if datetime.now() > expiry:
            return {
                "success": False,
                "error": "Verification token has expired"
            }
        
        # Get the user email from token data
        email = token_data["email"]
        
        # Update user's verification status
        user_data = self.db.get_user(email)
        if not user_data:
            return {
                "success": False,
                "error": "User not found"
            }
        
        # Mark user as verified
        user_data["verified"] = True
        self.db.update_user(email, user_data)
        
        # Mark token as used
        self.db.mark_token_used(token)
        
        return {
            "success": True,
            "message": "Email verified successfully",
            "email": email
        }
    
    def resend_verification_email(self, email: str) -> Dict[str, Any]:
        """
        Resend verification email to user.
        
        Args:
            email: User's email address
            
        Returns:
            Dict with result
        """
        # Check if user exists
        user_data = self.db.get_user(email)
        if not user_data:
            return {
                "success": False,
                "error": "User not found"
            }
        
        # Check if user is already verified
        if user_data.get("verified", False):
            return {
                "success": False,
                "error": "User is already verified"
            }
        
        # Generate and send new verification token
        token, expiry = self._generate_verification_token(email)
        
        # Store token
        self.db.add_token(token, email, expiry)
        
        # Send verification email
        email_result = self.send_verification_email(email, token, user_data.get("name", ""))
        
        return {
            "success": True,
            "message": "Verification email resent",
            "email_sent": email_result.get("success", False),
            "email_error": email_result.get("error")
        }
    
    def send_verification_email(self, email: str, token: str, name: str = "") -> Dict[str, Any]:
        """
        Send a verification email to the user.
        
        Args:
            email: User's email address
            token: Verification token
            name: User's name
            
        Returns:
            Dict with sending result
        """
        # Create verification link
        verification_link = f"{self.verification_url}?token={token}"
        
        # Personalized greeting
        greeting = f"Hello {name}," if name else "Hello,"
        
        # Email content
        subject = "Verify Your Email Address"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Email Verification</h2>
            <p>{greeting}</p>
            <p>Thank you for registering! Please verify your email address by clicking the button below:</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{verification_link}" style="background-color: #4CAF50; color: white; padding: 12px 20px; text-decoration: none; border-radius: 4px; font-weight: bold;">
                    Verify Email
                </a>
            </div>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; font-size: 14px; color: #666;">{verification_link}</p>
            <p>This verification link will expire in {self.token_expiry_hours} hours.</p>
            <p>If you didn't request this, please ignore this email.</p>
            <p>Best regards,<br>The Team</p>
        </div>
        """
        
        # If no API key is available, simulate sending
        if not self.api_key:
            print(f"\n=== SIMULATED EMAIL ===")
            print(f"To: {email}")
            print(f"Subject: {subject}")
            print(f"Verification Link: {verification_link}")
            print(f"===== END EMAIL =====\n")
            
            return {
                "success": True,
                "message": "Email sending simulated"
            }
        
        # Send using SendGrid
        try:
            # Initialize message
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            # Send the email
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            if response.status_code >= 200 and response.status_code < 300:
                return {
                    "success": True,
                    "message": "Verification email sent successfully"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to send email: Status code {response.status_code}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error sending email: {str(e)}"
            }
    
    def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a user.
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            Dict with login result
        """
        # Get user data
        user_data = self.db.get_user(email)
        if not user_data:
            return {
                "success": False,
                "error": "Invalid email or password"
            }
        
        # Check if user is verified
        if not user_data.get("verified", False):
            return {
                "success": False,
                "error": "Email not verified",
                "needs_verification": True,
                "email": email
            }
        
        # Verify password
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != user_data.get("password_hash"):
            return {
                "success": False,
                "error": "Invalid email or password"
            }
        
        # Update last login time
        user_data["last_login"] = datetime.now().isoformat()
        self.db.update_user(email, user_data)
        
        return {
            "success": True,
            "message": "Login successful",
            "user": {
                "email": email,
                "name": user_data.get("name", ""),
                "verified": user_data.get("verified", False)
            }
        }


# Example web server for verification
app = Flask(__name__)

# Initialize verification service
verification_service = EmailVerificationService(
    api_key=os.environ.get("SENDGRID_API_KEY"),
    from_email=os.environ.get("FROM_EMAIL", "verification@yourdomain.com"),
    verification_url=os.environ.get("VERIFICATION_URL", "http://localhost:5000/verify"),
    hmac_secret=os.environ.get("HMAC_SECRET")
)

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    name = data.get("name", "")
    
    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400
    
    result = verification_service.register_user(email, password, name)
    return jsonify(result)

@app.route("/verify", methods=["GET"])
def verify():
    token = request.args.get("token")
    
    if not token:
        return "Invalid verification link", 400
    
    result = verification_service.verify_email_token(token)
    
    if result.get("success"):
        # In a real application, redirect to a success page
        return f"<h1>Email Verified Successfully</h1><p>Your email {result.get('email')} has been verified. You can now log in.</p>"
    else:
        # In a real application, redirect to an error page
        return f"<h1>Verification Failed</h1><p>Error: {result.get('error')}</p>"

@app.route("/resend-verification", methods=["POST"])
def resend_verification():
    data = request.json
    email = data.get("email")
    
    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400
    
    result = verification_service.resend_verification_email(email)
    return jsonify(result)

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400
    
    result = verification_service.login_user(email, password)
    return jsonify(result)


def run_cli_demo():
    """Run a command-line demo of the email verification service"""
    parser = argparse.ArgumentParser(description="Email Verification Demo")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Register command
    register_parser = subparsers.add_parser("register", help="Register a new user")
    register_parser.add_argument("--email", required=True, help="User's email address")
    register_parser.add_argument("--password", required=True, help="User's password")
    register_parser.add_argument("--name", default="", help="User's name")
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify an email token")
    verify_parser.add_argument("--token", required=True, help="Verification token")
    
    # Resend verification command
    resend_parser = subparsers.add_parser("resend", help="Resend verification email")
    resend_parser.add_argument("--email", required=True, help="User's email address")
    
    # Login command
    login_parser = subparsers.add_parser("login", help="Log in a user")
    login_parser.add_argument("--email", required=True, help="User's email address")
    login_parser.add_argument("--password", required=True, help="User's password")
    
    # Web server command
    server_parser = subparsers.add_parser("server", help="Run the web server")
    server_parser.add_argument("--host", default="127.0.0.1", help="Server host")
    server_parser.add_argument("--port", type=int, default=5000, help="Server port")
    
    args = parser.parse_args()
    
    # Initialize service
    service = EmailVerificationService(
        api_key=os.environ.get("SENDGRID_API_KEY"),
        from_email=os.environ.get("FROM_EMAIL", "verification@yourdomain.com"),
        verification_url=os.environ.get("VERIFICATION_URL", "http://localhost:5000/verify"),
        hmac_secret=os.environ.get("HMAC_SECRET")
    )
    
    if args.command == "register":
        result = service.register_user(args.email, args.password, args.name)
        print(json.dumps(result, indent=2))
    
    elif args.command == "verify":
        result = service.verify_email_token(args.token)
        print(json.dumps(result, indent=2))
    
    elif args.command == "resend":
        result = service.resend_verification_email(args.email)
        print(json.dumps(result, indent=2))
    
    elif args.command == "login":
        result = service.login_user(args.email, args.password)
        print(json.dumps(result, indent=2))
    
    elif args.command == "server":
        # Configure app
        app.config["verification_service"] = service
        print(f"Starting server on http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=True)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    # Check if running as web server or CLI
    if os.environ.get("WEB_SERVER", "false").lower() == "true":
        # Run web server
        host = os.environ.get("HOST", "127.0.0.1")
        port = int(os.environ.get("PORT", 5000))
        print(f"Starting web server on http://{host}:{port}")
        app.run(host=host, port=port)
    else:
        # Run CLI demo
        run_cli_demo() 