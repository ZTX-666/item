#!/usr/bin/env python3
"""Quick test: ffmpeg RTMP capture"""
import subprocess, sys, os
from pathlib import Path

FFMPEG = "C:/Program Files/EVCapture/ffmpeg.exe"
OUTDIR = Path("C:/Users/User/WorkBuddy/2026-06-20-00-59-45/rtmp_test")
OUTDIR.mkdir(parents=True, exist_ok=True)

URLS = [
    ("cam-construction-01", "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_9_1?expire=1843920407&id=987542197595897856&c=122083786b&t=8a9e754865f7e8ab8b32a57afab11b5d23a50b80c394fefafa171e04b385cebe&ev=100"),
    ("cam-guard-01", "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_1_1?expire=1843920388&id=987542118474366976&c=122083786b&t=f1d6f039a568290ebf83e7a14cd8dd9cc0095ae6df76ae5e0f5816c1bbafb73c&ev=100"),
]

for cam_id, url in URLS:
    out = OUTDIR / f"{cam_id}.jpg"
    print(f"Testing {cam_id}...")
    try:
        result = subprocess.run(
            [FFMPEG, "-y", "-rtmp_live", "live", "-i", url, "-frames:v", "1", "-q:v", "2", str(out)],
            capture_output=True, text=True, timeout=30,
        )
        if out.exists() and out.stat().st_size > 1000:
            print(f"  SUCCESS: {out} ({out.stat().st_size} bytes)")
        else:
            print(f"  FAILED: {result.stderr[-300:] if result.stderr else 'no output'}")
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT")
    except Exception as e:
        print(f"  ERROR: {e}")
