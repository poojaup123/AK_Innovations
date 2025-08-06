import svgwrite
import os
from typing import List, Dict, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ComponentLayoutGenerator:
    """
    Generate SVG layouts with detected components, dimensions, and labels
    """
    
    def __init__(self):
        self.default_width = 800
        self.default_height = 600
        self.margin = 50
        self.colors = {
            'component': '#4CAF50',
            'text': '#333333',
            'dimension': '#FF5722',
            'background': '#FFFFFF',
            'grid': '#E0E0E0'
        }
    
    def create_detection_layout(self, detections: List[Dict], 
                              image_dimensions: Tuple[int, int],
                              session_id: str,
                              title: str = "Component Detection Layout") -> str:
        """
        Create SVG layout showing detected components with dimensions
        """
        try:
            # Calculate layout dimensions
            img_width, img_height = image_dimensions
            scale_factor = min(
                (self.default_width - 2 * self.margin) / img_width,
                (self.default_height - 2 * self.margin) / img_height
            )
            
            scaled_width = img_width * scale_factor
            scaled_height = img_height * scale_factor
            
            svg_width = scaled_width + 2 * self.margin + 300  # Extra space for legend
            svg_height = max(scaled_height + 2 * self.margin, 600)
            
            # Create SVG document
            dwg = svgwrite.Drawing(
                size=(f'{svg_width}px', f'{svg_height}px'),
                viewBox=f'0 0 {svg_width} {svg_height}'
            )
            
            # Add background
            dwg.add(dwg.rect(
                insert=(0, 0),
                size=(svg_width, svg_height),
                fill=self.colors['background']
            ))
            
            # Add title
            dwg.add(dwg.text(
                title,
                insert=(self.margin, 30),
                font_size='20px',
                font_weight='bold',
                fill=self.colors['text']
            ))
            
            # Add main image area background
            dwg.add(dwg.rect(
                insert=(self.margin, self.margin),
                size=(scaled_width, scaled_height),
                fill='none',
                stroke='#CCCCCC',
                stroke_width='2'
            ))
            
            # Add grid lines for reference
            self._add_grid_lines(dwg, self.margin, self.margin, 
                               scaled_width, scaled_height, scale_factor)
            
            # Draw detected components
            for i, detection in enumerate(detections):
                self._draw_component(dwg, detection, scale_factor, 
                                   self.margin, self.margin, i + 1)
            
            # Add legend
            self._add_legend(dwg, detections, scaled_width + self.margin + 20, 
                           self.margin)
            
            # Add scale information
            self._add_scale_info(dwg, scale_factor, 10, svg_height - 30)
            
            # Save SVG file
            filename = f"layout_{session_id}.svg"
            filepath = f"static/component_detection/layouts/{filename}"
            dwg.saveas(filepath)
            
            logger.info(f"SVG layout created: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error creating SVG layout: {e}")
            return None
    
    def _add_grid_lines(self, dwg, start_x: float, start_y: float,
                       width: float, height: float, scale_factor: float):
        """Add grid lines for dimension reference"""
        grid_spacing_mm = 50  # 50mm grid
        grid_spacing_px = grid_spacing_mm * scale_factor * 0.1  # Convert to pixels
        
        # Vertical lines
        x = start_x
        while x <= start_x + width:
            dwg.add(dwg.line(
                start=(x, start_y),
                end=(x, start_y + height),
                stroke=self.colors['grid'],
                stroke_width='0.5',
                opacity='0.5'
            ))
            x += grid_spacing_px
        
        # Horizontal lines
        y = start_y
        while y <= start_y + height:
            dwg.add(dwg.line(
                start=(start_x, y),
                end=(start_x + width, y),
                stroke=self.colors['grid'],
                stroke_width='0.5',
                opacity='0.5'
            ))
            y += grid_spacing_px
    
    def _draw_component(self, dwg, detection: Dict, scale_factor: float,
                       offset_x: float, offset_y: float, component_number: int):
        """Draw individual component with bounding box and dimensions"""
        
        # Calculate scaled coordinates
        coords = detection['pixel_coords']
        x1 = coords['x1'] * scale_factor + offset_x
        y1 = coords['y1'] * scale_factor + offset_y
        x2 = coords['x2'] * scale_factor + offset_x
        y2 = coords['y2'] * scale_factor + offset_y
        
        width = x2 - x1
        height = y2 - y1
        
        # Draw bounding box
        dwg.add(dwg.rect(
            insert=(x1, y1),
            size=(width, height),
            fill='none',
            stroke=self.colors['component'],
            stroke_width='2',
            opacity='0.8'
        ))
        
        # Add component number
        dwg.add(dwg.circle(
            center=(x1 + 15, y1 + 15),
            r=12,
            fill=self.colors['component'],
            stroke='white',
            stroke_width='2'
        ))
        
        dwg.add(dwg.text(
            str(component_number),
            insert=(x1 + 15, y1 + 20),
            text_anchor='middle',
            font_size='12px',
            font_weight='bold',
            fill='white'
        ))
        
        # Add dimensions
        self._add_dimensions(dwg, x1, y1, x2, y2, detection)
        
        # Add component label
        label = f"{detection['component_class']} ({detection['confidence']:.2f})"
        dwg.add(dwg.text(
            label,
            insert=(x1, y1 - 5),
            font_size='10px',
            fill=self.colors['text'],
            font_weight='bold'
        ))
    
    def _add_dimensions(self, dwg, x1: float, y1: float, x2: float, y2: float,
                       detection: Dict):
        """Add dimension lines and measurements"""
        
        # Width dimension (top)
        dim_y = y1 - 20
        dwg.add(dwg.line(
            start=(x1, dim_y),
            end=(x2, dim_y),
            stroke=self.colors['dimension'],
            stroke_width='1'
        ))
        
        # Width dimension arrows
        dwg.add(dwg.line(start=(x1, dim_y - 3), end=(x1, dim_y + 3),
                        stroke=self.colors['dimension'], stroke_width='1'))
        dwg.add(dwg.line(start=(x2, dim_y - 3), end=(x2, dim_y + 3),
                        stroke=self.colors['dimension'], stroke_width='1'))
        
        # Width measurement text
        width_mm = detection.get('estimated_width_mm', 0)
        dwg.add(dwg.text(
            f"{width_mm:.1f}mm",
            insert=((x1 + x2) / 2, dim_y - 5),
            text_anchor='middle',
            font_size='8px',
            fill=self.colors['dimension']
        ))
        
        # Height dimension (right side)
        dim_x = x2 + 20
        dwg.add(dwg.line(
            start=(dim_x, y1),
            end=(dim_x, y2),
            stroke=self.colors['dimension'],
            stroke_width='1'
        ))
        
        # Height dimension arrows
        dwg.add(dwg.line(start=(dim_x - 3, y1), end=(dim_x + 3, y1),
                        stroke=self.colors['dimension'], stroke_width='1'))
        dwg.add(dwg.line(start=(dim_x - 3, y2), end=(dim_x + 3, y2),
                        stroke=self.colors['dimension'], stroke_width='1'))
        
        # Height measurement text
        height_mm = detection.get('estimated_height_mm', 0)
        dwg.add(dwg.text(
            f"{height_mm:.1f}mm",
            insert=(dim_x + 5, (y1 + y2) / 2),
            text_anchor='start',
            font_size='8px',
            fill=self.colors['dimension'],
            transform=f"rotate(90, {dim_x + 5}, {(y1 + y2) / 2})"
        ))
    
    def _add_legend(self, dwg, detections: List[Dict], start_x: float, start_y: float):
        """Add legend showing component details"""
        
        # Legend background
        legend_height = len(detections) * 25 + 60
        dwg.add(dwg.rect(
            insert=(start_x, start_y),
            size=(250, legend_height),
            fill='#F5F5F5',
            stroke='#CCCCCC',
            stroke_width='1'
        ))
        
        # Legend title
        dwg.add(dwg.text(
            "Detected Components",
            insert=(start_x + 10, start_y + 20),
            font_size='14px',
            font_weight='bold',
            fill=self.colors['text']
        ))
        
        # Component list
        y_pos = start_y + 40
        for i, detection in enumerate(detections):
            # Component number circle
            dwg.add(dwg.circle(
                center=(start_x + 20, y_pos),
                r=8,
                fill=self.colors['component']
            ))
            
            dwg.add(dwg.text(
                str(i + 1),
                insert=(start_x + 20, y_pos + 4),
                text_anchor='middle',
                font_size='10px',
                font_weight='bold',
                fill='white'
            ))
            
            # Component details
            component_text = f"{detection['component_class']}"
            confidence_text = f"Confidence: {detection['confidence']:.2f}"
            dimensions_text = f"{detection.get('estimated_width_mm', 0):.1f} × {detection.get('estimated_height_mm', 0):.1f} mm"
            
            dwg.add(dwg.text(
                component_text,
                insert=(start_x + 35, y_pos - 5),
                font_size='11px',
                font_weight='bold',
                fill=self.colors['text']
            ))
            
            dwg.add(dwg.text(
                confidence_text,
                insert=(start_x + 35, y_pos + 5),
                font_size='9px',
                fill='#666666'
            ))
            
            dwg.add(dwg.text(
                dimensions_text,
                insert=(start_x + 35, y_pos + 15),
                font_size='9px',
                fill='#666666'
            ))
            
            y_pos += 25
    
    def _add_scale_info(self, dwg, scale_factor: float, x: float, y: float):
        """Add scale information"""
        scale_text = f"Scale: 1 pixel = {1/scale_factor:.2f} mm"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        dwg.add(dwg.text(
            scale_text,
            insert=(x, y),
            font_size='10px',
            fill='#666666'
        ))
        
        dwg.add(dwg.text(
            f"Generated: {timestamp}",
            insert=(x, y + 15),
            font_size='10px',
            fill='#666666'
        ))
    
    def create_bom_layout(self, bom_data: Dict, session_id: str) -> str:
        """Create SVG layout for Bill of Materials"""
        try:
            svg_width = 800
            svg_height = max(400, len(bom_data['items']) * 30 + 200)
            
            dwg = svgwrite.Drawing(
                size=(f'{svg_width}px', f'{svg_height}px'),
                viewBox=f'0 0 {svg_width} {svg_height}'
            )
            
            # Background
            dwg.add(dwg.rect(
                insert=(0, 0),
                size=(svg_width, svg_height),
                fill=self.colors['background']
            ))
            
            # Title
            dwg.add(dwg.text(
                f"Bill of Materials: {bom_data['product_name']}",
                insert=(50, 40),
                font_size='18px',
                font_weight='bold',
                fill=self.colors['text']
            ))
            
            # Summary
            summary_y = 70
            dwg.add(dwg.text(
                f"Total Items: {bom_data['total_items']} | Total Cost: ₹{bom_data['total_cost']:.2f}",
                insert=(50, summary_y),
                font_size='12px',
                fill=self.colors['text']
            ))
            
            # Table headers
            header_y = 110
            headers = ["Item", "Code", "Qty", "Unit Price", "Total"]
            x_positions = [50, 250, 400, 500, 600]
            
            for i, header in enumerate(headers):
                dwg.add(dwg.text(
                    header,
                    insert=(x_positions[i], header_y),
                    font_size='12px',
                    font_weight='bold',
                    fill=self.colors['text']
                ))
            
            # Table separator line
            dwg.add(dwg.line(
                start=(50, header_y + 10),
                end=(700, header_y + 10),
                stroke='#CCCCCC',
                stroke_width='1'
            ))
            
            # BOM items
            item_y = header_y + 30
            for item in bom_data['items']:
                values = [
                    item['item_name'][:25] + "..." if len(item['item_name']) > 25 else item['item_name'],
                    item['item_code'] or "N/A",
                    str(item['quantity_required']),
                    f"₹{item['unit_price']:.2f}",
                    f"₹{item['total_cost']:.2f}"
                ]
                
                for i, value in enumerate(values):
                    dwg.add(dwg.text(
                        value,
                        insert=(x_positions[i], item_y),
                        font_size='11px',
                        fill=self.colors['text']
                    ))
                
                item_y += 25
            
            # Save file
            filename = f"bom_{session_id}.svg"
            filepath = f"static/component_detection/layouts/{filename}"
            dwg.saveas(filepath)
            
            return filepath
            
        except Exception as e:
            logger.error(f"Error creating BOM layout: {e}")
            return None