"""
Test Violation Detector (YOLOv8 Computer Vision)
"""
from violation_detector import ViolationDetector
import cv2
import os

print("👁️  Testing Violation Detector...")
print("="*80)

try:
    # Check if model exists
    if not os.path.exists('models/best.onnx'):
        print("❌ ERROR: Model file not found at models/best.onnx")
        print("You need to train or download the YOLOv8 model first.")
        exit(1)
    
    print("✅ Model file found")
    
    # Initialize detector
    print("\n🔄 Initializing detector...")
    detector = ViolationDetector()
    print("✅ Detector initialized")
    
    # Test with webcam
    print("\n📹 Opening webcam...")
    print("Instructions:")
    print("  - Stay in front of camera for 10 seconds")
    print("  - Try to trigger detection (remove helmet, vest, etc.)")
    print("  - Press 'q' to quit early")
    print("\nStarting in 3 seconds...")
    
    import time
    time.sleep(3)
    
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ ERROR: Cannot open webcam")
        print("Try a different camera index (1, 2, etc.)")
        exit(1)
    
    print("✅ Webcam opened")
    
    frame_count = 0
    violations_detected = 0
    detection_results = []
    
    while frame_count < 100:  # ~10 seconds at 10 FPS
        ret, frame = cap.read()
        if not ret:
            print("⚠️  Cannot read frame")
            break
        
        # Run detection
        violations = detector.detect_violations(frame)
        
        if violations:
            violations_detected += 1
            detection_results.append(violations)
            print(f"⚠️  Frame {frame_count}: {len(violations)} violation(s) detected")
            
            # Draw boxes
            for v in violations:
                x1, y1, x2, y2 = v['bbox']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                label = f"{v['class_name']} ({v['confidence']:.2f})"
                cv2.putText(frame, label, (x1, y1-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        # Show frame
        cv2.imshow('Violation Detection Test (Press Q to quit)', frame)
        
        if cv2.waitKey(100) & 0xFF == ord('q'):
            print("\n⚠️  Test stopped by user")
            break
        
        frame_count += 1
    
    cap.release()
    cv2.destroyAllWindows()
    
    print("\n" + "="*80)
    print(f"✅ Processed {frame_count} frames")
    print(f"✅ Violations detected in {violations_detected} frames")
    
    if detection_results:
        print("\n📊 Detection Summary:")
        violation_types = {}
        for result in detection_results:
            for v in result:
                vtype = v['class_name']
                violation_types[vtype] = violation_types.get(vtype, 0) + 1
        
        for vtype, count in violation_types.items():
            print(f"  - {vtype}: {count} times")
    
    print("\n✅ Detector Tests PASSED!")
    print("="*80)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n❌ Detector tests FAILED!")
