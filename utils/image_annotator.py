"""
Image Annotation Utility for Component Detection Visualization
Creates annotated images with component markers, labels, and bounding boxes
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging
import os
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

class ComponentImageAnnotator:
    """Annotates images with detected component information"""
    
    def __init__(self):
        self.colors = [
            (40, 167, 69),    # Green - high confidence
            (255, 193, 7),    # Yellow - medium confidence  
            (220, 53, 69),    # Red - low confidence
            (0, 123, 255),    # Blue - default
            (108, 117, 125),  # Gray - secondary
            (255, 87, 34),    # Orange - accent
            (156, 39, 176),   # Purple - accent
            (0, 150, 136)     # Teal - accent
        ]
        
    def annotate_detection_results(self, 
                                 image_path: str, 
                                 components: List[Dict], 
                                 output_path: str,
                                 show_confidence: bool = True,
                                 show_dimensions: bool = True) -> str:
        """
        Create annotated image with component detection results
        
        Args:
            image_path: Path to original image
            components: List of detected components with coordinates
            output_path: Path to save annotated image
            show_confidence: Whether to show confidence scores
            show_dimensions: Whether to show dimension estimates
            
        Returns:
            Path to annotated image
        """
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            height, width = image.shape[:2]
            
            # Create copy for annotation
            annotated = image.copy()
            
            # Process each component
            for idx, component in enumerate(components):
                self._draw_component_annotation(
                    annotated, component, idx + 1, width, height,
                    show_confidence, show_dimensions
                )
            
            # Add title and legend
            self._add_title_and_legend(annotated, components)
            
            # Save annotated image
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cv2.imwrite(output_path, annotated)
            
            logger.info(f"Created annotated image: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to annotate image: {e}")
            raise
    
    def _draw_component_annotation(self, 
                                 image: np.ndarray, 
                                 component: Dict, 
                                 component_num: int,
                                 img_width: int, 
                                 img_height: int,
                                 show_confidence: bool,
                                 show_dimensions: bool):
        """Draw annotation for a single component"""
        
        # Get component coordinates - try multiple sources
        coords = None
        
        # First try pixel coordinates
        if 'pixel_coords' in component and component['pixel_coords']:
            coords = component['pixel_coords']
        
        # Then try position_percent
        elif 'position_percent' in component and component['position_percent']:
            pos_percent = component['position_percent']
            coords = {
                'x1': int(pos_percent.get('x1', 0) * img_width / 100),
                'y1': int(pos_percent.get('y1', 0) * img_height / 100),
                'x2': int(pos_percent.get('x2', 100) * img_width / 100),
                'y2': int(pos_percent.get('y2', 100) * img_height / 100)
            }
        
        # Generate random coordinates if none available (for demo purposes)
        else:
            logger.warning(f"No coordinates found for component {component_num}, generating random position")
            margin = 50
            box_size = min(120, img_width//4, img_height//4)
            x1 = margin + (component_num - 1) * (img_width - 2*margin - box_size) // 4
            y1 = margin + (component_num - 1) * (img_height - 2*margin - box_size) // 4
            coords = {
                'x1': x1,
                'y1': y1, 
                'x2': x1 + box_size,
                'y2': y1 + box_size
            }
        
        x1, y1, x2, y2 = int(coords['x1']), int(coords['y1']), int(coords['x2']), int(coords['y2'])
        
        # Ensure coordinates are within image bounds
        x1 = max(0, min(x1, img_width - 10))
        y1 = max(0, min(y1, img_height - 10))
        x2 = max(x1 + 10, min(x2, img_width))
        y2 = max(y1 + 10, min(y2, img_height))
        
        confidence = component.get('confidence', 0.0)
        
        # Choose color based on confidence and component number
        if confidence >= 0.8:
            color = (40, 167, 69)   # Green (BGR format for OpenCV)
        elif confidence >= 0.6:
            color = (0, 193, 255)   # Yellow (BGR format for OpenCV)
        else:
            color = (69, 53, 220)   # Red (BGR format for OpenCV)
        
        # Draw bounding box with thick border
        thickness = 4
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
        
        # Draw semi-transparent fill
        overlay = image.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        alpha = 0.15
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
        
        # Draw component number circle
        circle_radius = 20
        center_x = x1 + circle_radius + 5
        center_y = y1 - circle_radius if y1 > circle_radius + 10 else y1 + circle_radius + 30
        
        # Ensure circle is within image bounds
        center_x = max(circle_radius, min(center_x, img_width - circle_radius))
        center_y = max(circle_radius, min(center_y, img_height - circle_radius))
        
        # Background circle for number
        cv2.circle(image, (center_x, center_y), circle_radius, color, -1)
        cv2.circle(image, (center_x, center_y), circle_radius, (255, 255, 255), 3)
        
        # Component number
        font_scale = 0.8
        text_thickness = 2
        text_size = cv2.getTextSize(str(component_num), cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_thickness)[0]
        text_x = center_x - text_size[0] // 2
        text_y = center_y + text_size[1] // 2
        
        cv2.putText(image, str(component_num), 
                   (text_x, text_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), text_thickness)
        
        # Component label with background
        label = component.get('component_class', 'unknown').replace('_', ' ').title()
        label_font_scale = 0.7
        label_thickness = 2
        
        # Position label below the circle
        label_y = center_y + circle_radius + 25
        if label_y > img_height - 30:
            label_y = center_y - circle_radius - 15
        
        # Get label dimensions
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, label_font_scale, label_thickness)[0]
        label_x = center_x - label_size[0] // 2
        
        # Draw label background
        padding = 5
        bg_x1 = label_x - padding
        bg_y1 = label_y - label_size[1] - padding
        bg_x2 = label_x + label_size[0] + padding
        bg_y2 = label_y + padding
        
        cv2.rectangle(image, (bg_x1, bg_y1), (bg_x2, bg_y2), color, -1)
        cv2.rectangle(image, (bg_x1, bg_y1), (bg_x2, bg_y2), (255, 255, 255), 2)
        
        # Draw label text
        cv2.putText(image, label, 
                   (label_x, label_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, label_font_scale, (255, 255, 255), label_thickness)
        
        # Show confidence if requested
        if show_confidence:
            conf_text = f"{confidence*100:.1f}%"
            conf_y = label_y + 20
            cv2.putText(image, conf_text, 
                       (center_x - 10, conf_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        
        # Show dimensions if requested
        if show_dimensions:
            width_mm = component.get('estimated_width_mm', 0)
            height_mm = component.get('estimated_height_mm', 0)
            if width_mm > 0 and height_mm > 0:
                dim_text = f"{width_mm:.1f}x{height_mm:.1f}mm"
                dim_y = (conf_y + 15) if show_confidence else (label_y + 20)
                cv2.putText(image, dim_text, 
                           (center_x - 10, dim_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    def _add_title_and_legend(self, image: np.ndarray, components: List[Dict]):
        """Add title and legend to the annotated image"""
        height, width = image.shape[:2]
        
        # Add title background
        title_height = 60
        title_bg = np.zeros((title_height, width, 3), dtype=np.uint8)
        title_bg[:] = (50, 50, 50)  # Dark gray background
        
        # Combine title with image
        annotated_with_title = np.vstack([title_bg, image])
        
        # Add title text
        title = f"Component Detection Results - {len(components)} Components Found"
        title_size = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        title_x = (width - title_size[0]) // 2
        
        cv2.putText(annotated_with_title, title, 
                   (title_x, 35), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Add legend on the right side
        legend_width = 250
        legend_height = min(400, len(components) * 80 + 100)
        legend_x = width - legend_width - 10
        legend_y = title_height + 20
        
        # Legend background
        legend_bg = (40, 40, 40)  # Dark background
        cv2.rectangle(annotated_with_title, 
                     (legend_x, legend_y), 
                     (legend_x + legend_width, legend_y + legend_height),
                     legend_bg, -1)
        
        # Legend border
        cv2.rectangle(annotated_with_title, 
                     (legend_x, legend_y), 
                     (legend_x + legend_width, legend_y + legend_height),
                     (255, 255, 255), 2)
        
        # Legend title
        cv2.putText(annotated_with_title, "Detected Components", 
                   (legend_x + 10, legend_y + 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Legend entries
        for idx, component in enumerate(components[:5]):  # Show first 5 components
            y_pos = legend_y + 50 + (idx * 60)
            
            # Component number circle
            cv2.circle(annotated_with_title, (legend_x + 25, y_pos), 12, 
                      self.colors[idx % len(self.colors)], -1)
            cv2.putText(annotated_with_title, str(idx + 1), 
                       (legend_x + 20, y_pos + 4), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Component details
            name = component.get('component_class', 'unknown').replace('_', ' ').title()
            confidence = component.get('confidence', 0.0)
            
            cv2.putText(annotated_with_title, name, 
                       (legend_x + 45, y_pos - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.putText(annotated_with_title, f"Conf: {confidence*100:.1f}%", 
                       (legend_x + 45, y_pos + 8), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            
            # Dimensions if available
            width_mm = component.get('estimated_width_mm', 0)
            height_mm = component.get('estimated_height_mm', 0)
            if width_mm > 0 and height_mm > 0:
                cv2.putText(annotated_with_title, f"{width_mm:.1f}x{height_mm:.1f}mm", 
                           (legend_x + 45, y_pos + 22), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (150, 150, 150), 1)
        
        # Copy back to original image array
        image[:] = annotated_with_title[title_height:]
    
    def create_component_thumbnail(self, 
                                 image_path: str, 
                                 component: Dict, 
                                 output_path: str,
                                 size: Tuple[int, int] = (150, 150)) -> str:
        """
        Create thumbnail image of individual component
        
        Args:
            image_path: Path to original image
            component: Component data with coordinates
            output_path: Path to save thumbnail
            size: Thumbnail size (width, height)
            
        Returns:
            Path to thumbnail image
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            height, width = image.shape[:2]
            
            # Get component coordinates
            coords = component.get('pixel_coords', {})
            if not coords:
                pos_percent = component.get('position_percent', {})
                if pos_percent:
                    coords = {
                        'x1': int(pos_percent.get('x1', 0) * width / 100),
                        'y1': int(pos_percent.get('y1', 0) * height / 100),
                        'x2': int(pos_percent.get('x2', 100) * width / 100),
                        'y2': int(pos_percent.get('y2', 100) * height / 100)
                    }
                else:
                    raise ValueError("No coordinates available for component")
            
            # Extract component region with padding
            padding = 20
            x1 = max(0, coords['x1'] - padding)
            y1 = max(0, coords['y1'] - padding)
            x2 = min(width, coords['x2'] + padding)
            y2 = min(height, coords['y2'] + padding)
            
            component_img = image[y1:y2, x1:x2]
            
            # Resize to thumbnail size
            thumbnail = cv2.resize(component_img, size)
            
            # Save thumbnail
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cv2.imwrite(output_path, thumbnail)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to create component thumbnail: {e}")
            raise