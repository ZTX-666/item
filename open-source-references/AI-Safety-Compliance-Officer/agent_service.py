"""
Agent Service - Microservice Entry Point
Purpose: Consumes violations from SQS, generates AI reports, sends notifications
Architecture: Consumer service in event-driven architecture
"""

import json
import time
import os
import boto3
import requests
from datetime import datetime
from compliance_agent import ComplianceAgent
from pdf_generator import PDFGenerator
from email_sender import EmailSender
from database import Database
import config

class AgentService:
    """Microservice for AI report generation and notifications"""
    
    def __init__(self):
        """Initialize agent service with AWS integrations"""
        print("="*80)
        print("🤖 Agent Service - Initializing...")
        print("="*80)
        
        # Initialize components
        self.agent = ComplianceAgent()
        self.pdf_generator = PDFGenerator()
        self.email_sender = EmailSender()
        self.database = Database()
        
        # AWS Configuration
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self.sqs_queue_url = os.getenv('SQS_QUEUE_URL')
        self.s3_bucket = os.getenv('S3_BUCKET_NAME', 'safety-violations')
        
        # Initialize AWS clients
        self.sqs_client = boto3.client('sqs', region_name=self.aws_region)
        self.s3_client = boto3.client('s3', region_name=self.aws_region)
        
        # Statistics
        self.messages_processed = 0
        self.reports_generated = 0
        
        print(f"✅ Agent service initialized")
        print(f"   SQS Queue: {self.sqs_queue_url}")
        print(f"   S3 Bucket: {self.s3_bucket}")
        print(f"   Email Enabled: {config.EMAIL_ENABLED}")
        print("="*80 + "\n")
    
    def download_from_s3(self, s3_url, local_path):
        """
        Download file from S3
        
        Args:
            s3_url: S3 URL of file
            local_path: Local path to save file
            
        Returns:
            Boolean indicating success
        """
        try:
            # Extract S3 key from URL
            s3_key = s3_url.split(f"{self.s3_bucket}.s3.")[1].split(f"{self.aws_region}.amazonaws.com/")[1]
            
            # Download file
            self.s3_client.download_file(self.s3_bucket, s3_key, local_path)
            print(f"✅ Downloaded from S3: {local_path}")
            return True
        except Exception as e:
            print(f"❌ S3 download failed: {e}")
            return False
    
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
            print(f"✅ Uploaded report to S3: {s3_url}")
            return s3_url
        except Exception as e:
            print(f"❌ S3 upload failed: {e}")
            return None
    
    def process_violation_message(self, message):
        """
        Process a violation message from SQS queue
        
        Args:
            message: SQS message containing violation data
        """
        try:
            # Parse message body
            body = json.loads(message['Body'])
            
            print(f"\n{'='*80}")
            print(f"📨 Processing violation message")
            print(f"   Type: {body['class_name']}")
            print(f"   Time: {body['timestamp']}")
            print(f"   Confidence: {body['confidence']*100:.1f}%")
            print(f"{'='*80}")
            
            # Reconstruct violation object
            violation = {
                'timestamp': datetime.fromisoformat(body['timestamp']),
                'class_name': body['class_name'],
                'description': body['description'],
                'confidence': body['confidence'],
                'osha_regulation': body['osha_regulation'],
                'bbox': tuple(body['bbox'])
            }
            
            # Download violation image from S3
            image_s3_url = body['image_s3_url']
            local_image_path = f"violations/{os.path.basename(image_s3_url)}"
            
            if not self.download_from_s3(image_s3_url, local_image_path):
                print("⚠️  Proceeding without image")
                local_image_path = ""
            
            # Generate AI report
            print("📝 Generating AI incident report...")
            report_text = self.agent.generate_incident_report(violation)
            
            # Generate PDF
            print("📄 Creating PDF report...")
            pdf_path = self.pdf_generator.generate_pdf(violation, report_text, local_image_path)
            
            # Upload PDF to S3
            timestamp_str = violation['timestamp'].strftime("%Y%m%d_%H%M%S")
            pdf_s3_key = f"reports/{timestamp_str}_incident_report.pdf"
            pdf_s3_url = self.upload_to_s3(pdf_path, pdf_s3_key)
            
            # Send email notification (based on mode)
            email_sent = False
            if config.EMAIL_REPORT_MODE == "immediate":
                print("📧 Sending email notification...")
                email_body = self.agent.generate_email_body(violation, pdf_path)
                email_sent = self.email_sender.send_violation_alert(violation, pdf_path, email_body)
            else:
                print("📧 Email queued for daily summary")
            
            # Log to database
            print("💾 Logging to database...")
            self.database.log_violation(violation, image_s3_url, pdf_s3_url or pdf_path, email_sent)
            
            self.reports_generated += 1
            
            print(f"✅ Violation processed successfully!")
            print(f"   PDF: {pdf_s3_url or pdf_path}")
            print(f"   Email: {'Sent' if email_sent else 'Queued'}\n")
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing violation: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def poll_queue(self):
        """Poll SQS queue for violation messages"""
        print("="*80)
        print("🎧 AGENT SERVICE STARTED - Listening for violations...")
        print("="*80)
        print(f"Queue: {self.sqs_queue_url}")
        print(f"Press Ctrl+C to stop")
        print("="*80 + "\n")
        
        try:
            while True:
                # Receive messages from SQS
                response = self.sqs_client.receive_message(
                    QueueUrl=self.sqs_queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,  # Long polling
                    MessageAttributeNames=['All']
                )
                
                messages = response.get('Messages', [])
                
                if messages:
                    for message in messages:
                        self.messages_processed += 1
                        
                        # Process the violation
                        success = self.process_violation_message(message)
                        
                        # Delete message from queue if processed successfully
                        if success:
                            self.sqs_client.delete_message(
                                QueueUrl=self.sqs_queue_url,
                                ReceiptHandle=message['ReceiptHandle']
                            )
                            print("✅ Message deleted from queue")
                        else:
                            print("⚠️  Message will be retried")
                
                else:
                    # No messages, print heartbeat
                    print(f"💓 Waiting for violations... "
                          f"(Processed: {self.messages_processed}, "
                          f"Reports: {self.reports_generated})")
        
        except KeyboardInterrupt:
            print("\n🛑 Agent service stopped by user")
        
        finally:
            self.database.close()
            print(f"\n📊 Final Stats:")
            print(f"   Messages processed: {self.messages_processed}")
            print(f"   Reports generated: {self.reports_generated}")


def main():
    """Entry point for Agent Service"""
    service = AgentService()
    service.poll_queue()


if __name__ == "__main__":
    main()
