from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_login import login_required, current_user
from models import db, Production, Item, BOM, BOMItem, Employee, Supplier
from models.job_card import JobCard, JobCardDailyStatus, JobCardMaterial
from forms_job_card import JobCardForm, JobCardDailyUpdateForm, BulkJobCardForm
from services.bom_inventory_flow import BOMInventoryFlow
from datetime import datetime, date, timedelta
from utils import generate_production_number
from sqlalchemy import func, or_
import logging
import json

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
    """Create a new job card with smart suggestions"""
    form = JobCardForm()
    
    # Populate dropdown choices
    form.item_id.choices = [(0, 'Select Item')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.all()]
    form.assigned_worker_id.choices = [(0, 'Select Worker')] + [(e.id, e.name) for e in Employee.query.all()]
    form.assigned_vendor_id.choices = [(0, 'Select Vendor')] + [(s.id, s.name) for s in Supplier.query.filter_by(partner_type='vendor').all()]
    
    production = None
    smart_suggestions = None
    
    # Handle query parameters from suggestions
    from_suggestion = request.args.get('from_suggestion', type=bool)
    bom_id = request.args.get('bom_id', type=int)
    target_item_id = request.args.get('target_item_id', type=int)
    suggestion_type = request.args.get('suggestion_type')
    
    if production_id:
        production = Production.query.get_or_404(production_id)
        form.production_id.data = production_id
        
        # If coming from suggestion, check if job card already exists for this item/BOM
        if from_suggestion and target_item_id:
            existing_job_card = JobCard.query.filter_by(
                production_id=production_id,
                item_id=target_item_id
            ).first()
            
            if existing_job_card:
                flash(f'Job card {existing_job_card.job_card_number} already exists for {existing_job_card.item.name}', 'info')
                return redirect(url_for('job_cards.view_job_card', id=existing_job_card.id))
        
        # If coming from suggestion, use target item instead of production item
        if from_suggestion and target_item_id:
            form.item_id.data = target_item_id
            target_item = Item.query.get(target_item_id)
            if target_item:
                # For BOM-based job cards, the target item is the PRODUCT to be manufactured
                if bom_id:
                    bom = BOM.query.get(bom_id)
                    if bom and bom.product_id == target_item_id:
                        # This is a job card to manufacture the BOM product
                        suggested_qty = bom.output_quantity or production.quantity_planned
                        form.planned_quantity.data = suggested_qty
                        production_item = Item.query.get(production.item_id)
                        production_item_name = production_item.name if production_item else "Unknown Item"
                        form.operation_description.data = f"Manufacturing {target_item.name} for {production_item_name}"
                        
                        # Set process name based on the product being manufactured
                        if 'plate' in target_item.name.lower():
                            form.process_name.data = "Cutting & Forming"
                        elif 'base' in target_item.name.lower():
                            form.process_name.data = "Base Assembly"
                        elif 'wheel' in target_item.name.lower() or 'caster' in target_item.name.lower():
                            form.process_name.data = "Wheel Assembly"
                        else:
                            form.process_name.data = f"Manufacturing - {target_item.name}"
                        
                        # Set process sequence
                        form.process_sequence.data = 1
                        
                        # Set default times
                        form.setup_time_minutes.data = 30
                        form.run_time_minutes.data = 60
        
        # Generate smart suggestions from production order and BOM
        from services.smart_job_card_suggestions import SmartJobCardSuggestions
        smart_suggestions = SmartJobCardSuggestions.generate_comprehensive_suggestions(production_id)
        
        # Auto-populate form with intelligent suggestions
        next_sequence = JobCard.query.filter_by(production_id=production_id).count() + 1
        form.job_card_number.data = JobCard.generate_job_card_number(production.production_number, next_sequence)
        
        # Smart population based on BOM analysis
        if not smart_suggestions.get('error'):
            # Pre-fill item details (only if not already set from suggestion)
            if not from_suggestion:
                form.item_id.data = production.item_id
                form.planned_quantity.data = production.quantity_planned
            form.target_completion_date.data = getattr(production, 'target_completion_date', None) or (datetime.now().date() + timedelta(days=7))
            form.priority.data = getattr(production, 'priority', 'medium')
            
            # Smart process suggestions from BOM processes
            if smart_suggestions.get('process_suggestions') and len(smart_suggestions['process_suggestions']) > 0:
                # Find the next process based on existing job cards for this production
                existing_job_cards = JobCard.query.filter_by(production_id=production_id).count()
                process_index = existing_job_cards  # Next process in sequence
                
                if process_index < len(smart_suggestions['process_suggestions']):
                    current_process = smart_suggestions['process_suggestions'][process_index]
                    form.process_name.data = current_process['process_name']
                    form.operation_description.data = current_process['operation_description']
                    form.process_sequence.data = current_process.get('step_number', process_index + 1)
                    form.setup_time_minutes.data = current_process.get('setup_time', 30)
                    form.run_time_minutes.data = current_process.get('run_time', 60)
                
                # Suggest worker based on skill requirements
                if smart_suggestions.get('resource_assignments') and len(smart_suggestions['resource_assignments']) > process_index:
                    assignment = smart_suggestions['resource_assignments'][process_index]
                    suggested_workers = assignment.get('suggested_workers', [])
                    if suggested_workers:
                        form.assigned_worker_id.data = suggested_workers[0]['worker_id']
            
            # Cost estimation
            if smart_suggestions.get('cost_estimates'):
                form.estimated_cost.data = smart_suggestions['cost_estimates']['total_estimated_cost']
            
            # Generate comprehensive production notes with all suggestions
            production_notes = SmartJobCardSuggestions._generate_production_notes(smart_suggestions)
            form.production_notes.data = production_notes
    
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
    
    return render_template('job_cards/create.html', 
                         form=form, 
                         production=production, 
                         smart_suggestions=smart_suggestions)

@job_cards_bp.route('/create-sub-bom-cards/<int:production_id>')
@login_required
def create_sub_bom_job_cards(production_id):
    """Create job cards for all sub-BOMs within a master BOM"""
    production = Production.query.get_or_404(production_id)
    
    if not production.bom:
        flash('Production order must have a BOM to create sub-BOM job cards', 'warning')
        return redirect(url_for('production.view_production', id=production_id))
    
    try:
        created_cards = []
        current_date = date.today()
        
        # Iterate through each component in the master BOM
        for master_sequence, bom_item in enumerate(production.bom.items, 1):
            # Check if this component has its own BOM (sub-BOM)
            sub_bom = BOM.query.filter_by(product_id=bom_item.item_id, is_active=True).first()
            
            if sub_bom:
                print(f"Creating job cards for sub-BOM: {sub_bom.bom_code} ({bom_item.item.name})")
                
                # Create single consolidated job card for all processes in sub-BOM
                planned_qty = production.quantity_planned * bom_item.quantity_required
                job_card_number = JobCard.generate_job_card_number(
                    f"{production.production_number}-{bom_item.item.code}", 
                    1
                )
                
                # Build comprehensive process description with all sub-BOM processes
                if hasattr(sub_bom, 'processes') and sub_bom.processes:
                    # Create detailed process sequence description
                    process_names = [proc.process_name for proc in sub_bom.processes]
                    process_sequence = " → ".join(process_names)
                    
                    # Calculate total time from all processes
                    total_setup_time = sum(proc.setup_time_minutes or 0 for proc in sub_bom.processes)
                    total_run_time = sum(proc.run_time_minutes or 0 for proc in sub_bom.processes)
                    
                    # Build detailed operation description
                    operation_details = f"Complete manufacturing of {bom_item.item.name} through all processes:\n"
                    for i, proc in enumerate(sub_bom.processes, 1):
                        operation_details += f"Step {i}: {proc.process_name}"
                        if proc.operation_description:
                            operation_details += f" - {proc.operation_description}"
                        operation_details += "\n"
                    operation_details += f"Sub-BOM Reference: {sub_bom.bom_code}"
                    
                    process_name_display = f"Multi-Process: {process_sequence}"
                else:
                    # Fallback for sub-BOM without defined processes
                    process_name_display = _generate_process_name_for_component(bom_item)
                    total_setup_time = 30
                    total_run_time = 60
                    operation_details = f"Complete manufacturing of {bom_item.item.name} as per sub-BOM {sub_bom.bom_code}"
                
                # Calculate target date
                target_date = current_date + timedelta(days=master_sequence)
                
                job_card = JobCard(
                    job_card_number=job_card_number,
                    production_id=production_id,
                    item_id=bom_item.item_id,  # The component being manufactured
                    bom_id=sub_bom.id,  # Reference to the sub-BOM
                    process_name=process_name_display,
                    process_sequence=master_sequence,
                    operation_description=operation_details,
                    planned_quantity=planned_qty,
                    setup_time_minutes=total_setup_time,
                    run_time_minutes=total_run_time,
                    target_completion_date=target_date,
                    priority='medium',
                    estimated_cost=planned_qty * (bom_item.unit_cost or 0),
                    production_notes=f"Consolidated job card for all {len(sub_bom.processes) if hasattr(sub_bom, 'processes') else 1} processes in {bom_item.item.name} manufacturing",
                    created_by_id=current_user.id
                )
                
                db.session.add(job_card)
                created_cards.append({
                    'job_card_number': job_card_number,
                    'component': bom_item.item.name,
                    'process': process_name_display,
                    'quantity': planned_qty,
                    'total_processes': len(sub_bom.processes) if hasattr(sub_bom, 'processes') and sub_bom.processes else 1
                })
        
        if created_cards:
            db.session.commit()
            
            # Create summary message
            summary = "Consolidated sub-BOM job cards created:\n"
            for card in created_cards:
                processes_info = f" ({card['total_processes']} processes)" if card.get('total_processes', 1) > 1 else ""
                summary += f"• {card['job_card_number']}: {card['component']} - {card['process']}{processes_info} ({card['quantity']} units)\n"
            
            flash(f'Successfully created {len(created_cards)} job cards for sub-BOMs', 'success')
            return redirect(url_for('job_cards.list_job_cards'))
        else:
            flash('No sub-BOMs found in this production order', 'info')
            return redirect(url_for('production.view_production', id=production_id))
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating sub-BOM job cards: {str(e)}', 'danger')
        return redirect(url_for('production.view_production', id=production_id))

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
    
    # Get BOM processes for this job card - look for component-specific BOM
    bom_processes = []
    grn_data = {}  # Store GRN data for outsourced processes
    
    if job_card.item_id:
        from models import BOMProcess, BOM
        from models.grn import GRN, GRNLineItem
        try:
            # Find the BOM that has this component as its product
            component_bom = BOM.query.filter_by(product_id=job_card.item_id, is_active=True).first()
            print(f"DEBUG: Looking for BOM for item {job_card.item_id} ({job_card.item.name if job_card.item else 'Unknown'})")
            
            if component_bom:
                print(f"DEBUG: Found component-specific BOM: {component_bom.bom_code} (ID: {component_bom.id})")
                bom_processes = BOMProcess.query.filter_by(bom_id=component_bom.id).order_by(BOMProcess.step_number).all()
                print(f"DEBUG: Found {len(bom_processes)} BOM processes for job card {job_card_id}, BOM ID: {component_bom.id}")
                
                # Check for GRN entries for outsourced processes related to this job card
                for bp in bom_processes:
                    print(f"  Process {bp.step_number}: {bp.process_name}")
                    if bp.is_outsourced and bp.vendor_id:
                        print(f"    Process is outsourced to vendor ID: {bp.vendor_id}")
                        
                        # Look for GRN entries that reference this job card number
                        # GRN line items should contain the job card's item with reference to this job card
                        grn_line_items = db.session.query(GRNLineItem).join(GRN).filter(
                            GRNLineItem.item_id == job_card.item_id,
                            db.or_(
                                GRN.remarks.like(f'%{job_card.job_card_number}%'),
                                GRN.delivery_note.like(f'%{job_card.job_card_number}%')
                            ),
                            GRN.status.in_(['received', 'inspected', 'completed'])
                        ).all()
                        
                        total_received = sum(item.quantity_received for item in grn_line_items)
                        if total_received > 0:
                            grn_data[bp.id] = {
                                'process_name': bp.process_name,
                                'vendor_name': bp.vendor.name if bp.vendor else 'Unknown',
                                'total_received': total_received,
                                'grn_count': len(grn_line_items),
                                'is_outsourced': True
                            }
                            print(f"    Found {total_received} pieces received via {len(grn_line_items)} GRN line item(s) for outsourced {bp.process_name}")
                        else:
                            # Mark as outsourced but no GRN received yet
                            grn_data[bp.id] = {
                                'process_name': bp.process_name,
                                'vendor_name': bp.vendor.name if bp.vendor else 'Unknown',
                                'total_received': 0,
                                'grn_count': 0,
                                'is_outsourced': True
                            }
            else:
                print(f"DEBUG: No component-specific BOM found for item {job_card.item_id}")
        except Exception as e:
            print(f"DEBUG: Error getting BOM processes: {e}")
    else:
        print(f"DEBUG: Job card {job_card_id} has no item_id")
    
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
            
            # Update job card completed quantity
            job_card.completed_quantity = cumulative_good
            
            # Check if job card should be marked as completed
            # (when good quantity meets or exceeds planned quantity)
            if cumulative_good >= job_card.planned_quantity:
                try:
                    # Process BOM inventory flow for completed job card
                    inventory_success, inventory_message = BOMInventoryFlow.update_inventory_on_job_card_completion(
                        job_card_id, cumulative_good
                    )
                    
                    if inventory_success:
                        flash(f'Job card {job_card.job_card_number} completed! Daily status updated and inventory processed. {inventory_message}', 'success')
                    else:
                        flash(f'Job card {job_card.job_card_number} completed! Daily status updated but inventory processing had issues: {inventory_message}', 'warning')
                        
                except Exception as e:
                    logging.error(f'Error processing inventory for completed job card {job_card_id}: {str(e)}')
                    flash(f'Job card {job_card.job_card_number} completed! Daily status updated but inventory processing failed: {str(e)}', 'warning')
            else:
                # Job card not yet complete
                flash(f'Daily status updated for job card {job_card.job_card_number}', 'success')
            
            return redirect(url_for('job_cards.view_job_card', id=job_card_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating daily status: {str(e)}', 'danger')
    
    from datetime import date
    return render_template('job_cards/update_daily_clean.html',
                         form=form,
                         job_card=job_card,
                         today_report=today_report,
                         bom_processes=bom_processes,
                         grn_data=grn_data,
                         today=date.today())


@job_cards_bp.route('/outsourcing-workflow/<int:job_card_id>', methods=['GET', 'POST'])
@job_cards_bp.route('/outsourcing-workflow/<int:job_card_id>/<report_id>', methods=['GET', 'POST'])
@login_required
def outsourcing_workflow(job_card_id, report_id=None):
    """Separate outsourcing workflow after progress report submission"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    # Import required models
    from models import Supplier, JobCardDailyStatus
    
    # Get specific report if report_id provided
    selected_report = None
    if report_id:
        selected_report = JobCardDailyStatus.query.filter_by(
            job_card_id=job_card_id, 
            report_number=report_id
        ).first()
    
    # Get available vendors
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
    latest_report = JobCardDailyStatus.get_today_report(job_card_id)
    available_quantity = selected_report.qty_good_today if selected_report else (latest_report.qty_good_today if latest_report else 0)
    
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
            
            # Create new job card for outsourced work instead of updating existing one
            outsourced_job_card = JobCard(
                job_card_number=f"OUTSOURCE-{job_card.job_card_number}-{len(JobCard.query.filter(JobCard.parent_job_card_id == job_card_id).all()) + 1}",
                production_id=job_card.production_id,
                item_id=job_card.item_id,
                bom_item_id=job_card.bom_item_id,
                planned_quantity=outsource_quantity,
                quantity_planned=outsource_quantity,
                outsource_quantity=outsource_quantity,
                assigned_vendor_id=vendor_id,
                outsource_notes=form.outsource_notes.data,
                status='outsourced',
                parent_job_card_id=job_card_id,
                created_from_report_id=selected_report.report_number if selected_report else None,
                process_name=form.selected_processes.data,
                target_completion_date=job_card.target_completion_date
            )
            db.session.add(outsourced_job_card)
            
            # Create tracking batch if requested
            if form.create_tracking_batch.data:
                from models import ItemBatch
                outsource_batch = ItemBatch(
                    item_id=job_card.item_id,
                    batch_number=f"OUTSOURCE-{job_card.job_card_number}-{vendor.name.upper()[:3]}",
                    qty_wip=outsource_quantity,
                    quality_notes=f"Sent to {vendor.name} for processing"
                )
                db.session.add(outsource_batch)
            
            db.session.commit()
            flash(f'Successfully created outsourced job card {outsourced_job_card.job_card_number} - {outsource_quantity} pieces sent to {vendor.name}', 'success')
            return redirect(url_for('job_cards.view_job_card', id=job_card_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing outsourcing: {str(e)}', 'danger')
    
    return render_template('job_cards/outsourcing_workflow.html',
                         form=form,
                         job_card=job_card,
                         vendors=vendors,
                         bom_processes=bom_processes,
                         latest_report=latest_report,
                         available_quantity=available_quantity,
                         selected_report=selected_report)

# Route completely removed to fix conflicts
# @job_cards_bp.route('/view/<int:id>')
# @login_required
def view_job_card_old_disabled(id):
    """View job card details"""
    print(f"DEBUG job_cards: Attempting to view job card ID: {id}")
    job_card = JobCard.query.get(id)
    print(f"DEBUG job_cards: Found job card: {job_card}")
    if not job_card:
        # If job card doesn't exist, redirect to the first available one
        first_available = JobCard.query.order_by(JobCard.id.desc()).first()
        if first_available:
            flash(f'Job card {id} not found. Redirecting to latest job card.', 'info')
            return redirect(url_for('job_card_management.view_job_card', job_card_id=first_available.id))
        else:
            flash('No job cards found in the system.', 'warning')
            return redirect(url_for('job_cards.dashboard'))
    
    # Get BOM processes for this job card - look for component-specific BOM
    routing_steps = []
    if job_card.item_id:
        from models import BOMProcess, BOM
        # Find the BOM that has this component as its product
        component_bom = BOM.query.filter_by(product_id=job_card.item_id, is_active=True).first()
        print(f"DEBUG: Looking for BOM for item {job_card.item_id} ({job_card.item.name if job_card.item else 'Unknown'})")
        
        if component_bom:
            print(f"DEBUG: Found component-specific BOM: {component_bom.bom_code} (ID: {component_bom.id})")
            bom_processes = BOMProcess.query.filter_by(
                bom_id=component_bom.id
            ).order_by(BOMProcess.step_number).all()
            
            print(f"DEBUG: Found {len(bom_processes)} BOM processes for job card {id}, BOM ID: {component_bom.id}")
            for process in bom_processes:
                print(f"  Process {process.id}: {process.process_name}")
            
            routing_steps = [{
                'step': process.step_number,
                'process': process.process_name,
                'description': process.operation_description or f'{process.process_name} operation',
                'est_time': (process.setup_time_minutes or 0) + (process.run_time_minutes or 0) or 60,
                'status': 'pending',  # Default status
                'process_id': process.id,
                'scrap_weight_per_unit': process.scrap_weight_per_unit or 0,
                'scrap_tracking_enabled': process.scrap_tracking_enabled or False,
                'input_unit_weight': process.input_unit_weight or 0,
                'input_material_source': process.input_material_source
            } for process in bom_processes]
        else:
            print(f"DEBUG: No component-specific BOM found for item {job_card.item_id}")
    
    # Get recent daily reports
    daily_reports = JobCardDailyStatus.query.filter_by(
        job_card_id=id
    ).order_by(JobCardDailyStatus.report_date.desc()).limit(7).all()
    
    # Get outsourced job cards created from this job card
    for report in daily_reports:
        report.outsourced_jobs = []
        if hasattr(report, 'report_number') and report.report_number:
            # Debug: Check for outsourced jobs
            outsourced_jobs = JobCard.query.filter(
                JobCard.parent_job_card_id == id,
                JobCard.created_from_report_id == report.report_number
            ).all()
            print(f"Debug: Found {len(outsourced_jobs)} outsourced jobs for report {report.report_number}")
            report.outsourced_jobs = outsourced_jobs
    
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
    """List all job cards with parent-child hierarchical structure"""
    # Get filter parameters
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    
    # Get all parent job cards (those without parent_job_card_id) with production order details
    parent_query = JobCard.query.filter(JobCard.parent_job_card_id.is_(None)).options(
        db.joinedload(JobCard.production),
        db.joinedload(JobCard.item),
        db.joinedload(JobCard.assigned_worker),
        db.joinedload(JobCard.assigned_vendor)
    )
    
    if status_filter:
        parent_query = parent_query.filter_by(status=status_filter)
    
    if search:
        parent_query = parent_query.filter(
            or_(
                JobCard.job_card_number.contains(search),
                JobCard.process_name.contains(search)
            )
        )
    
    parent_job_cards = parent_query.order_by(JobCard.created_at.desc()).all()
    
    # Build hierarchical structure for each parent
    hierarchical_data = []
    
    for parent_card in parent_job_cards:
        # Get child job cards for this parent with related data
        child_cards = JobCard.query.filter(
            JobCard.parent_job_card_id == parent_card.id
        ).options(
            db.joinedload(JobCard.production),
            db.joinedload(JobCard.item),
            db.joinedload(JobCard.assigned_worker),
            db.joinedload(JobCard.assigned_vendor)
        ).order_by(JobCard.process_sequence, JobCard.created_at).all()
        
        # Calculate parent-level aggregated metrics
        total_planned = parent_card.planned_quantity or 0
        total_completed = parent_card.completed_quantity or 0
        
        # Calculate child-level aggregated metrics
        child_planned = sum(child.planned_quantity or 0 for child in child_cards)
        child_completed = sum(child.completed_quantity or 0 for child in child_cards)
        
        # Overall progress calculation
        overall_planned = total_planned + child_planned
        overall_completed = total_completed + child_completed
        overall_progress = (overall_completed / overall_planned * 100) if overall_planned > 0 else 0
        
        # Status analysis
        child_statuses = [child.status for child in child_cards]
        outsourced_count = len([c for c in child_cards if c.job_card_number and '-OUT-' in c.job_card_number])
        pending_grn_count = len([c for c in child_cards if c.job_card_number and '-OUT-' in c.job_card_number and not c.grn_id])
        
        hierarchical_data.append({
            'parent': parent_card,
            'children': child_cards,
            'metrics': {
                'total_planned': overall_planned,
                'total_completed': overall_completed,
                'progress_percentage': overall_progress,
                'child_count': len(child_cards),
                'outsourced_count': outsourced_count,
                'pending_grn_count': pending_grn_count
            }
        })
    
    return render_template('job_cards/list.html', 
                         hierarchical_job_cards=hierarchical_data,
                         total_parents=len(parent_job_cards),
                         status_filter=status_filter,
                         search=search)

@job_cards_bp.route('/create-outsourced/<int:job_card_id>', methods=['POST'])
@login_required
def create_outsourced_job_card(job_card_id):
    """Create outsourced job card via AJAX"""
    try:
        job_card = JobCard.query.get_or_404(job_card_id)
        
        # Get form data
        vendor_id = request.form.get('vendorId')
        process_name = request.form.get('processName')
        outsource_quantity = float(request.form.get('outsourceQuantity', 0))
        work_instructions = request.form.get('workInstructions', '')
        special_requirements = request.form.get('specialRequirements', '')
        expected_delivery = request.form.get('expectedDelivery')
        
        if not vendor_id or not process_name or outsource_quantity <= 0:
            return jsonify({'success': False, 'message': 'Missing required fields'})
        
        vendor = Supplier.query.get_or_404(vendor_id)
        
        # Create outsourced job card
        outsourced_count = JobCard.query.filter_by(parent_job_card_id=job_card_id).count()
        outsourced_job_card = JobCard(
            job_card_number=f"{job_card.job_card_number}-OUT-{outsourced_count + 1}",
            production_id=job_card.production_id,
            item_id=job_card.item_id,
            process_name=process_name,
            planned_quantity=outsource_quantity,
            assigned_vendor_id=vendor_id,
            production_notes=work_instructions,
            quality_notes=special_requirements,
            job_type='outsourced',
            status='outsourced',
            parent_job_card_id=job_card_id,
            target_completion_date=datetime.strptime(expected_delivery, '%Y-%m-%d').date() if expected_delivery else None,
            created_by_id=current_user.id
        )
        
        db.session.add(outsourced_job_card)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Outsourced {outsource_quantity} units of {process_name} to {vendor.name}',
            'outsourced_job_card_id': outsourced_job_card.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@job_cards_bp.route('/start-process/<int:job_card_id>', methods=['POST'])
@login_required  
def start_process(job_card_id):
    """Start a process in-house"""
    try:
        job_card = JobCard.query.get_or_404(job_card_id)
        process_name = request.form.get('process_name')
        notes = request.form.get('notes', '')
        
        if not process_name:
            flash('Process name is required', 'error')
            return redirect(url_for('job_cards.view_job_card', id=job_card_id))
        
        # Update job card to start the process
        job_card.current_process_step = process_name
        job_card.status = 'in_progress'
        job_card.actual_start_date = datetime.utcnow()
        
        # Add to processes_completed if not already there
        if not job_card.processes_completed:
            job_card.processes_completed = ''
        
        # Create daily status entry for starting the process
        today_report = JobCardDailyStatus.get_today_report(job_card_id)
        if not today_report:
            today_report = JobCardDailyStatus(
                job_card_id=job_card_id,
                report_date=date.today(),
                shift='day',
                supervisor_id=current_user.id,
                notes=f'Started process: {process_name}. {notes}' if notes else f'Started process: {process_name}',
                created_by_id=current_user.id
            )
            db.session.add(today_report)
        else:
            today_report.notes = f'{today_report.notes or ""}\nStarted process: {process_name}. {notes}' if notes else f'{today_report.notes or ""}\nStarted process: {process_name}'
        
        db.session.commit()
        flash(f'Process "{process_name}" started successfully', 'success')
        return redirect(url_for('job_cards.view_job_card', id=job_card_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error starting process: {str(e)}', 'error')
        return redirect(url_for('job_cards.view_job_card', id=job_card_id))

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

@job_cards_bp.route('/generate-challan/<int:job_card_id>')
@login_required
def generate_challan(job_card_id):
    """Generate Job Card Challan PDF for Outsourced Job Cards"""
    job_card = JobCard.query.get_or_404(job_card_id)
    
    # Only allow challan generation for outsourced job cards
    if '-OUT-' not in job_card.job_card_number:
        flash('Challan can only be generated for outsourced job cards', 'error')
        return redirect(url_for('job_cards.view_job_card', id=job_card_id))
    
    # Get company settings for sender information
    try:
        from models import CompanySettings
        company_settings = CompanySettings.query.first()
    except:
        company_settings = None
    
    # Get job card materials for the challan
    materials = []
    try:
        materials = JobCardMaterial.query.filter_by(job_card_id=job_card_id).all()
        
        # If no JobCardMaterial, get actual raw materials from BOM or production order
        if not materials and job_card.item:
            # Use job card's planned quantity (for outsourced work)
            job_card_qty = job_card.planned_quantity or 1
            
            # Try to find BOM for raw materials using correct field name
            from models import BOM, BOMItem
            try:
                bom = BOM.query.filter_by(product_id=job_card.item.id).first()
                if bom:
                    bom_items = BOMItem.query.filter_by(bom_id=bom.id).all()
                    materials = []
                    for bom_item in bom_items:
                        # Calculate raw material needed based on BOM output quantity and job card qty
                        # BOM shows quantity per bom.output_quantity, scale for job_card_qty
                        bom_output_qty = bom.output_quantity or 1
                        exact_qty = (bom_item.quantity_required * job_card_qty) / bom_output_qty
                        
                        # Round up material quantity for outsourcing (always send extra)
                        import math
                        rounded_qty = math.ceil(exact_qty)
                        excess_qty = rounded_qty - exact_qty
                        
                        # Calculate how many extra pieces can be made with excess material
                        extra_pieces = int(excess_qty / (bom_item.quantity_required / bom_output_qty)) if (bom_item.quantity_required / bom_output_qty) > 0 else 0
                        
                        remarks = f'Material for {int(job_card_qty):,} {job_card.item.name}'
                        if excess_qty > 0:
                            if extra_pieces > 0:
                                remarks += f' (Excess: {excess_qty:.3f} - Can make {extra_pieces} extra pcs or return material)'
                            else:
                                remarks += f' (Excess: {excess_qty:.3f} - Return excess material)'
                            
                        materials.append({
                            'item': bom_item.item,
                            'quantity_required': rounded_qty,
                            'exact_quantity': exact_qty,
                            'excess_quantity': excess_qty,
                            'batch_number': 'TBD',
                            'remarks': remarks
                        })
                else:
                    # For cutting process, show raw materials (MS sheets)
                    if job_card.process_name and 'cut' in job_card.process_name.lower():
                        # Calculate sheets needed (assuming 50 plates per sheet)
                        plates_per_sheet = 50
                        exact_sheets = job_card_qty / plates_per_sheet
                        sheets_needed = math.ceil(exact_sheets)  # Always round up
                        excess_plates = (sheets_needed * plates_per_sheet) - job_card_qty
                        
                        remarks = f'MS sheets to cut {int(job_card_qty):,} {job_card.item.name} ({plates_per_sheet} plates/sheet)'
                        if excess_plates > 0:
                            remarks += f' - Excess: {int(excess_plates)} plates (Can make {int(excess_plates)} extra pcs or return material)'
                        
                        materials = [{
                            'item': None,
                            'item_name': 'MS Sheet (Raw Material)',
                            'quantity_required': sheets_needed,
                            'exact_quantity': exact_sheets,
                            'excess_quantity': excess_plates,
                            'batch_number': 'TBD',
                            'remarks': remarks
                        }]
                    else:
                        # For other processes, show the item being processed
                        materials = [{
                            'item': job_card.item,
                            'quantity_required': job_card_qty,
                            'batch_number': 'TBD',
                            'remarks': f'Material for {job_card.process_name or "Processing"}'
                        }]
            except Exception as bom_error:
                print(f"BOM lookup error: {bom_error}")
                # For cutting process, show MS sheets
                if job_card.process_name and 'cut' in job_card.process_name.lower():
                    plates_per_sheet = 50
                    exact_sheets = job_card_qty / plates_per_sheet
                    sheets_needed = math.ceil(exact_sheets)  # Always round up
                    excess_plates = (sheets_needed * plates_per_sheet) - job_card_qty
                    
                    remarks = f'MS sheets to cut {int(job_card_qty):,} {job_card.item.name} ({plates_per_sheet} plates/sheet)'
                    if excess_plates > 0:
                        remarks += f' - Excess: {int(excess_plates)} plates (Can make {int(excess_plates)} extra pcs or return material)'
                    
                    materials = [{
                        'item': None,
                        'item_name': 'MS Sheet (Raw Material)',
                        'quantity_required': sheets_needed,
                        'exact_quantity': exact_sheets,
                        'excess_quantity': excess_plates,
                        'batch_number': 'TBD',
                        'remarks': remarks
                    }]
                else:
                    materials = [{
                        'item': job_card.item,
                        'quantity_required': job_card_qty,
                        'batch_number': 'TBD',
                        'remarks': f'Material for {job_card.process_name or "Processing"}'
                    }]
    except Exception as e:
        print(f"Error getting materials: {e}")
        pass
    
    # Calculate expected scrap for this job card quantity
    scrap_info = None
    try:
        from models import BOM, BOMProcess
        if job_card.item:
            bom = BOM.query.filter_by(product_id=job_card.item.id).first()
            if bom:
                # Find scrap for this specific process
                process = BOMProcess.query.filter(
                    BOMProcess.bom_id == bom.id,
                    BOMProcess.process_name.ilike(f'%{job_card.process_name}%')
                ).first()
                
                if process and process.scrap_weight_per_unit and process.scrap_tracking_enabled:
                    total_scrap = process.scrap_weight_per_unit * (job_card.planned_quantity or 1)
                    scrap_percent = (process.scrap_weight_per_unit / process.input_unit_weight * 100) if process.input_unit_weight else 0
                    scrap_info = {
                        'weight_per_unit': process.scrap_weight_per_unit,
                        'total_weight': total_scrap,
                        'percentage': scrap_percent,
                        'tracking_enabled': process.scrap_tracking_enabled
                    }
    except Exception as e:
        print(f"Error calculating scrap: {e}")
    
    return render_template('job_cards/outsourced_challan.html', 
                         job_card=job_card, 
                         company_settings=company_settings,
                         materials=materials,
                         scrap_info=scrap_info,
                         current_date=datetime.now().date(),
                         current_datetime=datetime.now())