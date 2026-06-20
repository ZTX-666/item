# 🚀 Quick Start Guide

## Installation

### 1. Install Dependencies
```bash
cd "AI Safety Compliance Officer"
pip install -r requirements.txt
```

### 2. Run Setup
```bash
python setup.py
```

### 3. Configure Environment
Edit `.env` file and add your credentials:

```env
OPENAI_API_KEY=sk-your-openai-api-key
EMAIL_SENDER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_RECIPIENTS=manager@company.com,safety@company.com
```

#### Getting API Keys:

**OpenAI API Key:**
1. Go to https://platform.openai.com/api-keys
2. Create new API key
3. Copy and paste into `.env`

**Gmail App Password:**
1. Go to https://myaccount.google.com/apppasswords
2. Generate new app password
3. Copy and paste into `.env` (not your regular password!)

### 4. Copy Model
Copy your custom-trained YOLOv11n PPE detection model:
```bash
# Copy from training project
copy "..\YOLOv11-PPE-Training\runs\detect\train\weights\best.onnx" "models\best.onnx"
```

**Note:** The model should be in ONNX format for optimized inference.

## Usage

### Run with Webcam
```bash
python safety_monitor.py --source 0
```

### Run with Video File
```bash
python safety_monitor.py --source "path/to/video.mp4"
```

### Run with IP Camera (RTSP)
```bash
python safety_monitor.py --source "rtsp://camera-ip:port/stream"
```

### View Configuration
```bash
python safety_monitor.py --config
```

## Controls

- **Press 'q'**: Quit monitoring
- **Press 's'**: Show statistics

## How It Works

1. **Detection**: Custom YOLOv11n analyzes CCTV frames for PPE violations
2. **AI Report**: GPT-4 generates OSHA-compliant incident report
3. **PDF Creation**: Professional PDF report with evidence screenshot
4. **Email Alert**: Automatic notification to site managers
5. **Database Logging**: All violations stored in SQLite database

## Output

The system generates:
- **PDF Reports**: `reports/YYYYMMDD_HHMMSS_incident_report.pdf`
- **Screenshots**: `violations/YYYYMMDD_HHMMSS_violation_type.jpg`
- **Database**: `violations.db` (SQLite)

## Troubleshooting

### "OPENAI_API_KEY not found"
- Make sure you created `.env` file from `.env.example`
- Add your OpenAI API key

### "Cannot open video source"
- Check camera is connected
- Try different camera index (0, 1, 2, etc.)
- Verify video file path is correct

### "Error sending email"
- Use App Password for Gmail, not regular password
- Enable "Less secure app access" if needed
- Check SMTP settings in config.py

### "Model not found"
- Copy best.onnx to models/ folder
- Check MODEL_PATH in config.py

## Testing Without Email

Edit `config.py` and set:
```python
EMAIL_ENABLED = False
```

The system will still generate reports and log violations, just won't send emails.

## Customization

### Change Monitored Violations
Edit `config.py`:
```python
VIOLATION_CLASSES = {
    "no_helmet": "Worker without hard hat",
    "no_vest": "Worker without safety vest",
    # Add more violations...
}
```

### Adjust Detection Sensitivity
Edit `config.py`:
```python
CONFIDENCE_THRESHOLD = 0.6  # Higher = more strict (0.0 to 1.0)
```

### Modify Report Cooldown
Edit `config.py`:
```python
VIOLATION_COOLDOWN = 300  # Seconds between same violation reports
```

## Example Output

When violation detected:
```
================================================================================
🚨 VIOLATION DETECTED: Worker without helmet
Time: 2025-11-29 14:02:35
Confidence: 94.5%
OSHA Regulation: 29 CFR 1926.100(a) - Head Protection
================================================================================

📝 Generating AI incident report...
📄 Creating PDF report...
📧 Sending email notification...
💾 Logging to database...

✅ Violation processed successfully!
   Report: reports/20251129_140235_incident_report.pdf
   Image: violations/20251129_140235_no_helmet.jpg
   Email: Sent
```

## Support

For issues or questions, check:
- README.md for detailed documentation
- config.py for all configuration options
- GitHub Issues for community support

Happy monitoring! 🦺👷‍♂️
