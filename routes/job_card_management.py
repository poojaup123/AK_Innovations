"""
Job Card Management Routes

Handles all job card related operations including viewing, creating, 
updating, and managing the job card lifecycle according to the 
production workflow specifications.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import Production, Item
from models.job_card import JobCard, JobCardDailyStatus
from services.job_card_generator import generate_job_cards_for_production
from forms_job_card import JobCardForm, JobCardDailyUpdateForm
from app import db
from datetime import date, datetime
import json

job_card_management_bp = Blueprint('job_card_management', __name__, url_prefix='/job-cards')

@job_card_management_bp.route('/production/<int:production_id>')
@login_required
def view_production_job_cards(production_id):
    """View all job cards for a specific production order"""
    production = Production.query.get_or_404(production_id)
    
    # Get all job cards for this production, ordered by component level and sequence
    job_cards = JobCard.query.filter_by(production_id=production_id)\
                            .order_by(JobCard.component_level, JobCard.process_sequence)\
                            .all()
    
    # Get the production item
    production.item = Item.query.get(production.item_id) if production.item_id else None
    
    return render_template('job_cards/production_job_cards.html',
                         production=production,
                         job_cards=job_cards,
                         title=f'Job Cards - {production.production_number}')

@job_card_management_bp.route('/view/<int:job_card_id>')
@login_required  
def view_job_card(job_card_id):
    """View detailed job card information"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    # Get job card item and production
    job_card.item = Item.query.get(job_card.item_id) if job_card.item_id else None
    job_card.production = Production.query.get(job_card.production_id)
    
    # Get daily status updates
    daily_statuses = JobCardDailyStatus.query.filter_by(job_card_id=job_card_id)\
                                             .order_by(JobCardDailyStatus.report_date.desc())\
                                             .all()
    
    # Get material requirements
    material_requirements = job_card.get_material_requirements()
    
    # Get process routing steps
    routing_steps = job_card.get_process_routing_steps()
    
    return render_template('job_cards/job_card_detail.html',
                         job_card=job_card,
                         daily_statuses=daily_statuses,
                         material_requirements=material_requirements,
                         routing_steps=routing_steps,
                         title=f'Job Card - {job_card.job_card_number}')

@job_card_management_bp.route('/generate/<int:production_id>', methods=['POST'])
@login_required
def generate_job_cards(production_id):
    """Generate job cards for a production order"""
    try:
        production = Production.query.get_or_404(production_id)
        
        # Generate job cards using the service
        generated_cards = generate_job_cards_for_production(production_id)
        
        if generated_cards:
            flash(f'Successfully generated {len(generated_cards)} job cards for {production.production_number}', 'success')
        else:
            flash('No job cards were generated. Check if the item has a valid BOM.', 'warning')
            
    except Exception as e:
        flash(f'Error generating job cards: {str(e)}', 'danger')
    
    return redirect(url_for('job_cards.view_production_job_cards', production_id=production_id))

@job_card_management_bp.route('/update/<int:job_card_id>', methods=['GET', 'POST'])
@login_required
def update_daily_status(job_card_id):
    """Update daily status for a job card"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    # Get or create today's status
    today = date.today()
    daily_status = JobCardDailyStatus.query.filter_by(
        job_card_id=job_card_id,
        report_date=today
    ).first()
    
    form = JobCardDailyUpdateForm()
    
    if daily_status:
        # Pre-populate form with existing data
        form = JobCardDailyUpdateForm(obj=daily_status)
    
    form.job_card_id.data = job_card_id
    
    if form.validate_on_submit():
        try:
            # Create or update daily status
            if not daily_status:
                daily_status = JobCardDailyStatus(
                    job_card_id=job_card_id,
                    report_date=today,
                    reported_by_id=current_user.id
                )
                db.session.add(daily_status)
            
            # Update values
            daily_status.qty_completed_today = form.qty_completed_today.data
            daily_status.qty_good_today = form.qty_good_today.data
            daily_status.qty_defective_today = form.qty_defective_today.data
            daily_status.qty_scrap_today = form.qty_scrap_today.data
            daily_status.daily_status = form.daily_status.data
            daily_status.efficiency_rate = form.efficiency_rate.data
            daily_status.machine_hours_used = form.machine_hours_used.data
            daily_status.overtime_hours = form.overtime_hours.data
            daily_status.material_consumed_cost = form.material_consumed_cost.data
            daily_status.labor_cost_today = form.labor_cost_today.data
            daily_status.production_issues = form.production_issues.data
            daily_status.quality_issues = form.quality_issues.data
            daily_status.supervisor_notes = form.supervisor_notes.data
            daily_status.updated_at = datetime.utcnow()
            
            # Handle workflow status
            if hasattr(form, 'status_after_entry') and form.status_after_entry.data:
                if form.status_after_entry.data == 'pending_approval':
                    daily_status.approval_status = 'pending_approval'
                elif form.status_after_entry.data == 'submit_to_qc':
                    daily_status.approval_status = 'approved'
                    daily_status.supervisor_approved = True
                    daily_status.supervisor_approved_by_id = current_user.id
                    daily_status.supervisor_approved_at = datetime.utcnow()
                    daily_status.qc_status = 'pending_qc'
            
            # Handle batch creation
            if hasattr(form, 'create_new_batch') and form.create_new_batch.data and form.qty_good_today.data > 0:
                batch_number = job_card.generate_output_batch()
                daily_status.batch_number = batch_number
                flash(f'Output batch {batch_number} created for good quantity', 'success')
            
            # Update main job card quantities
            job_card.completed_quantity += form.qty_completed_today.data
            job_card.good_quantity += form.qty_good_today.data
            job_card.defective_quantity += form.qty_defective_today.data
            job_card.scrap_quantity += form.qty_scrap_today.data
            
            # Update job card progress
            job_card.update_progress()
            
            db.session.commit()
            
            flash(f'Daily status updated for job card {job_card.job_card_number}', 'success')
            return redirect(url_for('job_cards.view_job_card', job_card_id=job_card_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating daily status: {str(e)}', 'danger')
    
    # Get job card details for display
    job_card.item = Item.query.get(job_card.item_id) if job_card.item_id else None
    job_card.production = Production.query.get(job_card.production_id)
    
    return render_template('job_cards/daily_update.html',
                         form=form,
                         job_card=job_card,
                         daily_status=daily_status,
                         title=f'Update Status - {job_card.job_card_number}')

@job_card_management_bp.route('/list')
@login_required
def list_job_cards():
    """List all job cards with filtering options"""
    # Get filter parameters
    status = request.args.get('status', '')
    job_type = request.args.get('job_type', '')
    search = request.args.get('search', '')
    
    # Build query
    query = JobCard.query.join(Production).join(Item)
    
    if status:
        query = query.filter(JobCard.status == status)
    
    if job_type:
        query = query.filter(JobCard.job_type == job_type)
    
    if search:
        query = query.filter(
            db.or_(
                JobCard.job_card_number.ilike(f'%{search}%'),
                Production.production_number.ilike(f'%{search}%'),
                Item.name.ilike(f'%{search}%')
            )
        )
    
    # Order by most recent
    job_cards = query.order_by(JobCard.created_at.desc()).all()
    
    # Get statistics
    stats = {
        'total': JobCard.query.count(),
        'planned': JobCard.query.filter_by(status='planned').count(),
        'in_progress': JobCard.query.filter_by(status='in_progress').count(),
        'completed': JobCard.query.filter_by(status='completed').count(),
        'in_house': JobCard.query.filter_by(job_type='in_house').count(),
        'outsourced': JobCard.query.filter_by(job_type='outsourced').count(),
    }
    
    return render_template('job_cards/list.html',
                         job_cards=job_cards,
                         stats=stats,
                         filters={'status': status, 'job_type': job_type, 'search': search},
                         title='All Job Cards')

@job_card_management_bp.route('/create-gate-pass/<int:job_card_id>', methods=['POST'])
@login_required
def create_gate_pass(job_card_id):
    """Create a gate pass for outsourced job card"""
    try:
        job_card = JobCard.query.get_or_404(job_card_id)
        
        if job_card.job_type != 'outsourced':
            return jsonify({'success': False, 'message': 'Gate pass can only be created for outsourced jobs'})
        
        if job_card.gate_pass_number:
            return jsonify({'success': False, 'message': 'Gate pass already exists for this job card'})
        
        # Generate gate pass number
        gate_pass_number = f"GP-{job_card.job_card_number}-{datetime.now().strftime('%Y%m%d')}"
        job_card.gate_pass_number = gate_pass_number
        
        # Update status to indicate materials are being sent out
        if job_card.status == 'planned':
            job_card.status = 'in_progress'
            job_card.actual_start_date = date.today()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Gate pass {gate_pass_number} created successfully',
            'gate_pass_number': gate_pass_number
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@job_card_management_bp.route('/api/dashboard-stats')
@login_required
def api_dashboard_stats():
    """API endpoint for job card dashboard statistics"""
    try:
        today = date.today()
        
        stats = {
            'total_job_cards': JobCard.query.count(),
            'active_today': JobCard.query.filter(
                JobCard.status.in_(['planned', 'in_progress']),
                JobCard.target_completion_date >= today
            ).count(),
            'overdue': JobCard.query.filter(
                JobCard.status.in_(['planned', 'in_progress']),
                JobCard.target_completion_date < today
            ).count(),
            'completed_today': JobCard.query.filter(
                JobCard.status == 'completed',
                JobCard.actual_end_date == today
            ).count(),
            'by_type': {
                'in_house': JobCard.query.filter_by(job_type='in_house').count(),
                'outsourced': JobCard.query.filter_by(job_type='outsourced').count()
            },
            'by_status': {
                'planned': JobCard.query.filter_by(status='planned').count(),
                'in_progress': JobCard.query.filter_by(status='in_progress').count(),
                'completed': JobCard.query.filter_by(status='completed').count(),
                'on_hold': JobCard.query.filter_by(status='on_hold').count()
            }
        }
        
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@job_card_management_bp.route('/update-status/<int:job_card_id>')
@login_required
def update_status(job_card_id):
    """Update job card status"""
    job_card = JobCard.query.get_or_404(job_card_id)
    new_status = request.args.get('status')
    
    if new_status in ['planned', 'in_progress', 'completed', 'on_hold']:
        job_card.status = new_status
        
        if new_status == 'in_progress' and not job_card.actual_start_date:
            job_card.actual_start_date = date.today()
        elif new_status == 'completed':
            job_card.actual_end_date = date.today()
            job_card.progress_percentage = 100
        
        db.session.commit()
        flash(f'Job card status updated to {new_status.replace("_", " ").title()}', 'success')
    
    return redirect(url_for('job_card_management.list_job_cards'))

@job_card_management_bp.route('/mark-process-complete/<int:job_card_id>', methods=['POST'])
@login_required
def mark_process_complete(job_card_id):
    """Mark a specific process step as complete"""
    try:
        job_card = JobCard.query.get_or_404(job_card_id)
        data = request.get_json()
        
        step_name = data.get('step_name')
        notes = data.get('notes', '')
        
        if not step_name:
            return jsonify({'success': False, 'message': 'Step name is required'})
        
        job_card.mark_process_step_complete(step_name, notes)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Process step "{step_name}" marked as complete',
            'current_step': job_card.current_process_step
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})