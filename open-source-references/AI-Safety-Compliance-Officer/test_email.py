"""
Test Email Configuration
Diagnose email sending issues step by step
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

def test_email_config():
    """Test email configuration step by step"""
    
    print("=" * 60)
    print("EMAIL CONFIGURATION TEST")
    print("=" * 60)
    
    # Step 1: Check .env file
    print("\n1. Checking .env file...")
    if not os.path.exists('.env'):
        print("   ❌ .env file not found!")
        print("   ⚠️  You need to create .env file from .env.example")
        print("\n   Quick Fix:")
        print("   1. Copy .env.example to .env")
        print("   2. Edit .env and add your email credentials")
        return False
    else:
        print("   ✅ .env file exists")
    
    # Step 2: Load environment variables
    print("\n2. Loading environment variables...")
    load_dotenv()
    
    email_sender = os.getenv("EMAIL_SENDER", "")
    email_password = os.getenv("EMAIL_PASSWORD", "")
    email_recipients = os.getenv("EMAIL_RECIPIENTS", "")
    
    # Step 3: Validate credentials
    print("\n3. Validating email credentials...")
    
    if not email_sender:
        print("   ❌ EMAIL_SENDER not configured in .env")
        print("   Add: EMAIL_SENDER=your_email@gmail.com")
        return False
    else:
        print(f"   ✅ EMAIL_SENDER: {email_sender}")
    
    if not email_password:
        print("   ❌ EMAIL_PASSWORD not configured in .env")
        print("   Add: EMAIL_PASSWORD=your_app_password")
        print("\n   📌 For Gmail users:")
        print("      1. Enable 2-Step Verification")
        print("      2. Generate App Password at: https://myaccount.google.com/apppasswords")
        print("      3. Use the 16-character app password (not your regular password)")
        return False
    else:
        print(f"   ✅ EMAIL_PASSWORD: {'*' * len(email_password)} (hidden)")
    
    if not email_recipients:
        print("   ❌ EMAIL_RECIPIENTS not configured in .env")
        print("   Add: EMAIL_RECIPIENTS=recipient@example.com")
        return False
    else:
        print(f"   ✅ EMAIL_RECIPIENTS: {email_recipients}")
    
    # Step 4: Test SMTP connection
    print("\n4. Testing SMTP connection...")
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    
    try:
        print(f"   Connecting to {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        print("   ✅ Connected to SMTP server")
        
        print("   Starting TLS encryption...")
        server.starttls()
        print("   ✅ TLS started")
        
        print("   Logging in...")
        server.login(email_sender, email_password)
        print("   ✅ Login successful!")
        
        server.quit()
        print("   ✅ SMTP connection closed properly")
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"   ❌ Authentication failed: {e}")
        print("\n   Common Causes:")
        print("   1. Wrong email/password")
        print("   2. Not using App Password (Gmail requires App Password)")
        print("   3. 2-Step Verification not enabled (required for App Password)")
        print("\n   Fix for Gmail:")
        print("   - Go to: https://myaccount.google.com/apppasswords")
        print("   - Generate 16-character App Password")
        print("   - Use that in EMAIL_PASSWORD (not your regular password)")
        return False
    
    except smtplib.SMTPConnectError as e:
        print(f"   ❌ Connection failed: {e}")
        print("   Check your internet connection")
        return False
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Step 5: Send test email
    print("\n5. Sending test email...")
    try:
        msg = MIMEMultipart()
        msg['From'] = email_sender
        msg['To'] = email_recipients.split(',')[0]  # Send to first recipient
        msg['Subject'] = "🧪 Test Email - AI Safety Compliance Officer"
        
        body = """
This is a test email from the AI Safety Compliance Officer system.

If you receive this email, your email configuration is working correctly!

✅ Email notifications are functional
✅ You will receive safety violation alerts
✅ PDF reports will be attached to future emails

System is ready to monitor construction site safety.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.starttls()
        server.login(email_sender, email_password)
        server.send_message(msg)
        server.quit()
        
        print(f"   ✅ Test email sent to {email_recipients.split(',')[0]}")
        print("\n   Check your inbox (and spam folder)!")
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to send email: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Email is configured correctly!")
    print("=" * 60)
    return True


def create_env_template():
    """Create .env file from template"""
    print("\n" + "=" * 60)
    print("CREATING .env FILE")
    print("=" * 60)
    
    if os.path.exists('.env'):
        response = input("\n.env file already exists. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return
    
    # Copy .env.example to .env
    if os.path.exists('.env.example'):
        with open('.env.example', 'r') as example:
            content = example.read()
        
        with open('.env', 'w') as env_file:
            env_file.write(content)
        
        print("✅ .env file created from .env.example")
        print("\nNext steps:")
        print("1. Open .env file in editor")
        print("2. Add your OpenAI API key")
        print("3. Add your email credentials (use App Password for Gmail)")
        print("4. Add recipient email addresses")
        print("5. Run this test again: python test_email.py")
    else:
        print("❌ .env.example not found!")


if __name__ == "__main__":
    print("\n🔧 AI Safety Compliance Officer - Email Configuration Test\n")
    
    # Check if .env exists
    if not os.path.exists('.env'):
        print("⚠️  No .env file found!")
        response = input("\nCreate .env from template? (y/n): ")
        if response.lower() == 'y':
            create_env_template()
            print("\n✅ Now edit the .env file with your credentials and run this test again.")
        else:
            print("\nPlease create .env file manually from .env.example")
    else:
        # Run tests
        success = test_email_config()
        
        if success:
            print("\n🎉 Success! Email configuration is working correctly.")
            print("You can now use the AI Safety Compliance Officer system.")
        else:
            print("\n❌ Email configuration needs attention.")
            print("Follow the instructions above to fix the issues.")
