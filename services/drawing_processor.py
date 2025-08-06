"""
Drawing Processing Service for CAD file analysis and component extraction
"""
import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import ezdxf
from ezdxf import recover
from werkzeug.utils import secure_filename
import tempfile
import uuid
import re
import svgwrite
import base64
from io import BytesIO
try:
    import cairosvg
    PNG_SUPPORT = True
except ImportError:
    PNG_SUPPORT = False

# Try importing STEP file processing libraries
try:
    import FreeCAD
    import Part
    STEP_SUPPORT = True
except ImportError:
    try:
        from OCC.Core import STEPControl_Reader, TopExp_Explorer, TopAbs_FACE, TopAbs_EDGE
        from OCC.Core import BRep_Tool, GeomLProp_SLProps, gp_Pnt
        STEP_SUPPORT = True
    except ImportError:
        STEP_SUPPORT = False

logger = logging.getLogger(__name__)

class DrawingProcessor:
    """Handles CAD drawing file processing and component extraction"""
    
    SUPPORTED_FORMATS = {'.dxf', '.dwg', '.stp', '.step'}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.svg_output_dir = os.path.join('static', 'uploads', 'generated_images')
    
    def validate_file(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Validate uploaded drawing file"""
        try:
            # Check file extension
            _, ext = os.path.splitext(original_filename.lower())
            if ext not in self.SUPPORTED_FORMATS:
                return {
                    'valid': False,
                    'error': f'Unsupported file format. Supported: {", ".join(self.SUPPORTED_FORMATS)}'
                }
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.MAX_FILE_SIZE:
                return {
                    'valid': False,
                    'error': f'File too large. Maximum size: {self.MAX_FILE_SIZE // (1024*1024)}MB'
                }
            
            # Try to read the file based on format
            if ext == '.dxf':
                try:
                    doc = ezdxf.readfile(file_path)
                    return {'valid': True, 'format': 'dxf', 'size': file_size}
                except ezdxf.DXFStructureError:
                    # Try recovery
                    try:
                        doc, auditor = recover.readfile(file_path)
                        return {'valid': True, 'format': 'dxf', 'size': file_size, 'recovered': True}
                    except Exception as e:
                        return {'valid': False, 'error': f'Invalid DXF file: {str(e)}'}
            
            elif ext in ['.stp', '.step']:
                try:
                    # Try to validate STEP file by checking header
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        header = f.read(100)
                        if not header.startswith('ISO-10303'):
                            return {'valid': False, 'error': 'Invalid STEP file format'}
                    return {'valid': True, 'format': 'step', 'size': file_size}
                except Exception as e:
                    return {'valid': False, 'error': f'Invalid STEP file: {str(e)}'}
            
            return {'valid': True, 'format': ext[1:], 'size': file_size}
            
        except Exception as e:
            logger.error(f"File validation error: {str(e)}")
            return {'valid': False, 'error': f'File validation failed: {str(e)}'}
    
    def extract_components_from_dxf(self, file_path: str) -> Dict[str, Any]:
        """Extract components and specifications from DXF file"""
        try:
            # Read DXF file
            try:
                doc = ezdxf.readfile(file_path)
            except ezdxf.DXFStructureError:
                doc, auditor = recover.readfile(file_path)
                logger.warning(f"DXF file recovered with {len(auditor.errors)} errors")
            
            components = []
            drawing_info = {
                'filename': os.path.basename(file_path),
                'layers': [],
                'blocks': [],
                'dimensions': [],
                'text_annotations': [],
                'title_block': {},
                'part_list': []
            }
            
            # Extract layers
            for layer in doc.layers:
                drawing_info['layers'].append({
                    'name': layer.dxf.name,
                    'color': layer.dxf.color,
                    'linetype': layer.dxf.linetype
                })
            
            # Extract blocks (potential components)
            for block in doc.blocks:
                if not block.name.startswith('*'):  # Skip model/paper space blocks
                    block_info = {
                        'name': block.name,
                        'entities': len(block),
                        'base_point': getattr(block, 'base_point', None)
                    }
                    drawing_info['blocks'].append(block_info)
            
            # Process modelspace entities
            modelspace = doc.modelspace()
            circles = []
            rectangles = []
            lines = []
            texts = []
            dimensions = []
            
            for entity in modelspace:
                try:
                    entity_data = {
                        'type': entity.dxftype(),
                        'layer': entity.dxf.layer,
                        'handle': entity.dxf.handle
                    }
                    
                    if entity.dxftype() == 'CIRCLE':
                        circles.append({
                            **entity_data,
                            'center': (entity.dxf.center.x, entity.dxf.center.y),
                            'radius': entity.dxf.radius,
                            'diameter': entity.dxf.radius * 2
                        })
                    
                    elif entity.dxftype() == 'LWPOLYLINE':
                        # Could be rectangular components
                        points = list(entity.get_points())
                        if len(points) >= 4:
                            rectangles.append({
                                **entity_data,
                                'points': points,
                                'closed': entity.closed
                            })
                    
                    elif entity.dxftype() == 'LINE':
                        lines.append({
                            **entity_data,
                            'start': (entity.dxf.start.x, entity.dxf.start.y),
                            'end': (entity.dxf.end.x, entity.dxf.end.y)
                        })
                    
                    elif entity.dxftype() == 'TEXT':
                        text_content = entity.dxf.text.strip()
                        if text_content:
                            texts.append({
                                **entity_data,
                                'text': text_content,
                                'position': (entity.dxf.insert.x, entity.dxf.insert.y),
                                'height': entity.dxf.height
                            })
                    
                    elif entity.dxftype() in ['DIMENSION', 'ALIGNED_DIMENSION', 'LINEAR_DIMENSION']:
                        dimensions.append({
                            **entity_data,
                            'measurement': getattr(entity.dxf, 'measurement', None),
                            'text': getattr(entity.dxf, 'text', '')
                        })
                
                except Exception as e:
                    logger.warning(f"Error processing entity {entity.dxftype()}: {str(e)}")
                    continue
            
            # Analyze components based on geometry
            detected_components = self._analyze_geometry_for_components(
                circles, rectangles, lines, texts, dimensions
            )
            
            # Extract title block information
            title_block = self._extract_title_block(texts)
            
            # Extract part list/BOM if present
            part_list = self._extract_part_list(texts)
            
            return {
                'success': True,
                'components': detected_components,
                'drawing_info': {
                    **drawing_info,
                    'title_block': title_block,
                    'part_list': part_list,
                    'entity_counts': {
                        'circles': len(circles),
                        'rectangles': len(rectangles),
                        'lines': len(lines),
                        'texts': len(texts),
                        'dimensions': len(dimensions)
                    }
                },
                'raw_geometry': {
                    'circles': circles,
                    'rectangles': rectangles,
                    'lines': lines,
                    'texts': texts,
                    'dimensions': dimensions
                }
            }
            
        except Exception as e:
            logger.error(f"DXF processing error: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to process DXF file: {str(e)}',
                'components': [],
                'drawing_info': {}
            }
    
    def _analyze_geometry_for_components(self, circles, rectangles, lines, texts, dimensions):
        """Analyze geometric entities to identify potential components"""
        components = []
        
        # Analyze circles (potential bearings, pulleys, wheels)
        for circle in circles:
            diameter = circle['diameter']
            component_type = self._classify_circular_component(diameter)
            
            components.append({
                'id': f"circle_{circle['handle']}",
                'type': component_type,
                'geometry': 'circular',
                'dimensions': {
                    'diameter': diameter,
                    'radius': circle['radius']
                },
                'position': circle['center'],
                'layer': circle['layer'],
                'confidence': 0.8,
                'source': 'drawing_geometry'
            })
        
        # Analyze rectangles (potential plates, brackets, frames)
        for rect in rectangles:
            if len(rect['points']) >= 4:
                width, height = self._calculate_rectangle_dimensions(rect['points'])
                component_type = self._classify_rectangular_component(width, height)
                
                components.append({
                    'id': f"rect_{rect['handle']}",
                    'type': component_type,
                    'geometry': 'rectangular',
                    'dimensions': {
                        'width': width,
                        'height': height,
                        'area': width * height
                    },
                    'points': rect['points'],
                    'layer': rect['layer'],
                    'confidence': 0.7,
                    'source': 'drawing_geometry'
                })
        
        # Look for component annotations in text
        for text in texts:
            component_info = self._extract_component_from_text(text['text'])
            if component_info:
                components.append({
                    'id': f"text_{text['handle']}",
                    'type': component_info['type'],
                    'name': component_info['name'],
                    'part_number': component_info.get('part_number'),
                    'specifications': component_info.get('specifications', {}),
                    'position': text['position'],
                    'layer': text['layer'],
                    'confidence': 0.9,
                    'source': 'drawing_annotation'
                })
        
        return components
    
    def _classify_circular_component(self, diameter):
        """Classify circular components based on diameter"""
        if diameter < 10:
            return 'small_bearing'
        elif diameter < 50:
            return 'bearing'
        elif diameter < 100:
            return 'pulley'
        elif diameter < 200:
            return 'wheel'
        else:
            return 'large_circular_component'
    
    def _classify_rectangular_component(self, width, height):
        """Classify rectangular components based on dimensions"""
        aspect_ratio = max(width, height) / min(width, height)
        area = width * height
        
        if aspect_ratio > 5:
            return 'bar' if max(width, height) > 100 else 'strip'
        elif area < 100:
            return 'small_plate'
        elif area < 1000:
            return 'bracket'
        else:
            return 'plate'
    
    def _calculate_rectangle_dimensions(self, points):
        """Calculate width and height from rectangle points"""
        try:
            if len(points) < 4:
                return 0, 0
            
            # Calculate distances between consecutive points
            distances = []
            for i in range(len(points)):
                p1 = points[i]
                p2 = points[(i + 1) % len(points)]
                dist = ((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)**0.5
                distances.append(dist)
            
            # For rectangles, we should have pairs of equal distances
            unique_distances = list(set(round(d, 2) for d in distances if d > 0.1))
            unique_distances.sort()
            
            if len(unique_distances) >= 2:
                return unique_distances[0], unique_distances[1]
            elif len(unique_distances) == 1:
                return unique_distances[0], unique_distances[0]
            else:
                return 0, 0
                
        except Exception:
            return 0, 0
    
    def _extract_component_from_text(self, text):
        """Extract component information from text annotations"""
        text_upper = text.upper()
        
        # Common component patterns
        component_patterns = {
            'BEARING': {'type': 'bearing', 'category': 'mechanical'},
            'PULLEY': {'type': 'pulley', 'category': 'mechanical'},
            'GEAR': {'type': 'gear', 'category': 'mechanical'},
            'SHAFT': {'type': 'shaft', 'category': 'mechanical'},
            'BOLT': {'type': 'bolt', 'category': 'fastener'},
            'SCREW': {'type': 'screw', 'category': 'fastener'},
            'WASHER': {'type': 'washer', 'category': 'fastener'},
            'MOTOR': {'type': 'motor', 'category': 'electrical'},
            'VALVE': {'type': 'valve', 'category': 'hydraulic'},
            'CYLINDER': {'type': 'cylinder', 'category': 'hydraulic'}
        }
        
        for pattern, info in component_patterns.items():
            if pattern in text_upper:
                return {
                    'type': info['type'],
                    'name': text,
                    'category': info['category']
                }
        
        return None
    
    def _extract_title_block(self, texts):
        """Extract title block information from text entities"""
        title_block = {}
        
        # Look for common title block fields
        for text in texts:
            text_content = text['text'].strip()
            text_upper = text_content.upper()
            
            # Drawing number
            if any(keyword in text_upper for keyword in ['DWG', 'DRAWING', 'PART NO', 'P/N']):
                if ':' in text_content:
                    title_block['drawing_number'] = text_content.split(':')[-1].strip()
            
            # Material specification
            if any(keyword in text_upper for keyword in ['MATERIAL', 'MAT', 'STEEL', 'ALUMINUM']):
                title_block['material'] = text_content
            
            # Scale
            if 'SCALE' in text_upper and ':' in text_content:
                title_block['scale'] = text_content.split(':')[-1].strip()
            
            # Date
            if any(keyword in text_upper for keyword in ['DATE', 'CREATED', 'MODIFIED']):
                title_block['date'] = text_content
        
        return title_block
    
    def _extract_part_list(self, texts):
        """Extract part list/BOM from drawing annotations"""
        part_list = []
        
        # Look for tabulated part lists
        potential_parts = []
        for text in texts:
            text_content = text['text'].strip()
            
            # Look for part number patterns
            if any(char.isdigit() for char in text_content) and len(text_content) > 3:
                potential_parts.append({
                    'text': text_content,
                    'position': text['position']
                })
        
        # Group nearby texts that might form part entries
        # This is a simplified implementation
        for part in potential_parts:
            part_list.append({
                'item': part['text'],
                'position': part['position']
            })
        
        return part_list
    
    def process_drawing_file(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Main method to process uploaded drawing file"""
        # Validate file
        validation = self.validate_file(file_path, original_filename)
        if not validation['valid']:
            return validation
        
        # Process based on file format
        file_format = validation['format']
        
        if file_format == 'dxf':
            result = self.extract_components_from_dxf(file_path)
        elif file_format in ['step', 'stp']:
            result = self.extract_components_from_step(file_path)
        else:
            return {
                'success': False,
                'error': f'Processing for {file_format} format not yet implemented'
            }
        
        if result['success']:
            # Add processing metadata
            result['processing_info'] = {
                'processed_at': datetime.now().isoformat(),
                'file_size': validation['size'],
                'file_format': file_format,
                'original_filename': original_filename
            }
        
        return result
    
    def save_processing_result(self, result: Dict[str, Any], session_id: str) -> str:
        """Save processing result to file for later retrieval"""
        try:
            # Create results directory if it doesn't exist
            results_dir = os.path.join('static', 'uploads', 'drawing_results')
            os.makedirs(results_dir, exist_ok=True)
            
            # Save result as JSON
            result_file = os.path.join(results_dir, f'{session_id}.json')
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            
            return result_file
            
        except Exception as e:
            logger.error(f"Error saving processing result: {str(e)}")
            return None
    
    def generate_component_visualization(self, components: List[Dict], drawing_info: Dict, session_id: str) -> Optional[str]:
        """Generate SVG visualization of detected components"""
        try:
            # Ensure output directory exists
            os.makedirs(self.svg_output_dir, exist_ok=True)
            
            # Create SVG drawing
            svg_filename = f"{session_id}_components.svg"
            svg_path = os.path.join(self.svg_output_dir, svg_filename)
            
            # SVG canvas settings
            canvas_width = 800
            canvas_height = 600
            dwg = svgwrite.Drawing(svg_path, size=(canvas_width, canvas_height))
            
            # Add background
            dwg.add(dwg.rect(insert=(0, 0), size=(canvas_width, canvas_height), 
                           fill='#f8f9fa', stroke='#dee2e6', stroke_width=1))
            
            # Add title
            title_text = drawing_info.get('original_filename', 'Component Analysis')
            dwg.add(dwg.text(title_text, insert=(20, 30), 
                           font_family='Arial', font_size='18px', font_weight='bold', fill='#212529'))
            
            # Component layout
            start_y = 70
            component_height = 100
            component_width = 350
            
            for i, component in enumerate(components):
                y_offset = start_y + (i * (component_height + 20))
                
                # Component box
                group = dwg.g()
                
                # Background box
                group.add(dwg.rect(insert=(20, y_offset), size=(component_width, component_height),
                                 fill='white', stroke='#007bff', stroke_width=2, rx=5))
                
                # Component type icon
                icon_x = 40
                icon_y = y_offset + 25
                
                if component.get('type') == 'locking_anchor_nut':
                    # Draw anchor nut icon
                    group.add(dwg.circle(center=(icon_x, icon_y), r=15, 
                                       fill='#ffc107', stroke='#f57c00', stroke_width=2))
                    group.add(dwg.text('⚓', insert=(icon_x-8, icon_y+5), 
                                     font_family='Arial', font_size='16px', fill='#f57c00'))
                elif 'fastener' in component.get('type', ''):
                    # Draw fastener icon
                    group.add(dwg.rect(insert=(icon_x-10, icon_y-10), size=(20, 20),
                                     fill='#28a745', stroke='#155724', stroke_width=2, rx=3))
                    group.add(dwg.text('⚙', insert=(icon_x-8, icon_y+5), 
                                     font_family='Arial', font_size='16px', fill='white'))
                else:
                    # Generic component icon
                    group.add(dwg.rect(insert=(icon_x-10, icon_y-10), size=(20, 20),
                                     fill='#6c757d', stroke='#495057', stroke_width=2, rx=3))
                
                # Component name
                name = component.get('name', 'Unknown Component')
                if len(name) > 30:
                    name = name[:30] + '...'
                group.add(dwg.text(name, insert=(icon_x + 30, icon_y - 5),
                                 font_family='Arial', font_size='14px', font_weight='bold', fill='#212529'))
                
                # Component type
                comp_type = component.get('type', 'unknown').replace('_', ' ').title()
                group.add(dwg.text(f"Type: {comp_type}", insert=(icon_x + 30, icon_y + 12),
                                 font_family='Arial', font_size='12px', fill='#6c757d'))
                
                # Confidence
                confidence = component.get('confidence', 0)
                confidence_color = '#28a745' if confidence > 0.8 else '#ffc107' if confidence > 0.6 else '#dc3545'
                group.add(dwg.text(f"Confidence: {confidence:.1%}", insert=(icon_x + 30, icon_y + 28),
                                 font_family='Arial', font_size='12px', fill=confidence_color))
                
                # Dimensions (if available)
                dimensions = component.get('dimensions', {})
                if dimensions:
                    dim_text = []
                    for key, value in list(dimensions.items())[:2]:  # Show max 2 dimensions
                        if isinstance(value, (int, float)):
                            dim_text.append(f"{key}: {value:.1f}mm")
                        else:
                            dim_text.append(f"{key}: {value}")
                    
                    if dim_text:
                        group.add(dwg.text(" | ".join(dim_text), insert=(icon_x + 30, icon_y + 44),
                                         font_family='Arial', font_size='11px', fill='#495057'))
                
                dwg.add(group)
            
            # Add legend
            legend_y = start_y + (len(components) * (component_height + 20)) + 20
            legend_group = dwg.g()
            
            legend_group.add(dwg.text("Legend:", insert=(20, legend_y),
                                    font_family='Arial', font_size='14px', font_weight='bold', fill='#212529'))
            
            # Legend items
            legend_items = [
                ("⚓", "#ffc107", "Anchor/Locking Components"),
                ("⚙", "#28a745", "Fasteners & Hardware"),
                ("▢", "#6c757d", "General Components")
            ]
            
            for i, (symbol, color, desc) in enumerate(legend_items):
                item_y = legend_y + 20 + (i * 18)
                legend_group.add(dwg.text(symbol, insert=(30, item_y),
                                        font_family='Arial', font_size='14px', fill=color))
                legend_group.add(dwg.text(desc, insert=(50, item_y),
                                        font_family='Arial', font_size='12px', fill='#495057'))
            
            dwg.add(legend_group)
            
            # Add processing info
            info_y = legend_y + 80
            dwg.add(dwg.text(f"Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                           insert=(20, info_y), font_family='Arial', font_size='10px', fill='#6c757d'))
            dwg.add(dwg.text(f"Components: {len(components)} detected", 
                           insert=(20, info_y + 15), font_family='Arial', font_size='10px', fill='#6c757d'))
            
            # Save SVG
            dwg.save()
            
            # Also generate PNG version if possible
            png_filename = None
            if PNG_SUPPORT:
                try:
                    png_filename = f"{session_id}_components.png"
                    png_path = os.path.join(self.svg_output_dir, png_filename)
                    cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=800, output_height=600)
                    logger.info(f"Generated PNG visualization: {png_filename}")
                except Exception as e:
                    logger.warning(f"Failed to generate PNG: {str(e)}")
            
            logger.info(f"Generated component visualization: {svg_filename}")
            return svg_filename
            
        except Exception as e:
            logger.error(f"Error generating component visualization: {str(e)}")
            return None
    
    def extract_components_from_step(self, file_path: str) -> Dict[str, Any]:
        """Extract components and specifications from STEP/STP file"""
        try:
            # Always proceed with filename and basic text analysis
            # Full 3D geometry processing would require additional libraries
            
            components = []
            drawing_info = {
                'filename': os.path.basename(file_path),
                'file_type': '3D STEP Model',
                'entities': [],
                'features': [],
                'materials': [],
                'part_name': '',
                'description': ''
            }
            
            # Extract filename-based component information
            filename = os.path.basename(file_path)
            component_info = self._analyze_step_filename(filename)
            
            if component_info:
                components.append({
                    'id': f"step_main_component",
                    'type': component_info['type'],
                    'name': component_info['name'],
                    'part_number': component_info.get('part_number'),
                    'specifications': component_info.get('specifications', {}),
                    'geometry': '3d_model',
                    'dimensions': component_info.get('dimensions', {}),
                    'confidence': 0.85,
                    'source': 'step_filename_analysis'
                })
            
            # Extract STEP file content information
            try:
                geometry_info = self._extract_basic_step_info(file_path)
                
                if geometry_info:
                    drawing_info.update(geometry_info)
                    
                    # Add geometry-based components from STEP file content
                    if geometry_info.get('detected_features'):
                        for feature in geometry_info['detected_features']:
                            components.append({
                                'id': f"step_feature_{len(components)}",
                                'type': feature['type'],
                                'name': feature['name'],
                                'geometry': '3d_feature',
                                'dimensions': feature.get('dimensions', {}),
                                'confidence': 0.75,
                                'source': 'step_content_analysis'
                            })
                    
                    # If STEP content has product information, use it to enhance the main component
                    if geometry_info.get('products') and components:
                        main_component = components[0]
                        product_name = geometry_info['products'][0]
                        main_component['specifications']['step_product_name'] = product_name
                        if product_name.lower() != main_component['name'].lower():
                            main_component['specifications']['alternative_name'] = product_name
            
            except Exception as e:
                logger.warning(f"Could not extract STEP file content: {str(e)}")
                # Continue with filename-based analysis only
            
            return {
                'success': True,
                'components': components,
                'drawing_info': drawing_info,
                'processing_method': 'step_analysis'
            }
            
        except Exception as e:
            logger.error(f"STEP processing error: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to process STEP file: {str(e)}',
                'components': [],
                'drawing_info': {}
            }
    
    def _analyze_step_filename(self, filename: str) -> Dict[str, Any]:
        """Analyze STEP filename to extract component information"""
        # Remove file extension
        name_part = filename.lower().replace('.stp', '').replace('.step', '')
        
        # Common mechanical component patterns
        component_patterns = {
            'anchor': {'type': 'anchor', 'category': 'fastener'},
            'nut': {'type': 'nut', 'category': 'fastener'},
            'bolt': {'type': 'bolt', 'category': 'fastener'},
            'screw': {'type': 'screw', 'category': 'fastener'},
            'washer': {'type': 'washer', 'category': 'fastener'},
            'lock': {'type': 'locking_mechanism', 'category': 'fastener'},
            'defeat': {'type': 'security_feature', 'category': 'fastener'},
            'bearing': {'type': 'bearing', 'category': 'mechanical'},
            'gear': {'type': 'gear', 'category': 'mechanical'},
            'pulley': {'type': 'pulley', 'category': 'mechanical'},
            'shaft': {'type': 'shaft', 'category': 'mechanical'},
            'plate': {'type': 'plate', 'category': 'structural'},
            'bracket': {'type': 'bracket', 'category': 'structural'},
            'housing': {'type': 'housing', 'category': 'enclosure'},
            'cover': {'type': 'cover', 'category': 'enclosure'}
        }
        
        detected_types = []
        detected_features = []
        
        for pattern, info in component_patterns.items():
            if pattern in name_part:
                detected_types.append(info['type'])
                detected_features.append(pattern)
        
        # Determine primary component type
        if detected_types:
            primary_type = detected_types[0]
            if len(detected_types) > 1:
                primary_type = 'composite_' + '_'.join(detected_types[:2])
        else:
            primary_type = 'mechanical_part'
        
        # Extract size/dimension information from filename
        dimensions = {}
        
        # Look for metric measurements (M6, M8, M10, etc.)
        metric_match = re.search(r'[mM](\d+)', name_part)
        if metric_match:
            thread_size = int(metric_match.group(1))
            dimensions['thread_diameter'] = thread_size
            dimensions['nominal_size'] = f"M{thread_size}"
        
        # Look for decimal measurements (6.5, 12.7, etc.)
        decimal_match = re.search(r'(\d+\.?\d*)', name_part)
        if decimal_match:
            dimension_value = float(decimal_match.group(1))
            if not dimensions.get('thread_diameter'):
                dimensions['primary_dimension'] = dimension_value
        
        # Special handling for anchor nuts
        if 'anchor' in name_part and 'nut' in name_part:
            primary_type = 'anchor_nut'
            if 'lock' in name_part or 'defeat' in name_part:
                primary_type = 'locking_anchor_nut'
        
        return {
            'type': primary_type,
            'name': filename,
            'part_number': self._extract_part_number(filename),
            'specifications': {
                'detected_features': detected_features,
                'category': 'fastener' if any(f in detected_features for f in ['anchor', 'nut', 'bolt', 'screw']) else 'mechanical'
            },
            'dimensions': dimensions
        }
    
    def _extract_part_number(self, filename: str) -> str:
        """Extract part number from filename if present"""
        # Common part number patterns
        patterns = [
            r'([A-Z]{2,}\d{3,})',  # Like ABC123, DEF456
            r'(\d{4,}[A-Z]*)',     # Like 1234A, 5678
            r'([A-Z]\d{2,}[A-Z]*)', # Like A123B, M6
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename.upper())
            if match:
                return match.group(1)
        
        return ''
    
    def _extract_freecad_geometry(self, file_path: str) -> Dict[str, Any]:
        """Extract geometry information using FreeCAD"""
        try:
            # This would require FreeCAD to be properly installed
            # For now, return basic info
            return {
                'geometry_engine': 'freecad',
                'status': 'freecad_not_fully_configured',
                'detected_features': []
            }
        except Exception as e:
            logger.warning(f"FreeCAD geometry extraction failed: {str(e)}")
            return {}
    
    def _extract_opencascade_geometry(self, file_path: str) -> Dict[str, Any]:
        """Extract geometry information using OpenCASCADE"""
        try:
            # This would require OpenCASCADE to be properly installed
            # For now, return basic info
            return {
                'geometry_engine': 'opencascade',
                'status': 'opencascade_not_fully_configured',
                'detected_features': []
            }
        except Exception as e:
            logger.warning(f"OpenCASCADE geometry extraction failed: {str(e)}")
            return {}
    
    def _extract_basic_step_info(self, file_path: str) -> Dict[str, Any]:
        """Extract basic information from STEP file by parsing text content"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(10000)  # Read first 10KB
            
            info = {
                'geometry_engine': 'text_parser',
                'detected_features': [],
                'entities': []
            }
            
            # Extract header information
            if 'FILE_DESCRIPTION' in content:
                desc_match = re.search(r"FILE_DESCRIPTION\s*\(\s*\(\s*'([^']+)'", content)
                if desc_match:
                    info['description'] = desc_match.group(1)
            
            if 'FILE_NAME' in content:
                name_match = re.search(r"FILE_NAME\s*\(\s*'([^']+)'", content)
                if name_match:
                    info['original_filename'] = name_match.group(1)
            
            # Look for product definitions
            product_matches = re.findall(r"PRODUCT\s*\(\s*'([^']+)'", content)
            if product_matches:
                info['products'] = product_matches
                
                # Try to classify based on product names
                for product in product_matches:
                    if any(keyword in product.lower() for keyword in ['nut', 'anchor', 'fastener']):
                        info['detected_features'].append({
                            'name': product,
                            'type': 'fastener_component',
                            'dimensions': {}
                        })
            
            return info
            
        except Exception as e:
            logger.warning(f"Basic STEP info extraction failed: {str(e)}")
            return {}