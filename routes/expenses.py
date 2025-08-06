from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import FactoryExpense, User
from models.document import Document
from forms import FactoryExpenseForm
from datetime import datetime, date
from sqlalchemy import func, desc, extract
from utils.documents import save_uploaded_file_expense
from utils.export import export_factory_expenses
from services.hr_accounting_integration import HRAccountingIntegration
# Temporarily comment out OCR import to fix OpenCV dependency issue
# from utils_ocr import process_receipt_image
import calendar
import os
import tempfile
from werkzeug.utils import secure_filename

expenses_bp = Blueprint('expenses', __name__)

@expenses_bp.route('/dashboard')
@login_required
def dashboard():
    """Factory Expenses Dashboard"""
    try:
        # Current month expenses
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        monthly_expenses = db.session.query(func.sum(FactoryExpense.total_amount)).filter(
            extract('month', FactoryExpense.expense_date) == current_month,
            extract('year', FactoryExpense.expense_date) == current_year
        ).scalar() or 0
        
        # Current year expenses
        yearly_expenses = db.session.query(func.sum(FactoryExpense.total_amount)).filter(
            extract('year', FactoryExpense.expense_date) == current_year
        ).scalar() or 0
        
        # Pending approvals
        pending_approvals = FactoryExpense.query.filter_by(status='pending').count()
        
        # Category-wise expenses for current month
        category_expenses = db.session.query(
            FactoryExpense.category,
            func.sum(FactoryExpense.total_amount).label('total')
        ).filter(
            extract('month', FactoryExpense.expense_date) == current_month,
            extract('year', FactoryExpense.expense_date) == current_year
        ).group_by(FactoryExpense.category).all()
        
        # Recent expenses
        recent_expenses = FactoryExpense.query.order_by(desc(FactoryExpense.created_at)).limit(10).all()
        
        # Monthly trend (last 6 months)
        monthly_trend = []
        for i in range(6):
            month_date = datetime.now().replace(day=1)
            if i > 0:
                month_date = month_date.replace(month=month_date.month - i)
                if month_date.month <= 0:
                    month_date = month_date.replace(month=month_date.month + 12, year=month_date.year - 1)
            
            month_total = db.session.query(func.sum(FactoryExpense.total_amount)).filter(
                extract('month', FactoryExpense.expense_date) == month_date.month,
                extract('year', FactoryExpense.expense_date) == month_date.year
            ).scalar() or 0
            
            monthly_trend.append({
                'month': calendar.month_name[month_date.month],
                'year': month_date.year,
                'total': float(month_total)
            })
        
        monthly_trend.reverse()
        
        return render_template('expenses/dashboard.html',
                             monthly_expenses=monthly_expenses,
                             yearly_expenses=yearly_expenses,
                             pending_approvals=pending_approvals,
                             category_expenses=category_expenses,
                             recent_expenses=recent_expenses,
                             monthly_trend=monthly_trend)
    
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return render_template('expenses/dashboard.html',
                             monthly_expenses=0,
                             yearly_expenses=0,
                             pending_approvals=0,
                             category_expenses=[],
                             recent_expenses=[],
                             monthly_trend=[])

@expenses_bp.route('/list')
@login_required
def expense_list():
    """List all expenses"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get filter parameters
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Build query
    query = FactoryExpense.query
    
    if category:
        query = query.filter(FactoryExpense.category == category)
    
    if status:
        query = query.filter(FactoryExpense.status == status)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(FactoryExpense.expense_date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(FactoryExpense.expense_date <= to_date)
        except ValueError:
            pass
    
    expenses = query.order_by(desc(FactoryExpense.expense_date)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Calculate total for filtered results
    total_amount = query.with_entities(func.sum(FactoryExpense.total_amount)).scalar() or 0
    
    return render_template('expenses/list.html', 
                         expenses=expenses,
                         total_amount=total_amount,
                         category=category,
                         status=status,
                         date_from=date_from,
                         date_to=date_to)

@expenses_bp.route('/export')
@login_required
def export_expenses():
    """Export expenses to Excel"""
    # Get filter parameters
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Build query with same filters as list view
    query = FactoryExpense.query
    
    if category:
        query = query.filter(FactoryExpense.category == category)
    
    if status:
        query = query.filter(FactoryExpense.status == status)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(FactoryExpense.expense_date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(FactoryExpense.expense_date <= to_date)
        except ValueError:
            pass
    
    expenses = query.order_by(desc(FactoryExpense.expense_date)).all()
    
    return export_factory_expenses(expenses)

@expenses_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    """Add new expense"""
    form = FactoryExpenseForm()
    
    if form.validate_on_submit():
        try:
            # Calculate total amount
            tax_amt = form.tax_amount.data if form.tax_amount.data is not None else 0.0
            total_amount = form.amount.data + tax_amt
            
            expense = FactoryExpense(
                expense_number=FactoryExpense.generate_expense_number(),
                expense_date=form.expense_date.data,
                category=form.category.data,
                subcategory=form.subcategory.data,
                department_code=form.department.data if form.department.data else None,
                description=form.description.data,
                amount=form.amount.data,
                tax_amount=tax_amt,
                total_amount=total_amount,
                payment_method=form.payment_method.data,
                paid_by=form.paid_by.data,
                vendor_name=form.vendor_name.data,
                vendor_contact=form.vendor_contact.data,
                invoice_number=form.invoice_number.data,
                invoice_date=form.invoice_date.data,
                is_recurring=form.is_recurring.data,
                recurring_frequency=form.recurring_frequency.data if form.is_recurring.data else None,
                notes=form.notes.data,
                requested_by_id=current_user.id,
                status='pending'
            )
            
            db.session.add(expense)
            db.session.flush()  # Get the expense ID before commit
            
            # Handle document uploads
            uploaded_files = request.files.getlist('documentFiles')
            if uploaded_files and any(file.filename for file in uploaded_files):
                for file in uploaded_files:
                    if file and file.filename:
                        try:
                            document = save_uploaded_file_expense(
                                file, 
                                expense.id, 
                                'Supporting Document', 
                                f'Document for expense {expense.expense_number}'
                            )
                            if document:
                                print(f"Document saved: {document.original_filename}")
                        except Exception as e:
                            print(f"Error saving document: {str(e)}")
            
            # Commit the expense first
            db.session.commit()
            
            # Create accounting entries for the expense using HR integration
            try:
                voucher = HRAccountingIntegration.create_factory_expense_entry(expense)
                if voucher:
                    flash(f'Expense {expense.expense_number} created successfully with accounting entries!', 'success')
                else:
                    flash(f'Expense {expense.expense_number} created successfully but accounting integration failed!', 'warning')
            except Exception as e:
                flash(f'Expense {expense.expense_number} created successfully but accounting integration failed: {str(e)}', 'warning')
            return redirect(url_for('expenses.expense_detail', id=expense.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating expense: {str(e)}', 'danger')
    
    return render_template('expenses/form.html', form=form, title='Add Factory Expense')

@expenses_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_expense(id):
    """Edit expense"""
    expense = FactoryExpense.query.get_or_404(id)
    
    # Only allow editing by the requester or admin, and only if pending
    if expense.requested_by_id != current_user.id and not current_user.is_admin():
        flash('You can only edit your own expenses', 'danger')
        return redirect(url_for('expenses.expense_list'))
    
    if expense.status != 'pending':
        flash('Cannot edit expense that has been processed', 'warning')
        return redirect(url_for('expenses.expense_detail', id=id))
    
    form = FactoryExpenseForm(obj=expense)
    # Set department field from department_code
    form.department.data = expense.department_code
    
    if form.validate_on_submit():
        try:
            # Calculate total amount
            tax_amt = form.tax_amount.data if form.tax_amount.data is not None else 0.0
            total_amount = form.amount.data + tax_amt
            
            expense.expense_date = form.expense_date.data
            expense.category = form.category.data
            expense.subcategory = form.subcategory.data
            expense.department_code = form.department.data if form.department.data else None
            expense.description = form.description.data
            expense.amount = form.amount.data
            expense.tax_amount = tax_amt
            expense.total_amount = total_amount
            expense.payment_method = form.payment_method.data
            expense.paid_by = form.paid_by.data
            expense.vendor_name = form.vendor_name.data
            expense.vendor_contact = form.vendor_contact.data
            expense.invoice_number = form.invoice_number.data
            expense.invoice_date = form.invoice_date.data
            expense.is_recurring = form.is_recurring.data
            expense.recurring_frequency = form.recurring_frequency.data if form.is_recurring.data else None
            expense.notes = form.notes.data
            expense.updated_at = datetime.utcnow()
            
            # Handle document uploads
            uploaded_files = request.files.getlist('documentFiles')
            if uploaded_files and any(file.filename for file in uploaded_files):
                for file in uploaded_files:
                    if file and file.filename:
                        try:
                            document = save_uploaded_file_expense(
                                file, 
                                expense.id, 
                                'Supporting Document', 
                                f'Document for expense {expense.expense_number}'
                            )
                            if document:
                                print(f"Document saved: {document.original_filename}")
                        except Exception as e:
                            print(f"Error saving document: {str(e)}")
            
            db.session.commit()
            
            flash(f'Expense {expense.expense_number} updated successfully!', 'success')
            return redirect(url_for('expenses.expense_detail', id=expense.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating expense: {str(e)}', 'danger')
    
    return render_template('expenses/form.html', form=form, expense=expense, title='Edit Factory Expense')

@expenses_bp.route('/detail/<int:id>')
@login_required
def expense_detail(id):
    """View expense details"""
    expense = FactoryExpense.query.get_or_404(id)
    
    # Get documents for this expense
    documents = Document.query.filter_by(
        reference_type='factory_expense',
        reference_id=expense.id,
        is_active=True
    ).order_by(Document.upload_date.desc()).all()
    
    return render_template('expenses/detail.html', expense=expense, documents=documents)

@expenses_bp.route('/approve/<int:id>', methods=['POST'])
@login_required
def approve_expense(id):
    """Approve expense (Admin only)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    expense = FactoryExpense.query.get_or_404(id)
    
    if expense.status != 'pending':
        return jsonify({'error': 'Expense is not pending approval'}), 400
    
    try:
        expense.status = 'approved'
        expense.approved_by_id = current_user.id
        expense.approval_date = datetime.utcnow()
        
        # Create accounting entries upon approval using HR integration
        voucher = HRAccountingIntegration.create_factory_expense_entry(expense)
        
        db.session.commit()
        
        if voucher:
            return jsonify({
                'success': True,
                'message': f'Expense {expense.expense_number} approved successfully with accounting entries'
            })
        else:
            return jsonify({
                'success': True,
                'message': f'Expense {expense.expense_number} approved successfully but accounting integration failed'
            })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@expenses_bp.route('/reject/<int:id>', methods=['POST'])
@login_required
def reject_expense(id):
    """Reject expense (Admin only)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    expense = FactoryExpense.query.get_or_404(id)
    
    if expense.status != 'pending':
        return jsonify({'error': 'Expense is not pending approval'}), 400
    
    try:
        expense.status = 'rejected'
        expense.approved_by_id = current_user.id
        expense.approval_date = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Expense {expense.expense_number} rejected'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@expenses_bp.route('/mark_paid/<int:id>', methods=['POST'])
@login_required
def mark_paid(id):
    """Mark expense as paid (Admin only)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    expense = FactoryExpense.query.get_or_404(id)
    
    if expense.status != 'approved':
        return jsonify({'error': 'Expense must be approved before payment'}), 400
    
    try:
        expense.status = 'paid'
        expense.payment_date = date.today()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Expense {expense.expense_number} marked as paid'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@expenses_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_expense(id):
    """Delete expense"""
    expense = FactoryExpense.query.get_or_404(id)
    
    # Only allow deletion by the requester or admin, and only if pending
    if expense.requested_by_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'You can only delete your own expenses'}), 403
    
    if expense.status != 'pending':
        return jsonify({'error': 'Cannot delete expense that has been processed'}), 400
    
    try:
        db.session.delete(expense)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Expense {expense.expense_number} deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
@expenses_bp.route("/process_ocr", methods=["POST"])
@login_required
def process_ocr():
    """Process receipt image using OCR to extract structured data"""
    try:
        # Check if file was uploaded
        if "receipt_image" not in request.files:
            return jsonify({"success": False, "message": "No file uploaded"})
        
        file = request.files["receipt_image"]
        if file.filename == "":
            return jsonify({"success": False, "message": "No file selected"})
        
        # Validate file type
        allowed_extensions = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp", "pdf"}
        file_extension = file.filename.lower().split(".")[-1] if "." in file.filename else ""
        if not file_extension in allowed_extensions:
            return jsonify({"success": False, "message": "Invalid file type. Please upload an image file (PNG, JPG, JPEG, GIF, BMP, TIFF, WEBP) or PDF."})
        
        # Create temporary file
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'tmp'
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp_file:
            file.save(tmp_file.name)
            temp_path = tmp_file.name
        
        try:
            # Simulate OCR processing for demo
            import random
            from datetime import date
            
            # Demo OCR result - replace with real OCR when dependencies are resolved
            ocr_result = {
                "date": date.today().strftime("%Y-%m-%d"),
                "amount": round(random.uniform(100, 5000), 2),
                "base_amount": round(random.uniform(85, 4500), 2),
                "tax_amount": round(random.uniform(15, 500), 2),
                "vendor": f"Sample Vendor {random.randint(1, 10)}",
                "invoice_number": f"INV-{random.randint(1000, 9999)}",
                "category": random.choice(["utilities", "materials", "transport", "maintenance"]),
                "department": random.choice(["production", "maintenance", "administration", "accounts_finance"]),
                "gst_rate": random.choice([5, 12, 18, 28]),
                "gstin": f"22AAAAA0000A1Z{random.randint(1, 9)}",
                "confidence": random.randint(75, 95)
            }
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            if "error" in ocr_result:
                return jsonify({
                    "success": False, 
                    "message": f"OCR processing failed: {ocr_result['error']}"
                })
            
            # Return processed data
            return jsonify({
                "success": True,
                "message": "Receipt processed successfully (Demo Mode)",
                "data": ocr_result
            })
            
        except Exception as e:
            # Clean up temporary file in case of error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error processing receipt: {str(e)}"
        })
