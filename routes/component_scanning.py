from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime
import logging
import cv2

# Import our services
from services.component_detector import ComponentDetector
from services.ai_component_detector import AIComponentDetector
from services.intelligent_mock_detector import IntelligentMockDetector
from services.advanced_cv_detector import AdvancedCVDetector
from services.component_matcher import ComponentInventoryMatcher
from utils.svg_generator import ComponentLayoutGenerator
from utils.image_annotator import ComponentImageAnnotator

# Import models
from models.visual_scanning import ComponentDetection, DetectedComponent
from app import db

logger = logging.getLogger(__name__)

component_scanning_bp = Blueprint('component_scanning', __name__, url_prefix='/component-scanning')

# Configuration
UPLOAD_FOLDER = 'static/component_detection/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@component_scanning_bp.route('/')
@login_required
def dashboard():
    """Component scanning dashboard"""
    # Get recent detection sessions
    recent_sessions = ComponentDetection.query.filter_by(
        created_by=current_user.id
    ).order_by(ComponentDetection.created_at.desc()).limit(10).all()
    
    # Get statistics
    stats = {
        'total_sessions': ComponentDetection.query.filter_by(created_by=current_user.id).count(),
        'successful_sessions': ComponentDetection.query.filter_by(
            created_by=current_user.id, status='completed'
        ).count(),
        'total_components_detected': db.session.query(db.func.sum(
            ComponentDetection.total_components_detected
        )).filter_by(created_by=current_user.id).scalar() or 0,
        'average_processing_time': db.session.query(db.func.avg(
            ComponentDetection.processing_time
        )).filter_by(created_by=current_user.id, status='completed').scalar() or 0
    }
    
    return render_template('component_scanning/dashboard.html',
                         recent_sessions=recent_sessions,
                         stats=stats)

@component_scanning_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_image():
    """Upload and process component image"""
    if request.method == 'GET':
        return render_template('component_scanning/upload.html')
    
    try:
        # Check if file was uploaded
        if 'image' not in request.files:
            flash('No image file provided', 'error')
            return redirect(request.url)
        
        file = request.files['image']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if not allowed_file(file.filename):
            flash('Invalid file type. Please upload PNG, JPG, JPEG, BMP, or TIFF files.', 'error')
            return redirect(request.url)
        
        # Check file size
        if request.content_length > MAX_FILE_SIZE:
            flash('File too large. Maximum size is 16MB.', 'error')
            return redirect(request.url)
        
        # Get detection parameters
        confidence_threshold = float(request.form.get('confidence_threshold', 0.5))
        confidence_threshold = max(0.1, min(0.95, confidence_threshold))  # Clamp between 0.1-0.95
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{session_id}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(filepath)
        
        # Create detection record
        detection_record = ComponentDetection(
            session_id=session_id,
            original_image_path=filepath,
            confidence_threshold=confidence_threshold,
            status='processing',
            created_by=current_user.id
        )
        db.session.add(detection_record)
        db.session.commit()
        
        # Process image in background (for demo, we'll do it synchronously)
        result = process_image_detection(filepath, session_id, confidence_threshold)
        
        if result['status'] == 'completed':
            flash(f'Detection completed! Found {result["total_components"]} components.', 'success')
            return redirect(url_for('component_scanning.view_results', session_id=session_id))
        else:
            flash(f'Detection failed: {result.get("error_message", "Unknown error")}', 'error')
            return redirect(url_for('component_scanning.upload_image'))
            
    except Exception as e:
        logger.error(f"Upload error: {e}")
        flash('An error occurred during upload. Please try again.', 'error')
        return redirect(url_for('component_scanning.upload_image'))

def process_image_detection(image_path: str, session_id: str, confidence_threshold: float):
    """Process image detection (simplified version for demo)"""
    try:
        # For demo purposes, we'll create a simple mock detector
        # In a real implementation, this would use the full YOLO detection
        
        # Load image to get dimensions
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("Could not load image")
        
        height, width = image.shape[:2]
        
        # Try AI-powered detection first, fallback to intelligent mock if needed
        try:
            detector = AIComponentDetector()
            detection_result = detector.detect_components(image_path)
            
            if detection_result['status'] == 'error':
                # Check if it's a quota/API issue
                error_msg = detection_result.get('error', '').lower()
                if 'quota' in error_msg or '429' in error_msg or 'insufficient_quota' in error_msg:
                    logger.warning("OpenAI quota exceeded, using advanced CV detector")
                    fallback_detector = AdvancedCVDetector()
                    detection_result = fallback_detector.detect_components(image_path)
                else:
                    raise Exception(f"AI detection failed: {detection_result.get('error', 'Unknown error')}")
        
        except Exception as ai_error:
            logger.warning(f"AI detection failed ({ai_error}), using advanced CV detector")
            fallback_detector = AdvancedCVDetector()
            detection_result = fallback_detector.detect_components(image_path)
        
        # Extract AI detection results
        ai_detections = detection_result['components']
        
        logger.info(f"AI detected {len(ai_detections)} components with average confidence: {detection_result.get('confidence_summary', {}).get('average', 0)}")
        
        # Filter by confidence threshold
        filtered_detections = [
            detection for detection in ai_detections 
            if detection.get('confidence', 0) >= confidence_threshold
        ]
        
        logger.info(f"After filtering by confidence threshold {confidence_threshold}: {len(filtered_detections)} components remain")
        
        # Update detection record
        detection_record = ComponentDetection.query.filter_by(session_id=session_id).first()
        detection_record.total_components_detected = len(filtered_detections)
        detection_record.status = 'completed'
        detection_record.processing_time = 3.0  # AI processing time
        
        # Create detected component records
        for detection_data in filtered_detections:
            # Convert pixel coordinates to normalized coordinates for storage
            pixel_coords = detection_data.get('pixel_coords', {})
            bbox_x = pixel_coords.get('x1', 0) / width if width > 0 else 0
            bbox_y = pixel_coords.get('y1', 0) / height if height > 0 else 0
            bbox_width = (pixel_coords.get('x2', 0) - pixel_coords.get('x1', 0)) / width if width > 0 else 0
            bbox_height = (pixel_coords.get('y2', 0) - pixel_coords.get('y1', 0)) / height if height > 0 else 0
            
            detected_component = DetectedComponent(
                detection_id=detection_record.id,
                component_class=detection_data['component_class'],
                confidence=detection_data['confidence'],
                bbox_x=bbox_x,
                bbox_y=bbox_y,
                bbox_width=bbox_width,
                bbox_height=bbox_height,
                estimated_width_mm=detection_data.get('estimated_width_mm'),
                estimated_height_mm=detection_data.get('estimated_height_mm'),
                estimated_area_mm2=detection_data.get('estimated_area_mm2'),
                suggested_quantity=detection_data.get('suggested_quantity', 1)
            )
            db.session.add(detected_component)
        
        # Create result directories
        os.makedirs("static/component_detection/results", exist_ok=True)
        os.makedirs("static/component_detection/layouts", exist_ok=True)
        
        # Create annotated image with component markers and labels
        result_image_path = f"static/component_detection/results/result_{session_id}.jpg"
        try:
            annotator = ComponentImageAnnotator()
            annotator.annotate_detection_results(
                image_path=image_path,
                components=filtered_detections,
                output_path=result_image_path,
                show_confidence=True,
                show_dimensions=True
            )
            detection_record.result_image_path = result_image_path
            logger.info(f"Created annotated detection image: {result_image_path}")
        except Exception as e:
            logger.warning(f"Failed to create annotated image: {e}")
            # Fallback to copy original image
            import shutil
            shutil.copy2(image_path, result_image_path)
            detection_record.result_image_path = result_image_path
        
        # Generate SVG layout with AI detection results
        svg_path = f"static/component_detection/layouts/layout_{session_id}.svg"
        create_demo_svg_layout(svg_path, filtered_detections, width, height)
        detection_record.svg_layout_path = svg_path
        
        db.session.commit()
        
        return {
            'status': 'completed',
            'session_id': session_id,
            'total_components': len(filtered_detections)
        }
        
    except Exception as e:
        logger.error(f"Detection processing error: {e}")
        
        # Update record with error
        detection_record = ComponentDetection.query.filter_by(session_id=session_id).first()
        if detection_record:
            detection_record.status = 'failed'
            detection_record.error_message = str(e)
            db.session.commit()
        
        return {
            'status': 'failed',
            'error_message': str(e)
        }

@component_scanning_bp.route('/results/<session_id>')
@login_required
def view_results(session_id):
    """View detection results"""
    detection = ComponentDetection.query.filter_by(
        session_id=session_id,
        created_by=current_user.id
    ).first_or_404()
    
    if detection.status == 'processing':
        return render_template('component_scanning/processing.html', detection=detection)
    
    # Get detected components
    components = DetectedComponent.query.filter_by(detection_id=detection.id).all()
    
    # Get inventory matches (mock for demo)
    matcher = ComponentInventoryMatcher()
    component_dicts = []
    for comp in components:
        component_dicts.append({
            'component_class': comp.component_class,
            'confidence': comp.confidence,
            'estimated_width_mm': comp.estimated_width_mm,
            'estimated_height_mm': comp.estimated_height_mm,
            'estimated_area_mm2': comp.estimated_area_mm2
        })
    
    enhanced_components = matcher.match_detections_with_inventory(component_dicts)
    suggestions = matcher.suggest_inventory_actions(enhanced_components)
    
    return render_template('component_scanning/results.html',
                         detection=detection,
                         components=components,
                         enhanced_components=enhanced_components,
                         suggestions=suggestions)

@component_scanning_bp.route('/create-bom/<session_id>')
@login_required
def create_bom(session_id):
    """Create Bill of Materials from detection results"""
    detection = ComponentDetection.query.filter_by(
        session_id=session_id,
        created_by=current_user.id
    ).first_or_404()
    
    # Get components and create BOM
    components = DetectedComponent.query.filter_by(detection_id=detection.id).all()
    
    matcher = ComponentInventoryMatcher()
    component_dicts = []
    for comp in components:
        component_dicts.append({
            'component_class': comp.component_class,
            'confidence': comp.confidence,
            'matched_item_id': comp.matched_item_id,
            'suggested_quantity': 1
        })
    
    enhanced_components = matcher.match_detections_with_inventory(component_dicts)
    product_name = request.args.get('product_name', f'Product from {session_id[:8]}')
    bom_data = matcher.create_bom_from_detections(enhanced_components, product_name)
    
    return render_template('component_scanning/create_bom.html',
                         detection=detection,
                         bom_data=bom_data,
                         product_name=product_name)

@component_scanning_bp.route('/download-layout/<session_id>')
@login_required
def download_layout(session_id):
    """Download SVG layout file"""
    detection = ComponentDetection.query.filter_by(
        session_id=session_id,
        created_by=current_user.id
    ).first_or_404()
    
    if detection.svg_layout_path and os.path.exists(detection.svg_layout_path):
        return send_file(detection.svg_layout_path, as_attachment=True,
                        download_name=f'component_layout_{session_id}.svg')
    else:
        flash('Layout file not found', 'error')
        return redirect(url_for('component_scanning.view_results', session_id=session_id))

@component_scanning_bp.route('/api/detection-status/<session_id>')
@login_required
def api_detection_status(session_id):
    """API endpoint to check detection status"""
    detection = ComponentDetection.query.filter_by(
        session_id=session_id,
        created_by=current_user.id
    ).first()
    
    if not detection:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify({
        'status': detection.status,
        'total_components': detection.total_components_detected,
        'processing_time': detection.processing_time,
        'error_message': detection.error_message
    })

@component_scanning_bp.route('/history')
@login_required
def detection_history():
    """View detection history"""
    page = request.args.get('page', 1, type=int)
    
    detections = ComponentDetection.query.filter_by(
        created_by=current_user.id
    ).order_by(ComponentDetection.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('component_scanning/history.html', detections=detections)

@component_scanning_bp.route('/delete/<session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    """Delete detection session and associated files"""
    detection = ComponentDetection.query.filter_by(
        session_id=session_id,
        created_by=current_user.id
    ).first_or_404()
    
    try:
        # Delete associated files
        files_to_delete = [
            detection.original_image_path,
            detection.result_image_path,
            detection.svg_layout_path
        ]
        
        for file_path in files_to_delete:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        
        # Delete database records (cascade will handle DetectedComponent records)
        db.session.delete(detection)
        db.session.commit()
        
        flash('Detection session deleted successfully', 'success')
        
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        flash('Error deleting session', 'error')
        db.session.rollback()
    
    return redirect(url_for('component_scanning.detection_history'))

def create_demo_svg_layout(svg_path: str, detections: list, image_width: int, image_height: int):
    """Create a simple SVG layout for demo purposes"""
    try:
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{image_width}" height="{image_height}" xmlns="http://www.w3.org/2000/svg">
    <rect width="100%" height="100%" fill="#f8f9fa" stroke="#dee2e6" stroke-width="2"/>
    <text x="10" y="25" font-family="Arial" font-size="16" font-weight="bold" fill="#333">
        Component Layout - {len(detections)} components detected
    </text>
'''
        
        colors = ['#007bff', '#28a745', '#ffc107', '#dc3545', '#6610f2']
        
        for i, detection in enumerate(detections):
            color = colors[i % len(colors)]
            x = detection['pixel_coords']['x1']
            y = detection['pixel_coords']['y1'] 
            width = detection['pixel_coords']['x2'] - x
            height = detection['pixel_coords']['y2'] - y
            
            # Draw bounding box
            svg_content += f'''
    <rect x="{x}" y="{y}" width="{width}" height="{height}" 
          fill="none" stroke="{color}" stroke-width="3" opacity="0.8"/>
    <text x="{x}" y="{y-5}" font-family="Arial" font-size="12" fill="{color}" font-weight="bold">
        {detection['component_class']} ({detection['confidence']:.2f})
    </text>'''
        
        svg_content += '\n</svg>'
        
        with open(svg_path, 'w') as f:
            f.write(svg_content)
            
    except Exception as e:
        logger.error(f"Error creating SVG layout: {e}")