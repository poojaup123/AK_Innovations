from app import db
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

class ComponentDetection(db.Model):
    """Store component detection results from images"""
    __tablename__ = 'component_detections'
    
    id = db.Column(Integer, primary_key=True)
    session_id = db.Column(String(100), nullable=False, index=True)
    original_image_path = db.Column(String(500), nullable=False)
    result_image_path = db.Column(String(500))
    svg_layout_path = db.Column(String(500))
    
    total_components_detected = db.Column(Integer, default=0)
    confidence_threshold = db.Column(Float, default=0.5)
    detection_model = db.Column(String(100), default='yolov8n')
    
    processing_time = db.Column(Float)  # seconds
    status = db.Column(String(50), default='pending')  # pending, processing, completed, failed
    error_message = db.Column(Text)
    
    created_at = db.Column(DateTime, default=datetime.utcnow)
    created_by = db.Column(Integer, ForeignKey('users.id'))
    
    # Relationships
    detected_components = relationship('DetectedComponent', back_populates='detection_session', cascade='all, delete-orphan')
    user = relationship('User', backref='component_detections')
    
    def __repr__(self):
        return f'<ComponentDetection {self.session_id}: {self.total_components_detected} components>'

class DetectedComponent(db.Model):
    """Individual detected component details"""
    __tablename__ = 'detected_components'
    
    id = db.Column(Integer, primary_key=True)
    detection_id = db.Column(Integer, ForeignKey('component_detections.id'), nullable=False)
    
    # Detection details
    component_class = db.Column(String(100))  # YOLO detected class name
    confidence = db.Column(Float)
    
    # Bounding box coordinates (normalized 0-1)
    bbox_x = db.Column(Float)
    bbox_y = db.Column(Float) 
    bbox_width = db.Column(Float)
    bbox_height = db.Column(Float)
    
    # Physical dimensions (estimated in mm)
    estimated_width_mm = db.Column(Float)
    estimated_height_mm = db.Column(Float)
    estimated_area_mm2 = db.Column(Float)
    
    # Inventory matching
    matched_item_id = db.Column(Integer, ForeignKey('items.id'))
    match_confidence = db.Column(Float)  # How confident the inventory match is
    suggested_quantity = db.Column(Integer, default=1)
    
    # Component image crop path
    cropped_image_path = db.Column(String(500))
    
    created_at = db.Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    detection_session = relationship('ComponentDetection', back_populates='detected_components')
    matched_item = relationship('Item', backref='detected_components')
    
    def __repr__(self):
        return f'<DetectedComponent {self.component_class}: {self.confidence:.2f}>'

class ComponentDetectionTemplate(db.Model):
    """Store template images for better component matching"""
    __tablename__ = 'component_detection_templates'
    
    id = db.Column(Integer, primary_key=True)
    item_id = db.Column(Integer, ForeignKey('items.id'), nullable=False)
    
    template_image_path = db.Column(String(500), nullable=False)
    template_name = db.Column(String(200))
    description = db.Column(Text)
    
    # Template matching settings
    scale_factor = db.Column(Float, default=1.0)
    rotation_tolerance = db.Column(Integer, default=15)  # degrees
    match_threshold = db.Column(Float, default=0.8)
    
    is_active = db.Column(Boolean, default=True)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    created_by = db.Column(Integer, ForeignKey('users.id'))
    
    # Relationships
    item = relationship('Item', backref='detection_templates')
    user = relationship('User', backref='created_templates')
    
    def __repr__(self):
        return f'<ComponentTemplate {self.template_name} for {self.item.item_name}>'