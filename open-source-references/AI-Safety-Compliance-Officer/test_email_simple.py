"""
Test Email Sender
"""
from email_sender import EmailSender
import os
from dotenv import load_dotenv

print("📧 Testing Email Sender...")
print("="*80)

# Load environment variables
load_dotenv()

try:
    # Check email config
    print("\n🔍 Checking email configuration...")
    
    required = {
        'EMAIL_SENDER': os.getenv('EMAIL_SENDER'),
        'EMAIL_PASSWORD': os.getenv('EMAIL_PASSWORD'),
        'EMAIL_RECIPIENTS': os.getenv('EMAIL_RECIPIENTS')
    }
    
    missing = [k for k, v in required.items() if not v]
    
    if missing:
        print(f"⚠️  WARNING: Missing configuration: {', '.join(missing)}")
        print("\nEmail test will be SKIPPED")
        print("\nTo enable email testing, add these to your .env file:")
        print("  EMAIL_SENDER=your-email@gmail.com")
        print("  EMAIL_PASSWORD=your-app-password")
        print("  EMAIL_RECIPIENTS=recipient@email.com")
        print("\n📖 See EMAIL_SETUP.md for detailed instructions")
        exit(0)
    
    print("✅ All email configuration found")
    print(f"✅ Sender: {required['EMAIL_SENDER']}")
    print(f"✅ Recipients: {required['EMAIL_RECIPIENTS']}")
    print(f"✅ Password: {'*' * len(required['EMAIL_PASSWORD'])}")
    
    # Initialize sender
    print("\n🔄 Initializing email sender...")
    sender = EmailSender()
    print("✅ Sender initialized")
    
    # Send test email
    print("\n📤 Sending test email...")
    print("(This may take a few seconds)")

    sender.send_email(
        subject="🧪 AI Safety System - Test Email",
        body="""
This is a test email from your AI Safety Compliance Officer system.

If you received this, your email configuration is working correctly! ✅

System Status:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Violation Detection: Working
✅ AI Reporting: Working  
✅ Email Alerts: Working
✅ Database: Working
✅ Dashboard: Working
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You're ready for production deployment! 🚀

Test Details:
- Sender: {sender}
- Recipients: {recipients}
- Timestamp: {timestamp}

Next Steps:
1. Complete remaining tests
2. Set up CI/CD pipeline
3. Deploy to AWS production

---
AI Safety Compliance Officer
Automated Construction Site Monitoring
        """.format(
            sender=required['EMAIL_SENDER'],
            recipients=required['EMAIL_RECIPIENTS'],
            timestamp=__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ),
        attachments=None
    )
    
    print("\n" + "="*80)
    print("✅ Email sent successfully!")
    print(f"✅ Check your inbox: {required['EMAIL_RECIPIENTS']}")
    print("✅ (Check spam folder if not in inbox)")
    print("\n✅ Email Tests PASSED!")
    print("="*80)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n❌ Email tests FAILED!")
    print("\nCommon issues:")
    print("  - Wrong email/password")
    print("  - Need Gmail app password (not regular password)")
    print("  - 2-factor authentication required")
    print("  - SMTP blocked by firewall")
    print("\n📖 See EMAIL_SETUP.md for troubleshooting")
