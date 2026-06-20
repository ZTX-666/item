from ultralytics import YOLO
import cv2
import numpy as np
from datetime import datetime
import config

class ViolationDetector:
    """Wrapper for YOLO model to detect PPE violations"""
    
    def __init__(self, model_path=config.MODEL_PATH):
        """Initialize the YOLO model"""
        print(f"Loading model from {model_path}...")
        self.model = YOLO(model_path)
        self.class_names = self.model.names
        print(f"Model loaded. Classes: {self.class_names}")
        
        # Track recent violations to avoid spam
        self.recent_violations = {}
        
        # Performance stats
        self.total_detections = 0
        self.total_time = 0
        
    def detect_violations(self, frame):
        """
        Detect PPE violations in a frame with CPU optimizations
        
        Args:
            frame: OpenCV image frame
            
        Returns:
            List of violation dictionaries
        """
        import time
        start_time = time.time()
        
        violations = []
        
        # CPU OPTIMIZATION 1: Resize frame for faster processing
        original_frame = frame
        if config.RESIZE_FRAME:
            frame_resized = cv2.resize(frame, (config.RESIZE_WIDTH, config.RESIZE_HEIGHT))
            # Calculate scaling factors for bounding boxes
            scale_x = frame.shape[1] / config.RESIZE_WIDTH
            scale_y = frame.shape[0] / config.RESIZE_HEIGHT
        else:
            frame_resized = frame
            scale_x = scale_y = 1.0
        
        # CPU OPTIMIZATION 2: Run detection with optimized parameters
        results = self.model(
            frame_resized,
            conf=config.CONFIDENCE_THRESHOLD,
            iou=config.IOU_THRESHOLD,  # NMS threshold
            max_det=config.MAX_DETECTIONS,  # Limit detections
            verbose=False,
            half=config.USE_HALF_PRECISION  # FP16 (GPU only)
        )
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                # Extract box details
                x1, y1, x2, y2 = box.xyxy[0]
                
                # Scale back to original frame size
                x1 = int(x1 * scale_x)
                y1 = int(y1 * scale_y)
                x2 = int(x2 * scale_x)
                y2 = int(y2 * scale_y)
                
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                class_name = self.class_names[class_id]
                
                # Check if it's a violation class
                if class_name in config.VIOLATION_CLASSES:
                    violation = {
                        'timestamp': datetime.now(),
                        'class_name': class_name,
                        'class_id': class_id,
                        'confidence': confidence,
                        'bbox': (x1, y1, x2, y2),
                        'description': config.VIOLATION_CLASSES[class_name],
                        'osha_regulation': config.OSHA_REGULATIONS.get(class_name, "N/A")
                    }
                    violations.append(violation)
        
        # Performance tracking
        detection_time = time.time() - start_time
        self.total_detections += 1
        self.total_time += detection_time
        
        return violations
    
    def get_performance_stats(self):
        """Get average detection performance"""
        if self.total_detections > 0:
            avg_time = self.total_time / self.total_detections
            fps = 1.0 / avg_time if avg_time > 0 else 0
            return {
                'avg_time_ms': avg_time * 1000,
                'avg_fps': fps,
                'total_detections': self.total_detections
            }
        return None
    
    def draw_violations(self, frame, violations):
        """
        Draw bounding boxes and labels on frame
        
        Args:
            frame: OpenCV image frame
            violations: List of violation dictionaries
            
        Returns:
            Annotated frame
        """
        annotated_frame = frame.copy()
        
        for violation in violations:
            x1, y1, x2, y2 = violation['bbox']
            class_name = violation['class_name']
            confidence = violation['confidence']
            
            # Color coding: Red for violations
            color = (0, 0, 255)  # BGR Red
            
            # Draw bounding box
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 3)
            
            # Prepare label
            label = f"{violation['description']}: {confidence:.2f}"
            
            # Calculate text size and position
            (text_width, text_height), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
            )
            
            # Draw label background
            cv2.rectangle(
                annotated_frame,
                (x1, y1 - text_height - 10),
                (x1 + text_width, y1),
                color,
                -1
            )
            
            # Draw label text
            cv2.putText(
                annotated_frame,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )
        
        return annotated_frame
    
    def should_report_violation(self, violation):
        """
        Check if enough time has passed since last report of same violation type
        
        Args:
            violation: Violation dictionary
            
        Returns:
            Boolean indicating if violation should be reported
        """
        class_name = violation['class_name']
        current_time = violation['timestamp']
        
        if class_name in self.recent_violations:
            last_time = self.recent_violations[class_name]
            time_diff = (current_time - last_time).total_seconds()
            
            if time_diff < config.VIOLATION_COOLDOWN:
                return False
        
        # Update last violation time
        self.recent_violations[class_name] = current_time
        return True
    
    def save_violation_image(self, frame, violation):
        """
        Save violation screenshot
        
        Args:
            frame: OpenCV image frame
            violation: Violation dictionary
            
        Returns:
            Path to saved image
        """
        timestamp_str = violation['timestamp'].strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp_str}_{violation['class_name']}.jpg"
        filepath = f"{config.VIOLATIONS_DIR}/{filename}"
        
        # Draw violation on frame
        annotated_frame = self.draw_violations(frame, [violation])
        
        # Save image
        cv2.imwrite(filepath, annotated_frame)
        print(f"Saved violation image: {filepath}")
        
        return filepath
