# AI Safety Compliance Officer (Construction Tech)

## Overview
An automated safety compliance system that monitors construction sites via CCTV, detects PPE violations using YOLOv11n (custom-trained), and automatically generates OSHA-compliant incident reports.

## Problem Statement
Small construction firms struggle with safety compliance paperwork:
- Daily safety reports are mandatory
- OSHA violations result in hefty fines
- Site managers are too busy for manual documentation
- Violations go unreported due to administrative burden

## Solution
Automated safety monitoring with intelligent report generation:
1. **Vision Layer**: Custom-trained YOLOv11n detects PPE violations in real-time
2. **Agent Layer**: LangChain + GPT-4 generates formal compliance reports
3. **Action Layer**: Automated email delivery to site managers

## Features
- ✅ Real-time PPE violation detection (helmet, vest, goggles, gloves, boots)
- ✅ Automatic timestamping and incident logging
- ✅ AI-generated OSHA-compliant incident reports
- ✅ PDF report generation with violation screenshots
- ✅ Automated email notifications
- ✅ Violation history tracking

## Tech Stack
- **Computer Vision**: YOLOv11n (custom-trained, exported to ONNX for inference)
- **AI Agent**: LangChain + OpenAI GPT-4
- **PDF Generation**: ReportLab
- **Email**: SMTP (Gmail/Outlook)
- **Backend**: Python, Flask (optional web interface)

## Project Structure
```
AI Safety Compliance Officer/
├── README.md
├── requirements.txt
├── config.py                    # Configuration (API keys, email settings)
├── safety_monitor.py            # Main monitoring system
├── violation_detector.py        # YOLO detection wrapper
├── compliance_agent.py          # LangChain agent for report generation
├── pdf_generator.py             # PDF report creation
├── email_sender.py              # Email notification system
├── database.py                  # SQLite for violation logging
├── models/
│   └── best.onnx               # PPE detection model
├── templates/
│   └── incident_report_template.txt
├── reports/                     # Generated PDF reports
└── violations/                  # Violation screenshots

```

## Installation
```bash
pip install -r requirements.txt
```

## Configuration
1. Copy `.env.example` to `.env`
2. Add your API keys:
   - OpenAI API key
   - Email credentials
3. Configure video source (CCTV URL or file path)

## Usage

### Basic Monitoring
```bash
python safety_monitor.py --source rtsp://camera-ip:port/stream
```

### Test with Video File
```bash
python safety_monitor.py --source test_video.mp4
```

### Web Interface (Optional)
```bash
python app.py
```

## How It Works

1. **Detection Phase**
   - CCTV feed analyzed frame-by-frame
   - Custom-trained YOLOv11n identifies workers and PPE items
   - Violations logged with timestamp and screenshot

2. **Agent Phase**
   - LangChain agent receives violation data
   - GPT-4 generates formal incident description
   - Legal language ensures OSHA compliance

3. **Report Phase**
   - PDF generated with violation details
   - Includes timestamp, location, screenshot, description
   - Formatted for official safety records

4. **Notification Phase**
   - Email sent to site manager
   - PDF report attached
   - Immediate violation alerts

## Example Output

**Detected Violation:**
```
Time: 2025-11-29 14:02:35
Location: Construction Site A - Zone 3
Violation: Worker without helmet
Confidence: 94.5%
```

**Generated Report:**
```
SAFETY INCIDENT REPORT

Date: November 29, 2025
Time: 14:02:35
Location: Construction Site A, Zone 3

INCIDENT DESCRIPTION:
At approximately 14:02 PM, surveillance footage captured an individual 
operating within the designated construction zone without proper head 
protection equipment. The worker was observed performing tasks in an 
active construction area where overhead hazards are present, in direct 
violation of OSHA Standard 1926.100(a) requiring the use of protective 
helmets in construction areas.

OSHA REGULATION VIOLATED:
29 CFR 1926.100(a) - Head Protection

RECOMMENDED ACTIONS:
1. Immediate safety briefing for affected worker
2. Review PPE compliance protocols
3. Additional signage in violation zone
4. Supervisor training reinforcement

Report generated automatically by AI Safety Compliance System
```

## License
MIT License

## Contact
Project by: Shezan
Repository: Computer-Vision
