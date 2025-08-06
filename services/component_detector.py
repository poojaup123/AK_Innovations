import cv2
import numpy as np
import os
import uuid
from datetime import datetime
import logging
from typing import List, Tuple, Dict, Optional
import json

# Note: This is a simplified version for demo purposes
# In production, you would install ultralytics with: pip install ultralytics
# from ultralytics import YOLO

logger = logging.getLogger(__name__)

class ComponentDetector:
    """
    Advanced component detection using YOLO and OpenCV
    Integrates with existing Factory Management System inventory
    """
    
    def __init__(self, model_path: str = None, confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold
        self.model_path = model_path or 'yolov8n.pt'  # Use nano model by default
        self.model = None
        self.load_model()
        
        # Ensure directories exist
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create necessary directories for storing results"""
        directories = [
            'static/component_detection/uploads',
            'static/component_detection/results',
            'static/component_detection/cropped',
            'static/component_detection/layouts'
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def load_model(self):
        """Load YOLO model (Demo version - uses mock detection)"""
        try:
            # In production, this would load the actual YOLO model:
            # self.model = YOLO(self.model_path)
            self.model = "mock_model"  # Demo placeholder
            logger.info(f"Demo mode: Mock YOLO model loaded")
        except Exception as e:
            logger.error(f"Error loading YOLO model: {e}")
            raise
    
    def detect_components(self, image_path: str, session_id: str = None) -> Dict:
        """
        Main detection function
        Returns detection results with component details
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        start_time = datetime.now()
        
        try:
            # Load and validate image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Run YOLO detection (Demo version with mock results)
            detections = self._create_mock_detections(image, session_id)
            
            # Generate result visualization
            result_image_path = self._create_result_visualization(
                image, detections, session_id
            )
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'session_id': session_id,
                'status': 'completed',
                'total_components': len(detections),
                'detections': detections,
                'result_image_path': result_image_path,
                'processing_time': processing_time,
                'original_image_path': image_path
            }
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return {
                'session_id': session_id,
                'status': 'failed',
                'error_message': str(e),
                'processing_time': (datetime.now() - start_time).total_seconds()
            }
    
    def _create_mock_detections(self, image: np.ndarray, session_id: str) -> List[Dict]:
        """Create mock detections for demo purposes"""
        detections = []
        image_height, image_width = image.shape[:2]
        
        # Mock detection data (in production, this would come from YOLO)
        mock_components = [
            {
                'class_name': 'screw',
                'confidence': 0.85,
                'box': [0.2 * image_width, 0.3 * image_height, 0.3 * image_width, 0.35 * image_height]
            },
            {
                'class_name': 'bolt',
                'confidence': 0.92,
                'box': [0.5 * image_width, 0.4 * image_height, 0.65 * image_width, 0.48 * image_height]
            },
            {
                'class_name': 'washer',
                'confidence': 0.78,
                'box': [0.7 * image_width, 0.2 * image_height, 0.8 * image_width, 0.25 * image_height]
            }
        ]
        
        for i, component in enumerate(mock_components):
            x1, y1, x2, y2 = component['box']
            
            # Normalize coordinates
            bbox_x = x1 / image_width
            bbox_y = y1 / image_height
            bbox_width = (x2 - x1) / image_width
            bbox_height = (y2 - y1) / image_height
            
            # Estimate physical dimensions
            estimated_width_mm = (x2 - x1) * 0.1
            estimated_height_mm = (y2 - y1) * 0.1
            estimated_area_mm2 = estimated_width_mm * estimated_height_mm
            
            # Crop component image
            cropped_path = self._crop_component(
                image, x1, y1, x2, y2, session_id, i
            )
            
            detection = {
                'component_class': component['class_name'],
                'confidence': component['confidence'],
                'bbox_x': bbox_x,
                'bbox_y': bbox_y,
                'bbox_width': bbox_width,
                'bbox_height': bbox_height,
                'estimated_width_mm': estimated_width_mm,
                'estimated_height_mm': estimated_height_mm,
                'estimated_area_mm2': estimated_area_mm2,
                'cropped_image_path': cropped_path,
                'pixel_coords': {
                    'x1': int(x1), 'y1': int(y1),
                    'x2': int(x2), 'y2': int(y2)
                }
            }
            
            detections.append(detection)
        
        return detections
    
    def _process_detections(self, results, image: np.ndarray, session_id: str) -> List[Dict]:
        """Process YOLO detection results"""
        detections = []
        image_height, image_width = image.shape[:2]
        
        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for i, box in enumerate(boxes):
                    # Extract box coordinates and confidence
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    confidence = box.conf[0].item()
                    class_id = int(box.cls[0].item())
                    class_name = f"component_{class_id}"  # Demo placeholder
                    
                    # Normalize coordinates
                    bbox_x = x1 / image_width
                    bbox_y = y1 / image_width
                    bbox_width = (x2 - x1) / image_width
                    bbox_height = (y2 - y1) / image_height
                    
                    # Estimate physical dimensions (assuming reference scale)
                    estimated_width_mm = (x2 - x1) * 0.1  # Rough estimation
                    estimated_height_mm = (y2 - y1) * 0.1
                    estimated_area_mm2 = estimated_width_mm * estimated_height_mm
                    
                    # Crop component image
                    cropped_path = self._crop_component(
                        image, x1, y1, x2, y2, session_id, i
                    )
                    
                    detection = {
                        'component_class': class_name,
                        'confidence': confidence,
                        'bbox_x': bbox_x,
                        'bbox_y': bbox_y,
                        'bbox_width': bbox_width,
                        'bbox_height': bbox_height,
                        'estimated_width_mm': estimated_width_mm,
                        'estimated_height_mm': estimated_height_mm,
                        'estimated_area_mm2': estimated_area_mm2,
                        'cropped_image_path': cropped_path,
                        'pixel_coords': {
                            'x1': int(x1), 'y1': int(y1),
                            'x2': int(x2), 'y2': int(y2)
                        }
                    }
                    
                    detections.append(detection)
        
        return detections
    
    def _crop_component(self, image: np.ndarray, x1: float, y1: float, 
                       x2: float, y2: float, session_id: str, index: int) -> str:
        """Crop individual component from image"""
        try:
            # Add padding around the component
            padding = 10
            x1 = max(0, int(x1) - padding)
            y1 = max(0, int(y1) - padding)
            x2 = min(image.shape[1], int(x2) + padding)
            y2 = min(image.shape[0], int(y2) + padding)
            
            cropped = image[y1:y2, x1:x2]
            
            # Save cropped image
            filename = f"component_{session_id}_{index}.jpg"
            cropped_path = f"static/component_detection/cropped/{filename}"
            cv2.imwrite(cropped_path, cropped)
            
            return cropped_path
            
        except Exception as e:
            logger.error(f"Error cropping component: {e}")
            return None
    
    def _create_result_visualization(self, image: np.ndarray, 
                                   detections: List[Dict], session_id: str) -> str:
        """Create visualization with bounding boxes and labels"""
        result_image = image.copy()
        
        for i, detection in enumerate(detections):
            coords = detection['pixel_coords']
            x1, y1, x2, y2 = coords['x1'], coords['y1'], coords['x2'], coords['y2']
            
            # Draw bounding box
            cv2.rectangle(result_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Add label
            label = f"{detection['component_class']}: {detection['confidence']:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            
            # Draw label background
            cv2.rectangle(result_image, (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), (0, 255, 0), -1)
            
            # Draw label text
            cv2.putText(result_image, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            
            # Add component number
            cv2.putText(result_image, str(i + 1), (x1 + 5, y1 + 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Save result image
        result_filename = f"detection_result_{session_id}.jpg"
        result_path = f"static/component_detection/results/{result_filename}"
        cv2.imwrite(result_path, result_image)
        
        return result_path
    
    def get_component_statistics(self, detections: List[Dict]) -> Dict:
        """Calculate component statistics"""
        if not detections:
            return {}
        
        stats = {
            'total_components': len(detections),
            'unique_classes': len(set(d['component_class'] for d in detections)),
            'average_confidence': np.mean([d['confidence'] for d in detections]),
            'class_counts': {},
            'total_estimated_area': sum(d['estimated_area_mm2'] for d in detections)
        }
        
        # Count components by class
        for detection in detections:
            class_name = detection['component_class']
            stats['class_counts'][class_name] = stats['class_counts'].get(class_name, 0) + 1
        
        return stats