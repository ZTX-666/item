# 🎛️ Camera Management Dashboard

## Overview

A real-time web-based dashboard for monitoring all detection services, violations, and system health across your AI Safety Compliance Officer deployment.

---

## 🌟 Features

### 📊 Real-Time Monitoring
- **Live Camera Status** - Monitor all cameras with online/offline indicators
- **Violation Feed** - Real-time stream of detected violations
- **System Health** - Database, SQS, S3 connectivity status
- **Queue Metrics** - Monitor SQS backlog and processing status

### 📈 Analytics
- **Daily Statistics** - Violations per day, per camera, per type
- **Camera Performance** - FPS, uptime, error rates
- **Alert System** - Automatic warnings for offline cameras or queue backlogs

### 🎨 Modern UI
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Auto-Refresh** - Updates every 30 seconds
- **Color-Coded Status** - Instant visual feedback
- **Gradient Design** - Professional, modern interface

---

## 🚀 Quick Start

### Method 1: Docker Compose (Recommended)

```bash
# Start dashboard with other services
docker-compose up dashboard-service

# Access dashboard
open http://localhost:5000
```

### Method 2: Standalone Docker

```bash
# Build image
docker build -f Dockerfile.dashboard -t safety-dashboard:latest .

# Run container
docker run -d \
  -p 5000:5000 \
  -e AWS_REGION=us-east-1 \
  -e SQS_QUEUE_URL=your-queue-url \
  -e S3_BUCKET_NAME=your-bucket \
  -v $(pwd)/cameras.json:/app/cameras.json:ro \
  safety-dashboard:latest

# Access dashboard
open http://localhost:5000
```

### Method 3: Local Development

```bash
# Install dependencies
pip install flask flask-cors boto3 sqlalchemy

# Run dashboard
python dashboard.py

# Access dashboard
open http://localhost:5000
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# AWS Configuration
AWS_REGION=us-east-1
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123/queue
S3_BUCKET_NAME=safety-violations
AWS_ACCESS_KEY_ID=your-key-id
AWS_SECRET_ACCESS_KEY=your-secret

# Database
DB_CONNECTION_STRING=sqlite:///violations.db
# Or PostgreSQL: postgresql://user:pass@host:5432/db

# Dashboard Settings
DASHBOARD_PORT=5000
FLASK_DEBUG=false
CAMERA_CONFIG=/app/cameras.json
```

### Camera Configuration File (`cameras.json`)

```json
{
  "cameras": [
    {
      "id": "front_gate",
      "name": "Front Gate Camera",
      "source": "rtsp://admin:password@192.168.1.100:554/stream",
      "enabled": true,
      "location": "Zone A - Main Entrance",
      "description": "Monitors main entrance for PPE compliance"
    },
    {
      "id": "loading_dock",
      "name": "Loading Dock Camera",
      "source": "rtsp://admin:password@192.168.1.101:554/stream",
      "enabled": true,
      "location": "Zone B - Loading Area",
      "description": "Monitors loading dock operations"
    }
  ],
  "settings": {
    "auto_refresh_interval": 30,
    "alerts_enabled": true,
    "daily_report_time": "18:00"
  }
}
```

---

## 📡 API Endpoints

The dashboard exposes a REST API that can be used by other applications:

### Camera Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cameras` | GET | List all cameras with status |
| `/api/camera/<camera_id>` | GET | Get details for specific camera |

**Example Response:**
```json
{
  "cameras": [
    {
      "id": "front_gate",
      "name": "Front Gate Camera",
      "location": "Zone A",
      "enabled": true,
      "status": true,
      "violation_count_today": 5,
      "last_violation": "2025-11-30T14:30:00"
    }
  ],
  "total": 3,
  "active": 2
}
```

### Violation Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/violations/recent?limit=20` | GET | Get recent violations |
| `/api/violations/stats` | GET | Get violation statistics |

**Example Response:**
```json
{
  "violations": [
    {
      "id": 123,
      "timestamp": "2025-11-30T14:30:00",
      "class_name": "no_helmet",
      "description": "Worker without hard hat/helmet",
      "confidence": 0.95,
      "osha_regulation": "29 CFR 1926.100(a)",
      "image_path": "s3://bucket/violations/...",
      "pdf_report_path": "s3://bucket/reports/..."
    }
  ],
  "count": 20
}
```

### System Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/queue/stats` | GET | Get SQS queue statistics |
| `/api/system/health` | GET | Get overall system health |
| `/api/alerts/active` | GET | Get active alerts |

---

## 🎨 Dashboard Sections

### 1. Statistics Cards (Top)
- **Total Cameras**: Number of registered cameras
- **Online Cameras**: Currently active cameras
- **Violations Today**: Total violations detected today
- **Queue Status**: Number of pending messages in SQS

### 2. Alerts Panel
- Displays warnings and errors
- Queue backlog alerts
- Offline camera notifications
- System health warnings

### 3. Camera Status Grid (Left)
- List of all cameras with:
  - Camera name and ID
  - Location
  - Online/Offline status
  - Violation count for today
- Color-coded status indicators
- Click for detailed view (future enhancement)

### 4. Recent Violations (Right)
- Real-time feed of violations
- Shows:
  - Violation type
  - Time detected
  - Confidence score
  - OSHA regulation
- Auto-scrolling list
- Time ago format (e.g., "5m ago")

---

## 🔧 Customization

### Change Refresh Interval

Edit `templates/dashboard.html`:
```javascript
// Change from 30 seconds to 10 seconds
setInterval(loadDashboard, 10000);
```

### Add Custom Styling

Create `static/custom.css`:
```css
.stat-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}
```

### Add New Metrics

Edit `dashboard.py`:
```python
@app.route('/api/custom/metric')
def get_custom_metric():
    # Your custom logic
    return jsonify({'metric': value})
```

---

## 📊 Monitoring & Alerts

### Alert Types

1. **Queue Backlog**: Triggers when SQS has >100 messages
2. **Camera Offline**: Triggers when camera stops sending data
3. **Database Error**: Triggers on connection failures
4. **S3 Error**: Triggers on upload failures

### Alert Thresholds

Configure in `dashboard.py`:
```python
QUEUE_BACKLOG_THRESHOLD = 100  # Messages
CAMERA_OFFLINE_THRESHOLD = 3600  # Seconds (1 hour)
```

---

## 🔒 Security

### Production Deployment Checklist

- [ ] Enable HTTPS/TLS
- [ ] Add authentication (OAuth, JWT, etc.)
- [ ] Restrict API access with API keys
- [ ] Use environment variables for secrets
- [ ] Enable CORS only for trusted origins
- [ ] Add rate limiting
- [ ] Enable audit logging

### Adding Basic Authentication

```python
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    # Add your authentication logic
    return username == 'admin' and password == 'secure_password'

@app.route('/')
@auth.login_required
def index():
    return render_template('dashboard.html')
```

---

## 🐛 Troubleshooting

### Issue 1: Dashboard shows "Loading..." indefinitely

**Cause:** API endpoints not responding
**Solution:**
```bash
# Check if services are running
docker-compose ps

# Check dashboard logs
docker logs safety-dashboard

# Test API directly
curl http://localhost:5000/api/cameras
```

### Issue 2: Cameras not showing

**Cause:** `cameras.json` not found or invalid
**Solution:**
```bash
# Verify file exists
ls cameras.json

# Validate JSON
python -m json.tool cameras.json

# Check Docker volume mount
docker exec safety-dashboard cat /app/cameras.json
```

### Issue 3: "Cannot connect to database"

**Cause:** Invalid `DB_CONNECTION_STRING`
**Solution:**
```bash
# For SQLite (local)
DB_CONNECTION_STRING=sqlite:///violations.db

# For PostgreSQL (production)
DB_CONNECTION_STRING=postgresql://user:pass@host:5432/dbname

# Test connection
python -c "from database import Database; db = Database(); print(db.get_total_violations())"
```

### Issue 4: High CPU usage

**Cause:** Too frequent API polling
**Solution:**
- Increase refresh interval to 60s
- Use WebSocket for real-time updates (future enhancement)
- Enable caching for API responses

---

## 📈 Performance Optimization

### Enable Caching

```python
from flask_caching import Cache

cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.route('/api/violations/stats')
@cache.cached(timeout=60)  # Cache for 60 seconds
def get_violation_stats():
    # ...existing code...
```

### Database Query Optimization

```python
# Add indexes to database
from sqlalchemy import Index

Index('idx_camera_timestamp', ViolationRecord.camera_id, ViolationRecord.timestamp)
```

---

## 🚀 Future Enhancements

### Phase 1 (Next Release)
- [ ] WebSocket support for real-time updates
- [ ] User authentication and role-based access
- [ ] Export reports to PDF/Excel
- [ ] Email alerts configuration UI
- [ ] Camera configuration management UI

### Phase 2
- [ ] Machine learning-based anomaly detection
- [ ] Predictive maintenance alerts
- [ ] Mobile app (React Native)
- [ ] Multi-site management
- [ ] Historical data visualization (charts)

### Phase 3
- [ ] Video playback integration
- [ ] Two-way camera control
- [ ] Advanced analytics dashboard
- [ ] Integration with OSHA reporting systems
- [ ] Compliance audit reports

---

## 📚 Related Documentation

- `DOCKER_DEPLOYMENT.md` - Docker deployment guide
- `VIDEO_SOURCE_CONFIG.md` - Camera configuration
- `cameras.json` - Camera registry
- `API_REFERENCE.md` - Full API documentation (future)

---

## 🤝 Contributing

To add new features to the dashboard:

1. Create a new API endpoint in `dashboard.py`
2. Update the frontend in `templates/dashboard.html`
3. Add tests (future)
4. Update this documentation

---

## 📞 Support

For issues or questions:
- Check troubleshooting section above
- Review logs: `docker logs safety-dashboard`
- Test API endpoints directly with curl/Postman
- Check network connectivity to AWS services

---

**Status:** ✅ Production Ready
**Version:** 1.0.0
**Last Updated:** November 30, 2025
