"""
Debug script to test violation detection on test_video.webm
"""

import cv2
from violation_detector import ViolationDetector
import config

# Initialize detector
print("Initializing detector...")
detector = ViolationDetector()

# Open video
video_path = "static/test_video.webm"
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print(f"Error: Cannot open video: {video_path}")
    exit(1)

print(f"Video opened successfully: {video_path}")
print(f"Confidence threshold: {config.CONFIDENCE_THRESHOLD}")
print(f"Violation classes: {list(config.VIOLATION_CLASSES.keys())}")
print("\nProcessing frames...\n")

frame_count = 0
violation_count = 0

while True:
    ret, frame = cap.read()
    
    if not ret:
        print("End of video")
        break
    
    frame_count += 1
    
    # Skip frames like in main system
    if frame_count % config.FRAME_SKIP != 0:
        continue
    
    # Detect violations
    violations = detector.detect_violations(frame)
    
    # Also check raw results to see what's being detected
    results = detector.model(frame, conf=config.CONFIDENCE_THRESHOLD, verbose=False)
    for r in results:
        boxes = r.boxes
        if len(boxes) > 0:
            print(f"Frame {frame_count}: Detected {len(boxes)} objects")
            for box in boxes:
                class_id = int(box.cls[0])
                class_name = detector.class_names[class_id]
                confidence = float(box.conf[0])
                print(f"  - Class: {class_name} (ID: {class_id}), Confidence: {confidence:.2f}")
    
    if violations:
        violation_count += len(violations)
        print(f"  --> Classified as {len(violations)} VIOLATION(S)")
        for v in violations:
            print(f"      * {v['class_name']}: {v['confidence']:.2f}")
            print(f"        Should report: {detector.should_report_violation(v)}")

cap.release()

print(f"\n{'='*60}")
print(f"Summary:")
print(f"  Total frames: {frame_count}")
print(f"  Frames processed: {frame_count // config.FRAME_SKIP}")
print(f"  Violations found: {violation_count}")
print(f"{'='*60}")
