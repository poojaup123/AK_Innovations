from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from models import db, Production, Item, BOM
from models.daily_production import DailyProductionStatus, ProductionShiftLog, DailyProductionSummary
from forms import ProductionForm
from sqlalchemy import func, and_, or_

daily_production_bp = Blueprint('daily_production', __name__, url_prefix='/daily-production')

@daily_production_bp.route('/dashboard')
@login_required
def dashboard():
    """Daily Production Dashboard"""
    today = date.today()
    
    # Get today's production summary
    daily_summary = DailyProductionSummary.query.filter_by(summary_date=today).first()
    if not daily_summary:
        daily_summary = DailyProductionSummary.generate_daily_summary(today)
    
    # Get all active productions with today's status
    active_productions = Production.query.filter(
        Production.status.in_(['planned', 'in_progress'])
    ).all()
    
    # Get today's status reports
    today_reports = []
    for prod in active_productions:
        daily_report = DailyProductionStatus.get_today_report(prod.id)
        if not daily_report:
            # Create empty report for display
            daily_report = DailyProductionStatus(
                production_id=prod.id,
                report_date=today,
                daily_status='planned'
            )
        today_reports.append({
            'production': prod,
            'daily_report': daily_report,
            'item': Item.query.get(prod.item_id)
        })
    
    # Recent completed productions (last 7 days)
    week_ago = today - timedelta(days=7)
    recent_completed = DailyProductionStatus.query.join(Production).filter(
        and_(
            DailyProductionStatus.report_date >= week_ago,
            DailyProductionStatus.daily_status == 'completed'
        )
    ).order_by(DailyProductionStatus.report_date.desc()).limit(10).all()
    
    # Performance metrics for the week
    week_reports = DailyProductionStatus.query.filter(
        DailyProductionStatus.report_date >= week_ago
    ).all()
    
    week_stats = {
        'total_produced': sum(r.qty_completed_today for r in week_reports),
        'total_good': sum(r.qty_good_today for r in week_reports),
        'total_defective': sum(r.qty_defective_today for r in week_reports),
        'avg_efficiency': sum(r.efficiency_rate for r in week_reports) / len(week_reports) if week_reports else 0,
        'on_schedule_count': len([r for r in week_reports if r.is_on_schedule]),
        'delayed_count': len([r for r in week_reports if not r.is_on_schedule])
    }
    
    return render_template('daily_production/dashboard.html',
                         title='Daily Production Dashboard',
                         daily_summary=daily_summary,
                         today_reports=today_reports,
                         recent_completed=recent_completed,
                         week_stats=week_stats,
                         today=today)

@daily_production_bp.route('/update-status/<int:production_id>', methods=['GET', 'POST'])
@login_required
def update_daily_status(production_id):
    """Update daily production status"""
    production = Production.query.get_or_404(production_id)
    item = Item.query.get(production.item_id)
    
    # Get or create today's report
    today_report = DailyProductionStatus.get_today_report(production_id)
    if not today_report:
        today_report = DailyProductionStatus(
            production_id=production_id,
            report_date=date.today(),
            created_by_id=current_user.id
        )
        db.session.add(today_report)
    
    if request.method == 'POST':
        try:
            # Update daily metrics
            today_report.qty_completed_today = float(request.form.get('qty_completed_today', 0))
            today_report.qty_good_today = float(request.form.get('qty_good_today', 0))
            today_report.qty_defective_today = float(request.form.get('qty_defective_today', 0))
            today_report.qty_scrap_today = float(request.form.get('qty_scrap_today', 0))
            
            # Update status and progress
            today_report.daily_status = request.form.get('daily_status', 'planned')
            today_report.progress_percentage = float(request.form.get('progress_percentage', 0))
            
            # Resource tracking
            today_report.workers_assigned = int(request.form.get('workers_assigned', 0))
            today_report.machine_hours_used = float(request.form.get('machine_hours_used', 0))
            today_report.overtime_hours = float(request.form.get('overtime_hours', 0))
            
            # Costs
            today_report.material_consumed_cost = float(request.form.get('material_consumed_cost', 0))
            today_report.labor_cost_today = float(request.form.get('labor_cost_today', 0))
            
            # Issues and notes
            today_report.production_issues = request.form.get('production_issues', '')
            today_report.quality_issues = request.form.get('quality_issues', '')
            today_report.delay_reason = request.form.get('delay_reason', '')
            today_report.supervisor_notes = request.form.get('supervisor_notes', '')
            
            # Shift times
            shift_start = request.form.get('shift_start_time')
            shift_end = request.form.get('shift_end_time')
            if shift_start:
                today_report.shift_start_time = datetime.strptime(f"{date.today()} {shift_start}", "%Y-%m-%d %H:%M")
            if shift_end:
                today_report.shift_end_time = datetime.strptime(f"{date.today()} {shift_end}", "%Y-%m-%d %H:%M")
            
            # Update cumulative totals
            yesterday_report = DailyProductionStatus.query.filter(
                and_(
                    DailyProductionStatus.production_id == production_id,
                    DailyProductionStatus.report_date < date.today()
                )
            ).order_by(DailyProductionStatus.report_date.desc()).first()
            
            if yesterday_report:
                today_report.cumulative_completed = yesterday_report.cumulative_completed + today_report.qty_completed_today
                today_report.cumulative_good = yesterday_report.cumulative_good + today_report.qty_good_today
                today_report.cumulative_defective = yesterday_report.cumulative_defective + today_report.qty_defective_today
                today_report.cumulative_scrap = yesterday_report.cumulative_scrap + today_report.qty_scrap_today
            else:
                today_report.cumulative_completed = today_report.qty_completed_today
                today_report.cumulative_good = today_report.qty_good_today
                today_report.cumulative_defective = today_report.qty_defective_today
                today_report.cumulative_scrap = today_report.qty_scrap_today
            
            # Update main production record if production completed today
            if today_report.daily_status == 'completed':
                production.quantity_produced = today_report.cumulative_completed
                production.quantity_good = today_report.cumulative_good
                production.quantity_damaged = today_report.cumulative_defective
                production.scrap_quantity = today_report.cumulative_scrap
                production.status = 'completed'
                production.updated_at = datetime.utcnow()
            
            today_report.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash('Daily production status updated successfully!', 'success')
            return redirect(url_for('daily_production.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating daily status: {str(e)}', 'error')
    
    return render_template('daily_production/update_status.html',
                         title=f'Update Daily Status - {production.production_number}',
                         production=production,
                         item=item,
                         today_report=today_report)

@daily_production_bp.route('/history/<int:production_id>')
@login_required
def production_history(production_id):
    """View production history over time"""
    production = Production.query.get_or_404(production_id)
    item = Item.query.get(production.item_id)
    
    # Get all daily reports for this production
    daily_reports = DailyProductionStatus.query.filter_by(
        production_id=production_id
    ).order_by(DailyProductionStatus.report_date).all()
    
    # Calculate trends
    efficiency_trend = [r.efficiency_rate for r in daily_reports if r.qty_completed_today > 0]
    progress_trend = [r.progress_percentage for r in daily_reports]
    
    return render_template('daily_production/history.html',
                         title=f'Production History - {production.production_number}',
                         production=production,
                         item=item,
                         daily_reports=daily_reports,
                         efficiency_trend=efficiency_trend,
                         progress_trend=progress_trend)

@daily_production_bp.route('/shift-log/<int:production_id>', methods=['GET', 'POST'])
@login_required
def shift_log(production_id):
    """Record shift-wise production log"""
    production = Production.query.get_or_404(production_id)
    today_report = DailyProductionStatus.get_today_report(production_id)
    
    if not today_report:
        flash('Please create daily production status first', 'warning')
        return redirect(url_for('daily_production.update_daily_status', production_id=production_id))
    
    if request.method == 'POST':
        try:
            shift_log = ProductionShiftLog(
                daily_production_status_id=today_report.id,
                shift_type=request.form.get('shift_type'),
                shift_start=datetime.strptime(
                    f"{date.today()} {request.form.get('shift_start')}", 
                    "%Y-%m-%d %H:%M"
                ),
                shift_end=datetime.strptime(
                    f"{date.today()} {request.form.get('shift_end')}", 
                    "%Y-%m-%d %H:%M"
                ) if request.form.get('shift_end') else None,
                qty_produced_shift=float(request.form.get('qty_produced_shift', 0)),
                qty_good_shift=float(request.form.get('qty_good_shift', 0)),
                qty_defective_shift=float(request.form.get('qty_defective_shift', 0)),
                workers_present=int(request.form.get('workers_present', 0)),
                supervisor_name=request.form.get('supervisor_name', ''),
                machine_downtime_minutes=int(request.form.get('machine_downtime_minutes', 0)),
                downtime_reason=request.form.get('downtime_reason', ''),
                shift_notes=request.form.get('shift_notes', ''),
                issues_encountered=request.form.get('issues_encountered', '')
            )
            
            db.session.add(shift_log)
            db.session.commit()
            
            flash('Shift log recorded successfully!', 'success')
            return redirect(url_for('daily_production.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording shift log: {str(e)}', 'error')
    
    # Get existing shift logs for today
    existing_logs = ProductionShiftLog.query.filter_by(
        daily_production_status_id=today_report.id
    ).order_by(ProductionShiftLog.shift_start).all()
    
    return render_template('daily_production/shift_log.html',
                         title=f'Shift Log - {production.production_number}',
                         production=production,
                         today_report=today_report,
                         existing_logs=existing_logs)

@daily_production_bp.route('/reports')
@login_required
def reports():
    """Daily production reports and analytics"""
    # Date filters
    start_date = request.args.get('start_date', 
                                 (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', date.today().strftime('%Y-%m-%d'))
    
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get daily summaries in range
    daily_summaries = DailyProductionSummary.query.filter(
        and_(
            DailyProductionSummary.summary_date >= start_date,
            DailyProductionSummary.summary_date <= end_date
        )
    ).order_by(DailyProductionSummary.summary_date).all()
    
    # Get detailed production reports
    production_reports = db.session.query(
        DailyProductionStatus,
        Production,
        Item
    ).join(Production).join(Item, Item.id == Production.item_id).filter(
        and_(
            DailyProductionStatus.report_date >= start_date,
            DailyProductionStatus.report_date <= end_date
        )
    ).order_by(DailyProductionStatus.report_date.desc()).all()
    
    # Calculate aggregate metrics
    total_production = sum(s.total_qty_produced for s in daily_summaries)
    total_good = sum(s.total_qty_good for s in daily_summaries)
    total_defective = sum(s.total_qty_defective for s in daily_summaries)
    avg_efficiency = sum(s.overall_efficiency for s in daily_summaries) / len(daily_summaries) if daily_summaries else 0
    
    return render_template('daily_production/reports.html',
                         title='Daily Production Reports',
                         daily_summaries=daily_summaries,
                         production_reports=production_reports,
                         start_date=start_date,
                         end_date=end_date,
                         total_production=total_production,
                         total_good=total_good,
                         total_defective=total_defective,
                         avg_efficiency=avg_efficiency)

@daily_production_bp.route('/api/generate-daily-summary', methods=['POST'])
@login_required
def api_generate_daily_summary():
    """API to generate daily summary"""
    try:
        target_date = request.json.get('date')
        if target_date:
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        else:
            target_date = date.today()
        
        summary = DailyProductionSummary.generate_daily_summary(target_date)
        
        if summary:
            return jsonify({
                'success': True,
                'message': f'Daily summary generated for {target_date}',
                'summary_id': summary.id
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No production data found for the specified date'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@daily_production_bp.route('/api/quick-update/<int:production_id>', methods=['POST'])
@login_required
def api_quick_update(production_id):
    """Quick API update for daily status"""
    try:
        data = request.json
        
        report = DailyProductionStatus.create_or_update_today(
            production_id=production_id,
            qty_completed_today=data.get('qty_completed', 0),
            qty_good_today=data.get('qty_good', 0),
            qty_defective_today=data.get('qty_defective', 0),
            daily_status=data.get('status', 'active'),
            supervisor_notes=data.get('notes', ''),
            created_by_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': 'Daily status updated successfully',
            'efficiency_rate': report.efficiency_rate,
            'defect_rate': report.defect_rate
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500