"""
Complete test with actual report generation for detected violations
"""

import cv2
from violation_detector import ViolationDetector
from compliance_agent import ComplianceAgent
from pdf_generator import PDFGenerator
from email_sender import EmailSender
from database import Database
import config
from datetime import datetime

print("="*80)
print("FULL VIOLATION PROCESSING TEST - WITH REPORTS")
print("="*80)

# Initialize components
detector = ViolationDetector()
agent = ComplianceAgent()
pdf_generator = PDFGenerator()
email_sender = EmailSender()
database = Database()

# Open video
video_path = "static/test_video.webm"
cap = cv2.VideoCapture(video_path)

print(f"\n📹 Processing: {video_path}")
print(f"🎯 Confidence Threshold: {config.CONFIDENCE_THRESHOLD}")
print(f"⏰ Cooldown: {config.VIOLATION_COOLDOWN} seconds")
print("\n" + "="*80)

frame_count = 0
violations_processed = 0
all_violations = []

while True:
    ret, frame = cap.read()
    
    if not ret:
        break
    
    frame_count += 1
    
    # Skip frames
    if frame_count % config.FRAME_SKIP != 0:
        continue
    
    # Detect violations
    violations = detector.detect_violations(frame)
    
    if violations:
        print(f"\n📍 Frame {frame_count}: Found {len(violations)} violation(s)")
        
        for v in violations:
            print(f"   🚨 {v['class_name']} - Confidence: {v['confidence']:.3f}")
            
            # Check if should report
            should_report = detector.should_report_violation(v)
            print(f"      Should report: {should_report}")
            
            if should_report:
                violations_processed += 1
                all_violations.append(v)
                
                print(f"      📸 Saving image...")
                image_path = detector.save_violation_image(frame, v)
                
                print(f"      📝 Generating AI report...")
                report_text = agent.generate_incident_report(v)
                
                print(f"      📄 Creating PDF...")
                pdf_path = pdf_generator.generate_pdf(v, report_text, image_path)
                
                # Send email
                email_sent = False
                if config.EMAIL_ENABLED and config.EMAIL_REPORT_MODE == "immediate":
                    print(f"      📧 Sending email...")
                    email_body = agent.generate_email_body(v, pdf_path)
                    email_sent = email_sender.send_violation_alert(v, pdf_path, email_body)
                    print(f"      {'✅' if email_sent else '❌'} Email {'sent' if email_sent else 'failed'}")
                
                # Log to database
                database.log_violation(v, image_path, pdf_path, email_sent)
                print(f"      💾 Logged to database")
                print(f"      ✅ COMPLETE - Report generated!")

cap.release()

# Summary
print("\n" + "="*80)
print("PROCESSING COMPLETE")
print("="*80)
print(f"📊 Frames processed: {frame_count // config.FRAME_SKIP}")
print(f"🚨 Violations processed: {violations_processed}")

if violations_processed > 0:
    print(f"\n✅ SUCCESS! Generated {violations_processed} violation report(s)")
    print(f"\n📂 Check these folders:")
    print(f"   • reports/ - PDF reports")
    print(f"   • violations/ - Evidence photos")
    
    print(f"\n📧 Email Status:")
    if config.EMAIL_ENABLED and config.EMAIL_REPORT_MODE == "immediate":
        print(f"   • Mode: Immediate")
        print(f"   • Recipients: {', '.join(config.EMAIL_RECIPIENTS)}")
        print(f"   • Check inbox for {violations_processed} alert(s)")
    else:
        print(f"   • Mode: Daily summary at {config.DAILY_REPORT_TIME}")
    
    print(f"\n🎯 For Supervisor Demo:")
    print(f"   1. Open the latest PDF in reports/ folder")
    print(f"   2. Show the violation image in violations/ folder")
    print(f"   3. Check your email for alerts")
    print(f"   4. Explain: '{violations_processed} violations detected and reported automatically'")
else:
    print(f"\n❌ No violations were processed")
    print(f"\nPossible reasons:")
    print(f"   1. Confidence threshold too high: {config.CONFIDENCE_THRESHOLD}")
    print(f"   2. Violations detected but filtered by cooldown logic")
    print(f"   3. Model needs better training for this video")
    
    print(f"\n💡 Try:")
    print(f"   • Lower threshold: Edit config.py CONFIDENCE_THRESHOLD to 0.25")
    print(f"   • Use demo: python demo_supervisor.py")

database.close()
print("\n" + "="*80)
