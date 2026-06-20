"""
Demo script optimized for short test video (9 seconds)
This will show detection capabilities even if no violations are present
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
print("AI SAFETY COMPLIANCE OFFICER - SHORT VIDEO DEMO")
print("="*80)
print(f"\nVideo: {config.VIDEO_SOURCE if hasattr(config, 'VIDEO_SOURCE') else 'static/test_video.webm'}")
print(f"Duration: ~9 seconds (~225 frames)")
print(f"Settings: FRAME_SKIP={config.FRAME_SKIP}, COOLDOWN={config.VIOLATION_COOLDOWN}s")
print(f"Expected frames to check: ~{225 // config.FRAME_SKIP}")
print("\n" + "="*80)

# Initialize components
print("\nInitializing components...")
detector = ViolationDetector()
agent = ComplianceAgent()
pdf_generator = PDFGenerator()
email_sender = EmailSender()
database = Database()
print("✅ Components initialized\n")

# Open video
video_path = "static/test_video.webm"
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print(f"❌ Error: Cannot open video: {video_path}")
    exit(1)

# Get video info
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
duration = total_frames / fps if fps > 0 else 0

print("="*80)
print("VIDEO INFORMATION")
print("="*80)
print(f"📹 File: {video_path}")
print(f"⏱️  FPS: {fps:.2f}")
print(f"📊 Total Frames: {total_frames}")
print(f"⏰ Duration: {duration:.2f} seconds")
print(f"🔍 Frames to check: ~{total_frames // config.FRAME_SKIP}")
print("="*80)

# Process video
frame_count = 0
frames_checked = 0
detections = []
violations_found = []

print("\n🎥 PROCESSING VIDEO...\n")

while True:
    ret, frame = cap.read()
    
    if not ret:
        break
    
    frame_count += 1
    
    # Skip frames based on config
    if frame_count % config.FRAME_SKIP != 0:
        continue
    
    frames_checked += 1
    print(f"Checking frame {frame_count}/{total_frames}...", end=" ")
    
    # Detect objects
    results = detector.model(frame, conf=config.CONFIDENCE_THRESHOLD, verbose=False)
    
    frame_detections = []
    for r in results:
        boxes = r.boxes
        for box in boxes:
            class_id = int(box.cls[0])
            class_name = detector.class_names[class_id]
            confidence = float(box.conf[0])
            frame_detections.append({
                'class_name': class_name,
                'confidence': confidence,
                'frame': frame_count
            })
    
    if frame_detections:
        print(f"✅ Found {len(frame_detections)} objects")
        detections.extend(frame_detections)
    else:
        print("⚪ No detections")
    
    # Check for violations
    violations = detector.detect_violations(frame)
    
    if violations:
        print(f"   🚨 VIOLATION DETECTED!")
        for v in violations:
            print(f"      - {v['class_name']} (confidence: {v['confidence']:.2f})")
            
            # Process violation
            if detector.should_report_violation(v):
                violations_found.append(v)
                
                # Save image
                image_path = detector.save_violation_image(frame, v)
                
                # Generate AI report
                print(f"      📝 Generating AI report...")
                report_text = agent.generate_incident_report(v)
                
                # Generate PDF
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

cap.release()

# Summary
print("\n" + "="*80)
print("PROCESSING COMPLETE - SUMMARY")
print("="*80)
print(f"📊 Statistics:")
print(f"   • Total frames: {frame_count}")
print(f"   • Frames checked: {frames_checked} (every {config.FRAME_SKIP} frames)")
print(f"   • Objects detected: {len(detections)}")
print(f"   • Violations found: {len(violations_found)}")

if detections:
    print(f"\n🔍 Detected Objects:")
    detection_summary = {}
    for d in detections:
        class_name = d['class_name']
        detection_summary[class_name] = detection_summary.get(class_name, 0) + 1
    
    for class_name, count in sorted(detection_summary.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {class_name}: {count} detections")

if violations_found:
    print(f"\n🚨 Processed Violations:")
    for i, v in enumerate(violations_found, 1):
        print(f"   {i}. {v['class_name']} - Confidence: {v['confidence']:.2f}")
        print(f"      Time: {v['timestamp'].strftime('%H:%M:%S')}")
    
    print(f"\n📂 Generated Files:")
    print(f"   • PDF Reports: Check reports/ folder")
    print(f"   • Evidence Photos: Check violations/ folder")
    print(f"   • Database: violations.db")
    
    if config.EMAIL_ENABLED and config.EMAIL_REPORT_MODE == "immediate":
        print(f"\n📧 Email Status:")
        print(f"   • Recipients: {', '.join(config.EMAIL_RECIPIENTS)}")
        print(f"   • Check inbox for violation alerts")
else:
    print(f"\n✅ Video Analysis Complete")
    print(f"   Note: No violations detected in this video")
    print(f"   This means workers are wearing proper PPE! ✅")
    print(f"\n💡 This video shows COMPLIANT workers (with helmets, vests)")
    print(f"   To test violation detection, use video with workers WITHOUT PPE")
    print(f"   Or run: python demo_supervisor.py (creates mock violation)")

# AI Usage Stats
ai_stats = agent.get_usage_stats()
print(f"\n🤖 AI Agent Usage:")
print(f"   • Reports generated: {ai_stats['total_reports']}")
print(f"   • GPT-4 tokens used: {ai_stats['total_tokens']:,}")

# Database stats
db_stats = database.get_violation_stats()
print(f"\n💾 Database:")
print(f"   • Total violations logged: {db_stats['total']}")

print("\n" + "="*80)
print("✅ SHORT VIDEO DEMO COMPLETE")
print("="*80)

if not violations_found:
    print("\n💡 RECOMMENDATION:")
    print("   Since this video has no violations, use:")
    print("   python demo_supervisor.py")
    print("   This creates a mock violation with full PDF + Email workflow")

database.close()
