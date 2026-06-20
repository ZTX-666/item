"""
Detailed frame-by-frame analysis to debug why violations aren't detected
Shows ALL detections with confidence scores
"""

import cv2
from violation_detector import ViolationDetector
import config

print("="*80)
print("DETAILED VIOLATION DETECTION ANALYSIS")
print("="*80)

# Initialize detector
detector = ViolationDetector()

# Open video
video_path = "static/test_video.webm"
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print(f"❌ Error: Cannot open video: {video_path}")
    exit(1)

print(f"\n📹 Video: {video_path}")
print(f"🎯 Confidence Threshold: {config.CONFIDENCE_THRESHOLD}")
print(f"🔍 Looking for violation classes: {list(config.VIOLATION_CLASSES.keys())}")
print(f"📊 Model classes: {detector.class_names}")
print("\n" + "="*80)
print("FRAME-BY-FRAME ANALYSIS")
print("="*80)

frame_count = 0
violation_detections = []
safety_equipment_detections = []

while True:
    ret, frame = cap.read()
    
    if not ret:
        break
    
    frame_count += 1
    
    # Check every 10 frames for detailed analysis
    if frame_count % 10 != 0:
        continue
    
    print(f"\n📍 Frame {frame_count}:")
    print("-" * 60)
    
    # Get raw model results
    results = detector.model(frame, conf=0.3, verbose=False)  # Lower threshold to see everything
    
    found_anything = False
    frame_objects = []
    
    for r in results:
        boxes = r.boxes
        for box in boxes:
            class_id = int(box.cls[0])
            class_name = detector.class_names[class_id]
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0]
            
            frame_objects.append({
                'class': class_name,
                'conf': confidence,
                'bbox': (int(x1), int(y1), int(x2), int(y2))
            })
            
            # Categorize detections
            is_violation = class_name in config.VIOLATION_CLASSES
            
            if is_violation:
                print(f"   🚨 VIOLATION: {class_name} - Confidence: {confidence:.3f}")
                violation_detections.append({
                    'frame': frame_count,
                    'class': class_name,
                    'conf': confidence
                })
                found_anything = True
            else:
                # Show safety equipment and people
                if class_name in ['helmet', 'vest', 'goggles', 'gloves', 'boots', 'Person']:
                    print(f"   ✅ Safety: {class_name} - Confidence: {confidence:.3f}")
                    safety_equipment_detections.append({
                        'frame': frame_count,
                        'class': class_name,
                        'conf': confidence
                    })
                    found_anything = True
                else:
                    print(f"   ⚪ Other: {class_name} - Confidence: {confidence:.3f}")
    
    if not found_anything:
        print("   ⚪ No detections in this frame")
    
    # Also check what violation_detector.detect_violations() returns
    violations = detector.detect_violations(frame)
    if violations:
        print(f"\n   ⚠️  detect_violations() found {len(violations)} violation(s):")
        for v in violations:
            print(f"      - {v['class_name']}: {v['confidence']:.3f}")

cap.release()

# Summary
print("\n" + "="*80)
print("DETECTION SUMMARY")
print("="*80)

print(f"\n📊 Total frames analyzed: {frame_count // 10}")

if violation_detections:
    print(f"\n🚨 VIOLATION DETECTIONS: {len(violation_detections)}")
    violation_summary = {}
    for d in violation_detections:
        key = d['class']
        if key not in violation_summary:
            violation_summary[key] = []
        violation_summary[key].append(d['conf'])
    
    for vclass, confs in violation_summary.items():
        avg_conf = sum(confs) / len(confs)
        max_conf = max(confs)
        min_conf = min(confs)
        print(f"\n   {vclass}:")
        print(f"      • Count: {len(confs)} detections")
        print(f"      • Avg confidence: {avg_conf:.3f}")
        print(f"      • Max confidence: {max_conf:.3f}")
        print(f"      • Min confidence: {min_conf:.3f}")
        print(f"      • Above threshold ({config.CONFIDENCE_THRESHOLD}): {sum(1 for c in confs if c >= config.CONFIDENCE_THRESHOLD)}")
else:
    print(f"\n❌ NO VIOLATION DETECTIONS")
    print(f"   The model did not detect any of these classes: {list(config.VIOLATION_CLASSES.keys())}")

if safety_equipment_detections:
    print(f"\n✅ SAFETY EQUIPMENT DETECTIONS: {len(safety_equipment_detections)}")
    safety_summary = {}
    for d in safety_equipment_detections:
        key = d['class']
        if key not in safety_summary:
            safety_summary[key] = []
        safety_summary[key].append(d['conf'])
    
    for sclass, confs in sorted(safety_summary.items(), key=lambda x: len(x[1]), reverse=True):
        avg_conf = sum(confs) / len(confs)
        print(f"   • {sclass}: {len(confs)} detections (avg: {avg_conf:.3f})")

print("\n" + "="*80)
print("DIAGNOSIS")
print("="*80)

if not violation_detections:
    print("\n🔍 POSSIBLE REASONS FOR NO VIOLATIONS:")
    print("\n1. Video shows workers WITH proper PPE (compliant)")
    print("   → Model correctly detects 'helmet', 'vest' (positive classes)")
    print("   → Model does NOT detect 'no_helmet', 'no_vest' (violation classes)")
    print("   → This is CORRECT behavior - no violations to report!")
    
    print("\n2. Model architecture:")
    print("   → Your model has TWO types of classes:")
    print("      • Positive classes: helmet, vest, goggles, gloves, boots, Person")
    print("      • Negative classes: no_helmet, no_goggle, no_gloves, no_boots")
    
    print("\n3. Detection logic:")
    print("   → Model detects what IS present (helmet on head)")
    print("   → Model does NOT detect what is ABSENT (no helmet)")
    print("   → This requires different training approach")
    
    print("\n💡 RECOMMENDATION:")
    print("   If you can see helmet violations visually, the model needs to:")
    print("   a) Detect person without helmet as 'no_helmet' class, OR")
    print("   b) Use logic: IF person detected AND no helmet nearby THEN violation")
    
    print("\n📸 VISUAL CHECK:")
    print("   Let's extract frames to verify what you're seeing...")
    print("   Run: python -c \"import cv2; cap=cv2.VideoCapture('static/test_video.webm'); ")
    print("        ret,f=cap.read(); cv2.imwrite('frame_check.jpg', f); print('Saved frame_check.jpg')\"")

else:
    print(f"\n✅ Model detected {len(violation_detections)} violations")
    print(f"   Check if confidence threshold is too high:")
    print(f"   Current: {config.CONFIDENCE_THRESHOLD}")
    if violation_detections:
        max_viol_conf = max(d['conf'] for d in violation_detections)
        if max_viol_conf < config.CONFIDENCE_THRESHOLD:
            print(f"   ⚠️  WARNING: Highest violation confidence ({max_viol_conf:.3f}) is below threshold!")
            print(f"   → Lower threshold to {max_viol_conf - 0.05:.2f} to capture these violations")

print("\n" + "="*80)
