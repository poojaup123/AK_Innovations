from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db
from models.job_card import JobCard, JobCardDailyStatus
from forms_job_card_supervisor import SupervisorApprovalForm, QCApprovalForm, BulkApprovalForm, DailyProductionReviewForm
from datetime import datetime, date
from sqlalchemy import func

job_card_workflow_bp = Blueprint('job_card_workflow', __name__, url_prefix='/job-cards/workflow')

@job_card_workflow_bp.route('/supervisor-approval')
@login_required
def supervisor_approval_dashboard():
    """Dashboard for supervisor approval of daily status reports"""
    today = date.today()
    
    # Get pending approvals
    pending_approvals = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.supervisor_approved == False,
        JobCardDailyStatus.supervisor_rejected == False
    ).join(JobCard).all()
    
    # Get approved reports
    approved_today = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.supervisor_approved == True
    ).join(JobCard).all()
    
    # Get rejected reports
    rejected_today = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.supervisor_rejected == True
    ).join(JobCard).all()
    
    stats = {
        'pending_count': len(pending_approvals),
        'approved_count': len(approved_today),
        'rejected_count': len(rejected_today),
        'total_reports': len(pending_approvals) + len(approved_today) + len(rejected_today)
    }
    
    return render_template('job_cards/supervisor_approval.html',
                         pending_approvals=pending_approvals,
                         approved_today=approved_today,
                         rejected_today=rejected_today,
                         stats=stats,
                         today=today)

@job_card_workflow_bp.route('/approve/<int:status_id>', methods=['GET', 'POST'])
@login_required
def approve_status(status_id):
    """Approve or reject a specific daily status report"""
    daily_status = JobCardDailyStatus.query.get_or_404(status_id)
    form = SupervisorApprovalForm()
    form.daily_status_id.data = status_id
    
    if form.validate_on_submit():
        if form.approval_action.data == 'approve':
            daily_status.approve_by_supervisor(
                supervisor_id=current_user.id,
                notes=form.supervisor_notes.data
            )
            flash(f'Daily status for Job Card {daily_status.job_card.job_card_number} approved successfully!', 'success')
            
        elif form.approval_action.data == 'reject':
            daily_status.reject_by_supervisor(
                supervisor_id=current_user.id,
                notes=form.supervisor_notes.data or "Rejected by supervisor"
            )
            flash(f'Daily status for Job Card {daily_status.job_card.job_card_number} rejected.', 'warning')
        
        return redirect(url_for('job_card_workflow.supervisor_approval_dashboard'))
    
    return render_template('job_cards/approve_status.html',
                         form=form,
                         daily_status=daily_status)

@job_card_workflow_bp.route('/qc-approval')
@login_required
def qc_approval_dashboard():
    """Dashboard for QC approval of daily status reports"""
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
    
    return render_template('job_cards/qc_approval.html',
                         pending_qc=pending_qc,
                         qc_approved_today=qc_approved_today,
                         qc_rejected_today=qc_rejected_today,
                         stats=stats,
                         today=today)

@job_card_workflow_bp.route('/qc-approve/<int:status_id>', methods=['GET', 'POST'])
@login_required
def qc_approve_status(status_id):
    """QC approve or reject a specific daily status report"""
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
        
        return redirect(url_for('job_card_workflow.qc_approval_dashboard'))
    
    return render_template('job_cards/qc_approve_status.html',
                         form=form,
                         daily_status=daily_status)

@job_card_workflow_bp.route('/bulk-approve', methods=['POST'])
@login_required
def bulk_approve():
    """Bulk approve multiple daily status reports"""
    form = BulkApprovalForm()
    
    if form.validate_on_submit():
        selected_ids = request.form.getlist('selected_reports')
        
        for status_id in selected_ids:
            daily_status = JobCardDailyStatus.query.get(int(status_id))
            if daily_status:
                if form.bulk_action.data == 'approve_all':
                    daily_status.approve_by_supervisor(
                        supervisor_id=current_user.id,
                        notes=form.bulk_notes.data or "Bulk approved"
                    )
                elif form.bulk_action.data == 'reject_all':
                    daily_status.reject_by_supervisor(
                        supervisor_id=current_user.id,
                        notes=form.bulk_notes.data or "Bulk rejected"
                    )
        
        flash(f'Bulk action applied to {len(selected_ids)} reports.', 'success')
    
    return redirect(url_for('job_card_workflow.supervisor_approval_dashboard'))

@job_card_workflow_bp.route('/daily-review', methods=['GET', 'POST'])
@login_required
def daily_production_review():
    """Daily production review and approval workflow"""
    today = date.today()
    form = DailyProductionReviewForm()
    form.review_date.data = today.isoformat()
    
    # Get today's summary
    total_reports = JobCardDailyStatus.query.filter_by(report_date=today).count()
    approved_reports = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.supervisor_approved == True
    ).count()
    
    # Production metrics
    total_qty_completed = db.session.query(func.sum(JobCardDailyStatus.qty_completed_today)).filter_by(report_date=today).scalar() or 0
    total_qty_good = db.session.query(func.sum(JobCardDailyStatus.qty_good_today)).filter_by(report_date=today).scalar() or 0
    total_efficiency = (total_qty_good / total_qty_completed * 100) if total_qty_completed > 0 else 0
    
    # Outstanding issues
    pending_approvals = JobCardDailyStatus.query.filter(
        JobCardDailyStatus.report_date == today,
        JobCardDailyStatus.supervisor_approved == False,
        JobCardDailyStatus.supervisor_rejected == False
    ).count()
    
    summary = {
        'total_reports': total_reports,
        'approved_reports': approved_reports,
        'approval_rate': (approved_reports / total_reports * 100) if total_reports > 0 else 0,
        'total_qty_completed': total_qty_completed,
        'total_qty_good': total_qty_good,
        'total_efficiency': total_efficiency,
        'pending_approvals': pending_approvals
    }
    
    if form.validate_on_submit():
        # Save daily review (you could create a DailyProductionReview model for this)
        flash('Daily production review completed successfully!', 'success')
        return redirect(url_for('production.dashboard'))
    
    return render_template('job_cards/daily_review.html',
                         form=form,
                         summary=summary,
                         today=today)

@job_card_workflow_bp.route('/api/status-summary')
@login_required
def api_status_summary():
    """API endpoint for real-time status summary"""
    today = date.today()
    
    summary = {
        'pending_supervisor': JobCardDailyStatus.query.filter(
            JobCardDailyStatus.report_date == today,
            JobCardDailyStatus.supervisor_approved == False,
            JobCardDailyStatus.supervisor_rejected == False
        ).count(),
        'pending_qc': JobCardDailyStatus.query.filter(
            JobCardDailyStatus.report_date == today,
            JobCardDailyStatus.supervisor_approved == True,
            JobCardDailyStatus.qc_approved == False,
            JobCardDailyStatus.qc_rejected == False
        ).count(),
        'completed_today': JobCardDailyStatus.query.filter(
            JobCardDailyStatus.report_date == today,
            JobCardDailyStatus.supervisor_approved == True,
            JobCardDailyStatus.qc_approved == True
        ).count()
    }
    
    return jsonify(summary)