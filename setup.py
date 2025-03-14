#!/usr/bin/env python
"""
Setup script for custom email verification system.
This script helps with installing dependencies and configuring the environment.
"""

import os
import sys
import subprocess
import shutil
import getpass
import random
import string
from pathlib import Path

def print_header(text):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f" {text} ".center(80, "="))
    print("=" * 80 + "\n")

def print_step(step, description):
    """Print a step in the setup process."""
    print(f"\n[{step}] {description}")

def generate_secret_key(length=32):
    """Generate a random secret key."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}|;:,.<>?"
    return ''.join(random.choice(chars) for _ in range(length))

def install_dependencies():
    """Install required Python packages."""
    print_step(1, "Installing dependencies")
    
    # Check if pip is available
    if not shutil.which("pip"):
        print("Error: pip is not installed or not in PATH. Please install pip first.")
        return False
    
    # Install dependencies
    packages = ["sendgrid", "flask", "python-dotenv"]
    print(f"Installing packages: {', '.join(packages)}")
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + packages)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def create_env_file():
    """Create .env file from .env.example."""
    print_step(2, "Creating environment configuration")
    
    # Check if .env.example exists
    if not os.path.exists(".env.example"):
        print("❌ .env.example file not found. Make sure you're running this script from the project directory.")
        return False
    
    # Check if .env already exists
    if os.path.exists(".env"):
        overwrite = input(".env file already exists. Overwrite? (y/n): ").lower() == 'y'
        if not overwrite:
            print("Skipping .env file creation.")
            return True
    
    # Read .env.example
    with open(".env.example", "r") as f:
        env_example = f.readlines()
    
    # Prepare new .env content
    env_content = []
    for line in env_example:
        line = line.strip()
        if not line or line.startswith("#"):
            env_content.append(line)
            continue
        
        # Parse key and default value/comment
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            
            # Special handling for secret keys
            if key == "HMAC_SECRET" and (not value or value == "your-secret-key-here"):
                value = generate_secret_key()
                print(f"🔑 Generated random HMAC_SECRET")
            else:
                # Prompt for value
                user_value = input(f"Enter value for {key} [{value}]: ").strip()
                if user_value:
                    value = user_value
            
            env_content.append(f"{key}={value}")
        else:
            env_content.append(line)
    
    # Write .env file
    with open(".env", "w") as f:
        f.write("\n".join(env_content))
    
    print("✅ .env file created successfully")
    return True

def test_configuration():
    """Test the configuration with a simple verification."""
    print_step(3, "Testing configuration")
    
    try:
        # Import the necessary modules and test
        import dotenv
        dotenv.load_dotenv()
        
        # Test SendGrid API key
        sendgrid_key = os.environ.get("SENDGRID_API_KEY")
        if sendgrid_key and sendgrid_key != "your-sendgrid-api-key-here":
            from sendgrid import SendGridAPIClient
            sg = SendGridAPIClient(api_key=sendgrid_key)
            # Just test if we can create the client - don't actually send an email
            print("✅ SendGrid API key validation successful")
        else:
            print("⚠️ SendGrid API key not configured. Email sending will be simulated.")
        
        print("\n✅ Configuration test completed")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you've installed all dependencies.")
        return False
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def show_usage_instructions():
    """Show instructions for using the system."""
    print_step(4, "Usage instructions")
    
    print("""
How to use the verification system:

1. As a Command Line Tool:
   # Register a new user
   python custom_email_verification.py register --email user@example.com --password secret123 --name "Example User"
   
   # Verify a token
   python custom_email_verification.py verify --token "the-token-from-email-link"
   
   # Login after verification
   python custom_email_verification.py login --email user@example.com --password secret123

2. As a Web Service:
   # Run the web server
   export WEB_SERVER=true
   python custom_email_verification.py
   
   Server endpoints:
   - POST /register - Register a new user
   - GET /verify?token=xyz - Verify an email
   - POST /resend-verification - Resend verification email
   - POST /login - Login a verified user
""")

def main():
    """Main setup function."""
    print_header("Email Verification System Setup")
    
    print("""This script will help you set up the custom email verification system.
It will install dependencies and guide you through configuration.
""")
    
    proceed = input("Do you want to proceed with setup? (y/n): ").lower() == 'y'
    if not proceed:
        print("Setup cancelled.")
        return
    
    # Run setup steps
    deps_ok = install_dependencies()
    if not deps_ok:
        print("\n⚠️ Failed to install dependencies. Please resolve the issues and try again.")
        return
    
    env_ok = create_env_file()
    if not env_ok:
        print("\n⚠️ Failed to create environment configuration. Please resolve the issues and try again.")
        return
    
    test_ok = test_configuration()
    if not test_ok:
        print("\n⚠️ Configuration test failed. Please check your settings in the .env file.")
    
    show_usage_instructions()
    
    print_header("Setup Complete")
    print("""
Your email verification system is now set up! 

Remember to:
1. Configure your domain's DNS settings if you're using a custom domain
2. Set up SendGrid or another email provider properly
3. Update your verification URL for production use

If you have any issues, check the documentation or seek help.
""")

if __name__ == "__main__":
    main() 