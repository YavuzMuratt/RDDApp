import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from ultralytics import YOLO

@dataclass
class Detection:
    """Class representing a detected road issue."""
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    class_id: int
    class_name: str

class RoadDamageDetector:
    def __init__(self, model_path: str, conf_threshold: float = 0.5):
        """
        Initialize the road damage detector.
        
        Args:
            model_path: Path to the YOLO model
            conf_threshold: Confidence threshold for detections
        """
        self.conf_threshold = conf_threshold
        self.model = YOLO(model_path)
        
        # Define classes for road damage detection
        self.classes = [
            'Alligator Cracks',
            'Longitudinal Cracks',
            'Manhole Covers',
            'Patchy Road Sections',
            'Potholes',
            'Transverse Cracks'
        ]
        
    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocess the frame for detection.
        
        Args:
            frame: Input frame
            
        Returns:
            Preprocessed frame
        """
        # Resize frame to model input size (460x460)
        height, width = frame.shape[:2]
        scale = min(460/width, 460/height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Create a black canvas
        canvas = np.zeros((460, 460, 3), dtype=np.uint8)
        
        # Resize and place the frame in the center
        resized = cv2.resize(frame, (new_width, new_height))
        x_offset = (460 - new_width) // 2
        y_offset = (460 - new_height) // 2
        canvas[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = resized
        
        return canvas
        
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Detect road issues in a frame.
        
        Args:
            frame: Input frame
            
        Returns:
            List of detections
        """
        # Run YOLO inference
        results = self.model(frame, conf=self.conf_threshold)
        
        # Process detections
        detections = []
        for result in results:
            for box in result.boxes:
                # Get box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                
                # Get confidence and class
                confidence = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())
                
                # Create detection object
                detections.append(Detection(
                    confidence=confidence,
                    bbox=(x1, y1, x2, y2),
                    class_id=class_id,
                    class_name=self.classes[class_id]
                ))
                
        return detections
        
    def draw_detections(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """
        Draw detections on the frame.
        
        Args:
            frame: Input frame
            detections: List of detections
            
        Returns:
            Frame with detections drawn
        """
        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw label
            label = f"{detection.class_name}: {detection.confidence:.2f}"
            cv2.putText(
                frame,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )
            
        return frame 