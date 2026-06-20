"""
Full System Test - Safety Monitor
Tests the complete pipeline: Detection → AI → PDF → Database
"""
from safety_monitor import SafetyMonitor
import time
import os
import threading
from config import DAILY_REPORT_TIME, EMAIL_REPORT_MODE

print("🎯 Testing Full Safety Monitor System...")
print("="*80)

print("\nThis test will:")
print("  1. Start violation detection from webcam")
print("  2. Generate AI compliance reports (if violations found)")
print("  3. Create PDF reports")
print("  4. Save to database")
print("  5. Run for 30 seconds")
print("\n💡 TIP: Stand in front of camera without helmet to trigger detection!")
print("\nStarting in 3 seconds...")

time.sleep(3)

# Flag to stop the monitor
stop_flag = threading.Event()

def run_monitor_with_timeout(monitor, timeout_seconds):
    """Run monitor for a specific duration"""
    import cv2
    
    cap = cv2.VideoCapture(monitor.video_source)
    
    if not cap.isOpened():
        print(f"❌ Error: Cannot open video source")
        return
    
    print("✅ Video source opened")
    start_time = time.time()
    frames_processed = 0
    
    try:
        while time.time() - start_time < timeout_seconds and not stop_flag.is_set():
            ret, frame = cap.read()
            
            if not ret:
                print("⚠️  Cannot read frame")
                break
            
            # Detect violations
            violations = monitor.detector.detect_violations(frame)
            
            if violations:
                print(f"⚠️  Violation detected: {len(violations)} violation(s)")
                
                # Process each violation
                for violation in violations:
                    if monitor.detector.should_report_violation(violation):
                        # Save screenshot
                        image_path = monitor.detector.save_violation_image(frame, violation)
                        
                        # Generate report
                        report = monitor.agent.generate_incident_report(violation)
                        
                        # Generate PDF
                        pdf_path = monitor.pdf_generator.generate_pdf(violation, report, image_path)
                        
                        # Log to database
                        monitor.database.log_violation(violation, image_path, pdf_path, False)
                        
                        print(f"✅ Processed violation: {violation['class_name']}")
            
            frames_processed += 1
            
            # Show progress every 5 seconds
            elapsed = int(time.time() - start_time)
            if elapsed % 5 == 0 and elapsed > 0 and frames_processed % 50 == 0:
                print(f"⏱️  {elapsed}s elapsed, {timeout_seconds-elapsed}s remaining...")
            
            # Show frame (optional)
            cv2.imshow('Safety Monitor Test (Press Q to quit)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
    finally:
        cap.release()
        cv2.destroyAllWindows()
    
    return frames_processed

try:
    # Initialize monitor
    print("\n🔄 Initializing safety monitor...")
    monitor = SafetyMonitor(video_source=0)  # Webcam
    print("✅ Monitor initialized")
    
    # Check daily report time
    print(f"\n📅 Daily report configured for: {DAILY_REPORT_TIME}")
    print(f"📧 Email mode: {EMAIL_REPORT_MODE}")
    
    # Run for 30 seconds
    print("\n🎥 Starting detection...")
    print("Press Ctrl+C to stop early, or 'Q' in video window")
    
    frames_processed = run_monitor_with_timeout(monitor, 30)
    
    # Check results
    print("\n" + "="*80)
    print("📊 TEST RESULTS")
    print("="*80)
    
    print(f"✅ Frames processed: {frames_processed}")
    print(f"✅ Test duration: ~30 seconds")
    
    # Check generated files
    print("\n📁 Checking generated files...")
    
    if os.path.exists('reports'):
        reports = [f for f in os.listdir('reports') if f.endswith('.pdf')]
        print(f"✅ PDF reports: {len(reports)}")
    
    if os.path.exists('violations'):
        images = [f for f in os.listdir('violations') if f.endswith(('.jpg', '.png'))]
        print(f"✅ Violation images: {len(images)}")
    
    # Check database
    from database import Database
    db = Database()
    total = db.get_total_violations()
    print(f"✅ Database records: {total}")
    
    print("\n" + "="*80)
    print("✅ Full System Test COMPLETED!")
    print("="*80)
    
    print("\n📋 Verify the following:")
    print(f"  - reports/ folder: {os.path.abspath('reports')}")
    print(f"  - violations/ folder: {os.path.abspath('violations')}")
    print(f"  - violations.db: {os.path.abspath('violations.db')}")
    
except KeyboardInterrupt:
    print("\n\n⚠️  Test interrupted by user")
    stop_flag.set()
    print("✅ Test stopped cleanly")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n❌ Full system test FAILED!")
