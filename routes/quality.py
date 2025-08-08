from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from forms import QualityIssueForm, QualityControlLogForm
from models import QualityIssue, QualityControlLog, Production, Item, User
from app import db
from sqlalchemy import func, desc
from utils import generate_quality_issue_number
from datetime import datetime, timedelta

quality_bp = Blueprint('quality', __name__)

@quality_bp.route('/dashboard')
@login_required
def dashboard():
    """Redirect to batch tracking quality control dashboard"""
    return redirect(url_for('batch_tracking.quality_dashboard'))

@quality_bp.route('/issues')
@login_required
def list_issues():
    """List all quality issues with filtering options"""
    status_filter = request.args.get('status', 'all')
    severity_filter = request.args.get('severity', 'all')
    
    query = QualityIssue.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if severity_filter != 'all':
        query = query.filter_by(severity=severity_filter)
    
    issues = query.order_by(desc(QualityIssue.created_at)).all()
    
    return render_template('quality/issues_list.html',
                         issues=issues,
                         status_filter=status_filter,
                         severity_filter=severity_filter,
                         title='Quality Issues')

@quality_bp.route('/issues/add', methods=['GET', 'POST'])
@login_required
def add_issue():
    """Add new quality issue"""
    form = QualityIssueForm()
    
    # Pre-populate issue number
    if not form.issue_number.data:
        form.issue_number.data = generate_quality_issue_number()
    
    if form.validate_on_submit():
        # Check if issue number already exists
        existing_issue = QualityIssue.query.filter_by(issue_number=form.issue_number.data).first()
        if existing_issue:
            flash('Issue number already exists', 'danger')
            return render_template('quality/issue_form.html', form=form, title='Add Quality Issue')
        
        issue = QualityIssue(
            issue_number=form.issue_number.data,
            production_id=form.production_id.data if form.production_id.data != 0 else None,
            item_id=form.item_id.data,
            issue_type=form.issue_type.data,
            severity=form.severity.data,
            quantity_affected=form.quantity_affected.data,
            description=form.description.data,
            root_cause=form.root_cause.data,
            corrective_action=form.corrective_action.data,
            preventive_action=form.preventive_action.data,
            status=form.status.data,
            assigned_to=form.assigned_to.data if form.assigned_to.data != 0 else None,
            cost_impact=form.cost_impact.data,
            detected_by=current_user.id
        )
        
        db.session.add(issue)
        db.session.commit()
        flash('Quality issue created successfully', 'success')
        return redirect(url_for('quality.list_issues'))
    
    return render_template('quality/issue_form.html', form=form, title='Add Quality Issue')

@quality_bp.route('/issues/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_issue(id):
    """Edit existing quality issue"""
    issue = QualityIssue.query.get_or_404(id)
    form = QualityIssueForm(obj=issue)
    
    if form.validate_on_submit():
        # Check if issue number already exists (excluding current issue)
        existing_issue = QualityIssue.query.filter(
            QualityIssue.issue_number == form.issue_number.data,
            QualityIssue.id != id
        ).first()
        if existing_issue:
            flash('Issue number already exists', 'danger')
            return render_template('quality/issue_form.html', form=form, title='Edit Quality Issue', issue=issue)
        
        # Update resolved date if status changed to resolved/closed
        if form.status.data in ['resolved', 'closed'] and issue.status not in ['resolved', 'closed']:
            issue.resolved_date = datetime.utcnow()
        
        issue.issue_number = form.issue_number.data
        issue.production_id = form.production_id.data if form.production_id.data != 0 else None
        issue.item_id = form.item_id.data
        issue.issue_type = form.issue_type.data
        issue.severity = form.severity.data
        issue.quantity_affected = form.quantity_affected.data
        issue.description = form.description.data
        issue.root_cause = form.root_cause.data
        issue.corrective_action = form.corrective_action.data
        issue.preventive_action = form.preventive_action.data
        issue.status = form.status.data
        issue.assigned_to = form.assigned_to.data if form.assigned_to.data != 0 else None
        issue.cost_impact = form.cost_impact.data
        
        db.session.commit()
        flash('Quality issue updated successfully', 'success')
        return redirect(url_for('quality.list_issues'))
    
    return render_template('quality/issue_form.html', form=form, title='Edit Quality Issue', issue=issue)

@quality_bp.route('/issues/<int:id>/view')
@login_required
def view_issue(id):
    """View quality issue details"""
    issue = QualityIssue.query.get_or_404(id)
    return render_template('quality/issue_detail.html', issue=issue, title='Quality Issue Details')

@quality_bp.route('/inspections')
@login_required
def list_inspections():
    """List quality control inspection logs"""
    inspections = QualityControlLog.query.order_by(desc(QualityControlLog.inspection_date)).all()
    return render_template('quality/inspections_list.html', inspections=inspections, title='Quality Inspections')

@quality_bp.route('/inspections/add', methods=['GET', 'POST'])
@login_required
def add_inspection():
    """Add quality control inspection log"""
    form = QualityControlLogForm()
    
    if form.validate_on_submit():
        # Calculate rejection rate
        total = form.total_inspected.data
        failed = form.failed_quantity.data
        rejection_rate = (failed / total * 100) if total > 0 else 0
        
        # Validate quantities
        if form.passed_quantity.data + form.failed_quantity.data != total:
            flash('Passed + Failed quantities must equal Total Inspected', 'danger')
            return render_template('quality/inspection_form.html', form=form, title='Add Quality Inspection')
        
        inspection = QualityControlLog(
            production_id=form.production_id.data,
            batch_number=form.batch_number.data,
            total_inspected=total,
            passed_quantity=form.passed_quantity.data,
            failed_quantity=failed,
            rejection_rate=rejection_rate,
            inspection_notes=form.inspection_notes.data,
            inspector_id=current_user.id
        )
        
        db.session.add(inspection)
        
        # Update production quantities based on inspection
        production = Production.query.get(form.production_id.data)
        if production:
            production.quantity_good = form.passed_quantity.data
            production.quantity_damaged = failed
        
        db.session.commit()
        flash('Quality inspection logged successfully', 'success')
        return redirect(url_for('quality.list_inspections'))
    
    return render_template('quality/inspection_form.html', form=form, title='Add Quality Inspection')

@quality_bp.route('/reports')
@login_required
def quality_reports():
    """Quality control reports and analytics"""
    
    # Quality issues by type
    issues_by_type = db.session.query(
        QualityIssue.issue_type,
        func.count(QualityIssue.id).label('count'),
        func.sum(QualityIssue.quantity_affected).label('total_affected')
    ).group_by(QualityIssue.issue_type).all()
    
    # Quality issues by severity
    issues_by_severity = db.session.query(
        QualityIssue.severity,
        func.count(QualityIssue.id).label('count')
    ).group_by(QualityIssue.severity).all()
    
    # Monthly quality trends - PostgreSQL compatible
    monthly_trends = db.session.query(
        func.to_char(QualityIssue.detected_date, 'YYYY-MM').label('month'),
        func.count(QualityIssue.id).label('issues'),
        func.sum(QualityIssue.cost_impact).label('cost')
    ).group_by(func.to_char(QualityIssue.detected_date, 'YYYY-MM')).order_by('month').limit(12).all()
    
    # Average rejection rates
    avg_rejection_rate = db.session.query(
        func.avg(QualityControlLog.rejection_rate)
    ).scalar() or 0
    
    # Top problematic items
    problem_items = db.session.query(
        Item.name,
        func.count(QualityIssue.id).label('issue_count'),
        func.sum(QualityIssue.quantity_affected).label('affected_quantity'),
        func.sum(QualityIssue.cost_impact).label('total_cost')
    ).join(QualityIssue).group_by(Item.id).order_by(desc('issue_count')).limit(10).all()
    
    return render_template('quality/reports.html',
                         issues_by_type=issues_by_type,
                         issues_by_severity=issues_by_severity,
                         monthly_trends=monthly_trends,
                         avg_rejection_rate=avg_rejection_rate,
                         problem_items=problem_items,
                         title='Quality Control Reports')