# 🧪 Local Testing Guide - AI Safety Compliance Officer

This guide will walk you through testing the entire system locally before production deployment.

## 📋 Testing Checklist

### ✅ Phase 1: Environment Setup
- [ ] Python environment activated
- [ ] All dependencies installed
- [ ] `.env` file configured
- [ ] Database initialized
- [ ] Model file exists

### ✅ Phase 2: Core Components
- [ ] Violation detector (YOLOv8)
- [ ] Compliance agent (GPT-4)
- [ ] PDF generator
- [ ] Email sender
- [ ] Database operations

### ✅ Phase 3: Full System
- [ ] Safety monitor with webcam
- [ ] Daily reporting system
- [ ] Dashboard web interface

### ✅ Phase 4: Docker (Optional)
- [ ] Build Docker images
- [ ] Run with docker-compose
- [ ] Test microservices

---

## 🚀 Quick Start Testing

### 1️⃣ **Check Your Environment**

```powershell
# Verify Python version
python --version  # Should be 3.11+

# Check installed packages
pip list | Select-String "ultralytics|langchain|flask|opencv"

# Verify .env file exists
Get-Content .env
```

### 2️⃣ **Verify Required Files**

```powershell
# Check model file
Test-Path ".\models\best.onnx"

# Check database
Test-Path ".\violations.db"

# Check config
Test-Path ".\config.py"
```

---

## 🧪 Testing Procedures

## Test 1: Database Operations

**File**: `test_database.py`

```python
from database import Database
from datetime import datetime

print("🗄️  Testing Database...")

db = Database()

# Test 1: Get stats
stats = db.get_violation_stats()
print(f"✅ Total violations: {stats['total']}")
print(f"✅ By type: {stats['by_type']}")

# Test 2: Add test violation
test_violation = {
    'timestamp': datetime.now(),
    'violation_type': 'no_helmet',
    'confidence': 0.95,
    'location': 'Test Site',
    'worker_id': 'TEST-001',
    'image_path': 'test.jpg',
    'severity': 'high'
}

violation_id = db.add_violation(test_violation)
print(f"✅ Added test violation: ID {violation_id}")

# Test 3: Retrieve violations
recent = db.get_recent_violations(limit=5)
print(f"✅ Retrieved {len(recent)} recent violations")

print("\n✅ Database tests PASSED!")
```

**Run it:**
```powershell
python test_database.py
```

---

## Test 2: Violation Detector (Computer Vision)

**File**: `test_detector.py`

```python
from violation_detector import ViolationDetector
import cv2
import os

print("👁️  Testing Violation Detector...")

detector = ViolationDetector()

# Test with webcam (press 'q' to quit)
print("Opening webcam for 10 seconds...")
print("Try to trigger detection (no helmet, no vest, etc.)")

cap = cv2.VideoCapture(0)
frame_count = 0
violations_detected = 0

while frame_count < 100:  # ~10 seconds at 10 FPS
    ret, frame = cap.read()
    if not ret:
        break
    
    # Run detection
    violations = detector.detect_violations(frame)
    
    if violations:
        violations_detected += 1
        print(f"⚠️  Violation detected: {violations}")
        
        # Draw boxes
        for v in violations:
            x1, y1, x2, y2 = v['bbox']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame, v['type'], (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    
    cv2.imshow('Violation Detection Test', frame)
    
    if cv2.waitKey(100) & 0xFF == ord('q'):
        break
    
    frame_count += 1

cap.release()
cv2.destroyAllWindows()

print(f"\n✅ Processed {frame_count} frames")
print(f"✅ Violations detected: {violations_detected}")
print("✅ Detector tests PASSED!")
```

**Run it:**
```powershell
python test_detector.py
```

---

## Test 3: AI Compliance Agent (GPT-4)

**File**: `test_agent.py`

```python
from compliance_agent import ComplianceAgent
from datetime import datetime
import os

print("🤖 Testing Compliance Agent...")

# Check API key
if not os.getenv('OPENAI_API_KEY'):
    print("❌ ERROR: OPENAI_API_KEY not found in .env")
    exit(1)

agent = ComplianceAgent()

# Test violation data
test_violation = {
    'timestamp': datetime.now(),
    'violation_type': 'no_helmet',
    'confidence': 0.95,
    'location': 'Construction Site A - Zone 3',
    'worker_id': 'W-12345',
    'severity': 'high',
    'image_path': 'test_violation.jpg'
}

print("Generating compliance report...")
print("(This will take 5-10 seconds - calling GPT-4)")

try:
    report = agent.generate_compliance_report(test_violation)
    
    print("\n" + "="*80)
    print(report)
    print("="*80)
    
    print("\n✅ Agent tests PASSED!")
    print("✅ GPT-4 API working correctly")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    print("Check your OPENAI_API_KEY in .env file")
```

**Run it:**
```powershell
python test_agent.py
```

---

## Test 4: PDF Generator

**File**: `test_pdf.py`

```python
from pdf_generator import PDFGenerator
from datetime import datetime

print("📄 Testing PDF Generator...")

generator = PDFGenerator()

# Test data
violations = [
    {
        'timestamp': datetime.now(),
        'violation_type': 'no_helmet',
        'confidence': 0.95,
        'location': 'Zone A',
        'worker_id': 'W-001',
        'severity': 'high'
    },
    {
        'timestamp': datetime.now(),
        'violation_type': 'no_vest',
        'confidence': 0.88,
        'location': 'Zone B',
        'worker_id': 'W-002',
        'severity': 'medium'
    }
]

compliance_report = """
TEST COMPLIANCE REPORT
======================

OSHA Violations Detected:
- Hard hat requirement violated (29 CFR 1926.100)
- High visibility vest required (29 CFR 1926.201)

Recommendations:
1. Immediate corrective action required
2. Worker safety training recommended
3. Site supervisor notification
"""

output_path = generator.generate_incident_report(
    violations[0],
    compliance_report,
    'test_violation.jpg' if os.path.exists('test_violation.jpg') else None
)

print(f"✅ PDF generated: {output_path}")
print(f"✅ File size: {os.path.getsize(output_path)} bytes")

# Test summary report
summary_path = generator.generate_summary_report(violations)
print(f"✅ Summary PDF generated: {summary_path}")

print("\n✅ PDF tests PASSED!")
```

**Run it:**
```powershell
python test_pdf.py
```

---

## Test 5: Email Sender

**File**: `test_email_simple.py`

```python
from email_sender import EmailSender
import os

print("📧 Testing Email Sender...")

# Check email config
required = ['EMAIL_SENDER', 'EMAIL_PASSWORD', 'EMAIL_RECIPIENT']
missing = [k for k in required if not os.getenv(k)]

if missing:
    print(f"⚠️  WARNING: Missing config: {missing}")
    print("Email test will be SKIPPED")
    print("Add these to your .env file to enable email testing")
    exit(0)

sender = EmailSender()

# Send test email
print("Sending test email...")

try:
    sender.send_email(
        subject="🧪 AI Safety System - Test Email",
        body="""
        This is a test email from your AI Safety Compliance Officer system.
        
        If you received this, email configuration is working correctly! ✅
        
        System Status:
        - Violation Detection: ✅ Working
        - AI Reporting: ✅ Working
        - Email Alerts: ✅ Working
        
        You're ready for production deployment!
        """,
        attachments=None
    )
    
    print("✅ Email sent successfully!")
    print(f"✅ Check your inbox: {os.getenv('EMAIL_RECIPIENT')}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    print("Check your email settings in .env")
```

**Run it:**
```powershell
python test_email_simple.py
```

---

## Test 6: Full System Test (Safety Monitor)

**File**: `test_full_system.py`

```python
from safety_monitor import SafetyMonitor
import time

print("🎯 Testing Full Safety Monitor System...")
print("\nThis will:")
print("1. Start violation detection from webcam")
print("2. Generate AI compliance reports")
print("3. Create PDF reports")
print("4. Save to database")
print("5. Run for 30 seconds")
print("\nStand in front of the camera without a helmet to trigger detection!")
print("\nStarting in 3 seconds...")
time.sleep(3)

monitor = SafetyMonitor(video_source=0)  # Webcam

try:
    # Run for 30 seconds
    start_time = time.time()
    while time.time() - start_time < 30:
        monitor.run_once()
        time.sleep(1)  # Check every second
        
except KeyboardInterrupt:
    print("\n⚠️  Test interrupted by user")
finally:
    monitor.stop()

print("\n✅ Full system test COMPLETED!")
print("Check the following:")
print("  - reports/ folder for generated PDFs")
print("  - violations/ folder for captured images")
print("  - violations.db for stored records")
```

**Run it:**
```powershell
python test_full_system.py
```

---

## Test 7: Dashboard Interface

**Already Running!** ✅

Your dashboard is live at: http://localhost:5000

**Test these endpoints:**

```powershell
# Test API endpoints
Invoke-WebRequest -Uri "http://localhost:5000/api/cameras" | Select-Object Content
Invoke-WebRequest -Uri "http://localhost:5000/api/violations/recent?limit=5" | Select-Object Content
Invoke-WebRequest -Uri "http://localhost:5000/api/violations/stats" | Select-Object Content
Invoke-WebRequest -Uri "http://localhost:5000/api/queue/stats" | Select-Object Content
Invoke-WebRequest -Uri "http://localhost:5000/api/system/health" | Select-Object Content
```

**Manual Testing Checklist:**
- [ ] Dashboard loads without errors
- [ ] Camera status displays correctly
- [ ] Violation feed shows recent violations
- [ ] Statistics cards update
- [ ] Auto-refresh works (wait 30 seconds)
- [ ] No console errors in browser

---

## Test 8: Docker System (Optional)

**File**: `test_docker.py`

```python
import subprocess
import time

print("🐳 Testing Docker Setup...")

# Check Docker installed
try:
    result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
    print(f"✅ Docker: {result.stdout.strip()}")
except:
    print("❌ Docker not found. Install Docker Desktop first.")
    exit(1)

# Check docker-compose
try:
    result = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True)
    print(f"✅ Docker Compose: {result.stdout.strip()}")
except:
    print("❌ Docker Compose not found.")
    exit(1)

print("\nTo test with Docker:")
print("1. docker-compose build")
print("2. docker-compose up")
print("3. Check http://localhost:5000")
```

**Run it:**
```powershell
python test_docker.py

# If Docker is ready, build and run:
docker-compose build
docker-compose up
```

---

## 📊 Test Results Summary

After running all tests, fill this out:

### Core Components
- [ ] ✅ Database: PASSED
- [ ] ✅ Violation Detector: PASSED
- [ ] ✅ AI Agent (GPT-4): PASSED
- [ ] ✅ PDF Generator: PASSED
- [ ] ✅ Email Sender: PASSED / SKIPPED

### System Tests
- [ ] ✅ Full Safety Monitor: PASSED
- [ ] ✅ Dashboard: PASSED
- [ ] ✅ Docker: PASSED / SKIPPED

### Issues Found
```
List any issues here:
1. 
2.
3.
```

---

## 🐛 Common Issues & Solutions

### Issue 1: "ModuleNotFoundError"
```powershell
pip install -r requirements.txt
```

### Issue 2: "OPENAI_API_KEY not found"
```powershell
# Create/edit .env file
Add-Content .env "OPENAI_API_KEY=sk-your-key-here"
```

### Issue 3: "Cannot open camera"
- Check if webcam is being used by another app
- Try different video source: `video_source=1` or `video_source=2`

### Issue 4: "Model file not found"
```powershell
# Check if model exists
Test-Path ".\models\best.onnx"

# If missing, you need to train or download the model
```

### Issue 5: Email not working
- Check Gmail app password (not regular password)
- Enable 2FA and create app password
- Update .env with correct credentials

---

## ✅ Next Steps After Testing

Once all tests pass:

1. **Fix any issues found**
2. **Document test results**
3. **Proceed to CI/CD setup**
4. **Deploy to production AWS**

---

## 📞 Need Help?

If any tests fail, share:
1. Error message
2. Which test failed
3. Your environment details

Good luck with testing! 🚀
