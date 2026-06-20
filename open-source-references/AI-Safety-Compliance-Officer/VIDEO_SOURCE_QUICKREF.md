# 🎥 Video Source Management - Quick Reference

## 📋 Summary

The Detection Service supports **multiple video input types** and can be deployed as **separate containers** for each camera. Each container is independent and reports to a shared SQS queue.

---

## 🚀 Deployment Patterns

### Pattern 1: Single Camera → Single Container

```yaml
# docker-compose.yml
detection-service:
  environment:
    - VIDEO_SOURCE=rtsp://camera-ip:554/stream
    - CAMERA_ID=main_camera
```

```bash
# Run command
docker run -e VIDEO_SOURCE="rtsp://192.168.1.100:554/stream" \
           -e CAMERA_ID="front_gate" \
           safety-detection:latest
```

---

### Pattern 2: Multiple Cameras → Multiple Containers

```yaml
# docker-compose.yml
services:
  camera1:
    image: safety-detection:latest
    environment:
      - VIDEO_SOURCE=rtsp://192.168.1.100:554/stream
      - CAMERA_ID=front_gate
      - SITE_LOCATION=Front Gate

  camera2:
    image: safety-detection:latest
    environment:
      - VIDEO_SOURCE=rtsp://192.168.1.101:554/stream
      - CAMERA_ID=loading_dock
      - SITE_LOCATION=Loading Dock

  camera3:
    image: safety-detection:latest
    environment:
      - VIDEO_SOURCE=rtsp://192.168.1.102:554/stream
      - CAMERA_ID=scaffolding
      - SITE_LOCATION=Scaffolding Area
```

```bash
# Scale up
docker-compose up --scale detection-service=3
```

---

## 📹 Video Source Types

| Type | Format | Example | Use Case |
|------|--------|---------|----------|
| **Webcam** | Integer | `0`, `1`, `2` | Local testing |
| **RTSP** | URL | `rtsp://user:pass@ip:554/stream` | IP cameras |
| **Video File** | Path | `/videos/test.mp4` | Testing/Demo |
| **HTTP Stream** | URL | `http://ip:8080/video` | MJPEG cameras |

---

## 🔧 Configuration via Environment Variables

```bash
# Core Settings
VIDEO_SOURCE=<source>          # Video input
CAMERA_ID=<identifier>         # Unique camera ID
SITE_LOCATION=<location>       # Physical location

# AWS Integration
SQS_QUEUE_URL=<url>           # Queue for violations
S3_BUCKET_NAME=<bucket>       # Storage for images

# Performance
FRAME_SKIP=30                 # Process every Nth frame
CONFIDENCE_THRESHOLD=0.5      # Min detection confidence
```

---

## 💡 Best Practices

### 1. **Use Unique Camera IDs**
```bash
CAMERA_ID=front_gate_cam1
CAMERA_ID=loading_dock_cam2
CAMERA_ID=scaffolding_cam3
```

### 2. **Organize S3 by Camera**
```
s3://bucket/violations/front_gate/20251130_143000_no_helmet.jpg
s3://bucket/violations/loading_dock/20251130_143015_no_vest.jpg
```

### 3. **Set Appropriate Frame Skip**
- Webcam: `FRAME_SKIP=15` (2 FPS)
- RTSP: `FRAME_SKIP=30` (1 FPS)
- Video File: `FRAME_SKIP=1` (all frames)

### 4. **Use Separate Volumes for Multi-Camera**
```yaml
volumes:
  - ./violations/camera1:/app/violations  # Camera 1
  - ./violations/camera2:/app/violations  # Camera 2
```

---

## 🐛 Common Issues & Solutions

### Issue 1: "Cannot open video source" (Webcam)
**Cause:** Docker on Windows can't access USB devices
**Solution:** Use RTSP relay or WSL2 USB passthrough

### Issue 2: RTSP connection timeout
**Cause:** Firewall or network issue
**Solution:** Test with `ffmpeg` first:
```bash
ffmpeg -i rtsp://your-camera-url -frames:v 1 test.jpg
```

### Issue 3: High CPU usage
**Cause:** Processing too many frames
**Solution:** Increase `FRAME_SKIP` to 30 or 60

### Issue 4: Multiple cameras overload
**Cause:** All containers on single machine
**Solution:** Distribute across multiple EC2 instances

---

## 📊 Resource Allocation

| Cameras | EC2 Instance | vCPU | Memory |
|---------|-------------|------|--------|
| 1 | t3.medium | 2 | 4 GB |
| 2-3 | t3.large | 2 | 8 GB |
| 4-6 | t3.xlarge | 4 | 16 GB |
| 7+ | Multiple instances | - | - |

---

## 🎯 Quick Commands

```bash
# Test webcam
docker run -e VIDEO_SOURCE=0 --device /dev/video0 safety-detection:latest

# Test RTSP
docker run -e VIDEO_SOURCE="rtsp://admin:pass@192.168.1.100:554/stream" \
           -e CAMERA_ID="test_camera" \
           safety-detection:latest

# Test video file
docker run -v "$(pwd)/videos:/videos" \
           -e VIDEO_SOURCE="/videos/test.mp4" \
           -e LOOP_VIDEO=true \
           safety-detection:latest

# Multiple cameras
docker-compose up camera1 camera2 camera3

# Scale dynamically
docker-compose up --scale detection-service=5
```

---

## 📚 Related Documentation

- `VIDEO_SOURCE_CONFIG.md` - Detailed configuration guide
- `DOCKER_DEPLOYMENT.md` - Full deployment guide
- `.env.examples` - Environment variable templates
- `docker-compose.yml` - Multi-camera setup examples

---

**Quick Start:** Copy `.env.examples` → `.env` → Edit `VIDEO_SOURCE` → Run `docker-compose up`
