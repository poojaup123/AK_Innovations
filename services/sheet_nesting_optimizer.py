"""
Advanced Sheet Nesting Optimizer with Image Processing
Supports irregular shapes, scrap calculation, and visual layout generation
"""

import cv2
import numpy as np
from skimage import filters, measure, morphology, segmentation
from skimage.feature import canny
from skimage.morphology import disk
# polygon3 is installed but not used directly in this implementation
# Using Shapely for all polygon operations instead
from shapely.geometry import Polygon as ShapelyPolygon, Point
from shapely.affinity import translate, rotate
import svgwrite
import tempfile
import os
from typing import List, Dict, Tuple, Optional
import json
from PIL import Image
import io
import base64
import time

class ShapeDetector:
    """Detects and extracts shapes from images using advanced image processing"""
    
    def __init__(self):
        self.min_contour_area = 1000  # Minimum area for valid contours
        
    def preprocess_image(self, image_data: bytes) -> np.ndarray:
        """Advanced image preprocessing using scikit-image"""
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        # Apply Gaussian filter to reduce noise
        img_filtered = filters.gaussian(img, sigma=1.0)
        
        # Apply adaptive threshold
        thresh = filters.threshold_otsu(img_filtered)
        binary = img_filtered > thresh
        
        # Morphological operations to clean up the image
        cleaned = morphology.remove_small_objects(binary, min_size=500)
        cleaned = morphology.remove_small_holes(cleaned, area_threshold=300)
        
        # Convert back to uint8 for OpenCV compatibility
        return (cleaned * 255).astype(np.uint8)
    
    def detect_contours(self, processed_image: np.ndarray) -> List[np.ndarray]:
        """Detect contours with enhanced precision"""
        # Use Canny edge detection with scikit-image
        edges = canny(processed_image, sigma=1.0, low_threshold=0.1, high_threshold=0.2)
        edges = (edges * 255).astype(np.uint8)
        
        # Find contours using OpenCV
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by area
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > self.min_contour_area:
                # Approximate contour to reduce points
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                valid_contours.append(approx)
        
        return valid_contours
    
    def contour_to_polygon(self, contour: np.ndarray) -> ShapelyPolygon:
        """Convert OpenCV contour to Shapely polygon"""
        points = [(point[0][0], point[0][1]) for point in contour]
        return ShapelyPolygon(points)
    
    def extract_shape_info(self, image_data: bytes) -> Dict:
        """Extract comprehensive shape information from image"""
        processed_img = self.preprocess_image(image_data)
        contours = self.detect_contours(processed_img)
        
        shapes = []
        for i, contour in enumerate(contours):
            try:
                polygon_shape = self.contour_to_polygon(contour)
                
                # Calculate shape properties
                area = polygon_shape.area
                bounds = polygon_shape.bounds  # (minx, miny, maxx, maxy)
                width = bounds[2] - bounds[0]
                height = bounds[3] - bounds[1]
                
                # Calculate complexity (number of vertices)
                complexity = len(contour)
                
                shapes.append({
                    'id': i,
                    'contour': contour.tolist(),
                    'polygon': polygon_shape,
                    'area': area,
                    'width': width,
                    'height': height,
                    'bounds': bounds,
                    'complexity': complexity,
                    'centroid': (polygon_shape.centroid.x, polygon_shape.centroid.y)
                })
            except Exception as e:
                print(f"Error processing contour {i}: {e}")
                continue
        
        return {
            'shapes': shapes,
            'image_dimensions': processed_img.shape,
            'total_shapes': len(shapes)
        }

class IrregularNestingOptimizer:
    """Advanced nesting optimizer for irregular shapes"""
    
    def __init__(self):
        self.rotation_angles = [0, 90, 180, 270]  # Standard rotation angles
        self.placement_precision = 5  # Grid precision for placement attempts
        
    def can_place_shape(self, sheet_polygon: ShapelyPolygon, part_polygon: ShapelyPolygon, 
                       x: float, y: float, placed_parts: List[ShapelyPolygon]) -> bool:
        """Check if a part can be placed at given position without overlap"""
        # Translate part to position
        translated_part = translate(part_polygon, xoff=x, yoff=y)
        
        # Check if part fits within sheet bounds
        if not sheet_polygon.contains(translated_part):
            return False
        
        # Check for overlaps with already placed parts
        for placed_part in placed_parts:
            if translated_part.intersects(placed_part):
                return False
        
        return True
    
    def find_best_placement(self, sheet_polygon: ShapelyPolygon, part_polygon: ShapelyPolygon, 
                          placed_parts: List[ShapelyPolygon]) -> Optional[Tuple[float, float, float]]:
        """Find the best placement position and rotation for a part"""
        best_placement = None
        best_efficiency = 0
        
        sheet_bounds = sheet_polygon.bounds
        
        # Try different rotations
        for angle in self.rotation_angles:
            rotated_part = rotate(part_polygon, angle, origin='centroid')
            part_bounds = rotated_part.bounds
            part_width = part_bounds[2] - part_bounds[0]
            part_height = part_bounds[3] - part_bounds[1]
            
            # Grid search for placement
            for x in range(int(sheet_bounds[0]), 
                          int(sheet_bounds[2] - part_width), 
                          self.placement_precision):
                for y in range(int(sheet_bounds[1]), 
                              int(sheet_bounds[3] - part_height), 
                              self.placement_precision):
                    
                    if self.can_place_shape(sheet_polygon, rotated_part, x, y, placed_parts):
                        # Calculate efficiency (how well it fits with existing parts)
                        efficiency = self.calculate_placement_efficiency(
                            sheet_polygon, rotated_part, x, y, placed_parts
                        )
                        
                        if efficiency > best_efficiency:
                            best_efficiency = efficiency
                            best_placement = (x, y, angle)
        
        return best_placement
    
    def calculate_placement_efficiency(self, sheet_polygon: ShapelyPolygon, part_polygon: ShapelyPolygon,
                                     x: float, y: float, placed_parts: List[ShapelyPolygon]) -> float:
        """Calculate efficiency score for a placement"""
        translated_part = translate(part_polygon, xoff=x, yoff=y)
        
        # Prefer placements closer to existing parts (better packing)
        if placed_parts:
            min_distance = min(translated_part.distance(placed) for placed in placed_parts)
            efficiency = 1.0 / (1.0 + min_distance)
        else:
            # First part - prefer corner placement
            sheet_bounds = sheet_polygon.bounds
            corner_distance = ((x - sheet_bounds[0])**2 + (y - sheet_bounds[1])**2)**0.5
            efficiency = 1.0 / (1.0 + corner_distance)
        
        return efficiency
    
    def nest_parts(self, sheet_shape: Dict, part_shapes: List[Dict], 
                   quantities: List[int]) -> Dict:
        """Perform nesting optimization for irregular shapes"""
        sheet_polygon = sheet_shape['polygon']
        placed_parts = []
        placement_results = []
        
        # Create list of parts to place based on quantities
        parts_to_place = []
        for i, (part_shape, quantity) in enumerate(zip(part_shapes, quantities)):
            for _ in range(quantity):
                parts_to_place.append({
                    'shape_id': i,
                    'polygon': part_shape['polygon'],
                    'original_shape': part_shape
                })
        
        # Sort parts by area (largest first - better packing)
        parts_to_place.sort(key=lambda p: p['polygon'].area, reverse=True)
        
        successful_placements = 0
        for part_info in parts_to_place:
            placement = self.find_best_placement(
                sheet_polygon, part_info['polygon'], placed_parts
            )
            
            if placement:
                x, y, angle = placement
                rotated_part = rotate(part_info['polygon'], angle, origin='centroid')
                final_part = translate(rotated_part, xoff=x, yoff=y)
                
                placed_parts.append(final_part)
                placement_results.append({
                    'shape_id': part_info['shape_id'],
                    'x': x,
                    'y': y,
                    'rotation': angle,
                    'polygon': final_part,
                    'area': final_part.area
                })
                successful_placements += 1
        
        # Calculate efficiency metrics
        total_part_area = sum(p['area'] for p in placement_results)
        sheet_area = sheet_polygon.area
        scrap_area = sheet_area - total_part_area
        efficiency_percent = (total_part_area / sheet_area) * 100
        
        return {
            'successful_placements': successful_placements,
            'total_requested': len(parts_to_place),
            'placement_results': placement_results,
            'sheet_area': sheet_area,
            'used_area': total_part_area,
            'scrap_area': scrap_area,
            'efficiency_percent': efficiency_percent,
            'sheet_polygon': sheet_polygon
        }

class NestingVisualizer:
    """Generate visual representations of nesting results"""
    
    def __init__(self):
        self.colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3']
    
    def generate_svg_layout(self, nesting_result: Dict, output_path: str = None) -> str:
        """Generate SVG visualization of nesting layout"""
        sheet_bounds = nesting_result['sheet_polygon'].bounds
        width = sheet_bounds[2] - sheet_bounds[0]
        height = sheet_bounds[3] - sheet_bounds[1]
        
        # Create SVG with proper scaling
        scale = min(800 / width, 600 / height)
        svg_width = width * scale
        svg_height = height * scale
        
        if output_path:
            dwg = svgwrite.Drawing(output_path, size=(f'{svg_width}px', f'{svg_height}px'))
        else:
            dwg = svgwrite.Drawing(size=(f'{svg_width}px', f'{svg_height}px'))
        
        # Add sheet outline
        sheet_points = []
        if hasattr(nesting_result['sheet_polygon'], 'exterior'):
            for x, y in nesting_result['sheet_polygon'].exterior.coords:
                sheet_points.append((x * scale, y * scale))
        
        if sheet_points:
            dwg.add(dwg.polygon(sheet_points, fill='lightgray', stroke='black', stroke_width=2))
        
        # Add placed parts
        for i, placement in enumerate(nesting_result['placement_results']):
            color = self.colors[placement['shape_id'] % len(self.colors)]
            
            part_points = []
            if hasattr(placement['polygon'], 'exterior'):
                for x, y in placement['polygon'].exterior.coords:
                    part_points.append((x * scale, y * scale))
            
            if part_points:
                dwg.add(dwg.polygon(part_points, fill=color, stroke='black', 
                                  stroke_width=1, opacity=0.8))
                
                # Add part label
                centroid = placement['polygon'].centroid
                dwg.add(dwg.text(f'P{placement["shape_id"]+1}', 
                               insert=(centroid.x * scale, centroid.y * scale),
                               text_anchor='middle', font_size='12px', fill='white'))
        
        if output_path:
            dwg.save()
            return output_path
        else:
            return dwg.tostring()
    
    def generate_efficiency_chart_data(self, nesting_result: Dict) -> Dict:
        """Generate data for efficiency visualization"""
        return {
            'labels': ['Used Area', 'Scrap Area'],
            'data': [nesting_result['used_area'], nesting_result['scrap_area']],
            'colors': ['#4ECDC4', '#FF6B6B'],
            'efficiency_percent': nesting_result['efficiency_percent'],
            'successful_parts': nesting_result['successful_placements'],
            'total_requested': nesting_result['total_requested']
        }

class SheetNestingService:
    """Main service for sheet nesting operations"""
    
    def __init__(self):
        self.shape_detector = ShapeDetector()
        self.nesting_optimizer = IrregularNestingOptimizer()
        self.visualizer = NestingVisualizer()
    
    def analyze_sheet_and_parts(self, sheet_image: bytes, part_images: List[bytes], 
                               quantities: List[int]) -> Dict:
        """Complete analysis of sheet nesting optimization"""
        try:
            # Detect sheet shape
            sheet_info = self.shape_detector.extract_shape_info(sheet_image)
            if not sheet_info['shapes']:
                raise ValueError("No valid sheet shape detected")
            
            sheet_shape = sheet_info['shapes'][0]  # Use largest shape
            
            # Detect part shapes
            part_shapes = []
            for part_image in part_images:
                part_info = self.shape_detector.extract_shape_info(part_image)
                if part_info['shapes']:
                    part_shapes.append(part_info['shapes'][0])  # Use largest shape
            
            if not part_shapes:
                raise ValueError("No valid part shapes detected")
            
            # Perform nesting optimization
            nesting_result = self.nesting_optimizer.nest_parts(
                sheet_shape, part_shapes, quantities
            )
            
            # Generate visualization
            svg_layout = self.visualizer.generate_svg_layout(nesting_result)
            chart_data = self.visualizer.generate_efficiency_chart_data(nesting_result)
            
            return {
                'success': True,
                'sheet_info': sheet_shape,
                'part_info': part_shapes,
                'nesting_result': nesting_result,
                'svg_layout': svg_layout,
                'chart_data': chart_data,
                'summary': {
                    'parts_placed': nesting_result['successful_placements'],
                    'parts_requested': nesting_result['total_requested'],
                    'efficiency': round(nesting_result['efficiency_percent'], 2),
                    'scrap_percent': round((nesting_result['scrap_area'] / nesting_result['sheet_area']) * 100, 2),
                    'total_scrap_area': round(nesting_result['scrap_area'], 2)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'details': 'Error in sheet nesting analysis'
            }
    
    def save_nesting_result(self, result: Dict, filename: str = None) -> str:
        """Save nesting result to file"""
        if not filename:
            filename = f"nesting_result_{int(time.time())}.json"
        
        from datetime import datetime
        
        # Prepare serializable data
        serializable_result = {
            'success': result['success'],
            'summary': result.get('summary', {}),
            'chart_data': result.get('chart_data', {}),
            'timestamp': datetime.now().isoformat()
        }
        
        filepath = os.path.join(tempfile.gettempdir(), filename)
        with open(filepath, 'w') as f:
            json.dump(serializable_result, f, indent=2)
        
        return filepath