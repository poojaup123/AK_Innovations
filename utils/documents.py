"""
Document utilities for handling file uploads across material receiving processes
"""
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
import mimetypes

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'pdf', 'jpg', 'jpeg', 'png', 'gif', 
    'doc', 'docx', 'xls', 'xlsx', 'txt',
    'csv', 'tif', 'tiff', 'bmp'
}

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_size(file):
    """Get file size"""
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning
    return size

def validate_uploaded_file(file):
    """Validate uploaded file"""
    errors = []
    
    if not file or file.filename == '':
        errors.append("No file selected")
        return errors
    
    if not allowed_file(file.filename):
        errors.append(f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}")
    
    file_size = get_file_size(file)
    if file_size > MAX_FILE_SIZE:
        errors.append(f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    return errors

def generate_unique_filename(original_filename):
    """Generate unique filename while preserving extension"""
    if not original_filename:
        return None
    
    # Get file extension
    ext = ''
    if '.' in original_filename:
        ext = '.' + original_filename.rsplit('.', 1)[1].lower()
    
    # Generate unique name with timestamp and UUID
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    
    return f"{timestamp}_{unique_id}{ext}"

def save_uploaded_file(file, subfolder='general'):
    """Save uploaded file and return file info"""
    if not file:
        return None
    
    # Validate file
    errors = validate_uploaded_file(file)
    if errors:
        return {'error': errors[0]}
    
    try:
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join(current_app.root_path, 'uploads', subfolder)
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        unique_filename = generate_unique_filename(original_filename)
        
        # Save file
        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)
        
        # Get file info
        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        
        return {
            'success': True,
            'original_filename': original_filename,
            'saved_filename': unique_filename,
            'file_path': file_path,
            'relative_path': os.path.join('uploads', subfolder, unique_filename),
            'file_size': file_size,
            'mime_type': mime_type or 'application/octet-stream',
            'upload_date': datetime.now()
        }
        
    except Exception as e:
        return {'error': f'Failed to save file: {str(e)}'}

def save_multiple_files(files, subfolder='general'):
    """Save multiple uploaded files"""
    results = []
    
    if not files:
        return results
    
    for file in files:
        if file and file.filename:
            result = save_uploaded_file(file, subfolder)
            if result:
                results.append(result)
    
    return results

def get_file_icon(filename):
    """Get appropriate icon class for file type"""
    if not filename:
        return 'fas fa-file'
    
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    
    icon_map = {
        'pdf': 'fas fa-file-pdf text-danger',
        'doc': 'fas fa-file-word text-primary',
        'docx': 'fas fa-file-word text-primary',
        'xls': 'fas fa-file-excel text-success',
        'xlsx': 'fas fa-file-excel text-success',
        'jpg': 'fas fa-file-image text-info',
        'jpeg': 'fas fa-file-image text-info',
        'png': 'fas fa-file-image text-info',
        'gif': 'fas fa-file-image text-info',
        'txt': 'fas fa-file-alt text-secondary',
        'csv': 'fas fa-file-csv text-success'
    }
    
    return icon_map.get(ext, 'fas fa-file text-muted')

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if not size_bytes:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    
    return f"{size_bytes:.1f} TB"

def delete_file(file_path):
    """Delete uploaded file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        print(f"Error deleting file {file_path}: {e}")
    return False

class DocumentUploadManager:
    """Manager class for handling document uploads in different modules"""
    
    def __init__(self, module_name):
        self.module_name = module_name
    
    def process_form_files(self, form):
        """Process files from a form"""
        files = []
        
        if hasattr(form, 'supporting_documents') and form.supporting_documents.data:
            uploaded_files = save_multiple_files(
                form.supporting_documents.data, 
                subfolder=self.module_name
            )
            files.extend(uploaded_files)
        
        return files
    
    def get_upload_summary(self, files):
        """Get summary of uploaded files"""
        if not files:
            return "No documents uploaded"
        
        total_size = sum(f.get('file_size', 0) for f in files if f.get('success'))
        file_count = len([f for f in files if f.get('success')])
        
        return f"{file_count} document(s) uploaded ({format_file_size(total_size)})"

def get_documents_for_transaction(reference_type, reference_id):
    """Get documents for a transaction - alias for get_documents_for_reference"""
    return get_documents_for_reference(reference_type, reference_id)

def get_documents_for_reference(reference_type, reference_id):
    """Get all documents for a specific reference"""
    try:
        from models.document import Document
        return Document.query.filter_by(
            reference_type=reference_type,
            reference_id=reference_id,
            is_active=True
        ).order_by(Document.upload_date.desc()).all()
    except ImportError:
        return []

def save_uploaded_documents(files, reference_type, reference_id, module_name='general', user_id=None):
    """Save uploaded documents and create database records"""
    try:
        from models.document import create_document_record
        saved_documents = []
        
        if not files:
            return saved_documents
        
        for file in files:
            if file and file.filename:
                # Save file to disk
                file_info = save_uploaded_file(file, subfolder=module_name)
                
                if file_info and file_info.get('success'):
                    # Create database record
                    document = create_document_record(
                        file_info=file_info,
                        module_name=module_name,
                        reference_type=reference_type,
                        reference_id=reference_id,
                        user_id=user_id
                    )
                    
                    if document:
                        saved_documents.append(document)
        
        return saved_documents
        
    except Exception as e:
        print(f"Error saving documents: {e}")
        return []

def save_uploaded_file_expense(file, expense_id, document_type='Supporting Document', description=''):
    """Save expense-related uploaded file and create document record"""
    try:
        from models.document import Document
        from flask_login import current_user
        from app import db
        
        # Save file to disk
        file_info = save_uploaded_file(file, subfolder='expenses')
        
        if file_info and file_info.get('success'):
            # Create document record
            document = Document(
                original_filename=file_info['original_filename'],
                saved_filename=file_info['saved_filename'],
                file_path=file_info['file_path'],
                file_size=file_info['file_size'],
                mime_type=file_info['mime_type'],
                description=description,
                uploaded_by=current_user.id if current_user.is_authenticated else None,
                module_name='expenses',
                reference_id=expense_id,
                reference_type='factory_expense',
                document_type=document_type
            )
            
            db.session.add(document)
            db.session.commit()
            
            return document
        else:
            return None
            
    except Exception as e:
        print(f"Error saving expense document: {str(e)}")
        return None

def delete_document(document_id, user_id=None):
    """Delete a document and its file"""
    try:
        from models.document import Document
        document = Document.query.get(document_id)
        
        if not document:
            return {'success': False, 'error': 'Document not found'}
        
        # Delete physical file
        if os.path.exists(document.file_path):
            delete_file(document.file_path)
        
        # Mark as inactive instead of deleting from database
        document.is_active = False
        
        # Log the deletion
        if user_id:
            from models.document import log_document_access
            log_document_access(document_id, user_id, 'delete')
        
        from app import db
        db.session.commit()
        
        return {'success': True, 'message': 'Document deleted successfully'}
        
    except Exception as e:
        return {'success': False, 'error': f'Error deleting document: {str(e)}'}