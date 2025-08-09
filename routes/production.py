from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from forms import ProductionForm, BOMForm, BOMItemForm, BOMProcessForm
from forms_daily_production import DailyProductionUpdateForm
from models import Production, Item, BOM, BOMItem, BOMProcess, Supplier, ItemBatch, ProductionBatch
from models.daily_production import DailyProductionStatus, DailyProductionSummary
from models.job_card import JobCard, JobCardDailyStatus, JobCardMaterial
from datetime import date
from services.process_integration import ProcessIntegrationService
from services.authentic_accounting_integration import AuthenticAccountingIntegration
from services.smart_bom_suggestions import SmartBOMSuggestionService
from app import db
from sqlalchemy import func, or_
from utils import generate_production_number
from services.job_card_generator import generate_job_cards_for_production
from utils.batch_tracking import BatchTracker
from datetime import datetime, timedelta, date
import json
from services.job_card_generator import generate_job_cards_for_production
from forms_daily_production import DailyProductionUpdateForm, QuickStatusUpdateForm

production_bp = Blueprint('production', __name__)

@production_bp.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    
    # Enhanced production statistics
    total_productions = Production.query.count()
    planned_productions = Production.query.filter_by(status='planned').count()
    in_progress_productions = Production.query.filter_by(status='in_progress').count()
    completed_productions = Production.query.filter_by(status='completed').count()
    
    # Daily Production Status Integration
    active_productions = Production.query.filter(
        Production.status.in_(['planned', 'in_progress'])
    ).all()
    
    # Get today's production status reports
    today_reports = DailyProductionStatus.query.filter_by(report_date=today).all()
    
    # Get or create today's summary
    daily_summary = DailyProductionSummary.generate_daily_summary(today)
    
    # Calculate daily metrics
    total_completed_today = sum(r.qty_completed_today for r in today_reports)
    total_good_today = sum(r.qty_good_today for r in today_reports)
    total_defective_today = sum(r.qty_defective_today for r in today_reports)
    efficiency_rate = (total_good_today / total_completed_today * 100) if total_completed_today > 0 else 0
    
    # Group reports by status
    status_groups = {
        'active': [r for r in today_reports if r.daily_status == 'active'],
        'planned': [r for r in today_reports if r.daily_status == 'planned'],
        'completed': [r for r in today_reports if r.daily_status == 'completed'],
        'delayed': [r for r in today_reports if r.daily_status == 'delayed'],
        'paused': [r for r in today_reports if r.daily_status == 'paused']
    }
    
    # Productions without daily reports (need initial entry)
    reported_production_ids = {r.production_id for r in today_reports}
    productions_without_reports = [
        prod for prod in active_productions 
        if prod.id not in reported_production_ids
    ]
    
    # Job Card Integration - get today's job card status
    today_job_card_reports = JobCardDailyStatus.query.filter_by(report_date=today).all()
    active_job_cards = JobCard.query.filter(
        JobCard.status.in_(['planned', 'in_progress']),
        JobCard.target_completion_date >= today
    ).limit(10).all()
    
    # Job card metrics
    total_job_cards_today = len(today_job_card_reports)
    job_cards_completed_today = len([r for r in today_job_card_reports if r.daily_status == 'completed'])
    job_cards_delayed_today = len([r for r in today_job_card_reports if r.daily_status == 'delayed'])
    job_cards_active_today = len([r for r in today_job_card_reports if r.daily_status == 'active'])
    
    # Calculate cost metrics from completed productions
    completed_prods = Production.query.filter_by(status='completed').all()
    avg_cost_per_unit = 0
    avg_material_cost = 0
    avg_labor_cost = 0
    avg_scrap_percent = 0
    avg_efficiency = 0  # Will calculate from real data
    
    if completed_prods:
        total_cost = 0
        total_material_cost = 0
        total_labor_cost = 0
        total_scrap = 0
        total_units = 0
        
        for prod in completed_prods:
            if prod.bom:
                # Calculate unit costs from BOM
                bom_material_cost = sum(
                    (getattr(item.item, 'cost_price', None) or getattr(item.item, 'purchase_price', 0)) * item.quantity_required 
                    for item in prod.bom.items 
                    if item.item and (getattr(item.item, 'cost_price', None) or getattr(item.item, 'purchase_price', None))
                ) or 0
                bom_labor_cost = getattr(prod.bom, 'labor_cost_per_unit', 0) or 0
                scrap_percent = getattr(prod.bom, 'scrap_percent', 0) or 0
                
                units = prod.quantity_produced or 1
                total_cost += (bom_material_cost + bom_labor_cost) * units
                total_material_cost += bom_material_cost * units
                total_labor_cost += bom_labor_cost * units
                total_scrap += scrap_percent
                total_units += units
        
        if total_units > 0:
            avg_cost_per_unit = total_cost / total_units
            avg_material_cost = total_material_cost / total_units
            avg_labor_cost = total_labor_cost / total_units
        
        if completed_prods:
            avg_scrap_percent = total_scrap / len(completed_prods)
            avg_efficiency = max(0, 100 - avg_scrap_percent)  # Real calculation without hardcoded minimum
    
    stats = {
        'total_productions': total_productions,
        'planned_productions': planned_productions,
        'in_progress_productions': in_progress_productions,
        'completed_productions': completed_productions,
        'total_boms': BOM.query.filter_by(is_active=True).count(),
        'avg_cost_per_unit': avg_cost_per_unit,
        'avg_material_cost': avg_material_cost,
        'avg_labor_cost': avg_labor_cost,
        'avg_scrap_percent': avg_scrap_percent,
        'avg_efficiency': avg_efficiency,
        # Daily production metrics
        'total_completed_today': total_completed_today,
        'total_good_today': total_good_today,
        'total_defective_today': total_defective_today,
        'efficiency_rate_today': efficiency_rate,
        # Job card metrics
        'total_job_cards_today': total_job_cards_today,
        'job_cards_completed_today': job_cards_completed_today,
        'job_cards_delayed_today': job_cards_delayed_today,
        'job_cards_active_today': job_cards_active_today
    }
    
    # Recent productions with item data loaded
    recent_productions = Production.query.join(Item).order_by(Production.created_at.desc()).limit(10).all()
    
    # Today's production summary - get active productions with proper item loading
    today_productions = Production.query.join(Item).filter(
        Production.status.in_(['planned', 'in_progress'])
    ).all()
    
    # Products with BOM
    products_with_bom = db.session.query(Item).join(BOM).filter(BOM.is_active == True).all()
    
    return render_template('production/dashboard.html', 
                         stats=stats, 
                         recent_productions=recent_productions,
                         active_productions=active_productions,
                         today_productions=today_productions,
                         products_with_bom=products_with_bom,
                         # Daily production status data
                         today=today,
                         today_reports=today_reports,
                         daily_summary=daily_summary,
                         status_groups=status_groups,
                         productions_without_reports=productions_without_reports,
                         # Job card data
                         today_job_card_reports=today_job_card_reports,
                         active_job_cards=active_job_cards)

@production_bp.route('/update-daily-status/<int:production_id>', methods=['GET', 'POST'])
@login_required
def update_daily_status(production_id):
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
            return redirect(url_for('production.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating production status: {str(e)}', 'danger')
    
    # Get production item for display
    item = Item.query.get(production.item_id) if production.item_id else None
    
    return render_template('production/update_daily_status.html',
                         form=form,
                         production=production,
                         item=item,
                         today_report=today_report,
                         today=date.today(),
                         title=f'Update Daily Status - {production.production_number}')

@production_bp.route('/quick-daily-update', methods=['POST'])
@login_required 
def quick_daily_update():
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

@production_bp.route('/list')
@login_required
def list_productions():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '', type=str)
    
    query = Production.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    productions = query.order_by(Production.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    return render_template('production/list.html', productions=productions, status_filter=status_filter)

# Enhanced Batch Tracking API Endpoints for Production

@production_bp.route('/api/production/<int:production_id>/available-batches')
@login_required
def api_get_available_batches_for_production(production_id):
    """Get available material batches for a production order"""
    try:
        production = Production.query.get_or_404(production_id)
        bom = production.bom
        
        if not bom:
            return jsonify({'success': False, 'message': 'No BOM associated with this production'})
        
        # Get all BOM materials and their available batches
        materials_with_batches = []
        for bom_item in bom.items:
            material = bom_item.material
            if material.batch_required:
                # Get available batches for this material
                available_batches = ItemBatch.query.filter(
                    ItemBatch.item_id == material.id,
                    ItemBatch.qty_raw > 0
                ).order_by(ItemBatch.manufacture_date).all()
                
                batch_data = []
                for batch in available_batches:
                    batch_data.append({
                        'batch_id': batch.id,
                        'batch_number': batch.batch_number,
                        'available_qty': batch.qty_raw,
                        'unit_of_measure': material.unit_of_measure,
                        'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
                        'quality_status': batch.quality_status,
                        'storage_location': batch.storage_location
                    })
                
                materials_with_batches.append({
                    'material_id': material.id,
                    'material_name': material.name,
                    'material_code': material.code,
                    'required_qty': bom_item.quantity_required * production.quantity_planned,
                    'unit_of_measure': material.unit_of_measure,
                    'available_batches': batch_data
                })
        
        return jsonify({
            'success': True,
            'production_number': production.production_number,
            'materials': materials_with_batches
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@production_bp.route('/api/production/<int:production_id>/issue-materials', methods=['POST'])
@login_required
def api_issue_materials_for_production(production_id):
    """Issue materials from specific batches for production"""
    try:
        production = Production.query.get_or_404(production_id)
        data = request.json
        batch_selections = data.get('batch_selections', [])
        
        # Validate and process each batch selection
        for selection in batch_selections:
            batch_id = selection.get('batch_id')
            quantity_to_issue = selection.get('quantity')
            bom_item_id = selection.get('bom_item_id')
            
            batch = ItemBatch.query.get(batch_id)
            if not batch:
                return jsonify({'success': False, 'message': f'Batch {batch_id} not found'})
            
            if batch.qty_raw < quantity_to_issue:
                return jsonify({'success': False, 'message': f'Insufficient quantity in batch {batch.batch_number}'})
            
            # Create production batch record
            production_batch = ProductionBatch(
                production_id=production_id,
                material_batch_id=batch_id,
                quantity_consumed=quantity_to_issue,
                quantity_remaining=batch.qty_raw - quantity_to_issue,
                bom_item_id=bom_item_id,
                notes=f"Issued for production {production.production_number}"
            )
            
            # Update batch inventory - move from raw to WIP
            success = batch.issue_to_production(quantity_to_issue, production.production_number)
            if not success:
                return jsonify({'success': False, 'message': f'Failed to issue from batch {batch.batch_number}'})
            
            db.session.add(production_batch)
        
        # Update production status
        production.status = 'in_progress'
        production.batch_tracking_enabled = True
        production.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Materials issued successfully for production {production.production_number}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@production_bp.route('/api/production/<int:production_id>/complete-production', methods=['POST'])
@login_required
def api_complete_production(production_id):
    """Complete production and create output batches"""
    try:
        production = Production.query.get_or_404(production_id)
        data = request.json
        
        quantity_good = data.get('quantity_good', 0)
        quantity_damaged = data.get('quantity_damaged', 0)
        scrap_quantity = data.get('scrap_quantity', 0)
        quality_control_passed = data.get('quality_control_passed', False)
        
        # Update production quantities
        production.quantity_produced = quantity_good + quantity_damaged
        production.quantity_good = quantity_good
        production.quantity_damaged = quantity_damaged
        production.scrap_quantity = scrap_quantity
        production.quality_control_passed = quality_control_passed
        production.status = 'completed'
        production.updated_at = datetime.utcnow()
        
        # Create output batch if batch tracking is enabled
        if production.batch_tracking_enabled and quantity_good > 0:
            output_batch = production.create_output_batch()
            if output_batch:
                # Create batch movement record
                BatchTracker.record_batch_movement(
                    batch_id=output_batch.id,
                    from_state=None,
                    to_state='Finished',
                    quantity=quantity_good,
                    ref_type='PRODUCTION',
                    ref_id=production_id,
                    ref_number=production.production_number,
                    notes=f"Production completed - {production.production_number}"
                )
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Production {production.production_number} completed successfully',
            'output_batch_id': production.output_batch_id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@production_bp.route('/api/production/<int:production_id>/batch-consumption')
@login_required
def api_get_production_batch_consumption(production_id):
    """Get batch consumption details for a production"""
    try:
        production = Production.query.get_or_404(production_id)
        production_batches = ProductionBatch.query.filter_by(production_id=production_id).all()
        
        consumption_data = []
        for pb in production_batches:
            consumption_data.append({
                'material_name': pb.material_name,
                'batch_number': pb.batch_number,
                'quantity_consumed': pb.quantity_consumed,
                'consumption_date': pb.consumption_date.isoformat(),
                'bom_item_name': pb.bom_item.material.name if pb.bom_item else 'Unknown',
                'notes': pb.notes
            })
        
        return jsonify({
            'success': True,
            'production_number': production.production_number,
            'batch_consumption': consumption_data,
            'output_batch_number': production.output_batch.batch_number if production.output_batch else None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@production_bp.route('/view/<int:production_id>')
@login_required
def view(production_id):
    """View production details"""
    production = Production.query.get_or_404(production_id)
    
    # Get the item being produced
    item = Item.query.get(production.item_id) if production.item_id else None
    
    # Get production batches and related data
    batches = ProductionBatch.query.filter_by(production_id=production_id).all()
    
    # Get BOM items if available
    bom_items = []
    if production.bom_id:
        bom = BOM.query.get(production.bom_id)
        if bom:
            bom_items = bom.items
    
    return render_template('production/view.html', 
                         production=production,
                         item=item,
                         batches=batches,
                         bom_items=bom_items,
                         title=f'Production {production.production_number}')

@production_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_production():
    form = ProductionForm()
    # Show all items for production - user can produce any item
    form.item_id.choices = [(0, 'Select Item')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.order_by(Item.name).all()]
    
    # Auto-generate production number if not provided
    if not form.production_number.data:
        form.production_number.data = generate_production_number()
    
    # Debug: check form validation
    if request.method == 'POST':
        if not form.validate():
            print("Form validation failed:")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
            # Also show validation errors to user
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Validation Error in {field}: {error}", 'danger')
    
    if form.validate_on_submit():
        print("Form validation passed, proceeding with production creation")
        print(f"Form data: production_number={form.production_number.data}, item_id={form.item_id.data}, quantity={form.quantity_planned.data}")
        print(f"Current user: {current_user}, User ID: {current_user.id if current_user and current_user.is_authenticated else 'Not authenticated'}")
        # Check if production number already exists
        existing_production = Production.query.filter_by(production_number=form.production_number.data).first()
        print(f"Existing production check: {existing_production}")
        if existing_production:
            flash('Production number already exists', 'danger')
            return render_template('production/form.html', form=form, title='Add Production')
        
        # Get the BOM for the selected item
        print(f"Getting BOM for item ID: {form.item_id.data}")
        selected_item = Item.query.get(form.item_id.data)
        print(f"Selected item: {selected_item}")
        active_bom = BOM.query.filter_by(product_id=form.item_id.data, is_active=True).first()
        print(f"Active BOM: {active_bom}")
        
        material_shortages = []
        bom_items = []
        
        if active_bom:
            print(f"Processing BOM items for BOM ID: {active_bom.id}")
            bom_items = BOMItem.query.filter_by(bom_id=active_bom.id).all()
            print(f"Found {len(bom_items)} BOM items")
            
            # Link the BOM to production order
            production_bom_id = active_bom.id
            
            # Check material availability for each BOM item using multi-state inventory
            print("Starting BOM item availability check")
            for i, bom_item in enumerate(bom_items):
                print(f"Processing BOM item {i+1}/{len(bom_items)}: {bom_item}")
                # Calculate material requirement based on BOM output quantity
                # BOM shows: 1 Ms sheet → 400 Mounted Plates
                # If producing 10,000 plates, need: 10,000 ÷ 400 = 25 Ms sheets
                try:
                    print(f"  Calculating requirements for BOM item")
                    material_qty_per_output = bom_item.quantity_required or bom_item.qty_required
                    bom_output_qty = active_bom.output_quantity or 1.0  # Default to 1 if not set
                    
                    # Calculate actual material needed: (planned_qty / bom_output_qty) * material_qty_per_output
                    required_qty = (form.quantity_planned.data / bom_output_qty) * material_qty_per_output
                    print(f"  Required qty: {required_qty}, Material qty per output: {material_qty_per_output}, BOM output qty: {bom_output_qty}")
                except Exception as e:
                    print(f"  Error calculating requirements: {e}")
                    continue
                
                # Check available quantity from multi-state inventory (Raw + Finished for materials)
                item = bom_item.item
                available_qty = 0
                
                # For materials, use raw + finished quantities
                if hasattr(item, 'qty_raw') and hasattr(item, 'qty_finished'):
                    available_qty = (item.qty_raw or 0) + (item.qty_finished or 0)
                else:
                    # Fallback to current_stock if multi-state not available
                    available_qty = item.current_stock or 0
                
                # Also check batch-level availability
                from models.batch import InventoryBatch
                batch_qty = db.session.query(
                    func.sum(InventoryBatch.qty_raw + InventoryBatch.qty_finished)
                ).filter_by(item_id=item.id).scalar() or 0
                
                # Use the higher of the two (item-level or batch-level)
                available_qty = max(available_qty, batch_qty)
                print(f"  Available qty: {available_qty}, Required qty: {required_qty}")
                
                if available_qty < required_qty:
                    shortage_qty = required_qty - available_qty
                    material_shortages.append({
                        'item_code': bom_item.item.code,
                        'item_name': bom_item.item.name,
                        'required_qty': required_qty,
                        'available_qty': available_qty,
                        'shortage_qty': shortage_qty,
                        'unit': bom_item.item.unit_of_measure
                    })
        
        # Get smart suggestions but don't block the save process
        smart_suggestions = []
        smart_analysis = {}
        if material_shortages and active_bom:
            try:
                print("Getting smart BOM suggestions (non-blocking)")
                from services.smart_bom_suggestions import SmartBOMSuggestionService
                smart_analysis = SmartBOMSuggestionService.analyze_material_shortages_with_suggestions(
                    active_bom, form.quantity_planned.data
                )
                smart_suggestions = smart_analysis.get('suggestions', [])
                print(f"Generated {len(smart_suggestions)} smart suggestions")
            except Exception as e:
                print(f"Smart suggestions failed (non-blocking): {e}")
                smart_suggestions = []
                smart_analysis = {}
        
        print(f"BOM processing complete. Material shortages: {len(material_shortages)}")
        print("Creating production order directly (simple mode)")
        
        print("Entering try block for production creation")
        try:
            # Create new Production instance
            print("Creating Production instance")
            production = Production()
            production.production_number = form.production_number.data
            production.item_id = form.item_id.data
            production.quantity_planned = form.quantity_planned.data
            production.planned_uom = form.planned_uom.data
            production.quantity_produced = form.quantity_produced.data or 0.0
            production.quantity_good = form.quantity_good.data or 0.0
            production.quantity_damaged = form.quantity_damaged.data or 0.0
            production.scrap_quantity = form.scrap_quantity.data or 0.0
            production.production_date = form.production_date.data
            production.status = form.status.data
            production.notes = form.notes.data
            production.bom_id = active_bom.id if active_bom else None
            production.batch_tracking_enabled = True  # Enable batch tracking by default
            production.created_by = current_user.id
            
            print(f"About to save production: {production.production_number}")
            db.session.add(production)
            db.session.flush()  # Flush to get the production ID
            print("Production flushed successfully")
            
            # Commit the production order first (separate from job card generation)
            db.session.commit()
            print("Production order saved successfully")
            
            # Job cards will be generated separately via smart suggestions or manual creation
            job_card_count = 0
            
            # Add smart suggestions info to flash message if available
            flash_message = 'Production order created successfully!'
            if job_card_count > 0:
                flash_message += f' Generated {job_card_count} job cards automatically.'
            if material_shortages:
                flash_message += f' Note: {len(material_shortages)} materials need procurement.'
            if smart_suggestions:
                flash_message += f' {len(smart_suggestions)} smart suggestions available.'
            
            flash(flash_message, 'success')
            
            # Redirect to job cards view if any were generated, otherwise to production list
            if job_card_count > 0:
                return redirect(url_for('job_card_management.view_production_job_cards', production_id=production.id))
            else:
                return redirect(url_for('production.list_productions'))
        except Exception as e:
            print(f"Error saving production: {str(e)}")
            db.session.rollback()
            flash(f'Error creating production order: {str(e)}', 'danger')
            return render_template('production/form.html', 
                                 form=form, 
                                 title='Add Production')
    
    # Get BOM items for display if an item is selected (including from URL parameters)
    bom_items = []
    selected_item = None
    
    # Check for item_id in URL parameters (for direct BOM loading)
    item_id_param = request.args.get('item_id')
    if item_id_param and not form.item_id.data:
        try:
            form.item_id.data = int(item_id_param)
        except (ValueError, TypeError):
            pass
    
    if form.item_id.data and form.item_id.data != 0:
        selected_item = Item.query.get(form.item_id.data)
        active_bom = BOM.query.filter_by(product_id=form.item_id.data, is_active=True).first()
        if active_bom:
            bom_items = BOMItem.query.filter_by(bom_id=active_bom.id).all()
    
    return render_template('production/form.html', 
                         form=form, 
                         title='Add Production',
                         bom_items=bom_items,
                         selected_item=selected_item)

@production_bp.route('/suggestions/<int:production_id>')
@login_required
def view_smart_suggestions(production_id):
    """View smart BOM suggestions for a production order"""
    production = Production.query.get_or_404(production_id)
    
    smart_suggestions = []
    smart_analysis = {}
    
    if production.bom_id:
        try:
            from services.smart_bom_suggestions import SmartBOMSuggestionService
            bom = BOM.query.get(production.bom_id)
            if bom:
                smart_analysis = SmartBOMSuggestionService.analyze_material_shortages_with_suggestions(
                    bom, production.quantity_planned
                )
                smart_suggestions = smart_analysis.get('suggestions', [])
        except Exception as e:
            flash(f'Error generating suggestions: {str(e)}', 'warning')
    
    return render_template('production/suggestions.html',
                         production=production,
                         smart_suggestions=smart_suggestions,
                         smart_analysis=smart_analysis,
                         title=f'Smart Suggestions - {production.production_number}')

@production_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_production(id):
    production = Production.query.get_or_404(id)
    form = ProductionForm(obj=production)
    form.item_id.choices = [(0, 'Select Item')] + [(i.id, f"{i.code} - {i.name}") for i in Item.query.order_by(Item.name).all()]
    
    if form.validate_on_submit():
        # Check if production number already exists (excluding current production)
        existing_production = Production.query.filter(
            Production.production_number == form.production_number.data, 
            Production.id != id
        ).first()
        if existing_production:
            flash('Production number already exists', 'danger')
            return render_template('production/form.html', form=form, title='Edit Production', production=production)
        
        production.production_number = form.production_number.data
        production.item_id = form.item_id.data
        production.quantity_planned = form.quantity_planned.data
        production.production_date = form.production_date.data
        production.notes = form.notes.data
        
        db.session.commit()
        flash('Production order updated successfully', 'success')
        return redirect(url_for('production.list_productions'))
    
    # Get BOM for the product if available
    bom = BOM.query.filter_by(product_id=production.item_id, is_active=True).first()
    bom_items = []
    if bom:
        bom_items = BOMItem.query.filter_by(bom_id=bom.id).all()
    
    return render_template('production/form.html', 
                         form=form, 
                         title='Edit Production', 
                         production=production,
                         bom_items=bom_items)

@production_bp.route('/update_status/<int:id>/<status>')
@login_required
def update_status(id, status):
    production = Production.query.get_or_404(id)
    if status in ['planned', 'in_progress', 'completed', 'cancelled']:
        production.status = status
        db.session.commit()
        flash(f'Production status updated to {status}', 'success')
    else:
        flash('Invalid status', 'danger')
    
    return redirect(url_for('production.list_productions'))

@production_bp.route('/cancel/<int:id>')
@login_required
def cancel_production(id):
    """Cancel a production order"""
    try:
        production = Production.query.get_or_404(id)
        
        # Only allow cancellation if production is not completed
        if production.status == 'completed':
            flash('Cannot cancel a completed production order', 'danger')
            return redirect(url_for('production.list_productions'))
        
        # Update status to cancelled
        production.status = 'cancelled'
        
        # Add cancellation note with timestamp
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cancellation_note = f"\n[CANCELLED on {current_time} by {current_user.username}]"
        production.notes = (production.notes or '') + cancellation_note
        
        db.session.commit()
        flash(f'Production order {production.production_number} has been cancelled successfully', 'warning')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling production: {str(e)}', 'danger')
    
    return redirect(url_for('production.list_productions'))

@production_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_production(id):
    """Delete a production order and all related data"""
    try:
        production = Production.query.get_or_404(id)
        production_number = production.production_number
        
        # Only allow deletion if production is planned or cancelled
        if production.status in ['in_progress', 'completed']:
            flash('Cannot delete a production order that is in progress or completed', 'danger')
            return redirect(url_for('production.list_productions'))
        
        # Delete related job cards and their daily status records
        job_cards = JobCard.query.filter_by(production_id=id).all()
        for job_card in job_cards:
            # Delete daily status records
            JobCardDailyStatus.query.filter_by(job_card_id=job_card.id).delete()
            # Delete job card materials
            JobCardMaterial.query.filter_by(job_card_id=job_card.id).delete()
        
        # Delete job cards
        JobCard.query.filter_by(production_id=id).delete()
        
        # Delete daily production status records
        DailyProductionStatus.query.filter_by(production_id=id).delete()
        
        # Delete production batches
        ProductionBatch.query.filter_by(production_id=id).delete()
        
        # Delete the production order itself
        db.session.delete(production)
        db.session.commit()
        
        flash(f'Production order {production_number} and all related data deleted successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting production: {str(e)}', 'danger')
    
    return redirect(url_for('production.list_productions'))

@production_bp.route('/bom')
@login_required
def list_bom():
    page = request.args.get('page', 1, type=int)
    boms = BOM.query.filter_by(is_active=True).paginate(
        page=page, per_page=20, error_out=False)
    
    return render_template('production/bom_list.html', boms=boms)

@production_bp.route('/bom/tree-view')
@login_required
def bom_tree_view():
    """Display BOMs in hierarchical tree structure"""
    # Get all top-level BOMs (those without parent)
    top_level_boms = BOM.query.filter_by(is_active=True, parent_bom_id=None).order_by(BOM.product_id).all()
    
    def build_bom_tree(bom):
        """Recursively build BOM tree structure"""
        tree_node = {
            'bom': bom,
            'product': bom.product,
            'materials': [],
            'sub_boms': []
        }
        
        # Add direct materials and check for intermediate BOMs
        for bom_item in bom.items:
            # Handle both new and legacy field mappings
            material_item = getattr(bom_item, 'material', None) or getattr(bom_item, 'item', None)
            if material_item:
                # Get quantity from either new or legacy field
                quantity = bom_item.qty_required or getattr(bom_item, 'quantity_required', 0) or 0
                
                # Get unit from UOM relationship or legacy unit field
                try:
                    unit = bom_item.uom.symbol if bom_item.uom else (bom_item.unit or 'pcs')
                except AttributeError:
                    unit = bom_item.unit or 'pcs'
                
                material_entry = {
                    'item': material_item,
                    'quantity': quantity,
                    'unit': unit,
                    'cost': bom_item.unit_cost or 0,
                    'sub_materials': []  # For materials that have their own BOM
                }
                
                # Check if this material has its own BOM (intermediate product)
                material_bom = BOM.query.filter_by(product_id=material_item.id, is_active=True).first()
                if material_bom:
                    # This material is an intermediate product - recursively get its materials
                    material_tree = build_bom_tree(material_bom)
                    material_entry['intermediate_bom'] = material_tree
                    material_entry['is_intermediate'] = True
                else:
                    material_entry['is_intermediate'] = False
                
                tree_node['materials'].append(material_entry)
        
        # Add sub-BOMs (child BOMs that have this BOM as parent)
        child_boms = BOM.query.filter_by(parent_bom_id=bom.id, is_active=True).all()
        for child_bom in child_boms:
            tree_node['sub_boms'].append(build_bom_tree(child_bom))
        
        return tree_node
    
    # Build tree structure for all top-level BOMs
    bom_trees = []
    for bom in top_level_boms:
        bom_trees.append(build_bom_tree(bom))
    
    return render_template('production/bom_tree_view.html', bom_trees=bom_trees)

@production_bp.route('/bom/add', methods=['GET', 'POST'])
@login_required
def add_bom():
    form = BOMForm()
    # Allow any product type for BOM creation - no restrictions
    form.product_id.choices = [(i.id, f"{i.code} - {i.name}") for i in Item.query.order_by(Item.name).all()]
    
    if form.validate_on_submit():
        # Auto-generate BOM code if not provided BEFORE validation checks
        bom_code = form.bom_code.data
        if not bom_code or not bom_code.strip():
            # Auto-generate BOM code: BOM-YYYY-####
            year = datetime.now().year
            last_bom = BOM.query.filter(
                BOM.bom_code.like(f'BOM-{year}-%')
            ).order_by(BOM.bom_code.desc()).first()
            
            if last_bom:
                # Extract the number from the last BOM code
                try:
                    last_number = int(last_bom.bom_code.split('-')[-1])
                    new_number = last_number + 1
                except:
                    new_number = 1
            else:
                new_number = 1
            
            bom_code = f'BOM-{year}-{new_number:04d}'
            form.bom_code.data = bom_code  # Set it back to the form
        else:
            bom_code = form.bom_code.data
        
        # Check if BOM code already exists
        existing_bom_code = BOM.query.filter_by(bom_code=bom_code).first()
        if existing_bom_code:
            flash('BOM code already exists. Please use a unique code.', 'warning')
            # Get UOM choices for error case
            try:
                from models.uom import UnitOfMeasure
                uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
                uom_choices = [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
            except Exception:
                uom_choices = [('pcs', 'Pieces (pcs)'), ('kg', 'Kilograms (kg)'), ('g', 'Grams (g)')]
            return render_template('production/bom_form.html', form=form, title='Add BOM', uom_choices=uom_choices)
        
        # Check if active BOM already exists for this product
        existing_bom = BOM.query.filter_by(product_id=form.product_id.data, is_active=True).first()
        if existing_bom and form.status.data == 'active':
            flash('An active BOM already exists for this product. Please deactivate the existing BOM first.', 'warning')
            # Get UOM choices for error case
            try:
                from models.uom import UnitOfMeasure
                uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
                uom_choices = [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
            except Exception:
                uom_choices = [('pcs', 'Pieces (pcs)'), ('kg', 'Kilograms (kg)'), ('g', 'Grams (g)')]
            return render_template('production/bom_form.html', form=form, title='Add BOM', uom_choices=uom_choices)
        
        # Use the already generated or provided BOM code
        # (BOM code was generated/validated above)

        bom = BOM(
            bom_code=bom_code,
            product_id=form.product_id.data,
            output_uom_id=form.output_uom_id.data if form.output_uom_id.data != 0 else None,
            version=form.version.data or '1.0',
            status=form.status.data or 'active',
            is_active=form.is_active.data and (form.status.data == 'active' if form.status.data else True),
            output_quantity=form.output_quantity.data or 1.0,
            unit_weight=form.unit_weight.data or 0.0,
            unit_weight_uom=form.unit_weight_uom.data or 'kg',
            estimated_scrap_percent=form.estimated_scrap_percent.data or 0.0,
            scrap_quantity=form.scrap_quantity.data or 0.0,
            scrap_uom=form.scrap_uom.data or 'kg',
            scrap_value_recovery_percent=form.scrap_value_recovery_percent.data or 15.0,
            description=form.description.data,
            remarks=form.remarks.data,
            labor_cost_per_unit=form.labor_cost_per_unit.data or 0.0,
            labor_hours_per_unit=form.labor_hours_per_unit.data or 0.0,
            labor_rate_per_hour=form.labor_rate_per_hour.data or 0.0,
            overhead_cost_per_unit=form.overhead_cost_per_unit.data or 0.0,
            overhead_percentage=form.overhead_percentage.data or 0.0,
            freight_cost_per_unit=form.freight_cost_per_unit.data or 0.0,
            freight_unit_type=form.freight_unit_type.data or 'per_piece',
            markup_percentage=form.markup_percentage.data or 0.0,
            # Multi-level BOM fields
            parent_bom_id=form.parent_bom_id.data if form.parent_bom_id.data != 0 else None,
            bom_level=form.bom_level.data or 0,
            is_phantom_bom=form.is_phantom_bom.data,
            intermediate_product=form.intermediate_product.data,
            created_by=current_user.id
        )
        db.session.add(bom)
        db.session.flush()  # Get the BOM ID
        
        # Create accounting cost allocation entry
        try:
            from services.accounting_automation import AccountingAutomation
            AccountingAutomation.create_bom_cost_allocation_entry(bom)
        except Exception as e:
            print(f"Warning: Failed to create BOM accounting entry: {str(e)}")
        
        db.session.commit()
        flash('Advanced BOM created successfully with cost accounting entries!', 'success')
        
        # Check which action was clicked
        action = request.form.get('action', 'save_and_continue')
        if action == 'save_and_close':
            return redirect(url_for('production.list_bom'))
        else:
            return redirect(url_for('production.edit_bom', id=bom.id))
    
    # Get UOM choices for dynamic dropdown
    try:
        from models.uom import UnitOfMeasure
        uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
        uom_choices = [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
    except Exception:
        uom_choices = [
            ('pcs', 'Pieces (pcs)'), ('kg', 'Kilograms (kg)'), ('g', 'Grams (g)'),
            ('nos', 'Numbers (nos)'), ('m', 'Meters (m)'), ('cm', 'Centimeters (cm)'),
            ('l', 'Liters (l)'), ('ml', 'Milliliters (ml)'), ('sqft', 'Square Feet (sq.ft)'),
            ('sqm', 'Square Meters (sq.m)')
        ]
    
    # Get materials for the component selection
    try:
        materials = Item.query.join(ItemType).filter(ItemType.name == 'Material').order_by(Item.name).all()
    except Exception:
        # Fallback to all items if ItemType relationship issues
        materials = Item.query.order_by(Item.name).all()
    
    return render_template('production/bom_form.html', form=form, title='Add BOM', uom_choices=uom_choices, materials=materials)

@production_bp.route('/bom/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_bom(id):
    bom = BOM.query.get_or_404(id)
    
    # Initialize form and populate choices first
    form = BOMForm()
    # Allow any product type for BOM creation - no restrictions  
    form.product_id.choices = [(i.id, f"{i.code} - {i.name}") for i in Item.query.order_by(Item.name).all()]
    
    # For GET request, populate form with existing BOM data
    if request.method == 'GET':
        form.bom_code.data = bom.bom_code
        form.product_id.data = bom.product_id
        form.output_uom_id.data = bom.output_uom_id
        form.version.data = bom.version
        form.status.data = bom.status
        form.is_active.data = bom.is_active
        form.output_quantity.data = bom.output_quantity
        form.unit_weight.data = bom.unit_weight
        form.unit_weight_uom.data = bom.unit_weight_uom
        form.estimated_scrap_percent.data = bom.estimated_scrap_percent
        form.scrap_quantity.data = bom.scrap_quantity
        form.scrap_uom.data = bom.scrap_uom
        form.scrap_value_recovery_percent.data = bom.scrap_value_recovery_percent
        form.description.data = bom.description
        form.remarks.data = bom.remarks
        form.labor_cost_per_unit.data = bom.labor_cost_per_unit
        form.labor_hours_per_unit.data = bom.labor_hours_per_unit
        form.labor_rate_per_hour.data = bom.labor_rate_per_hour
        form.overhead_cost_per_unit.data = bom.overhead_cost_per_unit
        form.overhead_percentage.data = bom.overhead_percentage
        form.freight_cost_per_unit.data = bom.freight_cost_per_unit
        form.freight_unit_type.data = bom.freight_unit_type
        form.markup_percentage.data = bom.markup_percentage
        
        # Multi-level BOM fields - these were missing in form population!
        form.parent_bom_id.data = bom.parent_bom_id
        form.bom_level.data = bom.bom_level
        form.is_phantom_bom.data = bom.is_phantom_bom
        form.intermediate_product.data = bom.intermediate_product
    
    if form.validate_on_submit():
        # Check if BOM already exists for this product (excluding current BOM)
        existing_bom = BOM.query.filter(
            BOM.product_id == form.product_id.data, 
            BOM.is_active == True,
            BOM.id != id
        ).first()
        if existing_bom:
            flash('An active BOM already exists for this product. Please deactivate the existing BOM first.', 'warning')
            # Get UOM choices for error case
            try:
                from models.uom import UnitOfMeasure
                uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
                uom_choices = [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
            except Exception:
                uom_choices = [('pcs', 'Pieces (pcs)'), ('kg', 'Kilograms (kg)'), ('g', 'Grams (g)')]
            return render_template('production/bom_form.html', form=form, title='Edit BOM', bom=bom, uom_choices=uom_choices)
        
        # Ensure bom_code is never None or empty
        if form.bom_code.data and form.bom_code.data.strip():
            bom.bom_code = form.bom_code.data.strip()
        # If empty, don't change the existing bom_code
        
        bom.product_id = form.product_id.data
        bom.output_uom_id = form.output_uom_id.data if form.output_uom_id.data != 0 else None
        bom.version = form.version.data
        bom.status = form.status.data
        bom.is_active = True if (form.status.data == 'active' or not form.status.data) else False
        bom.output_quantity = form.output_quantity.data or 1.0
        bom.unit_weight = form.unit_weight.data or 0.0
        bom.unit_weight_uom = form.unit_weight_uom.data or 'kg'
        bom.estimated_scrap_percent = form.estimated_scrap_percent.data or 0.0
        bom.scrap_quantity = form.scrap_quantity.data or 0.0
        bom.scrap_uom = form.scrap_uom.data or 'kg'
        bom.scrap_value_recovery_percent = form.scrap_value_recovery_percent.data or 15.0
        bom.description = form.description.data
        # Ensure remarks is not None - use existing value if form data is None
        bom.remarks = form.remarks.data if form.remarks.data is not None else bom.remarks
        bom.labor_cost_per_unit = form.labor_cost_per_unit.data or 0.0
        bom.labor_hours_per_unit = form.labor_hours_per_unit.data or 0.0
        bom.labor_rate_per_hour = form.labor_rate_per_hour.data or 0.0
        bom.overhead_cost_per_unit = form.overhead_cost_per_unit.data or 0.0
        bom.overhead_percentage = form.overhead_percentage.data or 0.0
        bom.freight_cost_per_unit = form.freight_cost_per_unit.data or 0.0
        bom.freight_unit_type = form.freight_unit_type.data or 'per_piece'
        bom.markup_percentage = form.markup_percentage.data or 0.0
        
        # Multi-level BOM fields - these were missing!
        bom.parent_bom_id = form.parent_bom_id.data if form.parent_bom_id.data != 0 else None
        bom.bom_level = form.bom_level.data or 0
        bom.is_phantom_bom = form.is_phantom_bom.data
        bom.intermediate_product = form.intermediate_product.data
        
        bom.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('BOM updated successfully', 'success')
        return redirect(url_for('production.list_bom'))
    
    # Get BOM items
    bom_items = BOMItem.query.filter_by(bom_id=bom.id).all()
    
    # Calculate total BOM cost using the enhanced BOM model properties
    material_cost = bom.total_material_cost
    total_cost_per_unit = bom.total_cost_per_unit
    
    # Get materials for adding new items
    materials = Item.query.filter(Item.item_type.in_(['material', 'consumable'])).all()
    
    # Get UOM choices for dynamic dropdown
    try:
        from models.uom import UnitOfMeasure
        uoms = UnitOfMeasure.query.order_by(UnitOfMeasure.category, UnitOfMeasure.name).all()
        uom_choices = [(u.symbol, f"{u.name} ({u.symbol})") for u in uoms]
    except Exception:
        uom_choices = [
            ('pcs', 'Pieces (pcs)'), ('kg', 'Kilograms (kg)'), ('g', 'Grams (g)'),
            ('nos', 'Numbers (nos)'), ('m', 'Meters (m)'), ('cm', 'Centimeters (cm)'),
            ('l', 'Liters (l)'), ('ml', 'Milliliters (ml)'), ('sqft', 'Square Feet (sq.ft)'),
            ('sqm', 'Square Meters (sq.m)')
        ]
    
    return render_template('production/bom_form.html', 
                         form=form, 
                         title='Edit BOM', 
                         bom=bom,
                         bom_items=bom_items,
                         materials=materials,
                         material_cost=material_cost,
                         total_cost_per_unit=total_cost_per_unit,
                         uom_choices=uom_choices)

@production_bp.route('/bom/<int:bom_id>/add_item', methods=['POST'])
@login_required
def add_bom_item(bom_id):
    bom = BOM.query.get_or_404(bom_id)
    
    item_id = request.form.get('item_id', type=int)
    quantity_required = request.form.get('quantity_required', type=float)
    unit = request.form.get('unit', default='pcs')
    unit_cost = request.form.get('unit_cost', type=float, default=0.0)
    
    if not item_id or not quantity_required:
        flash('Please provide item and quantity', 'danger')
        return redirect(url_for('production.edit_bom', id=bom_id))
    
    # Check if item already exists in this BOM
    existing_item = BOMItem.query.filter_by(bom_id=bom_id, item_id=item_id).first()
    if existing_item:
        flash('This item is already in the BOM', 'warning')
        return redirect(url_for('production.edit_bom', id=bom_id))
    
    # Auto-populate unit cost from inventory if not provided
    if unit_cost == 0.0:
        item = Item.query.get(item_id)
        if item and item.unit_price:
            unit_cost = item.unit_price
    
    # Get default UOM for the item or create a default one
    uom_id = None
    try:
        from models.uom import UnitOfMeasure
        
        # Try to get item's default UOM
        item = Item.query.get(item_id)
        if item and item.unit_of_measure:
            # Find UOM by symbol
            uom = UnitOfMeasure.query.filter_by(symbol=item.unit_of_measure).first()
            if uom:
                uom_id = uom.id
        
        # If no UOM found, get default "Pieces" UOM
        if not uom_id:
            uom = UnitOfMeasure.query.filter_by(symbol='Pcs').first()
            if not uom:
                # Create default UOM if it doesn't exist
                uom = UnitOfMeasure(
                    name='Pieces',
                    symbol='Pcs',
                    category='Count',
                    base_unit=True
                )
                db.session.add(uom)
                db.session.flush()  # Get ID without committing
            uom_id = uom.id
            
    except Exception as e:
        flash(f'Error setting UOM: {str(e)}', 'danger')
        return redirect(url_for('production.edit_bom', id=bom_id))
    
    bom_item = BOMItem(
        bom_id=bom_id,
        material_id=item_id,  # Use new field
        item_id=item_id,      # Keep legacy field for compatibility
        qty_required=quantity_required,  # Use new field
        quantity_required=quantity_required,  # Keep legacy field for compatibility
        uom_id=uom_id,        # Required UOM ID
        unit=unit,            # Keep legacy field for compatibility
        unit_cost=unit_cost
    )
    
    db.session.add(bom_item)
    db.session.commit()
    flash('Item added to BOM successfully', 'success')
    
    return redirect(url_for('production.edit_bom', id=bom_id))

@production_bp.route('/bom_item/delete/<int:id>')
@login_required
def delete_bom_item(id):
    bom_item = BOMItem.query.get_or_404(id)
    bom_id = bom_item.bom_id
    
    db.session.delete(bom_item)
    db.session.commit()
    flash('Item removed from BOM successfully', 'success')
    
    return redirect(url_for('production.edit_bom', id=bom_id))

# Nested BOM API endpoints
@production_bp.route('/api/bom/<int:bom_id>/refresh', methods=['GET'])
@login_required
def refresh_bom_api(bom_id):
    """API endpoint to refresh BOM data for nested displays"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        
        # Prepare BOM data with updated calculations
        bom_data = {
            'id': bom.id,
            'bom_code': bom.bom_code,
            'total_material_cost': float(bom.total_material_cost or 0),
            'total_cost_per_unit': float(bom.total_cost_per_unit or 0),
            'items': []
        }
        
        # Add items with current stock and cost data
        for item in bom.items:
            item_data = {
                'id': item.id,
                'name': item.item.name,
                'code': item.item.code,
                'quantity_required': float(item.quantity_required),
                'unit': item.unit,
                'unit_cost': float(item.unit_cost),
                'total_cost': float(item.quantity_required * item.unit_cost),
                'current_stock': float(item.item.current_stock or 0)
            }
            bom_data['items'].append(item_data)
        
        return jsonify({
            'success': True,
            'data': bom_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@production_bp.route('/bom/add')
@login_required  
def add_bom_with_params():
    """BOM creation with pre-filled parameters for nested BOM creation"""
    from forms import BOMForm
    
    form = BOMForm()
    
    # Pre-fill product if specified
    product_id = request.args.get('product_id', type=int)
    parent_bom_item = request.args.get('parent_bom_item', type=int)
    
    if product_id:
        product = Item.query.get(product_id)
        if product:
            # Pre-fill the form with product information
            form.product_id.data = product_id
            flash(f'Creating BOM for component: {product.name}', 'info')
    
    if parent_bom_item:
        # Store parent BOM item reference for linking
        session['parent_bom_item'] = parent_bom_item
        flash('This will create a sub-BOM for the selected component', 'info')
    
    # Get products for dropdown
    products = Item.query.filter(Item.item_type.in_(['product', 'semi_finished', 'intermediate'])).all()
    form.product_id.choices = [(0, 'Select Product')] + [(p.id, f"{p.name} ({p.code})") for p in products]
    
    # Get materials for adding new items
    materials = Item.query.filter(Item.item_type.in_(['material', 'consumable'])).all()
    
    return render_template('production/bom_form.html', 
                         form=form, 
                         title='Create BOM',
                         products=products,
                         materials=materials)

@production_bp.route('/bom/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_bom(id):
    bom = BOM.query.get(id)
    if not bom:
        flash(f'BOM with ID {id} not found', 'error')
        return redirect(url_for('production.list_bom'))
    
    try:
        # Delete all related BOM items first
        items_count = 0
        if hasattr(bom, 'items') and bom.items:
            items_count = len(bom.items)
            for item in list(bom.items):  # Create a copy of the list
                db.session.delete(item)
        
        # Delete all related BOM processes
        processes_count = 0
        if hasattr(bom, 'processes') and bom.processes:
            processes_count = len(bom.processes)
            for process in list(bom.processes):  # Create a copy of the list
                db.session.delete(process)
        
        # Delete the BOM itself
        bom_code = bom.bom_code
        db.session.delete(bom)
        db.session.commit()
        
        flash(f'BOM {bom_code} and all its components deleted successfully ({items_count} items, {processes_count} processes)', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting BOM: {str(e)}', 'error')
        print(f"Delete BOM error: {str(e)}")  # For debugging
    
    return redirect(url_for('production.list_bom'))

# Enhanced BOM Item Routes
@production_bp.route('/bom/<int:bom_id>/add_item', methods=['GET', 'POST'])
@login_required
def add_bom_item_enhanced(bom_id):
    """Add advanced BOM item with enhanced features"""
    bom = BOM.query.get_or_404(bom_id)
    form = BOMItemForm()
    
    if form.validate_on_submit():
        # Handle both new and legacy field structures
        material_id = form.material_id.data or form.item_id.data
        qty_required = form.qty_required.data or form.quantity_required.data
        
        if not material_id or not qty_required:
            flash('Material and quantity are required', 'error')
            return render_template('production/bom_item_form.html', form=form, bom=bom, title='Add BOM Item')
        
        # Check for duplicate items
        existing_item = BOMItem.query.filter_by(bom_id=bom_id, material_id=material_id).first()
        if existing_item:
            flash('This material is already in the BOM', 'warning')
            return render_template('production/bom_item_form.html', form=form, bom=bom, title='Add BOM Item')
        
        # Handle UOM - use default if none selected
        uom_id = form.uom_id.data if form.uom_id.data != 0 else None
        if not uom_id:
            # Try to get a default UOM (first available)
            try:
                from models.uom import UnitOfMeasure
                default_uom = UnitOfMeasure.query.first()
                uom_id = default_uom.id if default_uom else 1  # Fallback to ID 1
            except:
                uom_id = 1  # Fallback to default UOM ID
        
        # Create enhanced BOM item
        bom_item = BOMItem(
            bom_id=bom_id,
            material_id=material_id,
            qty_required=qty_required,
            uom_id=uom_id,
            unit_cost=form.unit_cost.data or 0.0,
            scrap_percent=form.scrap_percent.data or 0.0,
            process_step=form.process_step.data or 1,
            process_name=form.process_name.data,
            is_critical=form.is_critical.data,
            substitute_materials=form.substitute_materials.data,
            default_supplier_id=form.default_supplier_id.data if form.default_supplier_id.data != 0 else None,
            remarks=form.remarks.data,
            # Legacy compatibility
            item_id=material_id,
            quantity_required=qty_required,
            unit=form.unit.data or 'pcs'
        )
        
        db.session.add(bom_item)
        db.session.commit()
        flash('Enhanced BOM item added successfully with advanced features', 'success')
        return redirect(url_for('production.edit_bom', id=bom_id))
    
    return render_template('production/bom_item_form.html', form=form, bom=bom, title='Add Enhanced BOM Item')

# BOM Process Routes
@production_bp.route('/bom/<int:bom_id>/add_process', methods=['GET', 'POST'])
@login_required
def add_bom_process(bom_id):
    """Add process routing to BOM"""
    bom = BOM.query.get_or_404(bom_id)
    form = BOMProcessForm()
    
    if form.validate_on_submit():
        # Check for duplicate step numbers
        existing_step = BOMProcess.query.filter_by(bom_id=bom_id, step_number=form.step_number.data).first()
        if existing_step:
            flash('A process with this step number already exists', 'warning')
            return render_template('production/bom_process_form.html', form=form, bom=bom, title='Add Process')
        
        bom_process = BOMProcess(
            bom_id=bom_id,
            step_number=form.step_number.data,
            process_name=form.process_name.data,
            process_code=form.process_code.data,
            operation_description=form.operation_description.data,
            setup_time_minutes=form.setup_time_minutes.data or 0.0,
            run_time_minutes=form.run_time_minutes.data or 0.0,
            labor_rate_per_hour=form.labor_rate_per_hour.data or 0.0,
            machine_id=form.machine_id.data if form.machine_id.data != 0 else None,
            department_id=form.department_id.data if form.department_id.data != 0 else None,
            is_outsourced=form.is_outsourced.data,
            vendor_id=form.vendor_id.data if form.vendor_id.data != 0 else None,
            cost_per_unit=form.cost_per_unit.data or 0.0,
            quality_check_required=form.quality_check_required.data,
            estimated_scrap_percent=form.estimated_scrap_percent.data or 0.0,
            parallel_processes=form.parallel_processes.data,
            predecessor_processes=form.predecessor_processes.data,
            # New transformation fields
            input_product_id=form.input_product_id.data if form.input_product_id.data != 0 else None,
            output_product_id=form.output_product_id.data if form.output_product_id.data != 0 else None,
            input_quantity=form.input_quantity.data or 1.0,
            output_quantity=form.output_quantity.data or 1.0,
            transformation_type=form.transformation_type.data or 'modify',
            notes=form.notes.data
        )
        
        db.session.add(bom_process)
        db.session.commit()
        flash('Process routing added successfully', 'success')
        return redirect(url_for('production.edit_bom', id=bom_id))
    
    return render_template('production/bom_process_form.html', form=form, bom=bom, title='Add Process Routing')



# Enhanced BOM Analysis Routes
@production_bp.route('/bom/<int:id>/analysis')
@login_required
def bom_analysis(id):
    """Show detailed BOM analysis including material availability and cost breakdown"""
    bom = BOM.query.get_or_404(id)
    
    # Get material availability analysis
    shortages = bom.get_material_availability()
    
    # Calculate production capacity based on current inventory
    max_production_qty = float('inf')
    for bom_item in bom.items:
        material = bom_item.material or bom_item.item
        if material:
            available_qty = material.total_stock if hasattr(material, 'total_stock') else (material.current_stock or 0)
            effective_qty_needed = bom_item.effective_quantity
            if effective_qty_needed > 0:
                possible_production = available_qty / effective_qty_needed
                max_production_qty = min(max_production_qty, possible_production)
    
    if max_production_qty == float('inf'):
        max_production_qty = 0
    
    # Get process information
    processes = BOMProcess.query.filter_by(bom_id=bom.id).order_by(BOMProcess.step_number).all()
    
    # Calculate total process costs
    total_process_cost = sum(p.labor_cost_per_unit for p in processes)
    
    return render_template('production/bom_analysis.html', 
                         bom=bom, 
                         shortages=shortages,
                         max_production_qty=int(max_production_qty),
                         processes=processes,
                         total_process_cost=total_process_cost)

@production_bp.route('/api/bom/<int:id>/production_check/<int:qty>')
@login_required
def check_bom_production_capacity(id, qty):
    """API endpoint to check if BOM can produce specified quantity"""
    bom = BOM.query.get_or_404(id)
    can_produce, shortages = bom.can_produce_quantity(qty)
    
    return jsonify({
        'can_produce': can_produce,
        'shortages': [
            {
                'material_name': s['material'].name,
                'material_code': s['material'].code,
                'required': s['required'],
                'available': s['available'],
                'shortage': s['shortage']
            }
            for s in shortages
        ]
    })

@production_bp.route('/api/item_details/<int:item_id>')
@login_required  
def get_item_details(item_id):
    """API endpoint to get item details including unit price for BOM auto-population"""
    item = Item.query.get_or_404(item_id)
    return {
        'id': item.id,
        'code': item.code,
        'name': item.name,
        'unit_price': item.unit_price or 0.0,
        'unit_of_measure': item.unit_of_measure,
        'item_type': item.item_type
    }

@production_bp.route('/check_material_availability', methods=['POST'])
@login_required
def check_material_availability():
    """API endpoint to check material availability for production planning"""
    item_id = request.json.get('item_id')
    quantity = float(request.json.get('quantity', 1))
    
    if not item_id:
        return jsonify({'error': 'Item ID required'}), 400
    
    # Get BOM for the item
    active_bom = BOM.query.filter_by(product_id=item_id, is_active=True).first()
    
    if not active_bom:
        return jsonify({
            'has_bom': False,
            'message': 'No BOM found for this item'
        })
    
    # Check material availability
    bom_items = BOMItem.query.filter_by(bom_id=active_bom.id).all()
    material_data = []
    has_shortages = False
    
    for bom_item in bom_items:
        required_qty = bom_item.quantity_required * quantity
        available_qty = bom_item.item.current_stock or 0
        is_sufficient = available_qty >= required_qty
        
        if not is_sufficient:
            has_shortages = True
        
        material_data.append({
            'item_code': bom_item.item.code,
            'item_name': bom_item.item.name,
            'quantity_required': bom_item.quantity_required,
            'total_required': required_qty,
            'available_qty': available_qty,
            'is_sufficient': is_sufficient,
            'shortage_qty': max(0, required_qty - available_qty),
            'unit': bom_item.item.unit_of_measure
        })
    
    return jsonify({
        'has_bom': True,
        'has_shortages': has_shortages,
        'materials': material_data
    })

# Process Integration Routes
@production_bp.route('/bom/<int:id>/sync_from_processes', methods=['POST'])
@login_required
def sync_bom_from_processes(id):
    """Intelligent synchronization: Update BOM labor costs and scrap from process workflows"""
    try:
        success = ProcessIntegrationService.sync_bom_from_processes(id)
        if success:
            bom = BOM.query.get(id)
            flash(f'Successfully synchronized BOM from process workflow. Labor Cost: ₹{bom.calculated_labor_cost_per_unit:.2f}, Scrap Rate: {bom.calculated_scrap_percent:.2f}%', 'success')
        else:
            flash('No processes found or synchronization not needed', 'info')
    except Exception as e:
        flash(f'Error during synchronization: {str(e)}', 'error')
    
    return redirect(url_for('production.edit_bom', id=id))

@production_bp.route('/api/bom/<int:id>/process_summary')
@login_required
def get_process_summary(id):
    """API endpoint for process-driven BOM calculations"""
    bom = BOM.query.get_or_404(id)
    summary = ProcessIntegrationService.get_process_summary(bom)
    return jsonify(summary)

@production_bp.route('/bom/<int:id>/process_report')
@login_required
def process_integration_report(id):
    """Generate detailed process workflow integration report"""
    bom = BOM.query.get_or_404(id)
    report = ProcessIntegrationService.generate_process_workflow_report(bom)
    
    return render_template('production/process_report.html', 
                         bom=bom, 
                         report=report,
                         title=f'Process Integration Report - {bom.bom_code}')

@production_bp.route('/bom/<int:bom_id>/add_multi_process', methods=['GET', 'POST'])
@login_required
def add_multi_bom_process(bom_id):
    """Add multiple manufacturing processes to BOM or edit existing process"""
    bom = BOM.query.get_or_404(bom_id)
    
    # Check if we're editing an existing process
    edit_process_id = request.args.get('edit_process_id', type=int)
    edit_process = None
    if edit_process_id:
        edit_process = BOMProcess.query.get_or_404(edit_process_id)
    
    if request.method == 'POST':
        try:
            # Check if we're editing an existing process vs adding new ones
            if edit_process:
                # Editing mode - update the existing process
                form_data = request.form
                
                # Update the existing process with form data
                edit_process.step_number = int(form_data.get('processes[0][step_number]', 1))
                edit_process.process_name = form_data.get('processes[0][process_name]')
                edit_process.process_code = form_data.get('processes[0][process_code]', '')
                edit_process.operation_description = form_data.get('processes[0][operation_description]', '')
                edit_process.is_outsourced = form_data.get('processes[0][is_outsourced]') == 'true'
                edit_process.setup_time_minutes = float(form_data.get('processes[0][setup_time_minutes]') or 0)
                edit_process.run_time_minutes = float(form_data.get('processes[0][run_time_minutes]') or 0)
                edit_process.cost_per_unit = float(form_data.get('processes[0][cost_per_unit]') or 0)
                edit_process.cost_unit = form_data.get('processes[0][cost_unit]', 'per_unit')
                edit_process.labor_rate_per_hour = float(form_data.get('processes[0][labor_rate_per_hour]') or 0)
                edit_process.quality_check_required = form_data.get('processes[0][quality_check_required]') == 'true'
                
                # Update transformation fields
                edit_process.input_product_id = int(form_data.get('processes[0][input_product_id]') or 0) or None
                edit_process.output_product_id = int(form_data.get('processes[0][output_product_id]') or 0) or None
                edit_process.input_quantity = float(form_data.get('processes[0][input_quantity]') or 1.0)
                edit_process.output_quantity = float(form_data.get('processes[0][output_quantity]') or 1.0)
                edit_process.transformation_type = form_data.get('processes[0][transformation_type]', 'modify')
                
                db.session.commit()
                
                # Trigger intelligent sync after editing process
                ProcessIntegrationService.sync_bom_from_processes(bom_id)
                
                flash(f'Process "{edit_process.process_name}" updated successfully. BOM costs automatically synchronized!', 'success')
                return redirect(url_for('production.edit_bom', id=bom_id))
                
            else:
                # Adding mode - create new processes
                processes_data = []
                
                # Extract process data from form
                form_data = request.form
                process_indices = set()
                
                # Find all process indices
                for key in form_data.keys():
                    if key.startswith('processes[') and '][' in key:
                        index = int(key.split('[')[1].split(']')[0])
                        process_indices.add(index)
                
                # Process each process entry
                for index in sorted(process_indices):
                    process_name = form_data.get(f'processes[{index}][process_name]')
                    if not process_name:  # Skip empty processes
                        continue
                    
                    process_data = {
                        'step_number': int(form_data.get(f'processes[{index}][step_number]', 1)),
                        'process_name': process_name,
                        'process_code': form_data.get(f'processes[{index}][process_code]', ''),
                        'operation_description': form_data.get(f'processes[{index}][operation_description]', ''),
                        'is_outsourced': form_data.get(f'processes[{index}][is_outsourced]') == 'true',
                        'setup_time_minutes': float(form_data.get(f'processes[{index}][setup_time_minutes]') or 0),
                        'run_time_minutes': float(form_data.get(f'processes[{index}][run_time_minutes]') or 0),
                        'cost_per_unit': float(form_data.get(f'processes[{index}][cost_per_unit]') or 0),
                        'cost_unit': form_data.get(f'processes[{index}][cost_unit]', 'per_unit'),
                        'labor_rate_per_hour': float(form_data.get(f'processes[{index}][labor_rate_per_hour]') or 0),
                        'quality_check_required': form_data.get(f'processes[{index}][quality_check_required]') == 'true',
                        # Transformation fields
                        'input_product_id': int(form_data.get(f'processes[{index}][input_product_id]') or 0) or None,
                        'output_product_id': int(form_data.get(f'processes[{index}][output_product_id]') or 0) or None,
                        'input_quantity': float(form_data.get(f'processes[{index}][input_quantity]') or 1.0),
                        'output_quantity': float(form_data.get(f'processes[{index}][output_quantity]') or 1.0),
                        'transformation_type': form_data.get(f'processes[{index}][transformation_type]', 'modify')
                    }
                    processes_data.append(process_data)
                
                if not processes_data:
                    flash('Please add at least one process', 'error')
                    return redirect(url_for('production.add_multi_bom_process', bom_id=bom_id))
                
                # Create all BOM processes
                created_count = 0
                for process_data in processes_data:
                    bom_process = BOMProcess(
                        bom_id=bom_id,
                        step_number=process_data['step_number'],
                        process_name=process_data['process_name'],
                        process_code=process_data['process_code'],
                        operation_description=process_data['operation_description'],
                        is_outsourced=process_data['is_outsourced'],
                        setup_time_minutes=process_data['setup_time_minutes'],
                        run_time_minutes=process_data['run_time_minutes'],
                        cost_per_unit=process_data['cost_per_unit'],
                        cost_unit=process_data['cost_unit'],
                        labor_rate_per_hour=process_data['labor_rate_per_hour'], 
                        quality_check_required=process_data['quality_check_required'],
                        # Transformation fields
                        input_product_id=process_data['input_product_id'],
                        output_product_id=process_data['output_product_id'],
                        input_quantity=process_data['input_quantity'],
                        output_quantity=process_data['output_quantity'],
                        transformation_type=process_data['transformation_type']
                    )
                    db.session.add(bom_process)
                    created_count += 1
                
                db.session.commit()
                
                # Trigger intelligent sync after adding processes
                ProcessIntegrationService.sync_bom_from_processes(bom_id)
                
                flash(f'Successfully added {created_count} manufacturing processes. BOM costs automatically synchronized!', 'success')
                return redirect(url_for('production.edit_bom', id=bom_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing request: {str(e)}', 'error')
            
    # Create a simple form for CSRF protection  
    form = FlaskForm()
    
    # Get available items for transformation dropdowns
    available_items = Item.query.order_by(Item.name).all()
    
    # Determine the title based on whether we're editing or adding
    if edit_process:
        title = f'Edit Process: {edit_process.process_name} - {bom.bom_code}'
    else:
        title = f'Add Multiple Process Routing - {bom.bom_code}'
    
    return render_template('production/bom_multi_process_form.html',
                         bom=bom,
                         form=form,
                         available_items=available_items,
                         edit_process=edit_process,
                         title=title)

@production_bp.route('/api/item/<int:item_id>/unit')
@login_required
def get_item_unit(item_id):
    """Get unit of measure for an item"""
    item = Item.query.get_or_404(item_id)
    return jsonify({
        'unit': item.unit_of_measure,
        'name': item.name,
        'code': item.code
    })

@production_bp.route('/bom_process/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bom_process(id):
    """Edit a BOM process - redirect to unified multi-process interface"""
    process = BOMProcess.query.get_or_404(id)
    bom = process.bom
    
    # Since we now use unified interface, redirect to multi-process form
    # with the specific process pre-selected for editing
    flash(f'Editing process "{process.process_name}" in unified interface', 'info')
    return redirect(url_for('production.add_multi_bom_process', bom_id=bom.id, edit_process_id=id))

@production_bp.route('/bom_process/<int:id>/delete', methods=['POST'])
@login_required
def delete_bom_process(id):
    """Delete a BOM process"""
    process = BOMProcess.query.get_or_404(id)
    bom_id = process.bom_id
    process_name = process.process_name
    
    try:
        db.session.delete(process)
        db.session.commit()
        
        # Trigger intelligent sync after deleting process
        ProcessIntegrationService.sync_bom_from_processes(bom_id)
        
        flash(f'Process "{process_name}" deleted successfully. BOM costs automatically synchronized!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting process: {str(e)}', 'error')
    
    return redirect(url_for('production.edit_bom', id=bom_id) + '#manufacturing-processes')

# Multi-level BOM API Endpoints

@production_bp.route('/api/bom/<int:bom_id>/hierarchy')
@login_required
def api_bom_hierarchy(bom_id):
    """Get BOM hierarchy tree for nested BOMs"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        hierarchy = bom.get_bom_hierarchy()
        
        def serialize_hierarchy(node):
            return {
                'bom_id': node['bom'].id,
                'bom_code': node['bom'].bom_code,
                'product_name': node['bom'].product.name if node['bom'].product else '',
                'level': node['level'],
                'total_cost': node['bom'].total_cost_per_unit,
                'is_phantom': node['bom'].is_phantom_bom,
                'intermediate_product': node['bom'].intermediate_product,
                'parent_requirement': node.get('parent_requirement', {}),
                'children': [serialize_hierarchy(child) for child in node['children']]
            }
        
        return jsonify({
            'success': True,
            'hierarchy': serialize_hierarchy(hierarchy)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@production_bp.route('/api/bom/<int:bom_id>/missing-intermediate-products')
@login_required
def api_missing_intermediate_products(bom_id):
    """Get missing intermediate products that need to be produced"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        missing_products = bom.get_missing_intermediate_products()
        
        serialized_products = []
        for product in missing_products:
            serialized_products.append({
                'material_id': product['material'].id,
                'material_name': product['material'].name,
                'material_code': product['material'].code,
                'bom_id': product['bom'].id,
                'bom_code': product['bom'].bom_code,
                'required_qty': product['required_qty'],
                'available_qty': product['available_qty'],
                'shortage_qty': product['shortage_qty'],
                'suggested_job_work': product['suggested_job_work'],
                'estimated_cost': product['estimated_cost']
            })
        
        return jsonify({
            'success': True,
            'missing_products': serialized_products
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@production_bp.route('/api/bom/<int:bom_id>/production-sequence')
@login_required
def api_production_sequence(bom_id):
    """Get suggested production sequence for multi-level BOMs"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        sequence = bom.get_suggested_production_sequence()
        
        serialized_sequence = []
        for item in sequence:
            serialized_sequence.append({
                'bom_id': item['bom'].id,
                'bom_code': item['bom'].bom_code,
                'product_name': item['bom'].product.name if item['bom'].product else '',
                'level': item['level'],
                'estimated_lead_time': item['estimated_lead_time'],
                'priority': item['priority'],
                'total_cost': item['bom'].total_cost_per_unit
            })
        
        return jsonify({
            'success': True,
            'production_sequence': serialized_sequence
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@production_bp.route('/api/bom/<int:bom_id>/flattened-materials')
@login_required
def api_flattened_materials(bom_id):
    """Get flattened materials list including nested BOM materials"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        materials_list = bom.get_flattened_materials_list()
        
        serialized_materials = []
        for material in materials_list:
            available_qty = material['material'].total_stock if hasattr(material['material'], 'total_stock') else (material['material'].current_stock or 0)
            serialized_materials.append({
                'material_id': material['material'].id,
                'material_name': material['material'].name,
                'material_code': material['material'].code,
                'total_quantity': material['total_quantity'],
                'unit': material['unit'],
                'source_bom': material['source_bom'],
                'bom_level': material['bom_level'],
                'available_qty': available_qty,
                'shortage': max(0, material['total_quantity'] - available_qty)
            })
        
        return jsonify({
            'success': True,
            'flattened_materials': serialized_materials
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@production_bp.route('/api/bom/<int:bom_id>/cost-breakdown')
@login_required
def api_cost_breakdown(bom_id):
    """Get multi-level cost breakdown"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        breakdown = bom.calculate_multi_level_cost_breakdown()
        
        # Serialize cost details
        serialized_details = []
        for detail in breakdown['cost_details']:
            detail_data = {
                'material_id': detail['material'].id,
                'material_name': detail['material'].name,
                'material_code': detail['material'].code,
                'type': detail['type'],
                'quantity': detail['quantity'],
                'unit_cost': detail['unit_cost'],
                'total_cost': detail['total_cost']
            }
            
            if 'sub_breakdown' in detail:
                detail_data['sub_breakdown'] = detail['sub_breakdown']
            
            serialized_details.append(detail_data)
        
        breakdown['cost_details'] = serialized_details
        
        return jsonify({
            'success': True,
            'cost_breakdown': breakdown
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@production_bp.route('/api/bom/<int:bom_id>/job-work-data')
@login_required
def get_bom_job_work_data(bom_id):
    """Get BOM data formatted for job work auto-population"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        
        # Get the primary input material (first material in BOM items)
        input_material = None
        if bom.items:
            # Find the raw material item (largest quantity requirement typically)
            primary_item = max(bom.items, key=lambda x: x.quantity_required)
            input_material = primary_item.item
        
        # Get manufacturing processes from BOM
        processes = []
        if bom.processes:
            for i, process in enumerate(bom.processes):
                # Determine output product for each process
                if i == len(bom.processes) - 1:  # Last process
                    # Final output should be the BOM's final product
                    output_product = bom.final_product if bom.final_product else None
                    output_name = output_product.name if output_product else f"{bom.name} - Final Product"
                else:
                    # Intermediate output - create WIP name
                    output_name = f"{bom.name} - {process.process_name.title()} WIP"
                    output_product = None  # Will be created by the intelligent system
                
                process_data = {
                    'process_name': process.process_name,
                    'output_product_id': output_product.id if output_product else None,
                    'output_product_name': output_name,
                    'quantity': 1,  # Default quantity
                    'uom': input_material.unit_of_measure if input_material else 'piece',
                    'rate_per_unit': process.cost_per_unit if hasattr(process, 'cost_per_unit') else 0,
                    'quality_check': True,  # Default to requiring QC
                    'scrap_percent': process.scrap_percent if hasattr(process, 'scrap_percent') else 0,
                    'notes': f"Process from {bom.name} BOM"
                }
                processes.append(process_data)
        
        # Calculate quantity needed based on BOM
        quantity_needed = 1  # Default to 1 unit
        if input_material and bom.items:
            for item in bom.items:
                if item.item == input_material:
                    quantity_needed = item.quantity_required
                    break
        
        response_data = {
            'success': True,
            'bom_name': bom.name,
            'job_title': f"Job Work - {bom.name}",
            'input_material_id': input_material.id if input_material else None,
            'input_uom': input_material.unit_of_measure if input_material else 'piece',
            'quantity_needed': quantity_needed,
            'processes': processes,
            'final_output_product_id': bom.final_product.id if bom.final_product else None,
            'final_output_product_name': bom.final_product.name if bom.final_product else f"{bom.name} - Final Product"
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error loading BOM data: {str(e)}'
        })
