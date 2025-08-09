from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from models import db, Production, Item
from models.daily_production import DailyProductionStatus, ProductionShiftLog, DailyProductionSummary
from forms_daily_production import DailyProductionUpdateForm, ShiftLogForm, QuickStatusUpdateForm, BulkStatusUpdateForm
from services.manufacturing_intelligence import ManufacturingIntelligence
import json

daily_production_bp = Blueprint('daily_production', __name__, url_prefix='/daily-production')

@daily_production_bp.route('/')
@login_required
def dashboard():
    """Daily production dashboard showing today's status"""
    today = date.today()
    
    # Get today's active productions
    active_productions = Production.query.filter(
        Production.status.in_(['planned', 'in_progress'])
    ).all()
    
    # Get today's production status reports
    today_reports = DailyProductionStatus.query.filter_by(report_date=today).all()
    
    # Get or create today's summary
    daily_summary = DailyProductionSummary.generate_daily_summary(today)
    
    # Get recent shift logs
    recent_shifts = ProductionShiftLog.query.filter(
        ProductionShiftLog.shift_start >= datetime.combine(today, datetime.min.time())
    ).order_by(ProductionShiftLog.shift_start.desc()).limit(10).all()
    
    # Calculate dashboard metrics
    total_planned = sum(p.quantity_planned for p in active_productions if p.quantity_planned)
    total_completed_today = sum(r.qty_completed_today for r in today_reports)
    total_good_today = sum(r.qty_good_today for r in today_reports)
    total_defective_today = sum(r.qty_defective_today for r in today_reports)
    
    # Calculate efficiency
    efficiency_rate = (total_good_today / total_completed_today * 100) if total_completed_today > 0 else 0
    
    # Group reports by status
    status_groups = {
        'active': [r for r in today_reports if r.daily_status == 'active'],
        'planned': [r for r in today_reports if r.daily_status == 'planned'],
        'completed': [r for r in today_reports if r.daily_status == 'completed'],
        'delayed': [r for r in today_reports if r.daily_status == 'delayed'],
        'paused': [r for r in today_reports if r.daily_status == 'paused']
    }
    
    # Get productions without daily reports (need initial entry)
    productions_without_reports = []
    reported_production_ids = {r.production_id for r in today_reports}
    for prod in active_productions:
        if prod.id not in reported_production_ids:
            productions_without_reports.append(prod)
    
    return render_template('daily_production/dashboard.html',
                         today=today,
                         active_productions=active_productions,
                         today_reports=today_reports,
                         daily_summary=daily_summary,
                         recent_shifts=recent_shifts,
                         total_planned=total_planned,
                         total_completed_today=total_completed_today,
                         total_good_today=total_good_today,
                         total_defective_today=total_defective_today,
                         efficiency_rate=efficiency_rate,
                         status_groups=status_groups,
                         productions_without_reports=productions_without_reports)

@daily_production_bp.route('/update/<int:production_id>', methods=['GET', 'POST'])
@login_required
def update_production_status(production_id):
    """Update daily production status for a specific production order"""
    production = Production.query.get_or_404(production_id)
    
    # Get or create today's report
    today_report = DailyProductionStatus.get_today_report(production_id)
    
    form = DailyProductionUpdateForm()
    if today_report:
        # Pre-populate form with existing data
        form = DailyProductionUpdateForm(obj=today_report)
    
    form.production_id.data = production_id
    
    if form.validate_on_submit():
        try:
            # Calculate cumulative values
            cumulative_completed = (today_report.cumulative_completed if today_report else 0) + form.qty_completed_today.data
            cumulative_good = (today_report.cumulative_good if today_report else 0) + form.qty_good_today.data
            cumulative_defective = (today_report.cumulative_defective if today_report else 0) + form.qty_defective_today.data
            cumulative_scrap = (today_report.cumulative_scrap if today_report else 0) + form.qty_scrap_today.data
            
            # Calculate progress percentage
            progress_percentage = 0
            if production.quantity_planned and production.quantity_planned > 0:
                progress_percentage = min(100, (cumulative_completed / production.quantity_planned) * 100)
            
            # Create or update daily status
            updated_report = DailyProductionStatus.create_or_update_today(
                production_id=production_id,
                qty_completed_today=form.qty_completed_today.data,
                qty_good_today=form.qty_good_today.data,
                qty_defective_today=form.qty_defective_today.data,
                qty_scrap_today=form.qty_scrap_today.data,
                cumulative_completed=cumulative_completed,
                cumulative_good=cumulative_good,
                cumulative_defective=cumulative_defective,
                cumulative_scrap=cumulative_scrap,
                progress_percentage=progress_percentage,
                daily_status=form.daily_status.data,
                workers_assigned=form.workers_assigned.data,
                machine_hours_used=form.machine_hours_used.data,
                overtime_hours=form.overtime_hours.data,
                material_consumed_cost=form.material_consumed_cost.data,
                labor_cost_today=form.labor_cost_today.data,
                production_issues=form.production_issues.data,
                quality_issues=form.quality_issues.data,
                delay_reason=form.delay_reason.data,
                supervisor_notes=form.supervisor_notes.data,
                shift_start_time=form.shift_start_time.data,
                shift_end_time=form.shift_end_time.data,
                created_by_id=current_user.id
            )
            
            # Update main production status if needed
            if form.daily_status.data == 'completed':
                production.status = 'completed'
                production.quantity_produced = cumulative_completed
                production.quantity_good = cumulative_good
                production.quantity_damaged = cumulative_defective
                production.scrap_quantity = cumulative_scrap
            elif form.daily_status.data == 'active' and production.status == 'planned':
                production.status = 'in_progress'
            
            db.session.commit()
            
            flash(f'Daily production status updated for {production.production_number}', 'success')
            return redirect(url_for('daily_production.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating production status: {str(e)}', 'danger')
    
    # Get production item for display
    item = Item.query.get(production.item_id) if production.item_id else None
    
    return render_template('daily_production/update_form.html',
                         form=form,
                         production=production,
                         item=item,
                         today_report=today_report,
                         title=f'Update Daily Status - {production.production_number}')

@daily_production_bp.route('/quick-update', methods=['POST'])
@login_required
def quick_update():
    """Quick status update via AJAX"""
    try:
        data = request.get_json()
        production_id = data.get('production_id')
        qty_completed = float(data.get('qty_completed', 0))
        status = data.get('status', 'active')
        notes = data.get('notes', '')
        
        production = Production.query.get_or_404(production_id)
        
        # Update today's report
        today_report = DailyProductionStatus.get_today_report(production_id)
        cumulative_completed = (today_report.cumulative_completed if today_report else 0) + qty_completed
        
        # Calculate progress
        progress_percentage = 0
        if production.quantity_planned and production.quantity_planned > 0:
            progress_percentage = min(100, (cumulative_completed / production.quantity_planned) * 100)
        
        DailyProductionStatus.create_or_update_today(
            production_id=production_id,
            qty_completed_today=qty_completed,
            qty_good_today=qty_completed,  # Assume good unless specified otherwise
            cumulative_completed=cumulative_completed,
            cumulative_good=cumulative_completed,
            progress_percentage=progress_percentage,
            daily_status=status,
            supervisor_notes=notes,
            created_by_id=current_user.id
        )
        
        # Update main production status
        if status == 'completed':
            production.status = 'completed'
            production.quantity_produced = cumulative_completed
        elif status == 'active' and production.status == 'planned':
            production.status = 'in_progress'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Quick update applied to {production.production_number}',
            'progress_percentage': progress_percentage,
            'cumulative_completed': cumulative_completed
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@daily_production_bp.route('/shift-log/<int:daily_status_id>', methods=['GET', 'POST'])
@login_required
def shift_log(daily_status_id):
    """Log shift-specific production data"""
    daily_status = DailyProductionStatus.query.get_or_404(daily_status_id)
    
    form = ShiftLogForm()
    form.daily_production_status_id.data = daily_status_id
    
    if form.validate_on_submit():
        try:
            shift_log = ProductionShiftLog(
                daily_production_status_id=daily_status_id,
                shift_type=form.shift_type.data,
                shift_start=form.shift_start.data,
                shift_end=form.shift_end.data,
                qty_produced_shift=form.qty_produced_shift.data,
                qty_good_shift=form.qty_good_shift.data,
                qty_defective_shift=form.qty_defective_shift.data,
                workers_present=form.workers_present.data,
                supervisor_name=form.supervisor_name.data,
                machine_downtime_minutes=form.machine_downtime_minutes.data,
                downtime_reason=form.downtime_reason.data,
                shift_notes=form.shift_notes.data,
                issues_encountered=form.issues_encountered.data
            )
            
            db.session.add(shift_log)
            db.session.commit()
            
            flash(f'Shift log added for {form.shift_type.data} shift', 'success')
            return redirect(url_for('daily_production.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error logging shift data: {str(e)}', 'danger')
    
    return render_template('daily_production/shift_log_form.html',
                         form=form,
                         daily_status=daily_status,
                         title=f'Shift Log - {daily_status.production.production_number}')

@daily_production_bp.route('/reports')
@login_required
def reports():
    """Daily production reports and analytics"""
    # Get date range from query params
    start_date = request.args.get('start_date', date.today().strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', date.today().strftime('%Y-%m-%d'))
    
    try:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    except:
        start_date_obj = date.today()
        end_date_obj = date.today()
    
    # Get daily summaries for the period
    daily_summaries = DailyProductionSummary.query.filter(
        DailyProductionSummary.summary_date.between(start_date_obj, end_date_obj)
    ).order_by(DailyProductionSummary.summary_date.desc()).all()
    
    # Get detailed production reports
    production_reports = DailyProductionStatus.query.filter(
        DailyProductionStatus.report_date.between(start_date_obj, end_date_obj)
    ).order_by(DailyProductionStatus.report_date.desc(), DailyProductionStatus.updated_at.desc()).all()
    
    # Calculate period totals
    total_qty_produced = sum(s.total_qty_produced for s in daily_summaries)
    total_qty_good = sum(s.total_qty_good for s in daily_summaries)
    total_defective = sum(s.total_qty_defective for s in daily_summaries)
    avg_efficiency = sum(s.overall_efficiency for s in daily_summaries) / len(daily_summaries) if daily_summaries else 0
    
    # Get trend data for charts
    trend_data = []
    for summary in daily_summaries:
        trend_data.append({
            'date': summary.summary_date.strftime('%Y-%m-%d'),
            'produced': summary.total_qty_produced,
            'good': summary.total_qty_good,
            'defective': summary.total_qty_defective,
            'efficiency': summary.overall_efficiency
        })
    
    return render_template('daily_production/reports.html',
                         daily_summaries=daily_summaries,
                         production_reports=production_reports,
                         start_date=start_date,
                         end_date=end_date,
                         total_qty_produced=total_qty_produced,
                         total_qty_good=total_qty_good,
                         total_defective=total_defective,
                         avg_efficiency=avg_efficiency,
                         trend_data=json.dumps(trend_data),
                         title='Daily Production Reports')

@daily_production_bp.route('/api/productions-today')
@login_required
def api_productions_today():
    """API endpoint to get today's production status"""
    today = date.today()
    
    # Get all active productions with their today's status
    active_productions = Production.query.filter(
        Production.status.in_(['planned', 'in_progress'])
    ).all()
    
    productions_data = []
    for prod in active_productions:
        today_report = DailyProductionStatus.get_today_report(prod.id)
        
        # Get item info
        item = Item.query.get(prod.item_id) if prod.item_id else None
        
        productions_data.append({
            'id': prod.id,
            'production_number': prod.production_number,
            'item_name': item.name if item else 'Unknown Item',
            'item_code': item.code if item else '',
            'quantity_planned': prod.quantity_planned or 0,
            'quantity_produced': prod.quantity_produced or 0,
            'status': prod.status,
            'daily_status': today_report.daily_status if today_report else 'no_report',
            'qty_completed_today': today_report.qty_completed_today if today_report else 0,
            'qty_good_today': today_report.qty_good_today if today_report else 0,
            'progress_percentage': today_report.progress_percentage if today_report else 0,
            'workers_assigned': today_report.workers_assigned if today_report else 0,
            'has_issues': bool((today_report.production_issues if today_report else '') or (today_report.quality_issues if today_report else '')),
            'is_on_schedule': today_report.is_on_schedule if today_report else True
        })
    
    return jsonify({
        'success': True,
        'productions': productions_data,
        'total_count': len(productions_data),
        'date': today.strftime('%Y-%m-%d')
    })

@daily_production_bp.route('/generate-summary')
@login_required
def generate_summary():
    """Generate daily summary for today"""
    try:
        summary = DailyProductionSummary.generate_daily_summary()
        if summary:
            flash('Daily production summary generated successfully', 'success')
        else:
            flash('No production data available for summary', 'info')
    except Exception as e:
        flash(f'Error generating summary: {str(e)}', 'danger')
    
    return redirect(url_for('daily_production.dashboard'))