"""
AI-Powered Component Detection Service using OpenAI Vision API
Provides real component analysis for manufacturing applications
"""

import os
import base64
import json
import logging
from typing import Dict, List, Optional, Tuple
from PIL import Image
import openai

logger = logging.getLogger(__name__)

class AIComponentDetector:
    """Advanced AI-powered component detection using OpenAI's vision capabilities"""
    
    def __init__(self):
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        self.model = "gpt-4o"
        self.client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
    def detect_components(self, image_path: str) -> Dict:
        """
        Detect and analyze components in an image using OpenAI Vision API
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dict containing detection results with components and metadata
        """
        try:
            # Load and encode image
            base64_image = self._encode_image(image_path)
            if not base64_image:
                raise ValueError("Failed to encode image")
            
            # Get image dimensions
            with Image.open(image_path) as img:
                img_width, img_height = img.size
            
            # Create analysis prompt
            prompt = self._create_analysis_prompt()
            
            # Call OpenAI Vision API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert manufacturing engineer and component identification specialist. 
                        Analyze images to identify mechanical components, hardware, and manufacturing parts with high precision."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0.1  # Low temperature for consistent, accurate results
            )
            
            # Parse response
            analysis = json.loads(response.choices[0].message.content)
            
            # Process and enhance results
            processed_results = self._process_detection_results(
                analysis, img_width, img_height
            )
            
            return {
                'status': 'success',
                'image_width': img_width,
                'image_height': img_height,
                'total_components': len(processed_results.get('components', [])),
                'components': processed_results.get('components', []),
                'metadata': processed_results.get('metadata', {}),
                'confidence_summary': self._calculate_confidence_summary(processed_results.get('components', []))
            }
            
        except Exception as e:
            logger.error(f"AI component detection failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'components': [],
                'total_components': 0
            }
    
    def _encode_image(self, image_path: str) -> Optional[str]:
        """Encode image to base64 for API transmission"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Image encoding failed: {e}")
            return None
    
    def _create_analysis_prompt(self) -> str:
        """Create detailed analysis prompt for component detection"""
        return """
        Analyze this image and identify all visible mechanical components, hardware parts, and manufacturing elements. 
        
        For each component detected, provide:
        1. Component type/classification (e.g., "caster_wheel", "bearing", "bolt", "bracket", "motor", etc.)
        2. Confidence score (0.0 to 1.0)
        3. Estimated position in the image (x1, y1, x2, y2 as percentages of image dimensions)
        4. Estimated physical dimensions if possible (width_mm, height_mm, diameter_mm)
        5. Key characteristics (material, color, condition, etc.)
        6. Suggested inventory category
        7. Approximate quantity if multiple identical parts
        
        Focus on identifying:
        - Mechanical hardware (bolts, nuts, washers, screws)
        - Moving parts (wheels, casters, bearings, gears)
        - Structural components (brackets, plates, frames)
        - Electrical components (motors, switches, connectors)
        - Pneumatic/hydraulic parts (cylinders, valves, fittings)
        
        Return results in this JSON format:
        {
            "components": [
                {
                    "component_class": "component_type",
                    "confidence": 0.95,
                    "position_percent": {"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                    "estimated_dimensions": {
                        "width_mm": 50,
                        "height_mm": 30,
                        "diameter_mm": 25
                    },
                    "characteristics": {
                        "material": "steel",
                        "color": "black",
                        "condition": "good",
                        "mounting_type": "threaded"
                    },
                    "inventory_category": "hardware",
                    "quantity": 1,
                    "description": "Detailed description"
                }
            ],
            "metadata": {
                "analysis_quality": "high",
                "lighting_conditions": "good",
                "image_clarity": "clear",
                "background_complexity": "simple"
            }
        }
        """
    
    def _process_detection_results(self, analysis: Dict, img_width: int, img_height: int) -> Dict:
        """Process and enhance raw detection results"""
        processed_components = []
        
        for component in analysis.get('components', []):
            try:
                # Convert percentage positions to pixel coordinates
                pos_percent = component.get('position_percent', {})
                pixel_coords = {
                    'x1': int(pos_percent.get('x1', 0) * img_width / 100),
                    'y1': int(pos_percent.get('y1', 0) * img_height / 100),
                    'x2': int(pos_percent.get('x2', 100) * img_width / 100),
                    'y2': int(pos_percent.get('y2', 100) * img_height / 100)
                }
                
                # Ensure coordinates are within image bounds
                pixel_coords['x1'] = max(0, min(pixel_coords['x1'], img_width))
                pixel_coords['y1'] = max(0, min(pixel_coords['y1'], img_height))
                pixel_coords['x2'] = max(pixel_coords['x1'], min(pixel_coords['x2'], img_width))
                pixel_coords['y2'] = max(pixel_coords['y1'], min(pixel_coords['y2'], img_height))
                
                # Extract dimensions
                dimensions = component.get('estimated_dimensions', {})
                
                processed_component = {
                    'component_class': component.get('component_class', 'unknown'),
                    'confidence': float(component.get('confidence', 0.5)),
                    'pixel_coords': pixel_coords,
                    'position_percent': pos_percent,
                    'estimated_width_mm': dimensions.get('width_mm'),
                    'estimated_height_mm': dimensions.get('height_mm'),
                    'estimated_diameter_mm': dimensions.get('diameter_mm'),
                    'estimated_area_mm2': self._calculate_area(dimensions),
                    'characteristics': component.get('characteristics', {}),
                    'inventory_category': component.get('inventory_category', 'general'),
                    'quantity': component.get('quantity', 1),
                    'description': component.get('description', ''),
                    'suggested_quantity': component.get('quantity', 1)
                }
                
                processed_components.append(processed_component)
                
            except Exception as e:
                logger.warning(f"Error processing component: {e}")
                continue
        
        return {
            'components': processed_components,
            'metadata': analysis.get('metadata', {})
        }
    
    def _calculate_area(self, dimensions: Dict) -> Optional[float]:
        """Calculate estimated area from dimensions"""
        try:
            width = dimensions.get('width_mm')
            height = dimensions.get('height_mm')
            diameter = dimensions.get('diameter_mm')
            
            if width and height:
                return width * height
            elif diameter:
                return 3.14159 * (diameter / 2) ** 2
            
            return None
        except:
            return None
    
    def _calculate_confidence_summary(self, components: List[Dict]) -> Dict:
        """Calculate confidence statistics for the detection results"""
        if not components:
            return {'average': 0.0, 'high_confidence_count': 0, 'total_count': 0}
        
        confidences = [comp.get('confidence', 0.0) for comp in components]
        average_confidence = sum(confidences) / len(confidences)
        high_confidence_count = sum(1 for conf in confidences if conf >= 0.8)
        
        return {
            'average': round(average_confidence, 3),
            'high_confidence_count': high_confidence_count,
            'total_count': len(components),
            'reliability': 'high' if average_confidence >= 0.8 else 'medium' if average_confidence >= 0.6 else 'low'
        }
    
    def enhance_component_data(self, component_data: Dict) -> Dict:
        """Enhance component data with additional manufacturing insights"""
        try:
            component_class = component_data.get('component_class', '')
            characteristics = component_data.get('characteristics', {})
            
            # Add manufacturing-specific enhancements
            enhancements = {
                'manufacturing_category': self._categorize_for_manufacturing(component_class),
                'procurement_priority': self._assess_procurement_priority(component_class, characteristics),
                'standard_sizes': self._suggest_standard_sizes(component_class),
                'typical_suppliers': self._suggest_suppliers(component_class),
                'quality_checks': self._suggest_quality_checks(component_class)
            }
            
            # Merge with original data
            enhanced_data = component_data.copy()
            enhanced_data['manufacturing_insights'] = enhancements
            
            return enhanced_data
            
        except Exception as e:
            logger.warning(f"Enhancement failed: {e}")
            return component_data
    
    def _categorize_for_manufacturing(self, component_class: str) -> str:
        """Categorize component for manufacturing processes"""
        hardware_parts = ['bolt', 'nut', 'screw', 'washer', 'rivet']
        moving_parts = ['bearing', 'wheel', 'caster', 'gear', 'pulley']
        structural_parts = ['bracket', 'plate', 'frame', 'beam', 'support']
        electrical_parts = ['motor', 'switch', 'connector', 'wire', 'terminal']
        
        component_lower = component_class.lower()
        
        if any(part in component_lower for part in hardware_parts):
            return 'fasteners_hardware'
        elif any(part in component_lower for part in moving_parts):
            return 'mechanical_assemblies'
        elif any(part in component_lower for part in structural_parts):
            return 'structural_components'
        elif any(part in component_lower for part in electrical_parts):
            return 'electrical_components'
        else:
            return 'general_components'
    
    def _assess_procurement_priority(self, component_class: str, characteristics: Dict) -> str:
        """Assess procurement priority based on component type and characteristics"""
        critical_components = ['bearing', 'motor', 'valve', 'sensor']
        standard_hardware = ['bolt', 'nut', 'screw', 'washer']
        
        component_lower = component_class.lower()
        
        if any(comp in component_lower for comp in critical_components):
            return 'high'
        elif any(comp in component_lower for comp in standard_hardware):
            return 'low'
        else:
            return 'medium'
    
    def _suggest_standard_sizes(self, component_class: str) -> List[str]:
        """Suggest standard sizes for the component type"""
        size_suggestions = {
            'bolt': ['M6', 'M8', 'M10', 'M12', 'M16'],
            'nut': ['M6', 'M8', 'M10', 'M12', 'M16'],
            'bearing': ['6000', '6200', '6300', '6400'],
            'caster': ['50mm', '75mm', '100mm', '125mm'],
            'wheel': ['100mm', '150mm', '200mm', '250mm']
        }
        
        component_lower = component_class.lower()
        for key, sizes in size_suggestions.items():
            if key in component_lower:
                return sizes
        
        return []
    
    def _suggest_suppliers(self, component_class: str) -> List[str]:
        """Suggest typical supplier categories"""
        supplier_categories = {
            'bolt': ['Hardware Store', 'Fastener Supplier', 'Industrial Supply'],
            'bearing': ['Bearing Distributor', 'Industrial Supply', 'OEM Supplier'],
            'caster': ['Material Handling', 'Industrial Hardware', 'Furniture Hardware'],
            'motor': ['Electrical Supplier', 'Motor Distributor', 'Automation Supplier']
        }
        
        component_lower = component_class.lower()
        for key, suppliers in supplier_categories.items():
            if key in component_lower:
                return suppliers
        
        return ['General Industrial Supplier']
    
    def _suggest_quality_checks(self, component_class: str) -> List[str]:
        """Suggest quality inspection points"""
        quality_checks = {
            'bearing': ['Smooth rotation', 'No play or binding', 'Proper lubrication'],
            'bolt': ['Thread condition', 'Head integrity', 'Material grade'],
            'caster': ['Wheel rotation', 'Mounting integrity', 'Load capacity'],
            'motor': ['Electrical continuity', 'Shaft alignment', 'Mounting condition']
        }
        
        component_lower = component_class.lower()
        for key, checks in quality_checks.items():
            if key in component_lower:
                return checks
        
        return ['Visual inspection', 'Dimensional check', 'Function test']