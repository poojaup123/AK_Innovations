"""
Job Card Integration Routes

Routes for managing the integration between Job Cards and Job Work,
including outsourcing workflows, status tracking, and material flow.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import JobCard, JobWork, Production, Item, Supplier
try:
    from models.grn import GRN
except ImportError:
    GRN = None
from services.job_card_job_work_integration import JobCardJobWorkIntegration
from datetime import datetime, date

job_card_integration_bp = Blueprint('job_card_integration', __name__, url_prefix='/job-card-integration')

@job_card_integration_bp.route('/dashboard')
@login_required
def integration_dashboard():
    """Dashboard showing job card and job work integration status"""
    
    # Get summary data
    total_summary = JobCardJobWorkIntegration.get_job_card_status_summary()
    
    # Get recent activities
    recent_job_cards = JobCard.query.order_by(JobCard.created_at.desc()).limit(10).all()
    recent_job_works = JobWork.query.order_by(JobWork.created_at.desc()).limit(10).all()
    
    # Get production orders with job cards
    productions_with_jobs = Production.query.join(JobCard).distinct().all()
    
    return render_template('job_card_integration/dashboard.html',
                         summary=total_summary,
                         recent_job_cards=recent_job_cards,
                         recent_job_works=recent_job_works,
                         productions=productions_with_jobs)

@job_card_integration_bp.route('/outsource/<int:job_card_id>', methods=['GET', 'POST'])
@login_required
def outsource_job_card(job_card_id):
    """Convert job card to outsourced job work"""
    
    job_card = JobCard.query.get_or_404(job_card_id)
    
    if request.method == 'POST':
        try:
            vendor_id = request.form.get('vendor_id')
            expected_return_date = request.form.get('expected_return_date')
            notes = request.form.get('notes')
            
            # Convert date string to date object
            return_date = None
            if expected_return_date:
                return_date = datetime.strptime(expected_return_date, '%Y-%m-%d').date()
            
            # Create job work
            job_work = JobCardJobWorkIntegration.outsource_job_card(
                job_card_id=job_card_id,
                vendor_id=vendor_id,
                expected_return_date=return_date,
                notes=notes
            )
            
            flash(f'Job Card {job_card.job_card_number} successfully outsourced to vendor. Job Work {job_work.job_number} created.', 'success')
            return redirect(url_for('job_card_integration.view_job_card', job_card_id=job_card_id))
            
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash(f'Error outsourcing job card: {str(e)}', 'error')
    
    # Get available vendors
    vendors = Supplier.query.filter_by(partner_type='supplier').all()
    
    return render_template('job_card_integration/outsource_form.html',
                         job_card=job_card,
                         vendors=vendors)

@job_card_integration_bp.route('/api/job-card/<int:job_card_id>/outsourcing-options')
@login_required
def get_outsourcing_options(job_card_id):
    """API endpoint to get outsourcing options for a job card"""
    
    job_card = JobCard.query.get_or_404(job_card_id)
    
    # Get available vendors for this item/process
    vendors = Supplier.query.filter_by(partner_type='supplier').all()
    
    vendor_options = []
    for vendor in vendors:
        # Get vendor rate (this would be from a rates table in practice)
        rate = 100.0  # Placeholder
        
        vendor_options.append({
            'id': vendor.id,
            'name': vendor.name,
            'rate_per_unit': rate,
            'estimated_cost': rate * job_card.planned_quantity,
            'typical_lead_time': 7  # days
        })
    
    return jsonify({
        'job_card': {
            'number': job_card.job_card_number,
            'process': job_card.process_name,
            'quantity': job_card.planned_quantity,
            'can_outsource': job_card.status not in ['completed', 'cancelled']
        },
        'vendors': vendor_options
    })