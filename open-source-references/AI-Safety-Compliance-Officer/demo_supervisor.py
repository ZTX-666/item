"""
Demo script for supervisor - Creates a mock violation report for demonstration
This will show the complete workflow: Detection → AI Report → PDF → Email
"""

from datetime import datetime
from violation_detector import ViolationDetector
from compliance_agent import ComplianceAgent
from pdf_generator import PDFGenerator
from email_sender import EmailSender
from database import Database
import cv2
import config

print("="*80)
print("AI SAFETY COMPLIANCE OFFICER - SUPERVISOR DEMO")
print("="*80)
print(f"\nSite: {config.SITE_NAME}")
print(f"Location: {config.SITE_LOCATION}")
print(f"Demo Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\nEmail Mode: {config.EMAIL_REPORT_MODE}")
print(f"Recipients: {', '.join(config.EMAIL_RECIPIENTS)}")
print("\n" + "="*80)

# Initialize components
print("\nInitializing system components...")
detector = ViolationDetector()
agent = ComplianceAgent()
pdf_generator = PDFGenerator()
email_sender = EmailSender()
database = Database()
print("✅ All components initialized")

# Create a mock violation for demonstration
print("\n" + "="*80)
print("SIMULATING VIOLATION DETECTION")
print("="*80)

violation = {
    'timestamp': datetime.now(),
    'class_name': 'no_helmet',
    'class_id': 7,
    'confidence': 0.95,
    'bbox': (100, 100, 300, 400),
    'description': config.VIOLATION_CLASSES['no_helmet'],
    'osha_regulation': config.OSHA_REGULATIONS['no_helmet']
}

print(f"\n🚨 VIOLATION DETECTED:")
print(f"   Type: {violation['description']}")
print(f"   Confidence: {violation['confidence']*100:.1f}%")
print(f"   Time: {violation['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   OSHA Regulation: {violation['osha_regulation']}")

# Capture a frame from webcam or use test video
print("\n📸 Capturing evidence photo...")
cap = cv2.VideoCapture(0)  # Try webcam first
ret, frame = cap.read()

if not ret:
    # If webcam fails, try test video
    print("   Webcam not available, using test video...")
    cap = cv2.VideoCapture("static/test_video.webm")
    ret, frame = cap.read()

if ret:
    # Save violation image
    image_path = detector.save_violation_image(frame, violation)
    print(f"   ✅ Evidence photo saved: {image_path}")
else:
    image_path = ""
    print("   ⚠️  Could not capture image, proceeding without photo")

cap.release()

# Generate AI incident report
print("\n📝 Generating AI incident report using GPT-4...")
report_text = agent.generate_incident_report(violation)
print("   ✅ AI report generated")
print(f"\n   Report Preview:")
print(f"   {'-'*76}")
# Show first 500 characters of report
preview = report_text[:500] + "..." if len(report_text) > 500 else report_text
for line in preview.split('\n'):
    print(f"   {line}")
print(f"   {'-'*76}")

# Generate PDF
print("\n📄 Creating PDF report...")
pdf_path = pdf_generator.generate_pdf(violation, report_text, image_path)
print(f"   ✅ PDF report created: {pdf_path}")

# Send email notification
email_sent = False
if config.EMAIL_ENABLED and config.EMAIL_REPORT_MODE == "immediate":
    print("\n📧 Sending email notification to site managers...")
    try:
        email_body = agent.generate_email_body(violation, pdf_path)
        email_sent = email_sender.send_violation_alert(violation, pdf_path, email_body)
        if email_sent:
            print(f"   ✅ Email sent successfully to: {', '.join(config.EMAIL_RECIPIENTS)}")
        else:
            print("   ❌ Email sending failed (check credentials in .env)")
    except Exception as e:
        print(f"   ❌ Email error: {e}")
else:
    print(f"\n📧 Email notification: Queued for daily summary at {config.DAILY_REPORT_TIME}")

# Log to database
print("\n💾 Logging violation to database...")
database.log_violation(violation, image_path, pdf_path, email_sent)
print("   ✅ Violation logged to database")

# Show final summary
print("\n" + "="*80)
print("DEMO COMPLETE - VIOLATION PROCESSING SUMMARY")
print("="*80)
print(f"✅ Violation detected and classified")
print(f"✅ Evidence photo captured and saved")
print(f"✅ AI-generated OSHA-compliant report created")
print(f"✅ Professional PDF report generated")
print(f"{'✅' if email_sent else '⏳'} Email notification {'sent' if email_sent else 'queued'}")
print(f"✅ Violation logged to database")
print("\n📂 Generated Files:")
print(f"   • Image: {image_path}")
print(f"   • PDF Report: {pdf_path}")
print(f"   • Database: {config.DATABASE_PATH}")

# Show database stats
print("\n📊 System Statistics:")
db_stats = database.get_violation_stats()
print(f"   • Total violations in database: {db_stats['total']}")
if db_stats['by_type']:
    print(f"   • Violations by type:")
    for vtype, count in db_stats['by_type'].items():
        print(f"     - {vtype}: {count}")

ai_stats = agent.get_usage_stats()
print(f"   • AI Reports generated: {ai_stats['total_reports']}")
print(f"   • GPT-4 tokens used: {ai_stats['total_tokens']:,}")
print(f"   • LangSmith monitoring: {'Enabled' if ai_stats['langsmith_enabled'] else 'Disabled'}")

print("\n" + "="*80)
print("✅ DEMONSTRATION SUCCESSFUL")
print("="*80)
print("\nNext Steps for Supervisor Review:")
print("1. Open the PDF report to see the OSHA-compliant documentation")
print("2. Check your email for the violation alert")
print("3. Review the violation image for visual evidence")
print("4. Check the database for violation history tracking")
print("\n" + "="*80)

database.close()
