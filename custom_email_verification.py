import os
import time
import uuid
import json
import hashlib
import hmac
import base64
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Union, Tuple

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Using environment variables directly.")

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("email_verification")

# Email sending dependencies
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content, TemplateId, Substitution
    SENDGRID_AVAILABLE = True
except ImportError:
    logger.warning("SendGrid not installed. Email sending will be simulated.")
    SENDGRID_AVAILABLE = False

# Web server for verification (optional)
try:
    from flask import Flask, request, jsonify, redirect
    FLASK_AVAILABLE = True
except ImportError:
    logger.warning("Flask not installed. Web server functionality will not be available.")
    FLASK_AVAILABLE = False

# Database simulation
# In a real application, use a proper database like PostgreSQL, MongoDB, etc.
class SimpleDatabase:
    def __init__(self, db_file: str = None):
        self.db_file = db_file or os.environ.get("DB_FILE", "users_db.json")
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
                 from_email: Optional[str] = None,
                 from_name: Optional[str] = None,
                 verification_url: Optional[str] = None,
                 token_expiry_hours: Optional[int] = None,
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
        # Get configuration from parameters or environment variables
        self.api_key = api_key or os.environ.get("SENDGRID_API_KEY")
        self.from_email = from_email or os.environ.get("FROM_EMAIL", "verification@yourdomain.com")
        self.from_name = from_name or os.environ.get("FROM_NAME", "Your Application")
        self.verification_url = verification_url or os.environ.get("VERIFICATION_URL", "https://yourdomain.com/verify")
        
        # Parse token expiry from environment if not provided
        if token_expiry_hours is None:
            try:
                self.token_expiry_hours = int(os.environ.get("TOKEN_EXPIRY_HOURS", "24"))
            except ValueError:
                logger.warning("Invalid TOKEN_EXPIRY_HOURS, using default of 24 hours")
                self.token_expiry_hours = 24
        else:
            self.token_expiry_hours = token_expiry_hours
        
        # Initialize database
        self.db = db or SimpleDatabase()
        
        # Secret for token signing
        self.hmac_secret = hmac_secret or os.environ.get("HMAC_SECRET", "your-secret-key")
        
        # Log configuration (without sensitive details)
        logger.info(f"Email verification service initialized: from_email={self.from_email}, " +
                  f"verification_url={self.verification_url}, token_expiry_hours={self.token_expiry_hours}")
        
        if not self.api_key or self.api_key == "your-sendgrid-api-key-here":
            logger.warning("No valid SendGrid API key provided. Email sending will be simulated.")
    
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
        logger.info(f"Registering new user: {email}")
        
        # Check if user already exists
        if self.db.get_user(email):
            logger.warning(f"User already exists: {email}")
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
        
        logger.debug(f"Generated verification token for {email}, expires at {expiry}")
        return token, expiry
    
    def verify_email_token(self, token: str) -> Dict[str, Any]:
        """
        Verify an email verification token.
        
        Args:
            token: The verification token
            
        Returns:
            Dict with verification result
        """
        logger.info(f"Verifying token: {token[:10]}...")
        
        # Get token data from database
        token_data = self.db.get_token_data(token)
        
        if not token_data:
            logger.warning(f"Invalid token: {token[:10]}...")
            return {
                "success": False,
                "error": "Invalid verification token"
            }
        
        # Check if token has already been used
        if token_data.get("used", False):
            logger.warning(f"Token already used: {token[:10]}...")
            return {
                "success": False,
                "error": "Token has already been used"
            }
        
        # Check if token has expired
        expiry = datetime.fromisoformat(token_data["expiry"])
        if datetime.now() > expiry:
            logger.warning(f"Token expired: {token[:10]}..., expired at {expiry}")
            return {
                "success": False,
                "error": "Verification token has expired"
            }
        
        # Get the user email from token data
        email = token_data["email"]
        
        # Update user's verification status
        user_data = self.db.get_user(email)
        if not user_data:
            logger.error(f"User not found for token: {token[:10]}...")
            return {
                "success": False,
                "error": "User not found"
            }
        
        # Mark user as verified
        user_data["verified"] = True
        self.db.update_user(email, user_data)
        
        # Mark token as used
        self.db.mark_token_used(token)
        
        logger.info(f"Email verified successfully: {email}")
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
        logger.info(f"Resending verification email to: {email}")
        
        # Check if user exists
        user_data = self.db.get_user(email)
        if not user_data:
            logger.warning(f"User not found: {email}")
            return {
                "success": False,
                "error": "User not found"
            }
        
        # Check if user is already verified
        if user_data.get("verified", False):
            logger.warning(f"User already verified: {email}")
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
        logger.info(f"Sending verification email to: {email}")
        
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
        
        # If no API key is available or SendGrid is not installed, simulate sending
        if not self.api_key or not SENDGRID_AVAILABLE:
            logger.info(f"Simulating email to: {email}, subject: {subject}")
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
                logger.info(f"Email sent successfully to: {email}")
                return {
                    "success": True,
                    "message": "Verification email sent successfully"
                }
            else:
                logger.error(f"Failed to send email to {email}: Status code {response.status_code}")
                return {
                    "success": False,
                    "error": f"Failed to send email: Status code {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Error sending email to {email}: {str(e)}", exc_info=True)
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
        logger.info(f"Login attempt: {email}")
        
        # Get user data
        user_data = self.db.get_user(email)
        if not user_data:
            logger.warning(f"Login failed - user not found: {email}")
            return {
                "success": False,
                "error": "Invalid email or password"
            }
        
        # Check if user is verified
        if not user_data.get("verified", False):
            logger.warning(f"Login failed - email not verified: {email}")
            return {
                "success": False,
                "error": "Email not verified",
                "needs_verification": True,
                "email": email
            }
        
        # Verify password
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != user_data.get("password_hash"):
            logger.warning(f"Login failed - invalid password: {email}")
            return {
                "success": False,
                "error": "Invalid email or password"
            }
        
        # Update last login time
        user_data["last_login"] = datetime.now().isoformat()
        self.db.update_user(email, user_data)
        
        logger.info(f"Login successful: {email}")
        return {
            "success": True,
            "message": "Login successful",
            "user": {
                "email": email,
                "name": user_data.get("name", ""),
                "verified": user_data.get("verified", False)
            }
        }


# Initialize Flask app if available
if FLASK_AVAILABLE:
    app = Flask(__name__)

    # Initialize verification service
    verification_service = EmailVerificationService()

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
    if FLASK_AVAILABLE:
        server_parser = subparsers.add_parser("server", help="Run the web server")
        server_parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"), help="Server host")
        server_parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")), help="Server port")
        server_parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    
    args = parser.parse_args()
    
    # Initialize service
    service = EmailVerificationService()
    
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
    
    elif args.command == "server" and FLASK_AVAILABLE:
        # Get debug setting from arguments or environment
        debug = args.debug or os.environ.get("FLASK_DEBUG", "").lower() == "true"
        
        # Configure app
        app.config["verification_service"] = service
        print(f"Starting server on http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=debug)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    # Check if running as web server or CLI
    if os.environ.get("WEB_SERVER", "").lower() == "true" and FLASK_AVAILABLE:
        # Run web server
        host = os.environ.get("HOST", "127.0.0.1")
        port = int(os.environ.get("PORT", 5000))
        debug = os.environ.get("FLASK_DEBUG", "").lower() == "true"
        print(f"Starting web server on http://{host}:{port}")
        app.run(host=host, port=port, debug=debug)
    else:
        # Run CLI demo
        run_cli_demo() 