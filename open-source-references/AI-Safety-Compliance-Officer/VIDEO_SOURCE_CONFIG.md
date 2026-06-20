# ===================================================================
# Video Source Configuration Guide for Docker
# ===================================================================
# This file explains how to configure different video sources
# when running the Detection Service in Docker containers
# ===================================================================

## 📹 Supported Video Sources

### 1. Webcam (USB Camera)
### 2. IP Camera (RTSP Stream)
### 3. Video File (MP4, AVI, etc.)
### 4. HTTP/HTTPS Stream
### 5. Multiple Cameras (Advanced)

---

## 🎥 Configuration Methods

### Method 1: Environment Variables (Recommended)

Set `VIDEO_SOURCE` environment variable when running container:

```bash
# Webcam (Device 0)
docker run -e VIDEO_SOURCE=0 safety-detection:latest

# RTSP Stream
docker run -e VIDEO_SOURCE="rtsp://admin:password@192.168.1.100:554/stream" safety-detection:latest

# Video File (mounted volume)
docker run -v /path/to/videos:/videos -e VIDEO_SOURCE="/videos/test.mp4" safety-detection:latest

# HTTP Stream
docker run -e VIDEO_SOURCE="http://example.com/stream.mjpg" safety-detection:latest
```

---

## 📋 Configuration Examples

### Example 1: Local Webcam (Linux/Mac)

**docker-compose.yml:**
```yaml
detection-service:
  build:
    context: .
    dockerfile: Dockerfile.detection
  environment:
    - VIDEO_SOURCE=0
  devices:
    - /dev/video0:/dev/video0  # Map webcam device
  privileged: true  # Required for device access
```

**Note:** Webcam access in Docker is **Linux/Mac only**. Windows requires WSL2 with USB passthrough.

---

### Example 2: RTSP IP Camera

**docker-compose.yml:**
```yaml
detection-service:
  build:
    context: .
    dockerfile: Dockerfile.detection
  environment:
    - VIDEO_SOURCE=rtsp://admin:password123@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0
  network_mode: bridge  # Ensure network access
```

**Common RTSP URL Formats:**
- **Hikvision:** `rtsp://username:password@ip:554/Streaming/Channels/101`
- **Dahua:** `rtsp://username:password@ip:554/cam/realmonitor?channel=1&subtype=0`
- **Axis:** `rtsp://username:password@ip:554/axis-media/media.amp`
- **Generic:** `rtsp://username:password@ip:554/stream`

---

### Example 3: Video File from Host Machine

**docker-compose.yml:**
```yaml
detection-service:
  build:
    context: .
    dockerfile: Dockerfile.detection
  environment:
    - VIDEO_SOURCE=/videos/construction_site.mp4
  volumes:
    - ./test_videos:/videos:ro  # Mount video directory as read-only
```

**Command Line:**
```bash
docker run -v "D:\Videos\test.mp4:/app/video.mp4" \
  -e VIDEO_SOURCE=/app/video.mp4 \
  safety-detection:latest
```

---

### Example 4: Multiple Cameras (Separate Containers)

**docker-compose.yml:**
```yaml
services:
  # Camera 1 - Front Gate
  detection-camera1:
    build:
      context: .
      dockerfile: Dockerfile.detection
    environment:
      - VIDEO_SOURCE=rtsp://192.168.1.100:554/stream
      - CAMERA_ID=front_gate
      - SITE_LOCATION=Front Gate
    restart: unless-stopped

  # Camera 2 - Loading Zone
  detection-camera2:
    build:
      context: .
      dockerfile: Dockerfile.detection
    environment:
      - VIDEO_SOURCE=rtsp://192.168.1.101:554/stream
      - CAMERA_ID=loading_zone
      - SITE_LOCATION=Loading Zone
    restart: unless-stopped

  # Camera 3 - Scaffolding Area
  detection-camera3:
    build:
      context: .
      dockerfile: Dockerfile.detection
    environment:
      - VIDEO_SOURCE=rtsp://192.168.1.102:554/stream
      - CAMERA_ID=scaffolding
      - SITE_LOCATION=Scaffolding Area
    restart: unless-stopped
```

---

## 🔧 Advanced Configuration

### Dynamic Video Source Selection

Create a configuration file to manage multiple sources:

**cameras.json:**
```json
{
  "cameras": [
    {
      "id": "camera_1",
      "name": "Front Gate",
      "source": "rtsp://192.168.1.100:554/stream",
      "enabled": true,
      "location": "Zone A - Entrance"
    },
    {
      "id": "camera_2",
      "name": "Loading Dock",
      "source": "rtsp://192.168.1.101:554/stream",
      "enabled": true,
      "location": "Zone B - Loading"
    },
    {
      "id": "camera_3",
      "name": "Scaffolding",
      "source": "rtsp://192.168.1.102:554/stream",
      "enabled": false,
      "location": "Zone C - Construction"
    }
  ]
}
```

Mount this file:
```yaml
volumes:
  - ./cameras.json:/app/cameras.json:ro
environment:
  - CAMERA_CONFIG=/app/cameras.json
```

---

## 🐛 Troubleshooting

### Issue 1: "Cannot open video source" in Docker

**Causes:**
- Webcam not accessible (Windows/WSL limitation)
- RTSP URL incorrect
- Network firewall blocking RTSP port
- Video file not mounted correctly

**Solutions:**
```bash
# Test RTSP stream from host first
ffmpeg -i rtsp://your-camera-url -frames:v 1 test.jpg

# Check if file is mounted
docker exec -it container_name ls /videos

# Check network connectivity
docker exec -it container_name ping camera-ip
```

---

### Issue 2: Webcam Access in Windows Docker

**Problem:** Docker on Windows cannot directly access USB webcams.

**Solutions:**

**Option A: Use WSL2 with USB Passthrough**
```bash
# Requires Windows 11 and USBIPD
# See: https://docs.microsoft.com/en-us/windows/wsl/connect-usb
```

**Option B: Use RTSP Relay (Recommended)**
1. Run OBS Studio or FFmpeg on Windows host to stream webcam
2. Use RTSP Server to expose stream
3. Point Docker to `rtsp://host.docker.internal:8554/stream`

**Option C: Use Host Network Mode**
```yaml
network_mode: host  # Not recommended for production
```

---

### Issue 3: RTSP Stream Buffering/Lag

**Solution:** Add OpenCV optimization flags

Update `detection_service.py`:
```python
cap = cv2.VideoCapture(self.video_source)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer
cap.set(cv2.CAP_PROP_FPS, 30)
```

---

## 🚀 Production Deployment Strategies

### Strategy 1: One Container Per Camera (Recommended)

**Pros:**
- Easy to scale
- Fault isolation (one camera failure doesn't affect others)
- Independent restarts

**Cons:**
- More resource usage
- More containers to manage

**Best For:** 2-10 cameras

---

### Strategy 2: Multi-Camera in Single Container

**Pros:**
- Fewer containers
- Lower resource overhead

**Cons:**
- Single point of failure
- Complex management

**Best For:** 1-3 cameras or testing

---

### Strategy 3: Kubernetes with Auto-Scaling

**For Large Deployments (10+ cameras):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: safety-detection
spec:
  replicas: 5  # One per camera
  template:
    spec:
      containers:
      - name: detection
        image: safety-detection:latest
        env:
        - name: VIDEO_SOURCE
          valueFrom:
            configMapKeyRef:
              name: camera-config
              key: camera_url
```

---

## 📝 Environment Variables Reference

| Variable | Example | Description |
|----------|---------|-------------|
| `VIDEO_SOURCE` | `0` or `rtsp://...` or `/videos/test.mp4` | Video input source |
| `CAMERA_ID` | `front_gate` | Unique camera identifier |
| `SITE_LOCATION` | `Zone A - Entrance` | Physical location description |
| `FRAME_SKIP` | `30` | Process every Nth frame (performance) |
| `CONFIDENCE_THRESHOLD` | `0.5` | Minimum detection confidence |
| `SQS_QUEUE_URL` | `https://sqs...` | AWS SQS queue URL |
| `S3_BUCKET_NAME` | `safety-violations` | S3 bucket for images |

---

## 🔒 Security Best Practices

### 1. Never Hardcode Credentials
**Bad:**
```bash
VIDEO_SOURCE=rtsp://admin:password123@192.168.1.100/stream
```

**Good:**
```bash
# Use secrets management
docker run --env-file secrets.env safety-detection:latest
```

**secrets.env:**
```
RTSP_USERNAME=admin
RTSP_PASSWORD=secure_password
CAMERA_IP=192.168.1.100
RTSP_PORT=554
RTSP_PATH=/stream
```

### 2. Use VPN/VPC for Remote Cameras
- Don't expose cameras directly to internet
- Use AWS VPN or Site-to-Site VPN

### 3. Use RTSP over TLS (RTSPS)
```
rtsps://username:password@camera:322/stream
```

---

## 📊 Performance Tuning by Source Type

### Webcam (USB)
```bash
VIDEO_SOURCE=0
FRAME_SKIP=15  # 30 FPS → 2 FPS processing
RESIZE_FRAME=true
RESIZE_WIDTH=640
RESIZE_HEIGHT=480
```

### RTSP Stream (Network Camera)
```bash
VIDEO_SOURCE=rtsp://...
FRAME_SKIP=30  # Handle network latency
RTSP_TRANSPORT=tcp  # More reliable than UDP
```

### Video File (Testing)
```bash
VIDEO_SOURCE=/videos/test.mp4
FRAME_SKIP=1  # Process every frame (offline)
LOOP_VIDEO=true  # Restart when finished
```

---

## 🎯 Quick Reference Commands

```bash
# Test with webcam (Linux/Mac)
docker run --device=/dev/video0 -e VIDEO_SOURCE=0 safety-detection:latest

# Test with RTSP
docker run -e VIDEO_SOURCE="rtsp://admin:pass@192.168.1.100:554/stream" safety-detection:latest

# Test with video file
docker run -v "$(pwd)/videos:/videos" -e VIDEO_SOURCE="/videos/test.mp4" safety-detection:latest

# Multiple cameras with docker-compose
docker-compose up --scale detection-service=3
```

---

**See Also:**
- `docker-compose.yml` - Example configurations
- `DOCKER_DEPLOYMENT.md` - Full deployment guide
- `detection_service.py` - Source code
