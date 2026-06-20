import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import config
import os

class EmailSender:
    """Send email notifications with PDF reports"""
    
    def __init__(self):
        """Initialize email sender"""
        if not config.EMAIL_ENABLED:
            print("Email notifications are disabled in config")
            return
        
        if not config.EMAIL_SENDER or not config.EMAIL_PASSWORD:
            print("Warning: Email credentials not configured")
    
    def send_violation_alert(self, violation, pdf_path, email_body):
        """
        Send violation alert email with PDF attachment
        
        Args:
            violation: Violation dictionary
            pdf_path: Path to PDF report
            email_body: Email body text
            
        Returns:
            Boolean indicating success
        """
        if not config.EMAIL_ENABLED:
            print("Email disabled. Skipping notification.")
            return False
        
        if not config.EMAIL_RECIPIENTS:
            print("No email recipients configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = config.EMAIL_SENDER
            msg['To'] = ', '.join(config.EMAIL_RECIPIENTS)
            msg['Subject'] = f"🚨 URGENT: Safety Violation Detected - {violation['description']}"
            
            # Add body
            msg.attach(MIMEText(email_body, 'plain'))
            
            # Attach PDF report
            if os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as pdf_file:
                    pdf_attachment = MIMEApplication(pdf_file.read(), _subtype='pdf')
                    pdf_attachment.add_header(
                        'Content-Disposition',
                        'attachment',
                        filename=os.path.basename(pdf_path)
                    )
                    msg.attach(pdf_attachment)
            
            # Connect to SMTP server and send
            print(f"Connecting to {config.SMTP_SERVER}...")
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            server.starttls()
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            
            print(f"Sending email to {config.EMAIL_RECIPIENTS}...")
            server.send_message(msg)
            server.quit()
            
            print("✅ Email sent successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            print("Tip: For Gmail, use App Password instead of regular password")
            print("Generate at: https://myaccount.google.com/apppasswords")
            return False
    
    def send_daily_summary(self, pdf_path, violations_count):
        """
        Send daily summary report
        
        Args:
            pdf_path: Path to summary PDF
            violations_count: Total violations for the day
            
        Returns:
            Boolean indicating success
        """
        if not config.EMAIL_ENABLED or not config.EMAIL_RECIPIENTS:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = config.EMAIL_SENDER
            msg['To'] = ', '.join(config.EMAIL_RECIPIENTS)
            msg['Subject'] = f"Daily Safety Summary - {violations_count} Violations Detected"
            
            body = f"""
Daily Safety Compliance Summary

Site: {config.SITE_NAME}
Date: {config.datetime.now().strftime('%B %d, %Y')}

Total Violations Detected: {violations_count}

Please review the attached summary report for details.

This is an automated notification from the AI Safety Compliance Officer system.
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach PDF
            if os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as pdf_file:
                    pdf_attachment = MIMEApplication(pdf_file.read(), _subtype='pdf')
                    pdf_attachment.add_header(
                        'Content-Disposition',
                        'attachment',
                        filename=os.path.basename(pdf_path)
                    )
                    msg.attach(pdf_attachment)
            
            # Send
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            server.starttls()
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            print("Daily summary email sent!")
            return True
            
        except Exception as e:
            print(f"Error sending daily summary: {e}")
            return False
    
    def send_email(self, subject, body, attachments=None):
        """
        Send a generic email (useful for testing)
        
        Args:
            subject: Email subject line
            body: Email body text
            attachments: Optional list of file paths to attach
            
        Returns:
            Boolean indicating success
        """
        if not config.EMAIL_ENABLED or not config.EMAIL_RECIPIENTS:
            print("Email not configured")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = config.EMAIL_SENDER
            msg['To'] = ', '.join(config.EMAIL_RECIPIENTS)
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments if provided
            if attachments:
                for filepath in attachments:
                    if os.path.exists(filepath):
                        with open(filepath, 'rb') as f:
                            attachment = MIMEApplication(f.read())
                            attachment.add_header('Content-Disposition', 'attachment', 
                                                filename=os.path.basename(filepath))
                            msg.attach(attachment)
            
            # Send
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            server.starttls()
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
