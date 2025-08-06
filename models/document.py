"""
Document models for storing uploaded files across different modules
"""
from app import db
from datetime import datetime
from sqlalchemy import func

class Document(db.Model):
    """Model for storing uploaded documents"""
    __tablename__ = 'documents'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    
    # File information
    original_filename = db.Column(db.String(255), nullable=False)
    saved_filename = db.Column(db.String(255), nullable=False, unique=True)
    file_path = db.Column(db.Text, nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100))
    
    # Metadata
    description = db.Column(db.Text)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Module association (which module uploaded this)
    module_name = db.Column(db.String(50), nullable=False)  # 'grn', 'jobwork', 'production', etc.
    reference_id = db.Column(db.Integer)  # ID of the record this document is associated with
    reference_type = db.Column(db.String(50))  # 'grn', 'job_work', 'purchase_order', etc.
    
    # Document category
    document_type = db.Column(db.String(50))  # 'invoice', 'certificate', 'report', 'challan', etc.
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    uploader = db.relationship('User', backref='user_uploaded_documents')
    
    def __repr__(self):
        return f'<Document {self.original_filename}>'
    
    @property
    def file_extension(self):
        """Get file extension"""
        return self.original_filename.rsplit('.', 1)[-1].lower() if '.' in self.original_filename else ''
    
    @property
    def is_image(self):
        """Check if document is an image"""
        image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tif', 'tiff'}
        return self.file_extension in image_extensions
    
    @property
    def is_pdf(self):
        """Check if document is a PDF"""
        return self.file_extension == 'pdf'
    
    @property
    def formatted_size(self):
        """Get formatted file size"""
        from utils.documents import format_file_size
        return format_file_size(self.file_size)
    
    @property
    def icon_class(self):
        """Get CSS icon class for file type"""
        from utils.documents import get_file_icon
        return get_file_icon(self.original_filename)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'original_filename': self.original_filename,
            'saved_filename': self.saved_filename,
            'file_size': self.file_size,
            'formatted_size': self.formatted_size,
            'mime_type': self.mime_type,
            'description': self.description,
            'upload_date': self.upload_date.isoformat() if self.upload_date else None,
            'module_name': self.module_name,
            'reference_id': self.reference_id,
            'reference_type': self.reference_type,
            'document_type': self.document_type,
            'is_image': self.is_image,
            'is_pdf': self.is_pdf,
            'icon_class': self.icon_class
        }

class DocumentAccessLog(db.Model):
    """Log document access for audit trail"""
    __tablename__ = 'document_access_logs'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    access_type = db.Column(db.String(20), nullable=False)  # 'view', 'download', 'delete'
    access_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    
    # Relationships
    document = db.relationship('Document', backref='access_logs')
    user = db.relationship('User', backref='document_accesses')

# Add document relationships to existing models
def add_document_relationships():
    """Add document relationships to existing models (called after models are imported)"""
    try:
        from models.grn import GRN
        from models import JobWork, PurchaseOrder, Production
        
        # Add documents relationship to GRN
        if not hasattr(GRN, 'documents'):
            def get_grn_documents(self):
                return Document.query.filter_by(
                    reference_type='grn',
                    reference_id=self.id,
                    is_active=True
                ).all()
            GRN.documents = property(get_grn_documents)
        
        # Add documents relationship to JobWork
        if not hasattr(JobWork, 'documents'):
            def get_jobwork_documents(self):
                return Document.query.filter_by(
                    reference_type='job_work',
                    reference_id=self.id,
                    is_active=True
                ).all()
            JobWork.documents = property(get_jobwork_documents)
        
        # Add documents relationship to PurchaseOrder
        if not hasattr(PurchaseOrder, 'documents'):
            def get_po_documents(self):
                return Document.query.filter_by(
                    reference_type='purchase_order',
                    reference_id=self.id,
                    is_active=True
                ).all()
            PurchaseOrder.documents = property(get_po_documents)
            
    except ImportError:
        # Models not available yet, will be added later
        pass

# Helper functions for document management
def create_document_record(file_info, module_name, reference_type=None, reference_id=None, 
                          document_type=None, description=None, user_id=None):
    """Create a document record in the database"""
    if not file_info or not file_info.get('success'):
        return None
    
    document = Document(
        original_filename=file_info['original_filename'],
        saved_filename=file_info['saved_filename'],
        file_path=file_info['file_path'],
        file_size=file_info['file_size'],
        mime_type=file_info['mime_type'],
        description=description,
        module_name=module_name,
        reference_type=reference_type,
        reference_id=reference_id,
        document_type=document_type,
        uploaded_by=user_id
    )
    
    db.session.add(document)
    return document

def get_documents_for_reference(reference_type, reference_id):
    """Get all documents for a specific reference"""
    return Document.query.filter_by(
        reference_type=reference_type,
        reference_id=reference_id,
        is_active=True
    ).order_by(Document.upload_date.desc()).all()

def log_document_access(document_id, user_id, access_type, ip_address=None, user_agent=None):
    """Log document access"""
    log_entry = DocumentAccessLog(
        document_id=document_id,
        user_id=user_id,
        access_type=access_type,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.session.add(log_entry)
    return log_entry