"""
AI Safety Compliance Officer - Main Monitoring System

This system monitors construction sites for PPE violations and automatically
generates OSHA-compliant incident reports.
"""

import cv2
import argparse
import sys
from datetime import datetime
import config
from violation_detector import ViolationDetector
from compliance_agent import ComplianceAgent
from pdf_generator import PDFGenerator
from email_sender import EmailSender
from database import Database

class SafetyMonitor:
    """Main safety monitoring system"""
    
    def __init__(self, video_source=None):
        """
        Initialize the safety monitoring system
        
        Args:
            video_source: Video file path, RTSP URL, or camera index (default: webcam)
        """
        print("="*80)
        print("AI Safety Compliance Officer - Initializing...")
        print("="*80)
        
        # Initialize video source
        self.video_source = video_source if video_source is not None else config.VIDEO_SOURCE
        print(f"Video source: {self.video_source}")
        
        # Initialize components
        print("\nInitializing components...")
        try:
            self.detector = ViolationDetector()
            self.agent = ComplianceAgent()
            self.pdf_generator = PDFGenerator()
            self.email_sender = EmailSender()
            self.database = Database()
            print("✅ All components initialized successfully!\n")
        except Exception as e:
            print(f"❌ Error initializing components: {e}")
            print("Please check your configuration and API keys in .env file")
            sys.exit(1)
        
        # Statistics
        self.frame_count = 0
        self.violations_detected = 0
        self.violations_reported = 0
        self.last_report_date = None
    
    def process_violation(self, frame, violation):
        """
        Process a detected violation: generate report, send email, log to database
        
        Args:
            frame: OpenCV frame with violation
            violation: Violation dictionary
        """
        print(f"\n{'='*80}")
        print(f"🚨 VIOLATION DETECTED: {violation['description']}")
        print(f"Time: {violation['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Confidence: {violation['confidence']*100:.1f}%")
        print(f"OSHA Regulation: {violation['osha_regulation']}")
        print(f"{'='*80}\n")
        
        # Save violation image
        image_path = ""
        if config.SAVE_VIOLATION_IMAGES:
            image_path = self.detector.save_violation_image(frame, violation)
        
        # Generate AI incident report
        print("📝 Generating AI incident report...")
        report_text = self.agent.generate_incident_report(violation)
        
        # Generate PDF
        print("📄 Creating PDF report...")
        pdf_path = self.pdf_generator.generate_pdf(violation, report_text, image_path)
        
        # Send email notification (Only if immediate mode is enabled)
        email_sent = False
        if config.EMAIL_REPORT_MODE == "immediate":
            print("📧 Sending email notification...")
            email_body = self.agent.generate_email_body(violation, pdf_path)
            email_sent = self.email_sender.send_violation_alert(violation, pdf_path, email_body)
        else:
            print("📧 Email queued for daily summary.")
        
        # Log to database
        print("💾 Logging to database...")
        self.database.log_violation(violation, image_path, pdf_path, email_sent)
        
        self.violations_reported += 1
        
        print(f"\n✅ Violation processed successfully!")
        print(f"   Report: {pdf_path}")
        if image_path:
            print(f"   Image: {image_path}")
        if config.EMAIL_REPORT_MODE == "immediate":
            print(f"   Email: {'Sent' if email_sent else 'Failed or Disabled'}\n")
        else:
            print(f"   Email: Queued for {config.DAILY_REPORT_TIME}\n")

    def check_and_send_daily_report(self):
        """Check if it's time to send the daily report and send it if so"""
        if config.EMAIL_REPORT_MODE != "daily":
            return

        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        # Check if it's time to report and we haven't reported today yet
        if current_time == config.DAILY_REPORT_TIME and self.last_report_date != now.date():
            print(f"\n⏰ Time for daily report ({current_time})")
            self.send_daily_report()
            self.last_report_date = now.date()

    def send_daily_report(self):
        """Generate and send the daily summary report"""
        print("\n" + "="*80)
        print("📊 GENERATING DAILY SUMMARY REPORT")
        print("="*80)
        
        # Get today's violations from database
        today = datetime.now().date()
        violations = self.database.get_violations_by_date(today)
        
        if not violations:
            print("No violations detected today. Skipping report.")
            return

        print(f"Found {len(violations)} violations for today.")
        
        # Generate summary PDF
        summary_pdf_path = self.pdf_generator.generate_summary_report(violations)
        
        # Send email
        print("📧 Sending daily summary email...")
        success = self.email_sender.send_daily_summary(summary_pdf_path, len(violations))
        
        if success:
            print("✅ Daily summary sent successfully!")
        else:
            print("❌ Failed to send daily summary.")
        print("="*80 + "\n")

    def run(self):
        """Start the safety monitoring system"""
        # Open video source
        cap = cv2.VideoCapture(self.video_source)
        
        if not cap.isOpened():
            print(f"❌ Error: Cannot open video source: {self.video_source}")
            print("Please check:")
            print("  - File path is correct")
            print("  - Camera is connected (if using webcam)")
            print("  - RTSP URL is valid (if using IP camera)")
            sys.exit(1)
        
        print("="*80)
        print("🎥 MONITORING STARTED")
        print("="*80)
        print(f"Site: {config.SITE_NAME}")
        print(f"Location: {config.SITE_LOCATION}")
        print(f"Monitoring for violations: {', '.join(config.VIOLATION_CLASSES.keys())}")
        print("\nPress 'q' to quit, 's' to show statistics")
        print("="*80)
        
        try:
            while True:
                ret, frame = cap.read()
                
                if not ret:
                    print("End of video or cannot read frame")
                    break
                
                self.frame_count += 1
                
                # Skip frames for performance
                if self.frame_count % config.FRAME_SKIP != 0:
                    continue
                
                # Check for daily report time
                self.check_and_send_daily_report()

                # Detect violations
                violations = self.detector.detect_violations(frame)
                
                if violations:
                    self.violations_detected += len(violations)
                    
                    # Draw violations on frame
                    display_frame = self.detector.draw_violations(frame, violations)
                    
                    # Process each new violation
                    for violation in violations:
                        if self.detector.should_report_violation(violation):
                            self.process_violation(frame, violation)
                else:
                    display_frame = frame
                
                # Display frame
                cv2.imshow("AI Safety Compliance Officer - Live Monitoring", display_frame)
                
                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    print("\n🛑 Shutting down monitoring system...")
                    break
                elif key == ord('s'):
                    self.show_statistics()
        
        except KeyboardInterrupt:
            print("\n🛑 Monitoring interrupted by user")
        
        finally:
            # Cleanup
            cap.release()
            cv2.destroyAllWindows()
            self.database.close()
            
            # Final statistics
            print("\n" + "="*80)
            print("MONITORING SESSION SUMMARY")
            print("="*80)
            self.show_statistics()
            print("="*80)
            print("Thank you for using AI Safety Compliance Officer!")
            print("="*80)
    
    def show_statistics(self):
        """Display current statistics"""
        print(f"\n📊 STATISTICS")
        print(f"   Frames processed: {self.frame_count}")
        print(f"   Violations detected: {self.violations_detected}")
        print(f"   Reports generated: {self.violations_reported}")
        
        # Performance stats
        perf_stats = self.detector.get_performance_stats()
        if perf_stats:
            print(f"\n   ⚡ Performance:")
            print(f"     - Average FPS: {perf_stats['avg_fps']:.2f}")
            print(f"     - Avg detection time: {perf_stats['avg_time_ms']:.1f}ms")
            print(f"     - Total detections: {perf_stats['total_detections']}")
        
        # AI Agent Usage Stats
        ai_stats = self.agent.get_usage_stats()
        print(f"\n   🤖 AI Agent Usage:")
        print(f"     - Reports generated: {ai_stats['total_reports']}")
        print(f"     - Total tokens used: {ai_stats['total_tokens']:,}")
        if ai_stats['total_reports'] > 0:
            print(f"     - Avg tokens/report: {ai_stats['avg_tokens_per_report']:.0f}")
        print(f"     - LangSmith monitoring: {'✅ Enabled' if ai_stats['langsmith_enabled'] else '❌ Disabled'}")
        if ai_stats['langsmith_enabled']:
            print(f"     - View traces at: https://smith.langchain.com")
        
        # Database stats
        db_stats = self.database.get_violation_stats()
        print(f"\n   💾 Database:")
        print(f"     - Total violations: {db_stats['total']}")
        
        if db_stats['by_type']:
            print(f"\n   📋 Violations by type:")
            for vtype, count in db_stats['by_type'].items():
                print(f"     - {vtype}: {count}")
        
        # CPU Optimization Settings
        print(f"\n   ⚙️  CPU Optimizations:")
        print(f"     - Frame skip: Every {config.FRAME_SKIP} frames")
        print(f"     - Frame resize: {'Enabled' if config.RESIZE_FRAME else 'Disabled'}")
        if config.RESIZE_FRAME:
            print(f"     - Resolution: {config.RESIZE_WIDTH}x{config.RESIZE_HEIGHT}")
        print(f"     - Max detections: {config.MAX_DETECTIONS}")
        print(f"     - IoU threshold: {config.IOU_THRESHOLD}")
        print()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="AI Safety Compliance Officer - Automated PPE Violation Detection"
    )
    parser.add_argument(
        '--source',
        type=str,
        default=None,
        help='Video source: file path, RTSP URL, or camera index (0 for webcam)'
    )
    parser.add_argument(
        '--config',
        action='store_true',
        help='Show current configuration'
    )
    
    args = parser.parse_args()
    
    if args.config:
        print("\n" + "="*80)
        print("CURRENT CONFIGURATION")
        print("="*80)
        print(f"Site Name: {config.SITE_NAME}")
        print(f"Site Location: {config.SITE_LOCATION}")
        print(f"Company: {config.COMPANY_NAME}")
        print(f"Model Path: {config.MODEL_PATH}")
        print(f"Confidence Threshold: {config.CONFIDENCE_THRESHOLD}")
        print(f"Email Enabled: {config.EMAIL_ENABLED}")
        print(f"Email Recipients: {config.EMAIL_RECIPIENTS}")
        print(f"OpenAI Model: {config.OPENAI_MODEL}")
        print(f"Monitored Violations: {list(config.VIOLATION_CLASSES.keys())}")
        print("="*80 + "\n")
        return
    
    # Convert source to int if it's a digit (camera index)
    video_source = args.source
    if video_source and video_source.isdigit():
        video_source = int(video_source)
    
    # Create and run monitor
    monitor = SafetyMonitor(video_source)
    monitor.run()

if __name__ == "__main__":
    main()
