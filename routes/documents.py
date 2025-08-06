from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user
from app import db
from models import PurchaseOrder, SalesOrder, JobWork
from models.document import Document
from forms_documents import DocumentUploadForm, DocumentForm
from utils.documents import save_uploaded_file, get_documents_for_transaction, delete_document
from sqlalchemy import func
import os

documents_bp = Blueprint('documents', __name__)

@documents_bp.route('/list')
@login_required
def document_list():
    """List all documents with filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get filter parameters
    transaction_type = request.args.get('transaction_type', '')
    document_category = request.args.get('document_category', '')
    file_type = request.args.get('file_type', '')
    search = request.args.get('search', '')
    
    # Build query
    query = Document.query.filter_by(is_active=True)
    
    if transaction_type:
        query = query.filter(Document.reference_type == transaction_type)
    
    if document_category:
        query = query.filter(Document.document_type == document_category)
    
    if file_type:
        query = query.filter(Document.mime_type.contains(file_type))
    
    if search:
        query = query.filter(Document.original_filename.contains(search))
    
    documents = query.order_by(Document.upload_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Calculate statistics
    total_documents = Document.query.filter_by(is_active=True).count()
    total_size = db.session.query(func.sum(Document.file_size)).filter_by(is_active=True).scalar() or 0
    total_size_mb = round(total_size / 1024 / 1024, 2)
    document_types_count = db.session.query(func.count(func.distinct(Document.document_type))).filter_by(is_active=True).scalar()
    transactions_with_docs = db.session.query(func.count(func.distinct(Document.reference_id))).filter_by(is_active=True).scalar()
    
    return render_template('documents/list.html',
                         documents=documents,
                         transaction_type=transaction_type,
                         document_category=document_category,
                         file_type=file_type,
                         search=search,
                         total_documents=total_documents,
                         total_size_mb=total_size_mb,
                         document_types_count=document_types_count,
                         transactions_with_docs=transactions_with_docs)

@documents_bp.route('/upload/<transaction_type>/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def upload_document(transaction_type, transaction_id):
    """Upload document for a transaction"""
    form = DocumentUploadForm()
    form.transaction_type.data = transaction_type
    form.transaction_id.data = transaction_id
    
    # Verify transaction exists
    transaction = None
    if transaction_type == 'purchase_order':
        transaction = PurchaseOrder.query.get_or_404(transaction_id)
        transaction_name = f"Purchase Order {transaction.po_number}"
    elif transaction_type == 'sales_order':
        transaction = SalesOrder.query.get_or_404(transaction_id)
        transaction_name = f"Sales Order {transaction.so_number}"
    elif transaction_type == 'job_work':
        transaction = JobWork.query.get_or_404(transaction_id)
        transaction_name = f"Job Work {transaction.job_number}"
    else:
        flash('Invalid transaction type', 'error')
        return redirect(url_for('main.dashboard'))
    
    if form.validate_on_submit():
        document = save_uploaded_file(
            form.file.data,
            transaction_type,
            transaction_id,
            form.document_category.data,
            form.description.data
        )
        
        if document:
            flash(f'Document "{document.original_filename}" uploaded successfully!', 'success')
            
            # Redirect back to transaction detail page
            if transaction_type == 'purchase_order':
                return redirect(url_for('purchase.list_purchase_orders'))
            elif transaction_type == 'sales_order':
                return redirect(url_for('sales.list_sales_orders'))
            elif transaction_type == 'job_work':
                return redirect(url_for('jobwork.list_job_works'))
            elif transaction_type == 'factory_expense':
                return redirect(url_for('expenses.expense_detail', id=transaction_id))
        else:
            flash('Failed to upload document. Please try again.', 'error')
    
    # Get existing documents
    existing_documents = get_documents_for_transaction(transaction_type, transaction_id)
    
    return render_template('documents/upload.html', 
                         form=form, 
                         transaction=transaction,
                         transaction_name=transaction_name,
                         transaction_type=transaction_type,
                         existing_documents=existing_documents)

@documents_bp.route('/view/<int:document_id>')
@login_required
def view_document(document_id):
    """View/download a document"""
    document = Document.query.get_or_404(document_id)
    
    if not document.is_active:
        flash('Document not found', 'error')
        return redirect(url_for('documents.document_list'))
    
    file_path = document.file_path
    
    # Debug logging
    print(f"Attempting to view document {document_id}: {document.original_filename}")
    print(f"File path: {file_path}")
    print(f"File exists: {os.path.exists(file_path) if file_path else False}")
    
    if not file_path or not os.path.exists(file_path):
        flash(f'File not found on disk: {document.original_filename}', 'warning')
        return redirect(url_for('documents.document_list'))
    
    try:
        return send_file(file_path, as_attachment=False, download_name=document.original_filename)
    except Exception as e:
        flash(f'Error viewing file: {str(e)}', 'error')
        return redirect(url_for('documents.document_list'))

@documents_bp.route('/download/<int:document_id>')
@login_required
def download_document(document_id):
    """Download a document"""
    document = Document.query.get_or_404(document_id)
    
    if not document.is_active:
        flash('Document not found', 'error')
        return redirect(url_for('documents.document_list'))
    
    file_path = document.file_path
    
    # Debug logging
    print(f"Attempting to download document {document_id}: {document.original_filename}")
    print(f"File path: {file_path}")
    print(f"File exists: {os.path.exists(file_path) if file_path else False}")
    
    if not file_path or not os.path.exists(file_path):
        flash(f'File not found on disk: {document.original_filename}', 'warning')
        return redirect(url_for('documents.document_list'))
    
    try:
        return send_file(file_path, as_attachment=True, download_name=document.original_filename)
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('documents.document_list'))

@documents_bp.route('/edit/<int:document_id>', methods=['GET', 'POST'])
@login_required
def edit_document(document_id):
    """Edit document metadata"""
    document = Document.query.get_or_404(document_id)
    
    if not document.is_active:
        flash('Document not found', 'error')
        return redirect(url_for('main.dashboard'))
    
    form = DocumentForm(obj=document)
    
    if form.validate_on_submit():
        document.document_category = form.document_category.data
        document.description = form.description.data
        db.session.commit()
        
        flash('Document updated successfully!', 'success')
        
        # Redirect back to transaction detail page
        if document.transaction_type == 'purchase_order':
            return redirect(url_for('purchase.list_purchase_orders'))
        elif document.transaction_type == 'sales_order':
            return redirect(url_for('sales.list_sales_orders'))
        elif document.transaction_type == 'job_work':
            return redirect(url_for('jobwork.list_job_works'))
        elif document.transaction_type == 'factory_expense':
            return redirect(url_for('expenses.expense_detail', id=document.transaction_id))
    
    return render_template('documents/edit.html', form=form, document=document)

@documents_bp.route('/delete/<int:document_id>', methods=['POST'])
@login_required
def delete_document_route(document_id):
    """Delete a document"""
    document = Document.query.get_or_404(document_id)
    
    if not document.is_active:
        flash('Document not found', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Check permissions (admin or document uploader)
    if not current_user.is_admin() and document.uploaded_by != current_user.id:
        flash('You do not have permission to delete this document', 'error')
        return redirect(url_for('main.dashboard'))
    
    if delete_document(document_id):
        flash('Document deleted successfully!', 'success')
    else:
        flash('Failed to delete document', 'error')
    
    # Redirect back to transaction detail page
    if document.transaction_type == 'purchase_order':
        return redirect(url_for('purchase.list_purchase_orders'))
    elif document.transaction_type == 'sales_order':
        return redirect(url_for('sales.list_sales_orders'))
    elif document.transaction_type == 'job_work':
        return redirect(url_for('jobwork.list_job_works'))
    elif document.transaction_type == 'factory_expense':
        return redirect(url_for('expenses.expense_detail', id=document.transaction_id))
    
    return redirect(url_for('main.dashboard'))

@documents_bp.route('/list/<transaction_type>/<int:transaction_id>')
@login_required
def list_documents(transaction_type, transaction_id):
    """List all documents for a transaction"""
    # Verify transaction exists
    transaction = None
    if transaction_type == 'purchase_order':
        transaction = PurchaseOrder.query.get_or_404(transaction_id)
        transaction_name = f"Purchase Order {transaction.po_number}"
    elif transaction_type == 'sales_order':
        transaction = SalesOrder.query.get_or_404(transaction_id)
        transaction_name = f"Sales Order {transaction.so_number}"
    elif transaction_type == 'job_work':
        transaction = JobWork.query.get_or_404(transaction_id)
        transaction_name = f"Job Work {transaction.job_number}"
    else:
        flash('Invalid transaction type', 'error')
        return redirect(url_for('main.dashboard'))
    
    documents = get_documents_for_transaction(transaction_type, transaction_id)
    
    return render_template('documents/list.html',
                         documents=documents,
                         transaction=transaction,
                         transaction_name=transaction_name,
                         transaction_type=transaction_type)