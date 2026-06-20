"""
Speed Test Script - Compare different optimization settings
Run this to find the best configuration for your hardware
"""

import cv2
import time
import config
from violation_detector import ViolationDetector

def test_speed(detector, frame, num_runs=30):
    """Test detection speed"""
    times = []
    
    print(f"Running {num_runs} detections...")
    for i in range(num_runs):
        start = time.time()
        violations = detector.detect_violations(frame)
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"  Run {i+1}/{num_runs}: {elapsed*1000:.1f}ms - {len(violations)} violations", end='\r')
    
    print()  # New line
    avg_time = sum(times) / len(times)
    fps = 1.0 / avg_time
    
    return {
        'avg_time_ms': avg_time * 1000,
        'fps': fps,
        'min_time_ms': min(times) * 1000,
        'max_time_ms': max(times) * 1000
    }

def main():
    print("="*80)
    print("🚀 AI Safety Compliance Officer - Speed Test")
    print("="*80)
    print()
    
    # Get a test frame
    print("📹 Opening video source...")
    cap = cv2.VideoCapture(config.VIDEO_SOURCE)
    
    if not cap.isOpened():
        print("❌ Error: Cannot open video source")
        print("Using random test image instead...")
        import numpy as np
        frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
    else:
        ret, frame = cap.read()
        if not ret:
            print("❌ Error: Cannot read frame")
            return
        cap.release()
        print(f"✅ Got test frame: {frame.shape[1]}x{frame.shape[0]}")
    
    print()
    print("="*80)
    print("📊 CURRENT CONFIGURATION")
    print("="*80)
    print(f"Frame Skip: {config.FRAME_SKIP}")
    print(f"Resize Enabled: {config.RESIZE_FRAME}")
    if config.RESIZE_FRAME:
        print(f"Resize Resolution: {config.RESIZE_WIDTH}x{config.RESIZE_HEIGHT}")
    print(f"Max Detections: {config.MAX_DETECTIONS}")
    print(f"IoU Threshold: {config.IOU_THRESHOLD}")
    print(f"Confidence Threshold: {config.CONFIDENCE_THRESHOLD}")
    print()
    
    # Initialize detector
    print("🔄 Loading YOLO model...")
    detector = ViolationDetector()
    print()
    
    # Run speed test
    print("="*80)
    print("⚡ SPEED TEST - Running 30 detections...")
    print("="*80)
    results = test_speed(detector, frame, num_runs=30)
    
    print()
    print("="*80)
    print("📈 RESULTS")
    print("="*80)
    print(f"Average Detection Time: {results['avg_time_ms']:.1f}ms")
    print(f"Average FPS: {results['fps']:.2f}")
    print(f"Fastest Detection: {results['min_time_ms']:.1f}ms")
    print(f"Slowest Detection: {results['max_time_ms']:.1f}ms")
    print()
    
    # Performance rating
    if results['fps'] >= 15:
        rating = "🎉 EXCELLENT - Real-time performance!"
    elif results['fps'] >= 10:
        rating = "✅ GOOD - Suitable for monitoring"
    elif results['fps'] >= 5:
        rating = "⚠️  MODERATE - Consider more optimization"
    else:
        rating = "❌ SLOW - Apply more optimizations"
    
    print(f"Performance Rating: {rating}")
    print()
    
    # Recommendations
    print("="*80)
    print("💡 RECOMMENDATIONS")
    print("="*80)
    
    if results['fps'] < 10:
        print("\n🔧 To improve speed, try these in config.py:")
        print()
        if config.FRAME_SKIP < 60:
            print(f"   1. Increase FRAME_SKIP to 60 (currently {config.FRAME_SKIP})")
        if not config.RESIZE_FRAME:
            print("   2. Enable RESIZE_FRAME = True")
        if config.RESIZE_FRAME and config.RESIZE_WIDTH > 416:
            print(f"   3. Reduce RESIZE_WIDTH to 416 (currently {config.RESIZE_WIDTH})")
        if config.MAX_DETECTIONS > 30:
            print(f"   4. Reduce MAX_DETECTIONS to 30 (currently {config.MAX_DETECTIONS})")
        if config.CONFIDENCE_THRESHOLD < 0.6:
            print(f"   5. Increase CONFIDENCE_THRESHOLD to 0.6 (currently {config.CONFIDENCE_THRESHOLD})")
        print()
    elif results['fps'] >= 15:
        print("\n✨ Great performance! You can optionally:")
        print()
        if config.FRAME_SKIP > 15:
            print(f"   • Reduce FRAME_SKIP to {config.FRAME_SKIP // 2} for better detection")
        if config.RESIZE_FRAME and config.RESIZE_WIDTH < 640:
            print("   • Increase resolution to 640x480 for better accuracy")
        print()
    else:
        print("\n👍 Good performance! Your current settings are well balanced.")
        print()
    
    # Estimated real-world performance
    print("="*80)
    print("📊 ESTIMATED REAL-WORLD PERFORMANCE")
    print("="*80)
    effective_fps = results['fps'] / config.FRAME_SKIP
    print(f"With FRAME_SKIP={config.FRAME_SKIP}:")
    print(f"  • Processing Speed: {results['fps']:.2f} FPS")
    print(f"  • Effective Video FPS: ~{effective_fps:.2f} FPS")
    print(f"  • Frame Processing: Every {config.FRAME_SKIP} frames")
    
    # Time to process 1 hour of video
    frames_per_hour = 30 * 3600  # Assuming 30 FPS video
    processed_frames = frames_per_hour / config.FRAME_SKIP
    processing_time = processed_frames / results['fps']
    print(f"  • Time to process 1 hour of video: ~{processing_time/60:.1f} minutes")
    print()
    
    print("="*80)
    print("🎯 Test Complete!")
    print("="*80)
    print("\nNext steps:")
    print("1. Adjust settings in config.py based on recommendations")
    print("2. Run this test again to verify improvements")
    print("3. Start monitoring: python safety_monitor.py --source 0")
    print("="*80)

if __name__ == "__main__":
    main()
