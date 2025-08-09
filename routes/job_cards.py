from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Production, Item, BOM, BOMItem, Employee, Supplier
from models.job_card import JobCard, JobCardDailyStatus, JobCardMaterial
from forms_job_card import JobCardForm, JobCardDailyUpdateForm, BulkJobCardForm
from datetime import datetime, date, timedelta
from utils import generate_production_number
from sqlalchemy import func, or_

job_cards_bp = Blueprint('job_cards', __name__)

def _generate_process_name_for_component(bom_item):
    """Generate intelligent process name based on component type"""
    item_name = bom_item.item.name.lower() if bom_item.item else "component"
    
    # Define process mapping based on component names
    if any(keyword in item_name for keyword in ['plate', 'sheet', 'mounting']):
        return "Cutting & Forming"
    elif any(keyword in item_name for keyword in ['base', 'frame', 'support']):
        return "Base Assembly"
    elif any(keyword in item_name for keyword in ['wheel', 'caster', 'castor']):
        return "Wheel Assembly"
    elif any(keyword in item_name for keyword in ['bolt', 'screw', 'fastener', 'nut']):
        return "Fastening & Assembly"
    elif any(keyword in item_name for keyword in ['pipe', 'tube', 'rod']):
        return "Machining & Threading"
    elif any(keyword in item_name for keyword in ['bearing', 'bushing']):
        return "Precision Assembly"
    else:
        return f"Processing - {bom_item.item.name}"

@job_cards_bp.route('/first')
@login_required
def view_first_job_card():
    """Redirect to the first available job card for easy access"""
    first_job_card = JobCard.query.order_by(JobCard.id.desc()).first()
    if first_job_card:
        return redirect(url_for('job_cards.view_job_card', id=first_job_card.id))
    else:
        flash('No job cards found', 'warning')
        return redirect(url_for('job_cards.dashboard'))

@job_cards_bp.route('/dashboard')
@login_required
def dashboard():
    """Job Card Management Dashboard"""
    today = date.today()
    
    # Job Card Statistics
    total_job_cards = JobCard.query.count()
    planned_cards = JobCard.query.filter_by(status='planned').count()
    in_progress_cards = JobCard.query.filter_by(status='in_progress').count()
    completed_cards = JobCard.query.filter_by(status='completed').count()
    overdue_cards = JobCard.query.filter(
        JobCard.target_completion_date < today,
        JobCard.status.in_(['planned', 'in_progress'])
    ).count()
    
    # Today's Active Job Cards
    today_active_cards = JobCard.query.filter(
        JobCard.status.in_(['in_progress', 'planned']),
        JobCard.target_completion_date >= today
    ).order_by(JobCard.target_completion_date).limit(10).all()
    
    # Today's Daily Reports
    today_reports = JobCardDailyStatus.query.filter_by(report_date=today).all()
    
    # Calculate daily metrics
    total_completed_today = sum(r.qty_completed_today for r in today_reports)
    total_good_today = sum(r.qty_good_today for r in today_reports)
    total_defective_today = sum(r.qty_defective_today for r in today_reports)
    efficiency_rate = (total_good_today / total_completed_today * 100) if total_completed_today > 0 else 0
    
    # Group reports by status
    status_groups = {
        'active': [r for r in today_reports if r.daily_status == 'active'],
        'completed': [r for r in today_reports if r.daily_status == 'completed'],
        'delayed': [r for r in today_reports if r.daily_status == 'delayed'],
        'on_hold': [r for r in today_reports if r.daily_status == 'on_hold']
    }
    
    # Job cards without daily reports
    reported_job_card_ids = {r.job_card_id for r in today_reports}
    cards_without_reports = [
        card for card in today_active_cards 
        if card.id not in reported_job_card_ids
    ]
    
    stats = {
        'total_job_cards': total_job_cards,
        'planned_cards': planned_cards,
        'in_progress_cards': in_progress_cards,
        'completed_cards': completed_cards,
        'overdue_cards': overdue_cards,
        'total_completed_today': total_completed_today,
        'total_good_today': total_good_today,
        'total_defective_today': total_defective_today,
        'efficiency_rate_today': efficiency_rate
    }
    
    return render_template('job_cards/dashboard.html',
                         stats=stats,
                         today_active_cards=today_active_cards,
                         today_reports=today_reports,
                         status_groups=status_groups,
                         cards_without_reports=cards_without_reports,
                         today=today)

@job_cards_bp.route('/create/<int:production_id>')
@job_cards_bp.route('/create')
@login_required
def create_job_card(production_id=None):
    """Create a new job card"""
    form = JobCardForm()
    
    # Populate dropdown choices
    form.item_id.choices = [(0, 'Select Item')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.all()]
    form.assigned_worker_id.choices = [(0, 'Select Worker')] + [(e.id, e.name) for e in Employee.query.all()]
    form.assigned_vendor_id.choices = [(0, 'Select Vendor')] + [(s.id, s.name) for s in Supplier.query.filter_by(partner_type='vendor').all()]
    
    production = None
    if production_id:
        production = Production.query.get_or_404(production_id)
        form.production_id.data = production_id
        
        # Auto-generate job card number
        next_sequence = JobCard.query.filter_by(production_id=production_id).count() + 1
        form.job_card_number.data = JobCard.generate_job_card_number(production.production_number, next_sequence)
    
    if form.validate_on_submit():
        try:
            job_card = JobCard(
                job_card_number=form.job_card_number.data,
                production_id=form.production_id.data,
                item_id=form.item_id.data,
                process_name=form.process_name.data,
                process_sequence=form.process_sequence.data,
                operation_description=form.operation_description.data,
                planned_quantity=form.planned_quantity.data,
                assigned_worker_id=form.assigned_worker_id.data if form.assigned_worker_id.data else None,
                assigned_vendor_id=form.assigned_vendor_id.data if form.assigned_vendor_id.data else None,
                machine_workstation=form.machine_workstation.data,
                setup_time_minutes=form.setup_time_minutes.data,
                run_time_minutes=form.run_time_minutes.data,
                planned_start_date=form.planned_start_date.data,
                planned_end_date=form.planned_end_date.data,
                target_completion_date=form.target_completion_date.data,
                priority=form.priority.data,
                estimated_cost=form.estimated_cost.data,
                production_notes=form.production_notes.data,
                created_by_id=current_user.id
            )
            
            db.session.add(job_card)
            db.session.commit()
            
            flash(f'Job card {job_card.job_card_number} created successfully!', 'success')
            return redirect(url_for('job_cards.view_job_card', id=job_card.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating job card: {str(e)}', 'danger')
    
    return render_template('job_cards/create.html', form=form, production=production)

@job_cards_bp.route('/bulk-create/<int:production_id>')
@login_required
def bulk_create_from_bom(production_id):
    """Create multiple job cards from BOM"""
    production = Production.query.get_or_404(production_id)
    
    if not production.bom:
        flash('Production order must have a BOM to create job cards', 'warning')
        return redirect(url_for('production.view_production', id=production_id))
    
    form = BulkJobCardForm()
    form.production_id.data = production_id
    form.bom_id.data = production.bom.id
    
    if form.validate_on_submit():
        try:
            created_count = 0
            current_date = date.today()
            
            # First check if BOM has defined processes
            bom_processes = production.bom.processes if hasattr(production.bom, 'processes') else []
            
            if bom_processes:
                # Create job cards based on BOM processes
                for sequence, bom_process in enumerate(bom_processes, 1):
                    target_date = current_date + timedelta(days=form.buffer_days.data * sequence)
                    job_card_number = JobCard.generate_job_card_number(production.production_number, sequence)
                    
                    job_card = JobCard(
                        job_card_number=job_card_number,
                        production_id=production_id,
                        item_id=production.item_id,  # Use production item for process-based cards
                        process_name=bom_process.process_name,
                        process_sequence=bom_process.step_number,
                        operation_description=bom_process.operation_description or f"Process: {bom_process.process_name}",
                        planned_quantity=production.quantity_planned,
                        setup_time_minutes=bom_process.setup_time_minutes or 0,
                        run_time_minutes=bom_process.run_time_minutes or 0,
                        target_completion_date=target_date,
                        priority=form.default_priority.data,
                        created_by_id=current_user.id
                    )
                    db.session.add(job_card)
                    created_count += 1
            else:
                # Create job cards for each BOM item with intelligent process names
                for sequence, bom_item in enumerate(production.bom.items, 1):
                    target_date = current_date + timedelta(days=form.buffer_days.data * sequence)
                    job_card_number = JobCard.generate_job_card_number(production.production_number, sequence)
                    
                    # Generate intelligent process name based on component type
                    process_name = _generate_process_name_for_component(bom_item)
                    
                    job_card = JobCard(
                        job_card_number=job_card_number,
                        production_id=production_id,
                        item_id=bom_item.item_id,
                        process_name=process_name,
                        process_sequence=sequence,
                        operation_description=f"Manufacturing and assembly of {bom_item.item.name}",
                        planned_quantity=bom_item.quantity_required * production.quantity_planned,
                        target_completion_date=target_date,
                        priority=form.default_priority.data,
                        created_by_id=current_user.id
                    )
                
                    db.session.add(job_card)
                    created_count += 1
            
            db.session.commit()
            flash(f'Successfully created {created_count} job cards from BOM', 'success')
            return redirect(url_for('production.view_production', id=production_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating job cards: {str(e)}', 'danger')
    
    return render_template('job_cards/bulk_create.html', 
                         form=form, 
                         production=production,
                         bom_items=production.bom.items)

@job_cards_bp.route('/update-daily-status/<int:job_card_id>', methods=['GET', 'POST'])
@login_required
def update_daily_status(job_card_id):
    """Update daily status for a job card"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    # Get BOM processes for this job card
    bom_processes = []
    if job_card.bom_item_id:
        from models import BOMProcess
        bom_processes = BOMProcess.query.filter_by(
            bom_id=job_card.bom_item.bom_id if job_card.bom_item else None
        ).order_by(BOMProcess.step_number).all()
    
    # Vendors are handled in separate outsourcing workflow
    
    # Get today's report if exists
    today_report = JobCardDailyStatus.get_today_report(job_card_id)
    
    form = JobCardDailyUpdateForm()
    if today_report:
        form = JobCardDailyUpdateForm(obj=today_report)
    
    form.job_card_id.data = job_card_id
    
    if form.validate_on_submit():
        try:
            # Calculate cumulative values
            cumulative_completed = (today_report.cumulative_completed if today_report else 0) + form.qty_completed_today.data
            cumulative_good = (today_report.cumulative_good if today_report else 0) + form.qty_good_today.data
            cumulative_defective = (today_report.cumulative_defective if today_report else 0) + form.qty_defective_today.data
            cumulative_scrap = (today_report.cumulative_scrap if today_report else 0) + form.qty_scrap_today.data
            
            # Handle process selection for BOM-based tracking
            selected_processes = request.form.getlist('selected_processes')
            process_notes = ""
            if selected_processes:
                # Update job card with selected processes
                job_card.current_process_step = form.current_process_step.data
                job_card.process_notes = form.process_notes.data
                
                # Track which processes were worked on today (for multi-step workflow)
                from models import BOMProcess
                process_names = []
                for process_id in selected_processes:
                    process = BOMProcess.query.get(process_id)
                    if process:
                        process_names.append(f"Step {process.step_number}: {process.process_name}")
                
                process_notes = f"Processes worked: {', '.join(process_names)}"
            
            # No more inline outsourcing - handled in separate workflow
                
            # Update daily status report
            updated_report = JobCardDailyStatus.create_or_update_today(
                job_card_id=job_card_id,
                qty_completed_today=form.qty_completed_today.data,
                qty_good_today=form.qty_good_today.data,
                qty_defective_today=form.qty_defective_today.data,
                qty_scrap_today=form.qty_scrap_today.data,
                cumulative_completed=cumulative_completed,
                cumulative_good=cumulative_good,
                cumulative_defective=cumulative_defective,
                cumulative_scrap=cumulative_scrap,
                hours_worked=form.hours_worked.data,
                setup_time_actual=form.setup_time_actual.data,
                run_time_actual=form.run_time_actual.data,
                downtime_minutes=form.downtime_minutes.data,
                daily_status=form.daily_status.data,
                quality_issues=form.quality_issues.data,
                production_issues=form.production_issues.data,
                material_issues=form.material_issues.data,
                machine_issues=form.machine_issues.data,
                operator_notes=process_notes if process_notes else form.operator_notes.data,
                reported_by_id=current_user.id
            )
            
            # Always return to job card detail page to show the progress report
            flash(f'Daily status updated for job card {job_card.job_card_number}', 'success')
            return redirect(url_for('job_cards.view_job_card', id=job_card_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating daily status: {str(e)}', 'danger')
    
    return render_template('job_cards/update_daily.html',
                         form=form,
                         job_card=job_card,
                         today_report=today_report,
                         bom_processes=bom_processes)


@job_cards_bp.route('/outsourcing-workflow/<int:job_card_id>', methods=['GET', 'POST'])
@login_required
def outsourcing_workflow(job_card_id):
    """Separate outsourcing workflow after progress report submission"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    # Get available vendors
    from models import Supplier
    vendors = Supplier.query.filter(
        Supplier.partner_type.in_(['vendor', 'both'])
    ).filter_by(is_active=True).all()
    
    # Get BOM processes for this job card
    bom_processes = []
    if job_card.bom_item_id:
        from models import BOMProcess
        bom_processes = BOMProcess.query.filter_by(
            bom_id=job_card.bom_item.bom_id if job_card.bom_item else None
        ).order_by(BOMProcess.step_number).all()
    
    # Get latest daily report to check available quantities
    from models import JobCardDailyStatus
    latest_report = JobCardDailyStatus.get_today_report(job_card_id)
    available_quantity = latest_report.qty_good_today if latest_report else 0
    
    from forms_outsourcing import OutsourcingWorkflowForm
    form = OutsourcingWorkflowForm()
    
    # Populate form choices
    form.selected_processes.choices = [
        (str(process.id), f"Step {process.step_number}: {process.process_name}")
        for process in bom_processes
    ]
    
    form.vendor_id.choices = [
        (str(vendor.id), f"{vendor.name} - {vendor.contact_person}")
        for vendor in vendors
    ]
    
    form.job_card_id.data = job_card_id
    form.available_quantity.data = available_quantity
    
    if form.validate_on_submit():
        try:
            # Create outsourcing record
            vendor_id = int(form.vendor_id.data)
            vendor = Supplier.query.get(vendor_id)
            outsource_quantity = form.outsource_quantity.data
            
            # Update job card
            job_card.status = 'partially_outsourced'
            job_card.assigned_vendor_id = vendor_id
            job_card.outsource_notes = form.outsource_notes.data
            
            # Create tracking batch if requested
            if form.create_tracking_batch.data:
                from models import ItemBatch
                outsource_batch = ItemBatch(
                    item_id=job_card.item_id,
                    batch_number=f"OUTSOURCE-{job_card.job_card_number}-{vendor.name.upper()[:3]}",
                    qty_wip=outsource_quantity,
                    batch_type='outsourced',
                    notes=f"Sent to {vendor.name} for processing"
                )
                db.session.add(outsource_batch)
            
            db.session.commit()
            flash(f'Successfully sent {outsource_quantity} pieces to {vendor.name} for outsourcing', 'success')
            return redirect(url_for('job_cards.view_job_card', id=job_card_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing outsourcing: {str(e)}', 'danger')
    
    return render_template('job_cards/outsourcing_workflow.html',
                         form=form,
                         job_card=job_card,
                         latest_report=latest_report,
                         available_quantity=available_quantity)

@job_cards_bp.route('/view/<int:id>')
@login_required
def view_job_card(id):
    """View job card details"""
    job_card = JobCard.query.get(id)
    if not job_card:
        # If job card doesn't exist, redirect to the first available one
        first_available = JobCard.query.order_by(JobCard.id.desc()).first()
        if first_available:
            flash(f'Job card {id} not found. Redirecting to latest job card.', 'info')
            return redirect(url_for('job_cards.view_job_card', id=first_available.id))
        else:
            flash('No job cards found in the system.', 'warning')
            return redirect(url_for('job_cards.dashboard'))
    
    # Get BOM processes for this job card
    routing_steps = []
    if job_card.bom_item_id:
        from models import BOMProcess
        bom_processes = BOMProcess.query.filter_by(
            bom_id=job_card.bom_item.bom_id if job_card.bom_item else None
        ).order_by(BOMProcess.step_number).all()
        
        routing_steps = [{
            'step': process.step_number,
            'process': process.process_name,
            'description': process.operation_description,
            'est_time': (process.setup_time_minutes or 0) + (process.run_time_minutes or 0),
            'status': 'pending',  # Default status
            'process_id': process.id
        } for process in bom_processes]
    
    # Get recent daily reports
    daily_reports = JobCardDailyStatus.query.filter_by(
        job_card_id=id
    ).order_by(JobCardDailyStatus.report_date.desc()).limit(7).all()
    
    # Get materials for this job card
    materials = JobCardMaterial.query.filter_by(job_card_id=id).all()
    
    return render_template('job_cards/job_card_detail.html',
                         job_card=job_card,
                         daily_reports=daily_reports,
                         daily_statuses=daily_reports,  # Template compatibility
                         materials=materials,
                         routing_steps=routing_steps)

@job_cards_bp.route('/list')
@login_required
def list_job_cards():
    """List all job cards with filtering"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    
    query = JobCard.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    if search:
        query = query.filter(
            or_(
                JobCard.job_card_number.contains(search),
                JobCard.process_name.contains(search)
            )
        )
    
    job_cards = query.order_by(JobCard.created_at.desc()).all()
    
    return render_template('job_cards/list.html', job_cards=job_cards)

@job_cards_bp.route('/production/<int:production_id>')
@login_required
def production_job_cards(production_id):
    """View all job cards for a production order"""
    production = Production.query.get_or_404(production_id)
    job_cards = JobCard.query.filter_by(production_id=production_id).order_by(JobCard.process_sequence).all()
    
    return render_template('job_cards/production_cards.html',
                         production=production,
                         job_cards=job_cards)

@job_cards_bp.route('/quick-update', methods=['POST'])
@login_required
def quick_update():
    """Quick status update via AJAX"""
    try:
        data = request.get_json()
        job_card_id = data.get('job_card_id')
        qty_completed = float(data.get('qty_completed', 0))
        status = data.get('status', 'active')
        notes = data.get('notes', '')
        
        job_card = JobCard.query.get_or_404(job_card_id)
        
        # Get today's report
        today_report = JobCardDailyStatus.get_today_report(job_card_id)
        cumulative_completed = (today_report.cumulative_completed if today_report else 0) + qty_completed
        
        # Update daily status
        JobCardDailyStatus.create_or_update_today(
            job_card_id=job_card_id,
            qty_completed_today=qty_completed,
            qty_good_today=qty_completed,  # Assume good unless specified
            cumulative_completed=cumulative_completed,
            cumulative_good=cumulative_completed,
            daily_status=status,
            operator_notes=notes,
            reported_by_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': f'Quick update applied to {job_card.job_card_number}',
            'completion_rate': job_card.completion_rate,
            'cumulative_completed': cumulative_completed
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500