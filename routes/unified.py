from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import Production, Employee
from models.job_card import JobCard
from sqlalchemy import desc, and_, or_
from datetime import datetime, date
from app import db

unified_bp = Blueprint('unified', __name__, url_prefix='/unified')

@unified_bp.route('/manufacturing-hub')
@login_required
def manufacturing_hub():
    """Unified Manufacturing Hub - combines Production, Job Cards, and Live Status"""
    
    # Get all productions with their job cards
    productions = Production.query.order_by(desc(Production.created_at)).limit(20).all()
    
    # Get active job cards (not completed)
    active_job_cards = JobCard.query.filter(
        JobCard.status.in_(['planned', 'in_progress'])
    ).order_by(desc(JobCard.created_at)).limit(12).all()
    
    # Get active workers with current job assignments
    active_workers = Employee.query.filter_by(is_active=True).all()
    
    # Calculate statistics
    stats = {
        'active_productions': Production.query.filter(
            Production.status.in_(['approved', 'in_progress'])
        ).count(),
        'pending_job_cards': JobCard.query.filter(
            JobCard.status == 'planned'
        ).count(),
        'completed_today': JobCard.query.filter(
            and_(
                JobCard.status == 'completed',
                JobCard.actual_end_date == date.today()
            )
        ).count(),
        'overdue_cards': JobCard.query.filter(
            and_(
                JobCard.status.in_(['planned', 'in_progress']),
                JobCard.target_completion_date < date.today()
            )
        ).count()
    }
    
    return render_template('unified/manufacturing_hub.html',
                         productions=productions,
                         active_job_cards=active_job_cards,
                         active_workers=active_workers,
                         stats=stats)

@unified_bp.route('/api/production/<int:production_id>/job-cards')
@login_required
def get_production_job_cards(production_id):
    """API endpoint to get job cards for a production order"""
    production = Production.query.get_or_404(production_id)
    
    job_cards = production.job_cards
    
    # Return rendered HTML for the modal
    html = render_template('unified/partials/job_cards_detail.html', 
                          job_cards=job_cards, 
                          production=production)
    return html

@unified_bp.route('/api/job-cards/<int:job_card_id>/progress-form')
@login_required
def get_progress_form(job_card_id):
    """API endpoint to get progress update form for a job card"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    # Return rendered HTML for the modal
    html = render_template('unified/partials/progress_form.html', 
                          job_card=job_card)
    return html

@unified_bp.route('/api/live-status/refresh')
@login_required
def refresh_live_status():
    """API endpoint to refresh live status data"""
    
    # Get real-time statistics
    stats = {
        'active_productions': Production.query.filter(
            and_(
                Production.company_id == current_user.company_id,
                Production.status.in_(['approved', 'in_progress'])
            )
        ).count(),
        'today_completed': JobCard.query.filter(
            and_(
                JobCard.company_id == current_user.company_id,
                JobCard.status == 'completed',
                JobCard.actual_completion_date == date.today()
            )
        ).count(),
        'efficiency_rate': calculate_efficiency_rate(),
        'active_workers': Employee.query.filter_by(
            company_id=current_user.company_id,
            is_active=True
        ).count()
    }
    
    return jsonify(stats)

@unified_bp.route('/api/job-cards/update-progress', methods=['POST'])
@login_required
def update_job_card_progress():
    """API endpoint to update job card progress"""
    try:
        job_card_id = request.form.get('job_card_id')
        completed_quantity = float(request.form.get('completed_quantity', 0))
        status = request.form.get('status')
        progress_notes = request.form.get('progress_notes', '')
        
        job_card = JobCard.query.get_or_404(job_card_id)
        
        if job_card.company_id != current_user.company_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Update job card
        job_card.completed_quantity = completed_quantity
        job_card.status = status
        job_card.progress_notes = progress_notes
        
        if status == 'completed':
            job_card.actual_end_date = date.today()
        elif status == 'in_progress' and not job_card.actual_start_date:
            job_card.actual_start_date = date.today()
        
        # Calculate completion rate
        if job_card.planned_quantity > 0:
            job_card.progress_percentage = (completed_quantity / job_card.planned_quantity) * 100
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Progress updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

def calculate_efficiency_rate():
    """Calculate current efficiency rate based on planned vs actual completion"""
    try:
        # Get today's completed job cards
        completed_today = JobCard.query.filter(
            and_(
                JobCard.company_id == current_user.company_id,
                JobCard.actual_completion_date == date.today()
            )
        ).all()
        
        if not completed_today:
            return 0
        
        total_planned = sum(card.planned_quantity for card in completed_today)
        total_completed = sum(card.completed_quantity for card in completed_today)
        
        if total_planned > 0:
            return round((total_completed / total_planned) * 100, 1)
        
        return 0
    except:
        return 0