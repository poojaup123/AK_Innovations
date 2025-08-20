from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import Production, Item, User
from app import db
from sqlalchemy import func, desc
from utils import generate_quality_issue_number
from datetime import datetime, timedelta

quality_bp = Blueprint('quality', __name__)

@quality_bp.route('/dashboard')
@login_required
def dashboard():
    """Comprehensive Quality Control Dashboard - Centralized quality management"""
    from models import ItemBatch, JobCard, JobCardDailyStatus, DailyProductionStatus
    from models.grn import GRN, GRNLineItem
    from models.batch import InventoryBatch
    from sqlalchemy import func, or_, and_
    
    # =============================================================================
    # BATCH QUALITY STATISTICS
    # =============================================================================
    
    # Batch inspection statistics (try both InventoryBatch and ItemBatch models)
    try:
        total_batches = InventoryBatch.query.count()
        pending_batches = InventoryBatch.query.filter_by(inspection_status='pending').count()
        approved_batches = InventoryBatch.query.filter_by(inspection_status='passed').count()
        rejected_batches = InventoryBatch.query.filter_by(inspection_status='failed').count()
        quarantine_batches = InventoryBatch.query.filter_by(inspection_status='quarantine').count()
    except:
        # Fallback to ItemBatch if InventoryBatch doesn't exist
        total_batches = ItemBatch.query.count()
        pending_batches = ItemBatch.query.filter_by(quality_status='pending').count()
        approved_batches = ItemBatch.query.filter_by(quality_status='good').count()
        rejected_batches = ItemBatch.query.filter_by(quality_status='defective').count()
        quarantine_batches = 0
    
    # Calculate batch approval rate
    batch_approval_rate = (approved_batches / total_batches * 100) if total_batches > 0 else 0
    
    # =============================================================================
    # JOB CARD QUALITY STATISTICS
    # =============================================================================
    
    from datetime import date
    today = date.today()
    
    # QC Approval workflow
    pending_qc_reports = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.supervisor_approved == True,
        JobCardDailyStatus.qc_approved == False,
        JobCardDailyStatus.qc_rejected == False
    ).count()
    
    qc_approved_today = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.qc_approved == True
    ).count()
    
    qc_rejected_today = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.qc_rejected == True
    ).count()
    
    # =============================================================================
    # GRN MATERIAL INSPECTION STATISTICS
    # =============================================================================
    
    # GRN inspection statistics
    total_grn_items = GRNLineItem.query.count()
    pending_inspection_grn = GRNLineItem.query.filter_by(inspection_status='pending').count()
    passed_inspection_grn = GRNLineItem.query.filter_by(inspection_status='passed').count()
    rejected_inspection_grn = GRNLineItem.query.filter_by(inspection_status='rejected').count()
    
    # GRN material quality rate
    grn_quality_rate = (passed_inspection_grn / total_grn_items * 100) if total_grn_items > 0 else 0
    
    # =============================================================================
    # PRODUCTION QUALITY STATISTICS  
    # =============================================================================
    
    # Production quality from daily reports
    total_production_qty = float(db.session.query(func.sum(DailyProductionStatus.qty_completed_today)).scalar() or 0)
    total_defective_qty = float(db.session.query(func.sum(DailyProductionStatus.qty_defective_today)).scalar() or 0)
    total_scrap_qty = float(db.session.query(func.sum(DailyProductionStatus.qty_scrap_today)).scalar() or 0)
    total_good_qty = float(db.session.query(func.sum(DailyProductionStatus.qty_good_today)).scalar() or 0)
    
    # Calculate yield percentage
    yield_percentage = (total_good_qty / total_production_qty * 100) if total_production_qty > 0 else 0
    defect_rate = (total_defective_qty / total_production_qty * 100) if total_production_qty > 0 else 0
    scrap_rate = (total_scrap_qty / total_production_qty * 100) if total_production_qty > 0 else 0
    
    # =============================================================================
    # QUALITY ISSUE TRACKING (PLACEHOLDER - FUTURE FEATURE)
    # =============================================================================
    
    # Quality issues statistics (placeholder values until QualityIssue model is created)
    total_issues = 0
    open_issues = 0
    critical_issues = 0
    resolved_this_month = 0
    
    # Recent quality issues (empty until model is implemented)
    recent_issues = []
    
    # =============================================================================
    # RECENT ACTIVITY DATA
    # =============================================================================
    
    # Recent batch inspections  
    try:
        recent_batches = InventoryBatch.query.order_by(desc(InventoryBatch.updated_at)).limit(10).all()
    except:
        recent_batches = ItemBatch.query.order_by(desc(ItemBatch.updated_at)).limit(10).all()
    
    # Recent QC reports
    recent_qc_reports = JobCardDailyStatus.query.filter(
        or_(
            JobCardDailyStatus.qc_approved == True,
            JobCardDailyStatus.qc_rejected == True
        )
    ).order_by(desc(JobCardDailyStatus.updated_at)).limit(10).all()
    
    # Recent GRN inspections
    recent_grn_inspections = GRNLineItem.query.filter(
        GRNLineItem.inspection_status.in_(['passed', 'rejected'])
    ).order_by(desc(GRNLineItem.updated_at)).limit(10).all()
    
    # =============================================================================
    # DASHBOARD DATA COMPILATION
    # =============================================================================
    
    stats = {
        # Batch Quality
        'total_batches': total_batches,
        'pending_batches': pending_batches,
        'approved_batches': approved_batches,
        'rejected_batches': rejected_batches,
        'batch_approval_rate': round(batch_approval_rate, 1),
        
        # Job Card QC
        'pending_qc_reports': pending_qc_reports,
        'qc_approved_today': qc_approved_today,
        'qc_rejected_today': qc_rejected_today,
        
        # GRN Material Quality
        'total_grn_items': total_grn_items,
        'pending_inspection_grn': pending_inspection_grn,
        'passed_inspection_grn': passed_inspection_grn,
        'rejected_inspection_grn': rejected_inspection_grn,
        'grn_quality_rate': round(grn_quality_rate, 1),
        
        # Production Quality
        'total_production_qty': total_production_qty,
        'total_good_qty': total_good_qty,
        'total_defective_qty': total_defective_qty,
        'total_scrap_qty': total_scrap_qty,
        'yield_percentage': round(yield_percentage, 1),
        'defect_rate': round(defect_rate, 1),
        'scrap_rate': round(scrap_rate, 1),
        
        # Quality Issues
        'total_issues': total_issues,
        'open_issues': open_issues,
        'critical_issues': critical_issues,
        'resolved_this_month': resolved_this_month
    }
    
    return render_template('quality/dashboard.html',
                         stats=stats,
                         recent_issues=recent_issues,
                         recent_batches=recent_batches,
                         recent_qc_reports=recent_qc_reports,
                         recent_grn_inspections=recent_grn_inspections,
                         title='Quality Control Dashboard')

# =============================================================================
# BATCH QUALITY CONTROL ROUTES (Moved from batch_tracking)
# =============================================================================

@quality_bp.route('/batches/inspect')
@login_required
def batch_inspections():
    """Batch inspection management page"""
    from models import ItemBatch
    from models.batch import InventoryBatch
    
    status_filter = request.args.get('status', 'all')
    
    try:
        query = InventoryBatch.query
        if status_filter == 'pending':
            query = query.filter_by(inspection_status='pending')
        elif status_filter == 'approved':
            query = query.filter_by(inspection_status='passed')  
        elif status_filter == 'rejected':
            query = query.filter_by(inspection_status='failed')
        batches = query.order_by(desc(InventoryBatch.updated_at)).all()
    except:
        # Fallback to ItemBatch
        query = ItemBatch.query
        if status_filter == 'pending':
            query = query.filter_by(quality_status='pending')
        elif status_filter == 'approved':
            query = query.filter_by(quality_status='good')
        elif status_filter == 'rejected':
            query = query.filter_by(quality_status='defective')
        batches = query.order_by(desc(ItemBatch.updated_at)).all()
    
    return render_template('quality/batch_inspections.html',
                         batches=batches,
                         status_filter=status_filter,
                         title='Batch Quality Inspections')

@quality_bp.route('/batches/<int:batch_id>/update-quality', methods=['POST'])
@login_required
def update_batch_quality(batch_id):
    """Update batch quality status - moved from batch tracking"""
    from models import ItemBatch
    from models.batch import InventoryBatch
    
    try:
        try:
            batch = InventoryBatch.query.get_or_404(batch_id)
            batch_model = 'InventoryBatch'
        except:
            batch = ItemBatch.query.get_or_404(batch_id)
            batch_model = 'ItemBatch'
        
        new_status = request.form.get('quality_status')
        quality_notes = request.form.get('quality_notes', '')
        
        if batch_model == 'InventoryBatch':
            if new_status not in ['passed', 'failed', 'pending', 'quarantine']:
                flash(f'Invalid quality status: {new_status}', 'error')
                return redirect(url_for('quality.batch_inspections'))
            
            # Update batch
            batch.inspection_status = new_status
            batch.updated_at = datetime.utcnow()
            
            # Automatic quantity movement for approved batches
            if new_status == 'passed' and hasattr(batch, 'qty_inspection') and batch.qty_inspection > 0:
                qty_to_move = batch.qty_inspection
                batch.qty_inspection = 0.0
                batch.qty_raw += qty_to_move
        else:
            # ItemBatch model
            status_mapping = {
                'passed': 'good',
                'failed': 'defective',
                'pending': 'pending',
                'quarantine': 'defective'
            }
            mapped_status = status_mapping.get(new_status, 'good')
            batch.quality_status = mapped_status
            batch.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        status_names = {
            'passed': 'Approved',
            'failed': 'Rejected', 
            'pending': 'Pending',
            'quarantine': 'On Hold'
        }
        
        batch_code = getattr(batch, 'batch_code', None) or getattr(batch, 'batch_number', f'Batch {batch_id}')
        flash(f'Batch {batch_code} quality status updated to {status_names.get(new_status, new_status)}', 'success')
        return redirect(url_for('quality.batch_inspections'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating quality status: {str(e)}', 'error')
        return redirect(url_for('quality.batch_inspections'))

# =============================================================================
# JOB CARD QUALITY CONTROL ROUTES (Moved from job_card_workflow)
# =============================================================================

@quality_bp.route('/job-cards/qc-approval')
@login_required
def job_card_qc_approval():
    """QC approval dashboard for job cards"""
    from models import JobCardDailyStatus, JobCard
    from datetime import date
    
    today = date.today()
    
    # Get supervisor-approved reports pending QC
    pending_qc = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.supervisor_approved == True,
        JobCardDailyStatus.qc_approved == False,
        JobCardDailyStatus.qc_rejected == False
    ).join(JobCard).all()
    
    # Get QC approved reports
    qc_approved_today = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.qc_approved == True
    ).join(JobCard).all()
    
    # Get QC rejected reports
    qc_rejected_today = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.qc_rejected == True
    ).join(JobCard).all()
    
    stats = {
        'pending_qc_count': len(pending_qc),
        'qc_approved_count': len(qc_approved_today),
        'qc_rejected_count': len(qc_rejected_today),
        'total_qc_reports': len(pending_qc) + len(qc_approved_today) + len(qc_rejected_today)
    }
    
    return render_template('quality/job_card_qc.html',
                         pending_qc=pending_qc,
                         qc_approved_today=qc_approved_today,
                         qc_rejected_today=qc_rejected_today,
                         stats=stats,
                         today=today,
                         title='Job Card QC Approval')

@quality_bp.route('/job-cards/qc-approve/<int:status_id>', methods=['GET', 'POST'])
@login_required
def approve_job_card_qc(status_id):
    """QC approve or reject a specific daily status report"""
    from models import JobCardDailyStatus
    from forms_job_card import QCApprovalForm
    
    daily_status = JobCardDailyStatus.query.get_or_404(status_id)
    form = QCApprovalForm()
    form.daily_status_id.data = status_id
    
    if form.validate_on_submit():
        if form.qc_decision.data == 'approve':
            daily_status.approve_by_qc(
                qc_inspector_id=current_user.id,
                notes=form.qc_notes.data
            )
            flash(f'QC approval completed for Job Card {daily_status.job_card.job_card_number}!', 'success')
            
        elif form.qc_decision.data == 'reject':
            daily_status.reject_by_qc(
                qc_inspector_id=current_user.id,
                notes=form.qc_notes.data
            )
            flash(f'QC rejected Job Card {daily_status.job_card.job_card_number}.', 'warning')
        
        return redirect(url_for('quality.job_card_qc_approval'))
    
    return render_template('quality/qc_approval_form.html',
                         form=form,
                         daily_status=daily_status,
                         title='QC Approval')

# =============================================================================
# GRN QUALITY CONTROL ROUTES
# =============================================================================

@quality_bp.route('/grn/inspections')
@login_required
def grn_inspections():
    """GRN material inspection management"""
    from models.grn import GRNLineItem, GRN
    
    status_filter = request.args.get('status', 'all')
    query = GRNLineItem.query.join(GRN)
    
    if status_filter == 'pending':
        query = query.filter(GRNLineItem.inspection_status == 'pending')
    elif status_filter == 'passed':
        query = query.filter(GRNLineItem.inspection_status == 'passed')
    elif status_filter == 'rejected':
        query = query.filter(GRNLineItem.inspection_status == 'rejected')
    
    grn_items = query.order_by(desc(GRNLineItem.updated_at)).all()
    
    return render_template('quality/grn_inspections.html',
                         grn_items=grn_items,
                         status_filter=status_filter,
                         title='GRN Material Inspections')

@quality_bp.route('/grn/item/<int:item_id>/update-inspection', methods=['POST'])
@login_required
def update_grn_inspection(item_id):
    """Update GRN item inspection status"""
    from models.grn import GRNLineItem
    
    try:
        grn_item = GRNLineItem.query.get_or_404(item_id)
        
        inspection_status = request.form.get('inspection_status')
        quantity_passed = float(request.form.get('quantity_passed', 0))
        quantity_rejected = float(request.form.get('quantity_rejected', 0))
        rejection_reason = request.form.get('rejection_reason', '')
        
        grn_item.inspection_status = inspection_status
        grn_item.quantity_passed = quantity_passed
        grn_item.quantity_rejected = quantity_rejected
        grn_item.rejection_reason = rejection_reason
        grn_item.inspected_by = current_user.id
        grn_item.inspected_at = datetime.utcnow()
        grn_item.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'GRN item inspection updated: {inspection_status}', 'success')
        return redirect(url_for('quality.grn_inspections'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating inspection: {str(e)}', 'error')
        return redirect(url_for('quality.grn_inspections'))

@quality_bp.route('/issues')
@login_required
def list_issues():
    """List all quality issues with filtering options (PLACEHOLDER - Feature not implemented)"""
    status_filter = request.args.get('status', 'all')
    severity_filter = request.args.get('severity', 'all')
    
    # Placeholder: QualityIssue model not yet implemented
    issues = []
    
    return render_template('quality/issues_list.html',
                         issues=issues,
                         status_filter=status_filter,
                         severity_filter=severity_filter,
                         title='Quality Issues (Coming Soon)')

@quality_bp.route('/issues/add', methods=['GET', 'POST'])
@login_required  
def add_issue():
    """Add new quality issue (PLACEHOLDER - Feature not implemented)"""
    flash('Quality Issue Management feature is coming soon!', 'info')
    return redirect(url_for('quality.dashboard'))

# Future placeholder routes for quality issue management
@quality_bp.route('/issues/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_issue(id):
    """Edit quality issue (PLACEHOLDER - Feature not implemented)"""
    flash('Quality Issue Management feature is coming soon!', 'info')
    return redirect(url_for('quality.dashboard'))

@quality_bp.route('/issues/<int:id>/view')
@login_required  
def view_issue(id):
    """View quality issue details (PLACEHOLDER - Feature not implemented)"""
    flash('Quality Issue Management feature is coming soon!', 'info')
    return redirect(url_for('quality.dashboard'))

@quality_bp.route('/inspections')
@login_required
def list_inspections():
    """List quality control inspections (PLACEHOLDER - Feature not implemented)"""
    flash('Quality Inspection Logs feature is coming soon!', 'info')
    return redirect(url_for('quality.dashboard'))

@quality_bp.route('/inspections/add', methods=['GET', 'POST'])
@login_required
def add_inspection():
    """Add quality control inspection (PLACEHOLDER - Feature not implemented)"""
    flash('Quality Inspection Logs feature is coming soon!', 'info')  
    return redirect(url_for('quality.dashboard'))

@quality_bp.route('/reports')
@login_required
def quality_reports():
    """Quality control reports (PLACEHOLDER - Feature not implemented)"""
    flash('Quality Reports feature is coming soon!', 'info')
    return redirect(url_for('quality.dashboard'))