# 🏗️ AI Safety Compliance Officer - Project Structure

## 📁 Complete Directory Structure

```
AI Safety Compliance Officer/
│
├── 📄 Core Application Files (6 modules)
│   ├── safety_monitor.py          # Main monitoring application (entry point)
│   ├── violation_detector.py      # YOLOv11n detection wrapper
│   ├── compliance_agent.py        # LangChain AI agent for reports
│   ├── pdf_generator.py          # PDF report generation
│   ├── email_sender.py           # Email notification system
│   └── database.py               # SQLite database ORM
│
├── ⚙️ Configuration & Setup (4 files)
│   ├── config.py                 # Centralized configuration
│   ├── .env                      # Environment variables (secrets)
│   ├── .env.example              # Environment template
│   └── requirements.txt          # Python dependencies
│
├── 🧪 Testing & Utilities (4 files)
│   ├── test_system.py            # Full system test suite
│   ├── test_email.py             # Email configuration tester
│   ├── demo_report.py            # Demo report generator
│   ├── speed_test.py             # Performance benchmarking
│   └── setup.py                  # Automated setup script
│
├── 📚 Documentation (11 markdown files)
│   ├── README.md                 # Main project documentation
│   ├── GETTING_STARTED.md        # Quick start guide
│   ├── QUICKSTART.md             # 5-minute setup guide
│   ├── PROJECT_SUMMARY.md        # Technical overview
│   ├── EMAIL_SETUP.md            # Email configuration guide
│   ├── LANGSMITH_GUIDE.md        # LangSmith monitoring guide
│   ├── LANGSMITH_SETUP.md        # LangSmith quick setup
│   ├── SPEED_OPTIMIZATION.md     # CPU optimization guide
│   ├── CPU_OPTIMIZATION_SUMMARY.md # Performance summary
│   ├── EXAMPLE_REPORT.md         # Sample output report
│   └── FIX_APPLIED.md            # Bug fix documentation
│
├── 🤖 AI Models
│   └── models/
│       └── best.onnx             # Custom YOLOv11n PPE detection model (ONNX format)
│
├── 📊 Output Directories
│   ├── reports/                  # Generated PDF and TXT reports
│   │   ├── *_incident_report.pdf # PDF violation reports
│   │   └── demo_report_*.txt     # Text format reports
│   │
│   └── violations/               # Violation detection images
│       └── *_no_helmet.jpg       # Captured violation photos
│
├── 💾 Database
│   ├── violations.db             # Production violation logs
│   └── test_violations.db        # Test database
│
└── 🗑️ Others
    ├── .gitignore                # Git ignore rules
    └── __pycache__/              # Python cache files
```

---

## 🎯 Module Overview

### **1. safety_monitor.py** - Main Application
**Purpose:** Orchestrates the entire monitoring system

**Key Functions:**
- Video stream processing (webcam/file/RTSP)
- Real-time violation detection
- Coordinates all modules
- User interface (keyboard controls)
- Statistics display

**Usage:**
```bash
python safety_monitor.py --source 0              # Webcam
python safety_monitor.py --source video.mp4      # Video file
python safety_monitor.py --source rtsp://...     # RTSP stream
```

**Controls:**
- `s` - Show statistics
- `q` - Quit
- `ESC` - Exit

---

### **2. violation_detector.py** - Computer Vision
**Purpose:** YOLOv11n wrapper for PPE detection

**Features:**
- ONNX model inference
- CPU optimizations (5 techniques)
- Bounding box drawing
- Performance tracking
- Frame preprocessing

**Detects:**
- 🪖 No Helmet/Hard Hat
- 🦺 No Safety Vest
- 🥽 No Goggles
- 🧤 No Gloves
- 👢 No Safety Boots

**Optimizations:**
- Frame resizing (640x480)
- Limited detections (50 max)
- Higher IoU threshold (0.45)
- Disabled tracking
- Frame skipping support

---

### **3. compliance_agent.py** - AI Report Generator
**Purpose:** LangChain-powered OSHA report generation

**Features:**
- GPT-4 integration
- OSHA-compliant report format
- Context-aware recommendations
- LangSmith tracing
- Token usage tracking

**Report Sections:**
- Executive Summary
- Incident Details
- OSHA Regulation Citations
- Root Cause Analysis
- Corrective Actions
- Preventive Measures
- Compliance Requirements

**AI Provider:**
- Model: GPT-4 (or GPT-4o)
- Temperature: 0.3 (formal tone)
- Max Tokens: 2000

---

### **4. pdf_generator.py** - Document Creation
**Purpose:** Professional PDF report generation

**Features:**
- OSHA-compliant formatting
- Logo support
- Violation photos
- Multi-section layout
- Professional styling

**PDF Sections:**
1. Header with logo
2. Incident overview
3. Site information
4. Violation details with photos
5. AI-generated analysis
6. Footer with timestamp

**Libraries:**
- ReportLab for PDF generation
- PIL for image processing

---

### **5. email_sender.py** - Notification System
**Purpose:** SMTP email notifications

**Features:**
- Gmail/Outlook/Yahoo support
- PDF attachments
- HTML formatting
- Multiple recipients
- Error handling

**Email Types:**
1. **Violation Alerts**
   - Immediate notification
   - Subject: 🚨 URGENT: Safety Violation
   - Attached: PDF report + photos

2. **Daily Summary** (future)
   - End-of-day statistics
   - Aggregated violations
   - Trend analysis

---

### **6. database.py** - Data Persistence
**Purpose:** SQLite database for violation logs

**Schema:**
```sql
CREATE TABLE violations (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    violation_type VARCHAR(100),
    description TEXT,
    confidence FLOAT,
    site_name VARCHAR(200),
    site_location VARCHAR(200),
    osha_regulation VARCHAR(200),
    image_path VARCHAR(500),
    report_path VARCHAR(500),
    email_sent BOOLEAN,
    created_at DATETIME
)
```

**Features:**
- SQLAlchemy ORM
- Automatic table creation
- Query helpers
- Transaction management

---

## 📊 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     VIDEO INPUT SOURCES                      │
│         (Webcam / Video File / RTSP Stream)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   SAFETY_MONITOR.PY                          │
│              (Main Orchestration Layer)                      │
│  • Video capture & frame processing                         │
│  • User interface & controls                                │
│  • Statistics tracking                                      │
└────────────┬───────────────────────────────┬────────────────┘
             │                               │
             ▼                               ▼
┌────────────────────────┐    ┌─────────────────────────────┐
│  VIOLATION_DETECTOR.PY │    │     PERFORMANCE TRACKING    │
│   (Computer Vision)     │    │   • FPS calculation         │
│  • YOLOv11n inference  │    │   • Detection time stats    │
│  • Frame optimization   │    │   • Resource monitoring     │
│  • Bounding boxes      │    └─────────────────────────────┘
└────────────┬───────────┘
             │
             ▼
      [Violation Detected?]
             │
             ├─ NO → Continue monitoring
             │
             └─ YES ↓
                    │
┌───────────────────┴─────────────────────────────────────────┐
│                                                              │
▼                           ▼                          ▼       │
┌──────────────┐   ┌──────────────┐         ┌──────────────┐ │
│  DATABASE.PY │   │ COMPLIANCE_  │         │   Save Image │ │
│   (Storage)  │   │  AGENT.PY    │         │ to violations/│ │
│              │   │  (AI Agent)  │         │              │ │
│ • Log to DB  │   │              │         │ • Timestamp  │ │
│ • Query logs │   │ • GPT-4 call │         │ • Label type │ │
└──────────────┘   │ • OSHA report│         └──────────────┘ │
                   │ • LangSmith  │                          │
                   │   tracing    │                          │
                   └──────┬───────┘                          │
                          │                                   │
                          ▼                                   │
                 ┌──────────────┐                            │
                 │ PDF_GENERATOR│                            │
                 │    .PY       │                            │
                 │              │                            │
                 │ • Format PDF │                            │
                 │ • Add photos │                            │
                 │ • Save report│                            │
                 └──────┬───────┘                            │
                        │                                     │
                        ▼                                     │
                 ┌──────────────┐                            │
                 │ EMAIL_SENDER │                            │
                 │    .PY       │                            │
                 │              │                            │
                 │ • SMTP send  │                            │
                 │ • Attach PDF │                            │
                 │ • Multi recip│                            │
                 └──────────────┘                            │
                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Configuration Files

### **config.py**
Centralized configuration with categories:

1. **AI Configuration**
   - OpenAI API key
   - Model selection
   - LangSmith tracing

2. **Email Configuration**
   - SMTP settings
   - Credentials
   - Recipients

3. **Detection Configuration**
   - Confidence threshold
   - Model path
   - Video source

4. **CPU Optimization**
   - Frame skip rate
   - Resize dimensions
   - Detection limits
   - IoU threshold

5. **Site Configuration**
   - Site name/location
   - Company name
   - OSHA regulations

### **.env**
Sensitive credentials (never commit to git):
```env
OPENAI_API_KEY=sk-proj-...
LANGCHAIN_API_KEY=lsv2_pt_...
EMAIL_SENDER=your@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_RECIPIENTS=recipient@example.com
```

---

## 📦 Dependencies

### Core AI & ML
- `ultralytics` - YOLOv11n framework
- `onnx` + `onnxruntime` - Model inference
- `opencv-python` - Video processing
- `langchain` + `langchain-openai` - AI agent
- `openai` - GPT-4 API

### Monitoring & Observability
- `langsmith` - AI tracing & monitoring
- `langchain-core` - LangChain primitives

### Document Generation
- `reportlab` - PDF creation
- `Pillow` - Image processing

### Infrastructure
- `python-dotenv` - Environment variables
- `sqlalchemy` - Database ORM
- `flask` - Web interface (optional)

### Testing
- `pytest` - Unit testing (future)

---

## 🎮 Usage Examples

### 1. Basic Monitoring
```bash
# Monitor webcam
python safety_monitor.py --source 0

# Process video file
python safety_monitor.py --source demo.mp4

# Monitor RTSP stream
python safety_monitor.py --source rtsp://camera-ip/stream
```

### 2. Generate Demo Report
```bash
python demo_report.py
```

### 3. Test Email Configuration
```bash
python test_email.py
```

### 4. Performance Benchmark
```bash
python speed_test.py
```

### 5. Full System Test
```bash
python test_system.py
```

### 6. Setup Script
```bash
python setup.py
```

---

## 📈 Performance Stats

**Current Performance (CPU-optimized):**
- **Detection Speed:** 7.8 FPS (128ms per frame)
- **Accuracy:** 50% confidence threshold
- **Resolution:** 640x480 (resized from original)
- **Frame Skip:** Every 30th frame (1 FPS @ 30fps video)

**Optimization Impact:**
- Frame Resizing: **40% speed increase**
- Frame Skipping: **30x throughput**
- Limited Detections: **15% speed increase**
- Higher IoU: **10% speed increase**
- Disabled Tracking: **5% speed increase**

---

## 🗄️ Database Schema

### Violations Table
| Column           | Type    | Description                    |
|-----------------|---------|--------------------------------|
| id              | INTEGER | Primary key                    |
| timestamp       | DATETIME| When violation occurred        |
| violation_type  | VARCHAR | Type (no_helmet, no_vest, etc)|
| description     | TEXT    | Human-readable description     |
| confidence      | FLOAT   | Detection confidence (0-1)     |
| site_name       | VARCHAR | Construction site name         |
| site_location   | VARCHAR | Specific location on site      |
| osha_regulation | VARCHAR | Applicable OSHA regulation     |
| image_path      | VARCHAR | Path to violation photo        |
| report_path     | VARCHAR | Path to generated PDF          |
| email_sent      | BOOLEAN | Email notification sent?       |
| created_at      | DATETIME| Record creation time           |

---

## 🔐 Security Considerations

### Protected Files
- `.env` - Contains API keys and passwords
- `violations.db` - Contains violation records
- `violations/` - Contains worker photos
- `reports/` - Contains incident reports

### .gitignore Includes
```
.env
*.db
violations/
reports/
__pycache__/
models/*.onnx
```

### Best Practices
✅ Use environment variables for secrets  
✅ Use Gmail App Passwords (not regular passwords)  
✅ Rotate API keys periodically  
✅ Encrypt database in production  
✅ Secure RTSP stream credentials  
✅ Review report content before distribution  

---

## 🚀 Deployment Options

### 1. Local Development
```bash
python safety_monitor.py --source 0
```

### 2. Edge Device (Raspberry Pi, Jetson)
- Use ONNX model for efficiency
- Enable all CPU optimizations
- Consider lighter model (YOLOv8n)

### 3. Cloud Server
- Deploy with Docker
- Use GPU for faster inference
- Scale horizontally for multiple cameras

### 4. Web Application
```bash
python flaskapp.py  # (if created)
```

---

## 📊 Output Files

### Reports Directory
```
reports/
├── 20251129_145411_incident_report.pdf  # PDF report
├── demo_report_20251129_145411.txt      # Text format
└── ...
```

### Violations Directory
```
violations/
├── 20251129_145831_no_helmet.jpg        # Violation photo
├── 20251129_150657_no_helmet.jpg
└── ...
```

### Database
```
violations.db              # SQLite database
test_violations.db         # Test database
```

---

## 🎯 System Statistics

### Real-time Stats (Press 's')
- Total violations detected
- Violations by type
- Detection performance (FPS, avg time)
- AI usage (reports generated, tokens used)
- LangSmith status

### Database Queries
```python
from database import Database

db = Database()
# Get all violations today
violations = db.get_violations_by_date(date.today())

# Get violations by type
helmet_violations = db.get_violations_by_type("no_helmet")
```

---

## 🔄 Workflow Summary

1. **Video Input** → safety_monitor.py captures frames
2. **Detection** → violation_detector.py runs YOLOv8
3. **Validation** → Check confidence threshold & cooldown
4. **Storage** → Save image + log to database
5. **AI Analysis** → compliance_agent.py generates report
6. **PDF Creation** → pdf_generator.py formats document
7. **Notification** → email_sender.py sends alerts
8. **Monitoring** → LangSmith tracks AI performance

---

## 📚 Documentation Index

| File | Purpose |
|------|---------|
| README.md | Main project overview |
| GETTING_STARTED.md | Setup & installation guide |
| QUICKSTART.md | 5-minute quick start |
| EMAIL_SETUP.md | Email configuration |
| LANGSMITH_GUIDE.md | Monitoring setup |
| SPEED_OPTIMIZATION.md | CPU optimization guide |
| PROJECT_SUMMARY.md | Technical deep dive |
| EXAMPLE_REPORT.md | Sample output |

---

## 🎓 Learning Path

**For Users:**
1. Read QUICKSTART.md
2. Configure .env file
3. Run test_email.py
4. Run demo_report.py
5. Start safety_monitor.py

**For Developers:**
1. Read PROJECT_SUMMARY.md
2. Review module architecture
3. Check config.py settings
4. Run test_system.py
5. Modify & extend

---

**Total Files:** 28  
**Total Lines of Code:** ~2,500+  
**Total Documentation:** 11 markdown files  
**Total Tests:** 3 test scripts  

---

Generated: November 29, 2025  
Project: AI Safety Compliance Officer  
Version: 1.0.0
