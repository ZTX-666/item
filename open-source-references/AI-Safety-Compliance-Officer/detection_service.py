"""
Detection Service - Microservice Entry Point
Purpose: Continuously monitors video feed, detects violations, sends to SQS queue
Architecture: Producer service in event-driven architecture
"""

import cv2
import json
import time
import os
import boto3
from datetime import datetime
from violation_detector import ViolationDetector
import config

class DetectionService:
    """Microservice for PPE violation detection"""
    
    def __init__(self):
        """Initialize detection service with AWS integrations"""
        print("="*80)
        print("🚀 Detection Service - Initializing...")
        print("="*80)
        
        # Initialize detector
        self.detector = ViolationDetector()
        
        # AWS Configuration
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self.sqs_queue_url = os.getenv('SQS_QUEUE_URL')
        self.s3_bucket = os.getenv('S3_BUCKET_NAME', 'safety-violations')
        
        # Camera identification
        self.camera_id = os.getenv('CAMERA_ID', 'default_camera')
        self.site_location = os.getenv('SITE_LOCATION', config.SITE_LOCATION)
        
        # Initialize AWS clients
        self.sqs_client = boto3.client('sqs', region_name=self.aws_region)
        self.s3_client = boto3.client('s3', region_name=self.aws_region)
        
        # Video source configuration
        self.video_source = self._parse_video_source()
        
        # Statistics
        self.frame_count = 0
        self.violations_sent = 0
        
        print(f"✅ Detection service initialized")
        print(f"   Camera ID: {self.camera_id}")
        print(f"   Location: {self.site_location}")
        print(f"   Video source: {self.video_source}")
        print(f"   SQS Queue: {self.sqs_queue_url}")
        print(f"   S3 Bucket: {self.s3_bucket}")
        print(f"   AWS Region: {self.aws_region}")
        print("="*80 + "\n")
    
    def _parse_video_source(self):
        """
        Parse and validate video source from environment variable
        
        Returns:
            Parsed video source (int for webcam, str for RTSP/file)
        """
        video_source = os.getenv('VIDEO_SOURCE', config.VIDEO_SOURCE)
        
        # Check if it's a webcam index (0, 1, 2, etc.)
        if isinstance(video_source, str) and video_source.isdigit():
            source = int(video_source)
            print(f"📹 Video source type: Webcam (device {source})")
            return source
        
        # Check if it's an RTSP stream
        elif isinstance(video_source, str) and video_source.startswith('rtsp://'):
            print(f"📹 Video source type: RTSP Stream")
            # Hide credentials in logs
            safe_url = video_source.split('@')[-1] if '@' in video_source else video_source
            print(f"   URL: rtsp://***@{safe_url}")
            return video_source
        
        # Check if it's an HTTP stream
        elif isinstance(video_source, str) and (video_source.startswith('http://') or video_source.startswith('https://')):
            print(f"📹 Video source type: HTTP Stream")
            print(f"   URL: {video_source}")
            return video_source
        
        # Assume it's a file path
        else:
            print(f"📹 Video source type: Video File")
            print(f"   Path: {video_source}")
            return video_source
    
    def upload_to_s3(self, local_file_path, s3_key):
        """
        Upload file to S3
        
        Args:
            local_file_path: Local file path
            s3_key: S3 object key
            
        Returns:
            S3 URL of uploaded file
        """
        try:
            self.s3_client.upload_file(local_file_path, self.s3_bucket, s3_key)
            s3_url = f"https://{self.s3_bucket}.s3.{self.aws_region}.amazonaws.com/{s3_key}"
            print(f"✅ Uploaded to S3: {s3_url}")
            return s3_url
        except Exception as e:
            print(f"❌ S3 upload failed: {e}")
            return None
    
    def send_to_queue(self, violation, image_s3_url):
        """
        Send violation to SQS queue for processing by Agent Service
        
        Args:
            violation: Violation dictionary
            image_s3_url: S3 URL of violation image
        """
        try:
            # Prepare message payload with camera information
            message = {
                'timestamp': violation['timestamp'].isoformat(),
                'class_name': violation['class_name'],
                'description': violation['description'],
                'confidence': violation['confidence'],
                'osha_regulation': violation['osha_regulation'],
                'bbox': violation['bbox'],
                'image_s3_url': image_s3_url,
                'camera_id': self.camera_id,  # Add camera identification
                'site_location': self.site_location,  # Add specific location
                'site_name': config.SITE_NAME,
                'company_name': config.COMPANY_NAME
            }
            
            # Send to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.sqs_queue_url,
                MessageBody=json.dumps(message),
                MessageAttributes={
                    'ViolationType': {
                        'StringValue': violation['class_name'],
                        'DataType': 'String'
                    },
                    'Confidence': {
                        'StringValue': str(violation['confidence']),
                        'DataType': 'Number'
                    },
                    'CameraID': {
                        'StringValue': self.camera_id,
                        'DataType': 'String'
                    }
                }
            )
            
            print(f"✅ Sent to SQS queue: {response['MessageId']}")
            self.violations_sent += 1
            return True
            
        except Exception as e:
            print(f"❌ Failed to send to SQS: {e}")
            return False
    
    def process_violation(self, frame, violation):
        """
        Process detected violation: save image, upload to S3, send to queue
        
        Args:
            frame: OpenCV frame
            violation: Violation dictionary
        """
        print(f"\n{'='*80}")
        print(f"🚨 VIOLATION DETECTED: {violation['description']}")
        print(f"   Time: {violation['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Confidence: {violation['confidence']*100:.1f}%")
        print(f"{'='*80}")
        
        # Save violation image locally
        image_path = self.detector.save_violation_image(frame, violation)
        
        # Upload to S3
        timestamp_str = violation['timestamp'].strftime("%Y%m%d_%H%M%S")
        s3_key = f"violations/{self.camera_id}/{timestamp_str}_{violation['class_name']}.jpg"
        image_s3_url = self.upload_to_s3(image_path, s3_key)
        
        # Send to SQS queue for Agent Service to process
        if image_s3_url:
            self.send_to_queue(violation, image_s3_url)
            print(f"✅ Violation queued for processing\n")
        else:
            print(f"❌ Failed to queue violation\n")
    
    def run(self):
        """Main detection loop"""
        # Configure OpenCV video capture based on source type
        cap = cv2.VideoCapture(self.video_source)
        
        # RTSP stream optimization
        if isinstance(self.video_source, str) and self.video_source.startswith('rtsp://'):
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffering for real-time
            cap.set(cv2.CAP_PROP_FPS, 30)
            print("📡 RTSP stream optimizations applied")
        
        if not cap.isOpened():
            print(f"❌ Cannot open video source: {self.video_source}")
            print("\n🔍 Troubleshooting:")
            print("   • For webcam: Ensure device is connected and not in use")
            print("   • For RTSP: Check network connectivity and credentials")
            print("   • For file: Verify file exists and is readable")
            return
        
        print("="*80)
        print("🎥 DETECTION SERVICE STARTED")
        print("="*80)
        print(f"Camera ID: {self.camera_id}")
        print(f"Monitoring: {config.SITE_NAME}")
        print(f"Location: {self.site_location}")
        print(f"Press Ctrl+C to stop")
        print("="*80 + "\n")
        
        try:
            while True:
                ret, frame = cap.read()
                
                if not ret:
                    print("⚠️  Cannot read frame from video source")
                    
                    # For video files, optionally loop
                    if isinstance(self.video_source, str) and not self.video_source.startswith(('rtsp://', 'http://')):
                        if os.getenv('LOOP_VIDEO', 'false').lower() == 'true':
                            print("🔄 Restarting video file...")
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                    
                    print("🛑 End of video or stream error")
                    break
                
                self.frame_count += 1
                
                # Skip frames for performance
                if self.frame_count % config.FRAME_SKIP != 0:
                    continue
                
                # Detect violations
                violations = self.detector.detect_violations(frame)
                
                if violations:
                    for violation in violations:
                        if self.detector.should_report_violation(violation):
                            self.process_violation(frame, violation)
                
                # Log statistics every 100 processed frames
                if self.frame_count % (config.FRAME_SKIP * 100) == 0:
                    print(f"📊 Stats [{self.camera_id}]: Frames={self.frame_count}, "
                          f"Violations Sent={self.violations_sent}")
        
        except KeyboardInterrupt:
            print(f"\n🛑 Detection service [{self.camera_id}] stopped by user")
        
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            cap.release()
            print(f"\n📊 Final Stats [{self.camera_id}]:")
            print(f"   Frames processed: {self.frame_count}")
            print(f"   Violations sent to queue: {self.violations_sent}")


def main():
    """Entry point for Detection Service"""
    service = DetectionService()
    service.run()


if __name__ == "__main__":
    main()
