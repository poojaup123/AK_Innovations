from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, date
from app import db
from models import ComponentJobCard, ComponentJobCardProcess, Production, BOM, User, Item, Supplier
from services.component_job_card_service import ComponentJobCardService
import json

component_job_cards_bp = Blueprint('component_job_cards', __name__, url_prefix='/job-cards')

@component_job_cards_bp.route('/')
@login_required
def dashboard():
    """Component Job Cards Dashboard"""
    dashboard_data = ComponentJobCardService.get_dashboard_data()
    return render_template('component_job_cards/dashboard.html', **dashboard_data)

@component_job_cards_bp.route('/today')
@login_required
def todays_jobs():
    """Today's Job Cards - Live Production Status"""
    today_cards = ComponentJobCardService.get_todays_job_cards()
    workers = User.query.filter_by(is_active=True).all()
    vendors = Supplier.query.filter_by(is_active=True).all()
    
    return render_template('component_job_cards/todays_jobs.html', 
                         job_cards=today_cards, 
                         workers=workers, 
                         vendors=vendors)

@component_job_cards_bp.route('/create/<int:production_id>')
@login_required
def create_from_production(production_id):
    """Create job cards from production order"""
    success, message = ComponentJobCardService.create_job_cards_for_production(production_id, current_user.id)
    
    if success:
        flash(message, 'success')
        return redirect(url_for('component_job_cards.production_cards', production_id=production_id))
    else:
        flash(message, 'error')
        return redirect(url_for('production.dashboard'))

@component_job_cards_bp.route('/production/<int:production_id>')
@login_required
def production_cards(production_id):
    """View all job cards for a production order"""
    production = Production.query.get_or_404(production_id)
    job_cards = ComponentJobCardService.get_production_job_cards(production_id)
    
    return render_template('component_job_cards/production_cards.html', 
                         production=production, 
                         job_cards=job_cards)

@component_job_cards_bp.route('/card/<int:job_card_id>')
@login_required
def view_card(job_card_id):
    """View detailed job card information"""
    card_details = ComponentJobCardService.get_job_card_details(job_card_id)
    
    if not card_details:
        flash('Job card not found', 'error')
        return redirect(url_for('component_job_cards.dashboard'))
    
    workers = User.query.filter_by(is_active=True).all()
    vendors = Supplier.query.filter_by(is_active=True).all()
    
    return render_template('component_job_cards/card_detail.html', 
                         **card_details, 
                         workers=workers, 
                         vendors=vendors)

@component_job_cards_bp.route('/assign/<int:job_card_id>', methods=['POST'])
@login_required
def assign_card(job_card_id):
    """Assign job card to worker/vendor"""
    data = request.get_json()
    
    worker_id = data.get('worker_id')
    vendor_id = data.get('vendor_id')
    department = data.get('department')
    target_date = data.get('target_date')
    
    # Convert target_date string to date object
    if target_date:
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    
    success, message = ComponentJobCardService.assign_job_card(
        job_card_id, worker_id, vendor_id, department, target_date
    )
    
    return jsonify({'success': success, 'message': message})

@component_job_cards_bp.route('/update-progress/<int:job_card_id>', methods=['POST'])
@login_required
def update_progress(job_card_id):
    """Update job card progress"""
    data = request.get_json()
    
    quantity_consumed = float(data.get('quantity_consumed', 0))
    process_step = data.get('process_step')
    worker_id = data.get('worker_id')
    notes = data.get('notes')
    
    success, message = ComponentJobCardService.update_job_card_progress(
        job_card_id, quantity_consumed, process_step, worker_id, notes
    )
    
    return jsonify({'success': success, 'message': message})

@component_job_cards_bp.route('/hold/<int:job_card_id>', methods=['POST'])
@login_required
def hold_card(job_card_id):
    """Put job card on hold"""
    data = request.get_json()
    reason = data.get('reason', 'Unknown')
    notes = data.get('notes')
    
    success, message = ComponentJobCardService.hold_job_card(job_card_id, reason, notes)
    
    return jsonify({'success': success, 'message': message})

@component_job_cards_bp.route('/resume/<int:job_card_id>', methods=['POST'])
@login_required
def resume_card(job_card_id):
    """Resume job card from hold"""
    data = request.get_json()
    notes = data.get('notes')
    
    success, message = ComponentJobCardService.resume_job_card(job_card_id, notes)
    
    return jsonify({'success': success, 'message': message})

@component_job_cards_bp.route('/complete/<int:job_card_id>', methods=['POST'])
@login_required
def complete_card(job_card_id):
    """Complete a job card"""
    data = request.get_json()
    
    actual_quantity = data.get('actual_quantity')
    scrap_quantity = float(data.get('scrap_quantity', 0))
    quality_notes = data.get('quality_notes')
    
    if actual_quantity is not None:
        actual_quantity = float(actual_quantity)
    
    success, message = ComponentJobCardService.complete_job_card(
        job_card_id, actual_quantity, scrap_quantity, quality_notes
    )
    
    return jsonify({'success': success, 'message': message})

@component_job_cards_bp.route('/worker/<int:worker_id>')
@login_required
def worker_cards(worker_id):
    """View job cards assigned to a specific worker"""
    worker = User.query.get_or_404(worker_id)
    job_cards = ComponentJobCardService.get_worker_job_cards(worker_id)
    
    return render_template('component_job_cards/worker_cards.html', 
                         worker=worker, 
                         job_cards=job_cards)

@component_job_cards_bp.route('/analytics')
@login_required
def analytics():
    """Job Cards Analytics Dashboard"""
    analytics_data = ComponentJobCardService.get_analytics_data()
    dashboard_data = ComponentJobCardService.get_dashboard_data()
    
    return render_template('component_job_cards/analytics.html', 
                         analytics=analytics_data, 
                         dashboard=dashboard_data)

@component_job_cards_bp.route('/api/card/<int:job_card_id>')
@login_required
def api_get_card(job_card_id):
    """API endpoint to get job card details"""
    card_details = ComponentJobCardService.get_job_card_details(job_card_id)
    
    if not card_details:
        return jsonify({'error': 'Job card not found'}), 404
    
    job_card = card_details['job_card']
    
    return jsonify({
        'id': job_card.id,
        'job_card_number': job_card.job_card_number,
        'component_name': job_card.component_name,
        'status': job_card.status,
        'progress_percentage': job_card.progress_percentage,
        'planned_quantity': job_card.planned_quantity,
        'actual_quantity_consumed': job_card.actual_quantity_consumed,
        'remaining_quantity': job_card.remaining_quantity,
        'scrap_quantity': job_card.scrap_quantity,
        'target_completion_date': job_card.target_completion_date.isoformat(),
        'assigned_worker': job_card.assigned_worker.username if job_card.assigned_worker else None,
        'assigned_department': job_card.assigned_department,
        'priority': job_card.priority,
        'is_delayed': job_card.is_delayed,
        'days_remaining': job_card.days_remaining
    })

@component_job_cards_bp.route('/api/todays-summary')
@login_required
def api_todays_summary():
    """API endpoint for today's job cards summary"""
    today_cards = ComponentJobCardService.get_todays_job_cards()
    
    summary = {
        'total_cards': len(today_cards),
        'planned': len([c for c in today_cards if c.status == 'planned']),
        'issued': len([c for c in today_cards if c.status == 'issued']),
        'in_progress': len([c for c in today_cards if c.status == 'in_progress']),
        'completed': len([c for c in today_cards if c.status == 'completed']),
        'on_hold': len([c for c in today_cards if c.status == 'on_hold']),
        'delayed': len([c for c in today_cards if c.is_delayed]),
        'high_priority': len([c for c in today_cards if c.priority in ['high', 'urgent']])
    }
    
    return jsonify(summary)