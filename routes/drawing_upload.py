"""
Drawing Upload Routes for CAD file processing
"""
import os
import uuid
import json
from flask import Blueprint, render_template, request, jsonify, current_app, session
from werkzeug.utils import secure_filename
from services.drawing_processor import DrawingProcessor
import logging

logger = logging.getLogger(__name__)

drawing_upload_bp = Blueprint('drawing_upload', __name__)

@drawing_upload_bp.route('/upload-drawing', methods=['POST'])
def upload_drawing():
    """Handle drawing file upload and processing"""
    try:
        if 'drawing_file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No drawing file provided'
            }), 400
        
        file = request.files['drawing_file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Generate session ID for this processing
        session_id = str(uuid.uuid4())
        
        # Secure filename
        original_filename = file.filename
        filename = secure_filename(original_filename)
        
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join('static', 'uploads', 'drawings')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save uploaded file
        file_path = os.path.join(upload_dir, f"{session_id}_{filename}")
        file.save(file_path)
        
        # Process the drawing
        processor = DrawingProcessor()
        result = processor.process_drawing_file(file_path, original_filename)
        
        if result.get('success'):
            # Save processing result
            result_file = processor.save_processing_result(result, session_id)
            
            # Store session info
            session['drawing_session_id'] = session_id
            session['drawing_filename'] = original_filename
            
            return jsonify({
                'success': True,
                'session_id': session_id,
                'redirect_url': f'/component-scanning/drawing-results/{session_id}',
                'components_count': len(result.get('components', [])),
                'processing_info': result.get('processing_info', {})
            })
        else:
            # Clean up file on error
            try:
                os.remove(file_path)
            except:
                pass
            
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown processing error')
            }), 400
    
    except Exception as e:
        logger.error(f"Drawing upload error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Upload failed: {str(e)}'
        }), 500

@drawing_upload_bp.route('/drawing-results/<session_id>')
def drawing_results(session_id):
    """Display drawing processing results"""
    try:
        # Load processing result
        result_file = os.path.join('static', 'uploads', 'drawing_results', f'{session_id}.json')
        
        if not os.path.exists(result_file):
            return render_template('component_scanning/error.html', 
                                 error="Processing result not found"), 404
        
        with open(result_file, 'r') as f:
            result = json.load(f)
        
        # Get additional context from session if available
        drawing_filename = session.get('drawing_filename', 'Unknown')
        
        return render_template('component_scanning/drawing_results.html',
                             result=result,
                             session_id=session_id,
                             drawing_filename=drawing_filename)
    
    except Exception as e:
        logger.error(f"Error displaying drawing results: {str(e)}")
        return render_template('component_scanning/error.html', 
                             error=f"Failed to load results: {str(e)}"), 500

@drawing_upload_bp.route('/drawing-component-details/<session_id>/<component_id>')
def drawing_component_details(session_id, component_id):
    """Get detailed information about a specific component from drawing"""
    try:
        result_file = os.path.join('static', 'uploads', 'drawing_results', f'{session_id}.json')
        
        if not os.path.exists(result_file):
            return jsonify({'error': 'Result not found'}), 404
        
        with open(result_file, 'r') as f:
            result = json.load(f)
        
        # Find the specific component
        components = result.get('components', [])
        component = next((c for c in components if c['id'] == component_id), None)
        
        if not component:
            return jsonify({'error': 'Component not found'}), 404
        
        return jsonify({
            'success': True,
            'component': component,
            'drawing_info': result.get('drawing_info', {})
        })
    
    except Exception as e:
        logger.error(f"Error getting component details: {str(e)}")
        return jsonify({'error': str(e)}), 500

@drawing_upload_bp.route('/create-bom-from-drawing/<session_id>')
def create_bom_from_drawing(session_id):
    """Create BOM from drawing components"""
    try:
        result_file = os.path.join('static', 'uploads', 'drawing_results', f'{session_id}.json')
        
        if not os.path.exists(result_file):
            return jsonify({'error': 'Result not found'}), 404
        
        with open(result_file, 'r') as f:
            result = json.load(f)
        
        components = result.get('components', [])
        drawing_info = result.get('drawing_info', {})
        
        return render_template('component_scanning/create_bom_from_drawing.html',
                             components=components,
                             drawing_info=drawing_info,
                             session_id=session_id)
    
    except Exception as e:
        logger.error(f"Error creating BOM from drawing: {str(e)}")
        return render_template('component_scanning/error.html', 
                             error=f"Failed to create BOM: {str(e)}"), 500

@drawing_upload_bp.route('/generate-visualization/<session_id>')
def generate_visualization(session_id):
    """Generate and display component visualization"""
    try:
        result_file = os.path.join('static', 'uploads', 'drawing_results', f'{session_id}.json')
        
        if not os.path.exists(result_file):
            return jsonify({'error': 'Result not found'}), 404
        
        with open(result_file, 'r') as f:
            result = json.load(f)
        
        components = result.get('components', [])
        drawing_info = result.get('drawing_info', {})
        
        # Check if visualization already exists
        svg_filename = f"{session_id}_components.svg"
        png_filename = f"{session_id}_components.png"
        svg_path = os.path.join('static', 'uploads', 'generated_images', svg_filename)
        png_path = os.path.join('static', 'uploads', 'generated_images', png_filename)
        
        if not os.path.exists(svg_path):
            # Generate new visualization
            from services.drawing_processor import DrawingProcessor
            processor = DrawingProcessor()
            svg_filename = processor.generate_component_visualization(components, drawing_info, session_id)
            
            if not svg_filename:
                return jsonify({'error': 'Failed to generate visualization'}), 500
        
        # Check if PNG version exists
        png_url = None
        if os.path.exists(png_path):
            png_url = f'/static/uploads/generated_images/{png_filename}'
        
        return jsonify({
            'success': True,
            'svg_url': f'/static/uploads/generated_images/{svg_filename}',
            'png_url': png_url,
            'components_count': len(components)
        })
    
    except Exception as e:
        logger.error(f"Error generating visualization: {str(e)}")
        return jsonify({'error': str(e)}), 500