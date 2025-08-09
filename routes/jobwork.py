from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from forms import JobWorkForm, JobWorkQuantityUpdateForm, DailyJobWorkForm, JobWorkTeamAssignmentForm, JobWorkBatchReturnForm
from models import JobWork, Supplier, Item, BOM, BOMItem, CompanySettings, DailyJobWorkEntry, JobWorkTeamAssignment, Employee, JobWorkBatch, ItemBatch
from models.batch import BatchMovementLedger, BatchConsumptionReport
from utils.batch_tracking import BatchTracker, BatchValidator, get_batch_options_for_item_api, validate_batch_selection_api
from services.batch_management import BatchManager, BatchValidator as BatchValidatorService
from app import db
from sqlalchemy import func, or_
from datetime import datetime, timedelta
from utils import generate_job_number  
from services.notification_helpers import send_email_notification, send_whatsapp_notification, send_email_with_attachment
from utils.documents import get_documents_for_transaction

jobwork_bp = Blueprint('jobwork', __name__)

@jobwork_bp.route('/dashboard')
@login_required
def dashboard():
    # Job work statistics
    stats = {
        'total_jobs': JobWork.query.count(),
        'sent_jobs': JobWork.query.filter_by(status='sent').count(),
        'partial_received': JobWork.query.filter_by(status='partial_received').count(),
        'completed_jobs': JobWork.query.filter_by(status='completed').count(),
        'in_house_jobs': JobWork.query.filter_by(work_type='in_house').count(),
        'outsourced_jobs': JobWork.query.filter_by(work_type='outsourced').count(),
        'team_jobs': JobWork.query.filter_by(is_team_work=True).count()
    }
    
    # Get all active job works with progress information
    active_jobs = JobWork.query.filter(JobWork.status.in_(['sent', 'partial_received'])).order_by(JobWork.created_at.desc()).all()
    
    # Get team assignments for team jobs
    team_assignments = {}
    for job in active_jobs:
        if job.is_team_work:
            assignments = JobWorkTeamAssignment.query.filter_by(job_work_id=job.id).all()
            team_assignments[job.id] = assignments
    
    # Recent job works
    recent_jobs = JobWork.query.order_by(JobWork.created_at.desc()).limit(10).all()
    
    # Pending returns (jobs sent but not completed)
    pending_jobs = JobWork.query.filter(JobWork.status.in_(['sent', 'partial_received'])).all()
    
    # Top job work customers
    top_customers = db.session.query(
        JobWork.customer_name, 
        func.count(JobWork.id).label('job_count')
    ).group_by(JobWork.customer_name).order_by(func.count(JobWork.id).desc()).limit(5).all()
    
    return render_template('jobwork/dashboard.html', 
                         stats=stats, 
                         active_jobs=active_jobs,
                         team_assignments=team_assignments,
                         recent_jobs=recent_jobs,
                         pending_jobs=pending_jobs,
                         top_customers=top_customers)

@jobwork_bp.route('/list')
@login_required
def list_job_works():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '', type=str)
    
    query = JobWork.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    jobs = query.order_by(JobWork.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    return render_template('jobwork/list.html', jobs=jobs, status_filter=status_filter)

# API endpoints for new Job Work form
@jobwork_bp.route('/api/items')
@login_required
def api_items():
    """API to get all items for dropdown population"""
    try:
        items = Item.query.order_by(Item.name).all()
        items_data = []
        for item in items:
            items_data.append({
                'id': item.id,
                'code': item.code,
                'name': item.name,
                'unit_of_measure': item.unit_of_measure
            })
        return jsonify({'items': items_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobwork_bp.route('/api/boms')
@login_required
def api_boms():
    """API to get all BOMs for dropdown population"""
    try:
        from models import BOM
        boms = BOM.query.filter_by(is_active=True).order_by(BOM.bom_code).all()
        boms_data = []
        for bom in boms:
            boms_data.append({
                'id': bom.id,
                'bom_code': bom.bom_code,
                'product_name': bom.product.name if bom.product else 'Unknown Product'
            })
        return jsonify({'boms': boms_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobwork_bp.route('/api/suppliers')
@login_required
def api_suppliers():
    """API to get suppliers/vendors for dropdown population"""
    try:
        suppliers = Supplier.query.filter(
            Supplier.partner_type.in_(['supplier', 'vendor', 'both']),
            Supplier.is_active == True
        ).order_by(Supplier.name).all()
        suppliers_data = []
        for supplier in suppliers:
            suppliers_data.append({
                'id': supplier.id,
                'name': supplier.name,
                'partner_type': supplier.partner_type
            })
        return jsonify({'suppliers': suppliers_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobwork_bp.route('/api/departments')
@login_required
def api_departments():
    """API to get departments for dropdown population"""
    try:
        from models.department import Department
        departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
        departments_data = []
        for dept in departments:
            departments_data.append({
                'code': dept.code,
                'name': dept.name
            })
        return jsonify({'departments': departments_data})
    except ImportError:
        # Fallback if Department model not available
        return jsonify({'departments': [
            {'code': 'production', 'name': 'Production'},
            {'code': 'assembly', 'name': 'Assembly'},
            {'code': 'quality', 'name': 'Quality Control'},
            {'code': 'maintenance', 'name': 'Maintenance'}
        ]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobwork_bp.route('/api/generate_title')
@login_required
def api_generate_title():
    """API to generate auto job work title"""
    try:
        # Get the next job number sequence
        next_job_number = generate_job_number()
        
        # Extract just the number part (JOB-2025-0008 → 008)
        job_sequence = next_job_number.split('-')[-1]
        
        # Generate title like "JW-008 – Manual Work"
        title = f"JW-{job_sequence} – Manual Work"
        
        return jsonify({'title': title})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobwork_bp.route('/api/inventory/stock/<int:item_id>')
@login_required
def api_inventory_stock(item_id):
    """API to get available stock for an item"""
    try:
        item = Item.query.get_or_404(item_id)
        available_stock = item.qty_raw or item.current_stock or 0
        return jsonify({
            'item_id': item_id,
            'available_stock': available_stock,
            'unit_of_measure': item.unit_of_measure
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500





@jobwork_bp.route('/api/items')
@login_required
def api_get_items():
    """API endpoint to get all items for process output product selection"""
    try:
        items = Item.query.order_by(Item.name).all()
        items_data = []
        for item in items:
            items_data.append({
                'id': item.id,
                'code': item.code,
                'name': item.name,
                'unit': item.unit_of_measure
            })
        return jsonify({'items': items_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobwork_bp.route('/api/batches/<int:item_id>')
@login_required
def api_get_item_batches(item_id):
    """API endpoint to get available batches for an item"""
    try:
        item = Item.query.get_or_404(item_id)
        
        # Get available batches with raw material quantity
        available_batches = ItemBatch.query.filter(
            ItemBatch.item_id == item_id,
            ItemBatch.qty_raw > 0,
            ItemBatch.quality_status.in_(['good', 'pending_inspection'])
        ).order_by(ItemBatch.manufacture_date.asc()).all()  # FIFO order
        
        batches_data = []
        for batch in available_batches:
            batches_data.append({
                'id': batch.id,
                'batch_number': batch.batch_number,
                'supplier_batch': batch.supplier_batch or '',
                'manufacture_date': batch.manufacture_date.isoformat() if batch.manufacture_date else '',
                'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else '',
                'available_quantity': batch.qty_raw or 0,
                'unit_of_measure': item.unit_of_measure,
                'quality_status': batch.quality_status,
                'storage_location': batch.storage_location or 'Default',
                'unit_cost': batch.unit_cost or 0,
                'is_expiring_soon': batch.expiry_date and batch.expiry_date <= (datetime.now().date() + timedelta(days=7)) if batch.expiry_date else False
            })
        
        return jsonify({
            'item_id': item_id,
            'item_name': item.name,
            'item_code': item.code,
            'batches': batches_data,
            'total_available': sum(b['available_quantity'] for b in batches_data)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobwork_bp.route('/api/batch/auto-allocate', methods=['POST'])
@login_required
def api_auto_allocate_batches():
    """API endpoint to automatically allocate batches for job work"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')
        required_quantity = data.get('quantity', 0)
        
        if not item_id:
            return jsonify({'success': False, 'message': 'Item ID is required'})
        
        if required_quantity <= 0:
            return jsonify({'success': False, 'message': 'Quantity must be greater than 0'})
        
        # Auto-allocate batches using FIFO logic
        success, batch_selections, message = BatchManager.auto_allocate_batches(item_id, required_quantity)
        
        if success:
            return jsonify({
                'success': True,
                'batch_selections': batch_selections,
                'message': message,
                'total_allocated': sum(b['quantity'] for b in batch_selections),
                'batches_count': len(batch_selections)
            })
        else:
            return jsonify({'success': False, 'message': message})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error auto-allocating batches: {str(e)}'})

@jobwork_bp.route('/api/batch/validate', methods=['POST'])
@login_required
def api_validate_batch_selection():
    """API endpoint to validate batch selection for job work"""
    try:
        data = request.get_json()
        batch_selections = data.get('batch_selections', [])
        
        if not batch_selections:
            return jsonify({'is_valid': False, 'errors': ['No batches selected']})
        
        # Validate batch selection using BatchValidator
        validation_result = BatchValidatorService.validate_batch_selection(batch_selections)
        
        # Check FIFO compliance if requested
        if data.get('check_fifo', True) and batch_selections:
            first_selection = batch_selections[0]
            if 'item_id' in first_selection:
                item_id = first_selection['item_id']
                batch_ids = [sel['batch_id'] for sel in batch_selections]
                fifo_result = BatchValidatorService.validate_fifo_compliance(item_id, batch_ids)
                
                if not fifo_result['compliant']:
                    validation_result['warnings'].append(fifo_result['message'])
                    validation_result['fifo_suggestion'] = fifo_result.get('suggested_batch')
        
        return jsonify(validation_result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobwork_bp.route('/api/batch/issue', methods=['POST'])
@login_required
def api_issue_batch_to_jobwork():
    """API endpoint to issue batches to job work"""
    try:
        data = request.get_json()
        job_work_id = data.get('job_work_id')
        batch_selections = data.get('batch_selections', [])
        
        if not job_work_id or not batch_selections:
            return jsonify({'success': False, 'message': 'Missing job work ID or batch selections'})
        
        # Issue batches using BatchManager
        success, message = BatchManager.issue_batch_to_jobwork(job_work_id, batch_selections)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error issuing batches: {str(e)}'})

@jobwork_bp.route('/api/batch/receive', methods=['POST'])
@login_required
def api_receive_from_jobwork():
    """API endpoint to receive materials back from job work"""
    try:
        data = request.get_json()
        job_work_id = data.get('job_work_id')
        return_data = data.get('return_data', [])
        
        if not job_work_id or not return_data:
            return jsonify({'success': False, 'message': 'Missing job work ID or return data'})
        
        # Receive materials using BatchManager
        success, message = BatchManager.receive_from_jobwork(job_work_id, return_data)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error receiving materials: {str(e)}'})

# API endpoint handled in inventory module

@jobwork_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_job_work():
    """New redesigned job work form with BOM/Manual selection and process routing"""
    form = JobWorkForm()
    
    # Check if coming from production suggestion
    from_suggestion = request.args.get('from_suggestion')
    production_id = request.args.get('production_id')
    suggested_bom_id = request.args.get('bom_id')
    suggested_target_item_id = request.args.get('target_item_id')
    suggested_quantity = request.args.get('quantity')
    
    # Debug form submission
    if request.method == 'POST':
        print(f"Form validation result: {form.validate_on_submit()}")
        print(f"Form data: {request.form}")
        if form.errors:
            print(f"Form errors: {form.errors}")
            for field, errors in form.errors.items():
                print(f"Field {field}: {errors}")
                flash(f"Validation error in {field}: {', '.join(errors)}", 'error')
    
    if form.validate_on_submit():
        try:
            # Generate job number
            job_number = generate_job_number()
            
            # Extract process data from JSON
            import json
            process_data_str = request.form.get('process_data', '[]')
            process_data = json.loads(process_data_str) if process_data_str else []
            
            # Parse assignment data
            assigned_to = form.assigned_to.data
            if assigned_to.startswith('supplier_'):
                supplier_id = int(assigned_to.split('_')[1])
                supplier = Supplier.query.get(supplier_id)
                assigned_to_name = supplier.name if supplier else 'Unknown'
                assigned_to_type = 'vendor'
            elif assigned_to.startswith('department_'):
                dept_code = assigned_to.split('_')[1]
                try:
                    from models.department import Department
                    dept = Department.query.filter_by(code=dept_code).first()
                    assigned_to_name = dept.name if dept else assigned_to.split('_')[1].title()
                    assigned_to_type = 'in_house'
                except ImportError:
                    # Fallback department names
                    dept_names = {
                        'production': 'Production',
                        'assembly': 'Assembly', 
                        'quality': 'Quality Control'
                    }
                    assigned_to_name = dept_names.get(dept_code, dept_code.title())
                    assigned_to_type = 'in_house'
            else:
                assigned_to_name = assigned_to
                assigned_to_type = form.work_type.data
            
            # Determine final output product from last selected process
            final_output_product_id = None
            final_output_quantity = 0
            if process_data:
                # Sort by sequence to get the last process
                sorted_processes = sorted(process_data, key=lambda x: int(x.get('sequence', 0)))
                if sorted_processes:
                    last_process = sorted_processes[-1]
                    final_output_product_id = int(last_process.get('output_product_id', 0))
                    final_output_quantity = int(last_process.get('quantity', 0))
            
            # Get input material for inventory deduction
            input_material = Item.query.get(form.input_material_id.data)
            if not input_material:
                flash('Selected input material not found', 'error')
                return redirect(url_for('jobwork.add_job_work'))
            
            # Check available stock
            available_stock = input_material.qty_raw or input_material.current_stock or 0
            if available_stock < form.quantity_to_issue.data:
                flash(f'Insufficient stock. Available: {available_stock} {input_material.unit_of_measure}', 'error')
                return redirect(url_for('jobwork.add_job_work'))
            
            # Create job work record
            job = JobWork(
                job_number=job_number,
                customer_name=assigned_to_name,  # Always set customer_name (required field)
                work_type=assigned_to_type,
                department=assigned_to_name if assigned_to_type == 'in_house' else None,
                item_id=input_material.id,
                quantity_sent=form.quantity_to_issue.data,
                rate_per_unit=0.0,  # Set default rate (required field)
                process='multi_process' if len(process_data) > 1 else (process_data[0].get('process_name', 'General') if process_data else 'General'),
                sent_date=form.send_date.data,
                expected_return=form.expected_return.data,
                notes=f"Job Work Title: {form.job_title.data}\nType: {form.job_work_type.data}\n{form.remarks.data or ''}",
                created_by=current_user.id,
                bom_id=form.bom_id.data if form.bom_id.data else None,
                production_quantity=final_output_quantity if final_output_quantity > 0 else None  # Set expected output quantity for BOM jobs
            )
            
            # Move input material from store to WIP
            if form.store_location.data == 'raw_store' and input_material.qty_raw:
                input_material.qty_raw -= form.quantity_to_issue.data
            elif form.store_location.data == 'finished_store' and hasattr(input_material, 'qty_finished'):
                input_material.qty_finished -= form.quantity_to_issue.data
            else:
                # Fallback to current_stock
                input_material.current_stock = (input_material.current_stock or 0) - form.quantity_to_issue.data
            
            # Add material movement note
            movement_note = f"[{datetime.utcnow().strftime('%d/%m/%Y %H:%M')}] {form.quantity_to_issue.data} {input_material.unit_of_measure} {input_material.name} issued from {form.store_location.data.replace('_', ' ').title()}"
            job.notes = (job.notes or '') + f"\n{movement_note}"
            
            db.session.add(job)
            db.session.flush()  # Get job ID
            
            # Create job work processes if any
            if process_data:
                try:
                    from models import JobWorkProcess
                    for process_info in process_data:
                        if process_info.get('output_product_id') and process_info.get('sequence'):
                            process = JobWorkProcess(
                                job_work_id=job.id,
                                sequence_number=int(process_info.get('sequence', 1)),
                                process_name=process_info.get('process_name', ''),
                                output_item_id=int(process_info.get('output_product_id', 0)),
                                output_quantity=int(process_info.get('quantity', 0)),
                                quantity_input=int(process_info.get('quantity', 0)),  # Set input quantity
                                rate_per_unit=float(process_info.get('rate_per_unit', 0)),
                                expected_scrap=float(process_info.get('scrap_percent', 0)),  # Use expected_scrap instead of scrap_percentage
                                notes=process_info.get('notes', '')
                            )
                            db.session.add(process)
                except ImportError:
                    # JobWorkProcess model not available, store in notes
                    process_notes = "\nProcess Routing:\n"
                    for i, process_info in enumerate(process_data, 1):
                        process_notes += f"{i}. {process_info.get('process_name', '')} → {process_info.get('quantity', 0)} units"
                        if process_info.get('notes'):
                            process_notes += f" ({process_info.get('notes')})"
                        process_notes += "\n"
                    job.notes = (job.notes or '') + process_notes
            
            db.session.commit()
            
            flash(f'Job Work {job_number} created successfully! Assigned to: {assigned_to_name}', 'success')
            return redirect(url_for('jobwork.list_job_works'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Exception during job work creation: {str(e)}")
            print(f"Exception type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            flash(f'Error creating job work: {str(e)}', 'error')
            return redirect(url_for('jobwork.add_job_work'))
    
    # GET request - show form
    title = "Create New Job Work"
    return render_template('jobwork/form.html', 
                         form=form, 
                         title=title,
                         from_suggestion=from_suggestion,
                         production_id=production_id,
                         suggested_bom_id=suggested_bom_id,
                         suggested_target_item_id=suggested_target_item_id,
                         suggested_quantity=suggested_quantity)

@jobwork_bp.route('/api/generate-job-number')
@login_required
def api_generate_job_number():
    """API endpoint to generate job number"""
    try:
        job_number = generate_job_number()
        return jsonify({'job_number': job_number})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# BOM Integration API Routes
@jobwork_bp.route('/api/bom/<int:bom_id>/materials')
@login_required
def api_bom_materials(bom_id):
    """Get materials for a specific BOM"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        materials = []
        
        for bom_item in bom.items:
            material = bom_item.material or bom_item.item
            if material:
                material_data = {
                    'id': material.id,
                    'material_name': material.name,
                    'material_code': material.code,
                    'qty_required': bom_item.qty_required or bom_item.quantity_required,
                    'uom_name': bom_item.uom.name if bom_item.uom else material.unit_of_measure,
                    'process_step': bom_item.process_step or 1,
                    'process_name': bom_item.process_name,
                    'is_critical': bom_item.is_critical or False,
                    'current_stock': material.total_stock if hasattr(material, 'total_stock') else (material.current_stock or 0),
                    'unit_cost': bom_item.unit_cost or 0.0
                }
                materials.append(material_data)
        
        return jsonify({
            'bom_id': bom_id,
            'bom_code': bom.bom_code,
            'product_name': bom.product.name if bom.product else 'Unknown',
            'materials': materials
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobwork_bp.route('/api/bom/<int:bom_id>/production_check/<int:qty>')
@login_required  
def api_bom_production_check(bom_id, qty):
    """Check if BOM can produce specified quantity"""
    try:
        bom = BOM.query.get_or_404(bom_id)
        can_produce, shortages = bom.can_produce_quantity(qty)
        
        return jsonify({
            'bom_id': bom_id,
            'production_quantity': qty,
            'can_produce': can_produce,
            'shortages': [
                {
                    'material_id': s['material'].id,
                    'material_name': s['material'].name,
                    'material_code': s['material'].code,
                    'required': s['required'],
                    'available': s['available'],
                    'shortage': s['shortage']
                }
                for s in shortages
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobwork_bp.route('/api/bom/<int:bom_id>/details')
@login_required
def api_bom_details(bom_id):
    """Get complete BOM details with processes and material requirements"""
    try:
        from models import BOM, BOMItem, BOMProcess
        bom = BOM.query.get_or_404(bom_id)
        
        # Get BOM materials
        materials = []
        for bom_item in bom.items:
            material = bom_item.material or bom_item.item
            if material:
                materials.append({
                    'id': material.id,
                    'name': material.name,
                    'code': material.code,
                    'qty_required': bom_item.qty_required or bom_item.quantity_required or 0,
                    'unit_cost': bom_item.unit_cost or 0,
                    'uom': bom_item.uom.symbol if bom_item.uom else material.unit_of_measure,
                    'current_stock': material.qty_raw or material.current_stock or 0,
                    'is_critical': getattr(bom_item, 'is_critical', False)
                })
        
        # Get BOM processes
        processes = []
        try:
            bom_processes = BOMProcess.query.filter_by(bom_id=bom_id).order_by(BOMProcess.step_number).all()
            for process in bom_processes:
                processes.append({
                    'id': process.id,
                    'sequence': process.step_number,
                    'name': process.process_name,
                    'output_product_id': getattr(process, 'output_product_id', None),
                    'output_quantity': getattr(process, 'output_quantity', 1),
                    'rate_per_unit': getattr(process, 'rate_per_unit', 0),
                    'estimated_time': getattr(process, 'estimated_time_minutes', 0),
                    'scrap_percent': getattr(process, 'scrap_percent', 0),
                    'work_type': getattr(process, 'work_type', 'in_house'),
                    'supplier_id': getattr(process, 'supplier_id', None)
                })
        except Exception as e:
            print(f"Error loading BOM processes: {e}")
        
        return jsonify({
            'success': True,
            'bom': {
                'id': bom.id,
                'code': bom.bom_code,
                'product_name': bom.product.name if bom.product else 'Unknown',
                'product_id': bom.product_id,
                'output_quantity': bom.output_quantity or 1,
                'labor_cost_per_unit': bom.labor_cost_per_unit or 0,
                'overhead_cost_per_unit': bom.overhead_cost_per_unit or 0,
                'estimated_scrap_percent': bom.estimated_scrap_percent or 0
            },
            'materials': materials,
            'processes': processes
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@jobwork_bp.route('/api/bom/<int:bom_id>/calculate_requirements/<float:output_qty>')
@login_required
def api_bom_calculate_requirements(bom_id, output_qty):
    """Calculate material requirements for specific output quantity"""
    try:
        from models import BOM
        bom = BOM.query.get_or_404(bom_id)
        
        # Calculate conversion factor from BOM's output quantity to requested quantity
        bom_output_qty = bom.output_quantity or 1.0
        conversion_factor = output_qty / bom_output_qty
        
        # Calculate material requirements
        material_requirements = []
        total_material_cost = 0
        
        for bom_item in bom.items:
            material = bom_item.material or bom_item.item
            if material:
                required_qty = (bom_item.qty_required or bom_item.quantity_required or 0) * conversion_factor
                unit_cost = bom_item.unit_cost or 0
                total_cost = required_qty * unit_cost
                total_material_cost += total_cost
                
                material_requirements.append({
                    'material_id': material.id,
                    'material_name': material.name,
                    'material_code': material.code,
                    'required_qty': round(required_qty, 4),
                    'unit_cost': unit_cost,
                    'total_cost': round(total_cost, 2),
                    'uom': bom_item.uom.symbol if bom_item.uom else material.unit_of_measure,
                    'available_stock': material.qty_raw or material.current_stock or 0,
                    'sufficient_stock': (material.qty_raw or material.current_stock or 0) >= required_qty
                })
        
        # Calculate total costs
        labor_cost = (bom.labor_cost_per_unit or 0) * conversion_factor
        overhead_cost = (bom.overhead_cost_per_unit or 0) * conversion_factor
        total_cost = total_material_cost + labor_cost + overhead_cost
        
        return jsonify({
            'success': True,
            'bom_id': bom_id,
            'output_quantity': output_qty,
            'conversion_factor': conversion_factor,
            'material_requirements': material_requirements,
            'costs': {
                'total_material_cost': round(total_material_cost, 2),
                'labor_cost': round(labor_cost, 2),
                'overhead_cost': round(overhead_cost, 2),
                'total_cost': round(total_cost, 2)
            },
            'can_produce': all(req['sufficient_stock'] for req in material_requirements)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Comprehensive Batch Tracking API Endpoints

# This function is handled by the earlier defined api_validate_batch_selection

@jobwork_bp.route('/api/issue-material-with-batches', methods=['POST'])
@login_required
def api_issue_material_with_batches():
    """Issue material from specific batches for job work"""
    try:
        data = request.json
        job_work_id = data.get('job_work_id')
        item_id = data.get('item_id')
        total_quantity = data.get('total_quantity')
        batch_selections = data.get('batch_selections', [])
        process_name = data.get('process_name')
        
        success, message = BatchTracker.issue_material_with_batch_tracking(
            job_work_id, item_id, total_quantity, batch_selections, process_name
        )
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@jobwork_bp.route('/api/receive-material-with-batches', methods=['POST'])
@login_required
def api_receive_material_with_batches():
    """Receive processed material back from job work with batch tracking"""
    try:
        data = request.json
        job_work_id = data.get('job_work_id')
        return_data = data.get('return_data', [])
        
        success, message = BatchTracker.receive_material_with_batch_tracking(
            job_work_id, return_data
        )
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Batch traceability API moved to inventory module to avoid conflicts

@jobwork_bp.route('/api/transfer-batches-between-processes', methods=['POST'])
@login_required
def api_transfer_batches_between_processes():
    """Transfer material between different process stages"""
    try:
        data = request.json
        job_work_id = data.get('job_work_id')
        transfer_data = data.get('transfer_data', [])
        
        success, message = BatchTracker.transfer_batches_between_processes(
            job_work_id, transfer_data
        )
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@jobwork_bp.route('/api/job-work/<int:job_work_id>/batch-status')
@login_required
def api_job_work_batch_status(job_work_id):
    """Get batch status for a specific job work"""
    try:
        job_work_batches = JobWorkBatch.query.filter_by(job_work_id=job_work_id).all()
        
        batch_status = []
        for jwb in job_work_batches:
            input_batch = jwb.input_batch
            output_batch = jwb.output_batch
            
            status_info = {
                'job_work_batch_id': jwb.id,
                'input_batch': {
                    'id': input_batch.id if input_batch else None,
                    'batch_number': input_batch.batch_number if input_batch else None,
                    'item_name': input_batch.item.name if input_batch and input_batch.item else None
                },
                'output_batch': {
                    'id': output_batch.id if output_batch else None,
                    'batch_number': output_batch.batch_number if output_batch else None,
                    'item_name': output_batch.item.name if output_batch and output_batch.item else None
                },
                'process_name': jwb.process_name,
                'quantity_issued': jwb.quantity_issued,
                'quantity_finished': jwb.quantity_finished,
                'quantity_scrap': jwb.quantity_scrap,
                'quantity_unused': jwb.quantity_unused,
                'status': jwb.status,
                'issued_date': jwb.issued_date.isoformat() if jwb.issued_date else None,
                'received_date': jwb.received_date.isoformat() if jwb.received_date else None
            }
            batch_status.append(status_info)
        
        return jsonify({
            'success': True,
            'batch_status': batch_status,
            'total_batches': len(batch_status)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@jobwork_bp.route('/detail/<int:id>')
@login_required
def detail(id):
    """View job work details with team assignments and multi-process information"""
    job = JobWork.query.get_or_404(id)
    
    # Get team assignments if this is a team work
    team_assignments = []
    if job.is_team_work:
        team_assignments = JobWorkTeamAssignment.query.filter_by(job_work_id=id).all()
    
    # Load processes for multi-process job works
    processes = []
    if job.work_type == 'multi_process':
        try:
            from models import JobWorkProcess
            processes = JobWorkProcess.query.filter_by(job_work_id=id).order_by(JobWorkProcess.sequence_number).all()
        except ImportError:
            processes = []
    
    return render_template('jobwork/detail.html', job=job, team_assignments=team_assignments, processes=processes)

@jobwork_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_job_work(id):
    job = JobWork.query.get_or_404(id)
    form = JobWorkForm(obj=job)
    
    # Pre-populate the process_type field since obj=job doesn't handle it correctly
    if job.process:
        form.process_type.data = job.process
    
    if form.validate_on_submit():
        # Check if job number already exists (excluding current job)
        existing_job = JobWork.query.filter(
            JobWork.job_number == form.job_number.data, 
            JobWork.id != id
        ).first()
        if existing_job:
            flash('Job number already exists', 'danger')
            return render_template('jobwork/form.html', form=form, title='Edit Job Work', job=job)
        
        # Handle inventory adjustments if quantity_sent is changed
        old_quantity_sent = job.quantity_sent
        new_quantity_sent = form.quantity_sent.data
        
        if old_quantity_sent != new_quantity_sent:
            item = job.item
            quantity_difference = new_quantity_sent - old_quantity_sent
            
            # Initialize multi-state inventory if not set
            if item.qty_raw is None:
                item.qty_raw = item.current_stock or 0.0
                item.qty_wip = 0.0
                item.qty_finished = 0.0
                item.qty_scrap = 0.0
            
            if quantity_difference > 0:
                # Increasing quantity - need more raw materials
                if (item.qty_raw or 0) < quantity_difference:
                    flash(f'Insufficient raw material for increase. Available: {item.qty_raw or 0} {item.unit_of_measure}', 'danger')
                    from utils.documents import get_documents_for_transaction
                    return render_template('jobwork/form.html', form=form, title='Edit Job Work', job=job, get_documents_for_transaction=get_documents_for_transaction)
                # Move additional materials to WIP
                item.qty_raw -= quantity_difference
                item.qty_wip += quantity_difference
            else:
                # Decreasing quantity - return materials to raw from WIP
                return_quantity = abs(quantity_difference)
                item.qty_wip -= return_quantity
                item.qty_raw += return_quantity
            
            # Update legacy stock
            item.sync_legacy_stock()
        
        job.job_number = form.job_number.data
        job.customer_name = form.customer_name.data
        job.item_id = form.item_id.data
        job.process = form.process_type.data
        job.work_type = form.work_type.data
        job.department = form.department.data if form.work_type.data == 'in_house' else None
        job.quantity_sent = form.quantity_sent.data
        job.expected_finished_material = form.expected_finished_material.data or 0.0
        job.expected_scrap = form.expected_scrap.data or 0.0
        job.rate_per_unit = form.rate_per_unit.data
        job.sent_date = form.sent_date.data
        job.expected_return = form.expected_return.data
        job.notes = form.notes.data
        job.is_team_work = form.is_team_work.data if form.work_type.data == 'in_house' else False
        job.max_team_members = form.max_team_members.data if form.is_team_work.data and form.work_type.data == 'in_house' else 1
        
        db.session.commit()
        
        # Create appropriate success message based on work type
        if form.work_type.data == 'in_house':
            flash(f'Job Work {form.job_number.data} updated successfully for in-house processing in {form.department.data} department.', 'success')
        else:
            flash(f'Job Work {form.job_number.data} updated successfully for {form.customer_name.data}.', 'success')
        
        return redirect(url_for('jobwork.dashboard'))
    
    from utils.documents import get_documents_for_transaction
    return render_template('jobwork/form.html', form=form, title='Edit Job Work', job=job, get_documents_for_transaction=get_documents_for_transaction, original_quantity=job.quantity_sent)

@jobwork_bp.route('/update_status/<int:id>/<status>')
@login_required
def update_status(id, status):
    job = JobWork.query.get_or_404(id)
    
    if status not in ['sent', 'partial_received', 'completed']:
        flash('Invalid status', 'danger')
        return redirect(url_for('jobwork.list_job_works'))
    
    # Special validation for completion status
    if status == 'completed':
        # Check if job has team assignments
        team_assignments = JobWorkTeamAssignment.query.filter_by(job_work_id=id).all()
        
        if team_assignments:
            # For team work, all assignments must be completed
            incomplete_assignments = [a for a in team_assignments if a.status != 'completed']
            
            if incomplete_assignments:
                incomplete_names = [a.member_name for a in incomplete_assignments]
                flash(f'Cannot complete job work. The following team members have not completed their assignments: {", ".join(incomplete_names)}', 'danger')
                return redirect(url_for('jobwork.detail', id=id))
        
        # If no team assignments or all are completed, allow completion
        job.status = status
        job.actual_return = datetime.utcnow()
        flash(f'Job Work {job.job_number} marked as completed successfully!', 'success')
    else:
        # For other statuses, allow direct update
        job.status = status
        flash(f'Job Work status updated to {status}', 'success')
    
    db.session.commit()
    return redirect(url_for('jobwork.list_job_works'))

@jobwork_bp.route('/clear-modal-fix')
def clear_modal_fix():
    """Simple route to clear any stuck modals by redirecting"""
    return render_template('clear_modal.html')

@jobwork_bp.route('/daily-entry-detail/<int:entry_id>')
@login_required
def daily_entry_detail(entry_id):
    """View details of a daily work entry"""
    entry = DailyJobWorkEntry.query.get_or_404(entry_id)
    return render_template('jobwork/daily_entry_detail.html', entry=entry)

@jobwork_bp.route('/edit-daily-entry/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_daily_entry(entry_id):
    """Edit a daily work entry"""
    entry = DailyJobWorkEntry.query.get_or_404(entry_id)
    
    from forms import DailyJobWorkForm
    form = DailyJobWorkForm()
    
    # Get in-house job works for the dropdown
    in_house_jobs = JobWork.query.filter_by(work_type='in_house').all()
    form.job_work_id.choices = [(job.id, f"{job.job_number} - {job.item.name}") for job in in_house_jobs]
    
    if form.validate_on_submit():
        # Get the old assignment progress for rollback if needed
        old_assignment = None
        if entry.job_work.is_team_work:
            old_assignment = JobWorkTeamAssignment.query.filter_by(
                job_work_id=entry.job_work_id,
                member_name=entry.worker_name
            ).first()
            old_progress = old_assignment.progress_percentage if old_assignment else 0
        
        # Update the entry
        entry.job_work_id = form.job_work_id.data
        entry.worker_name = form.worker_name.data
        entry.work_date = form.work_date.data
        entry.hours_worked = form.hours_worked.data
        entry.quantity_completed = form.quantity_completed.data
        entry.scrap_quantity = form.scrap_quantity.data or 0.0
        entry.quality_status = form.quality_status.data
        entry.process_stage = form.process_stage.data
        entry.notes = form.notes.data
        # Update inspection fields
        entry.inspected_quantity = form.inspected_quantity.data or 0.0
        entry.passed_quantity = form.passed_quantity.data or 0.0
        entry.rejected_quantity = form.rejected_quantity.data or 0.0
        entry.rejection_reasons = form.rejection_reasons.data
        
        # Update team assignment progress if this is team work
        if entry.job_work.is_team_work:
            assignment = JobWorkTeamAssignment.query.filter_by(
                job_work_id=entry.job_work_id,
                member_name=entry.worker_name
            ).first()
            
            if assignment:
                # Calculate total completed quantity for this worker
                total_completed = db.session.query(func.sum(DailyJobWorkEntry.quantity_completed)).filter_by(
                    job_work_id=entry.job_work_id,
                    worker_name=entry.worker_name
                ).scalar() or 0
                
                # Update progress percentage
                if assignment.assigned_quantity > 0:
                    new_progress = min(100, (total_completed / assignment.assigned_quantity) * 100)
                    assignment.progress_percentage = new_progress
                    assignment.status = 'completed' if new_progress >= 100 else 'in_progress'
        
        db.session.commit()
        
        # Check if job should be auto-completed
        if entry.job_work.is_team_work:
            entry.job_work.check_and_update_completion_status()
            db.session.commit()
        
        flash('Daily work entry updated successfully!', 'success')
        return redirect(url_for('jobwork.daily_entries_list'))
    
    # Pre-populate form with existing data
    if request.method == 'GET':
        form.job_work_id.data = entry.job_work_id
        form.worker_name.data = entry.worker_name
        form.work_date.data = entry.work_date
        form.hours_worked.data = entry.hours_worked
        form.quantity_completed.data = entry.quantity_completed
        form.scrap_quantity.data = entry.scrap_quantity
        form.quality_status.data = entry.quality_status
        form.process_stage.data = entry.process_stage
        form.notes.data = entry.notes
        # Pre-populate inspection fields
        form.inspected_quantity.data = entry.inspected_quantity
        form.passed_quantity.data = entry.passed_quantity
        form.rejected_quantity.data = entry.rejected_quantity
        form.rejection_reasons.data = entry.rejection_reasons
    
    return render_template('jobwork/edit_daily_entry_form.html', form=form, entry=entry)

@jobwork_bp.route('/update-team-progress/<int:job_id>')
@login_required
def update_team_progress(job_id):
    """Update progress for all team assignments based on daily work entries"""
    job_work = JobWork.query.get_or_404(job_id)
    
    if not job_work.is_team_work:
        flash('This job work is not configured for team assignments.', 'warning')
        return redirect(url_for('jobwork.detail', id=job_id))
    
    assignments = JobWorkTeamAssignment.query.filter_by(job_work_id=job_id).all()
    updated_count = 0
    
    for assignment in assignments:
        old_percentage = assignment.completion_percentage
        assignment.update_progress_from_daily_entries()
        
        if assignment.completion_percentage != old_percentage:
            updated_count += 1
    
    # Check if job work can be completed
    job_work.check_and_update_completion_status()
    db.session.commit()
    
    if updated_count > 0:
        flash(f'Progress updated for {updated_count} team assignments based on daily work entries.', 'success')
    else:
        flash('No progress updates were needed. All assignments are up to date.', 'info')
    
    return redirect(url_for('jobwork.team_assignments', id=job_id))

@jobwork_bp.route('/validate-and-fix-completion/<int:job_id>')
@login_required
def validate_and_fix_completion(job_id):
    """Validate job completion status against team assignments and fix if needed"""
    job = JobWork.query.get_or_404(job_id)
    
    # Check if job is marked as completed
    if job.status == 'completed':
        # Check team assignments
        team_assignments = JobWorkTeamAssignment.query.filter_by(job_work_id=job_id).all()
        
        if team_assignments:
            # Check if all team members are actually completed
            incomplete_assignments = [a for a in team_assignments if a.status != 'completed']
            
            if incomplete_assignments:
                # Job was incorrectly marked as completed - revert it
                job.status = 'in_progress'
                job.actual_return = None
                db.session.commit()
                
                incomplete_names = [a.member_name for a in incomplete_assignments]
                flash(f'Job Work status corrected to "In Progress". Team members still working: {", ".join(incomplete_names)}', 'warning')
                return redirect(url_for('jobwork.detail', id=job_id))
    
    flash('Job Work status is correct based on team assignment completion.', 'info')
    return redirect(url_for('jobwork.detail', id=job_id))

@jobwork_bp.route('/update_quantity/<int:id>', methods=['GET', 'POST'])
@login_required
def update_quantity(id):
    job = JobWork.query.get_or_404(id)
    form = JobWorkQuantityUpdateForm(job=job)
    
    if form.validate_on_submit():
        # Update quantity received
        additional_received = form.quantity_received.data
        job.quantity_received += additional_received
        job.received_date = form.received_date.data
        
        # Add received quantity back to inventory
        item = job.item
        item.current_stock = (item.current_stock or 0) + additional_received
        
        # Update notes
        if form.notes.data:
            if job.notes:
                job.notes += f"\n\n[{form.received_date.data.strftime('%m/%d/%Y')}] Received: {additional_received} {item.unit_of_measure}. {form.notes.data}"
            else:
                job.notes = f"[{form.received_date.data.strftime('%m/%d/%Y')}] Received: {additional_received} {item.unit_of_measure}. {form.notes.data}"
        else:
            if job.notes:
                job.notes += f"\n\n[{form.received_date.data.strftime('%m/%d/%Y')}] Received: {additional_received} {item.unit_of_measure}"
            else:
                job.notes = f"[{form.received_date.data.strftime('%m/%d/%Y')}] Received: {additional_received} {item.unit_of_measure}"
        
        # Update status based on quantity received
        if job.quantity_received >= job.quantity_sent:
            job.status = 'completed'
            job.quantity_received = job.quantity_sent  # Ensure we don't exceed sent quantity
        elif job.quantity_received > 0:
            job.status = 'partial_received'
        
        db.session.commit()
        flash(f'Quantity updated successfully. Received: {additional_received} {job.item.unit_of_measure}', 'success')
        return redirect(url_for('jobwork.list_job_works'))
    
    return render_template('jobwork/update_quantity.html', form=form, job=job, title='Update Quantity')

@jobwork_bp.route('/send/<int:job_id>', methods=['GET', 'POST'])
@login_required
def send_job_work(job_id):
    job = JobWork.query.get_or_404(job_id)
    
    if request.method == 'POST':
        send_type = request.form.get('send_type')
        recipient = request.form.get('recipient')
        message = request.form.get('message', '')
        
        # Get company info for email
        company = CompanySettings.query.first()
        
        # Create Job Work summary for message
        job_summary = f"""
Job Work Order: {job.job_number}
Customer: {job.customer_name}
Item: {job.item.name}
Quantity Sent: {job.quantity_sent} {job.item.unit_of_measure}
Rate per Unit: ₹{job.rate_per_unit:.2f}
Total Value: ₹{job.quantity_sent * job.rate_per_unit:.2f}
Sent Date: {job.sent_date}
Expected Return: {job.expected_return or 'Not specified'}

{message}
"""
        
        success = False
        if send_type == 'email':
            subject = f"Job Work Order {job.job_number} - {company.company_name if company else 'AK Innovations'}"
            
            # Generate PDF attachment for Job Work
            from weasyprint import HTML, CSS
            from flask import render_template_string
            
            # Create a simple Job Work PDF template
            job_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Job Work Order - {job.job_number}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .header {{ text-align: center; margin-bottom: 30px; }}
                    .details {{ margin-bottom: 20px; }}
                    .details th, .details td {{ padding: 8px; text-align: left; }}
                    table {{ width: 100%; border-collapse: collapse; }}
                    th, td {{ border: 1px solid #ddd; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>{company.company_name if company else 'AK Innovations'}</h2>
                    <h3>Job Work Order</h3>
                </div>
                <table class="details">
                    <tr><th>Job Number:</th><td>{job.job_number}</td></tr>
                    <tr><th>Customer:</th><td>{job.customer_name}</td></tr>
                    <tr><th>Item:</th><td>{job.item.name}</td></tr>
                    <tr><th>Quantity Sent:</th><td>{job.quantity_sent} {job.item.unit_of_measure}</td></tr>
                    <tr><th>Rate per Unit:</th><td>₹{job.rate_per_unit:.2f}</td></tr>
                    <tr><th>Total Value:</th><td>₹{job.quantity_sent * job.rate_per_unit:.2f}</td></tr>
                    <tr><th>Sent Date:</th><td>{job.sent_date}</td></tr>
                    <tr><th>Expected Return:</th><td>{job.expected_return or 'Not specified'}</td></tr>
                </table>
            </body>
            </html>
            """
            
            # Convert to PDF
            pdf_bytes = HTML(string=job_html, base_url=request.url_root).write_pdf()
            
            # Send email with PDF attachment
            success = send_email_with_attachment(
                recipient, 
                subject, 
                job_summary,
                pdf_bytes,
                f"JobWork_{job.job_number}.pdf"
            )
        elif send_type == 'whatsapp':
            success = send_whatsapp_notification(recipient, job_summary)
        
        if success:
            flash(f'Job Work order sent successfully via {send_type.title()}!', 'success')
        else:
            flash(f'Failed to send Job Work order via {send_type.title()}. Please check your notification settings.', 'danger')
        
        return redirect(url_for('jobwork.list_job_works'))
    
    return render_template('jobwork/send.html', job=job, title=f'Send Job Work {job.job_number}')

# BOM rate auto-filling API removed as requested - users will manually enter rates

@jobwork_bp.route('/daily-entry', methods=['GET', 'POST'])
@login_required
def daily_job_work_entry():
    """Streamlined daily job work entry for workers"""
    form = DailyJobWorkForm()
    
    if form.validate_on_submit():
        # Check if entry already exists for this worker/job/date
        existing_entry = DailyJobWorkEntry.query.filter_by(
            job_work_id=form.job_work_id.data,
            worker_name=form.worker_name.data,
            work_date=form.work_date.data
        ).first()
        
        if existing_entry:
            flash(f'Daily entry already exists for {form.worker_name.data} on {form.work_date.data}. Please edit the existing entry or use a different date.', 'warning')
            return render_template('jobwork/daily_entry_form.html', form=form, title='Daily Job Work Entry')
        
        # Create new daily entry
        daily_entry = DailyJobWorkEntry(
            job_work_id=form.job_work_id.data,
            worker_name=form.worker_name.data,
            work_date=form.work_date.data,
            hours_worked=form.hours_worked.data,
            quantity_completed=form.quantity_completed.data,
            scrap_quantity=form.scrap_quantity.data or 0.0,
            quality_status=form.quality_status.data,
            process_stage=form.process_stage.data,
            notes=form.notes.data,
            logged_by=current_user.id,
            # Add inspection fields
            inspected_quantity=form.inspected_quantity.data or 0.0,
            passed_quantity=form.passed_quantity.data or 0.0,
            rejected_quantity=form.rejected_quantity.data or 0.0,
            rejection_reasons=form.rejection_reasons.data
        )
        
        db.session.add(daily_entry)
        db.session.commit()
        
        # Get job work details for further processing
        job_work = JobWork.query.get(form.job_work_id.data)
        
        # For in-house job works, automatically update inventory based on daily entries
        if job_work and job_work.work_type == 'in_house':
            try:
                # Update inventory with completed quantity (add finished goods back to stock)
                if form.quantity_completed.data > 0:
                    job_work.item.current_stock += form.quantity_completed.data
                    
                    # Log inventory movement
                    inventory_note = f"In-house job work completion: {form.quantity_completed.data} {job_work.item.unit_of_measure} added from {job_work.job_number} by {form.worker_name.data}"
                    if job_work.notes:
                        job_work.notes += f"\n{inventory_note}"
                    else:
                        job_work.notes = inventory_note
                
                # Handle scrap quantity (if any) - could be logged for reporting but not added to inventory
                if form.scrap_quantity.data and form.scrap_quantity.data > 0:
                    scrap_note = f"Scrap generated: {form.scrap_quantity.data} {job_work.item.unit_of_measure} on {form.work_date.data} by {form.worker_name.data}"
                    if job_work.notes:
                        job_work.notes += f"\n{scrap_note}"
                    else:
                        job_work.notes = scrap_note
                
                db.session.commit()
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating inventory: {str(e)}', 'danger')
                return render_template('jobwork/daily_entry_form.html', form=form, title='Daily Job Work Entry')
        
        # Update team assignment progress automatically
        if job_work and job_work.is_team_work:
            # Find the team assignment for this worker
            employee = Employee.query.filter_by(name=form.worker_name.data).first()
            if employee:
                assignment = JobWorkTeamAssignment.query.filter_by(
                    job_work_id=job_work.id,
                    employee_id=employee.id
                ).first()
                if assignment:
                    assignment.update_progress_from_daily_entries()
                    db.session.commit()
                    
                    # Check if job work can be marked as completed
                    job_work.check_and_update_completion_status()
                    db.session.commit()
        
        success_message = f'Daily work logged successfully for {form.worker_name.data} on {job_work.job_number}!'
        if job_work.work_type == 'in_house' and form.quantity_completed.data > 0:
            success_message += f' Inventory updated: +{form.quantity_completed.data} {job_work.item.unit_of_measure} added to stock.'
        
        flash(success_message, 'success')
        return redirect(url_for('jobwork.daily_entries_list'))
    
    return render_template('jobwork/daily_entry_form.html', form=form, title='Daily Job Work Entry')

@jobwork_bp.route('/daily-entries')
@login_required
def daily_entries_list():
    """List all daily job work entries with filtering"""
    page = request.args.get('page', 1, type=int)
    worker_name = request.args.get('worker_name', '', type=str)
    job_work_id = request.args.get('job_work_id', None, type=int)
    date_from = request.args.get('date_from', '', type=str)
    date_to = request.args.get('date_to', '', type=str)
    
    # Build query
    query = DailyJobWorkEntry.query.join(JobWork)
    
    if worker_name:
        query = query.filter(DailyJobWorkEntry.worker_name.ilike(f'%{worker_name}%'))
    
    if job_work_id:
        query = query.filter(DailyJobWorkEntry.job_work_id == job_work_id)
    
    if date_from:
        try:
            from datetime import datetime
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(DailyJobWorkEntry.work_date >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(DailyJobWorkEntry.work_date <= to_date)
        except ValueError:
            pass
    
    entries = query.order_by(DailyJobWorkEntry.work_date.desc(), DailyJobWorkEntry.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    # Get active job works for filter dropdown
    active_jobs = JobWork.query.filter(JobWork.status.in_(['sent', 'partial_received'])).order_by(JobWork.job_number).all()
    
    return render_template('jobwork/daily_entries_list.html', 
                         entries=entries,
                         active_jobs=active_jobs,
                         worker_name=worker_name,
                         job_work_id=job_work_id,
                         date_from=date_from,
                         date_to=date_to)

@jobwork_bp.route('/team-assignments/<int:job_id>')
@login_required
def team_assignments(job_id):
    """View and manage team assignments for a job work"""
    job = JobWork.query.get_or_404(job_id)
    
    # Check if this is a team work job
    if not job.is_team_work:
        flash('This job work is not configured for team assignments.', 'warning')
        return redirect(url_for('jobwork.detail', id=job_id))
    
    # Get existing team assignments
    assignments = JobWorkTeamAssignment.query.filter_by(job_work_id=job_id).all()
    
    # Get available employees for assignment
    available_employees = Employee.query.filter_by(is_active=True).all()
    
    return render_template('jobwork/team_assignments.html', 
                         job=job, 
                         assignments=assignments,
                         available_employees=available_employees)

@jobwork_bp.route('/assign-team-member/<int:job_id>', methods=['GET', 'POST'])
@login_required  
def assign_team_member(job_id):
    """Assign a team member to a job work"""
    job = JobWork.query.get_or_404(job_id)
    
    # Check if this is a team work job
    if not job.is_team_work:
        flash('This job work is not configured for team assignments.', 'warning')
        return redirect(url_for('jobwork.detail', id=job_id))
    
    # Check if we've reached max team members
    current_assignments = JobWorkTeamAssignment.query.filter_by(job_work_id=job_id).count()
    if current_assignments >= job.max_team_members:
        flash(f'Maximum team members ({job.max_team_members}) already assigned to this job.', 'warning')
        return redirect(url_for('jobwork.team_assignments', job_id=job_id))
    
    form = JobWorkTeamAssignmentForm()
    
    # Filter out already assigned employees
    assigned_employee_ids = [a.employee_id for a in JobWorkTeamAssignment.query.filter_by(job_work_id=job_id).all()]
    available_employees = Employee.query.filter(
        Employee.is_active == True,
        ~Employee.id.in_(assigned_employee_ids)
    ).all()
    
    form.employee_id.choices = [(emp.id, f"{emp.name} ({emp.employee_code})") for emp in available_employees]
    
    if form.validate_on_submit():
        # Check if employee is already assigned
        existing_assignment = JobWorkTeamAssignment.query.filter_by(
            job_work_id=job_id,
            employee_id=form.employee_id.data
        ).first()
        
        if existing_assignment:
            flash('This employee is already assigned to this job work.', 'warning')
            return redirect(url_for('jobwork.team_assignments', job_id=job_id))
        
        # Get the selected employee
        employee = Employee.query.get(form.employee_id.data)
        
        # Create new team assignment
        assignment = JobWorkTeamAssignment(
            job_work_id=job_id,
            employee_id=form.employee_id.data,
            member_name=employee.name,  # Populate from employee
            assigned_quantity=form.assigned_quantity.data,
            estimated_hours=form.estimated_hours.data,
            member_role=form.member_role.data,
            start_date=form.start_date.data,
            target_completion=form.target_completion.data,
            status='assigned',
            notes=form.notes.data,
            assigned_by=current_user.id
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        flash(f'Successfully assigned {employee.name} to job work {job.job_number}!', 'success')
        return redirect(url_for('jobwork.team_assignments', job_id=job_id))
    
    return render_template('jobwork/assign_team_member.html', 
                         form=form, 
                         job=job,
                         available_count=len(available_employees))

@jobwork_bp.route('/update-team-assignment/<int:assignment_id>', methods=['POST'])
@login_required
def update_team_assignment(assignment_id):
    """Update team assignment progress with automatic completion"""
    assignment = JobWorkTeamAssignment.query.get_or_404(assignment_id)
    
    try:
        data = request.get_json()
        if 'completed_quantity' in data:
            completed_qty = float(data['completed_quantity'])
            # Calculate completion percentage based on completed quantity
            assignment.completion_percentage = (completed_qty / assignment.assigned_quantity * 100) if assignment.assigned_quantity > 0 else 0
            
            # Auto-complete when reaching 100%
            if assignment.completion_percentage >= 100:
                assignment.status = 'completed'
                assignment.completion_date = datetime.utcnow()
                flash(f'{assignment.member_name} has completed their assignment (100%)!', 'success')
            
        if 'status' in data:
            assignment.status = data['status']
            if data['status'] == 'completed':
                assignment.completion_date = datetime.utcnow()
        
        assignment.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Check if all team members are completed
        job_work = assignment.job_work
        all_assignments = JobWorkTeamAssignment.query.filter_by(job_work_id=job_work.id).all()
        all_completed = all(a.status == 'completed' for a in all_assignments)
        
        if all_completed and job_work.status != 'completed':
            job_work.status = 'completed'
            job_work.actual_return = datetime.utcnow()
            db.session.commit()
            flash(f'Job Work {job_work.job_number} automatically completed - all team members finished!', 'info')
        
        return jsonify({'success': True, 'message': 'Assignment updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@jobwork_bp.route('/update-assigned-quantity/<int:assignment_id>', methods=['POST'])
@login_required
def update_assigned_quantity(assignment_id):
    """Update the assigned quantity for a team member"""
    assignment = JobWorkTeamAssignment.query.get_or_404(assignment_id)
    
    try:
        data = request.get_json()
        new_assigned_qty = float(data['assigned_quantity'])
        
        if new_assigned_qty <= 0:
            return jsonify({'success': False, 'message': 'Assigned quantity must be greater than 0'}), 400
        
        old_assigned_qty = assignment.assigned_quantity
        assignment.assigned_quantity = new_assigned_qty
        
        # Recalculate completion percentage based on new assigned quantity
        # Get total completed quantity from daily entries for this worker
        total_completed = db.session.query(func.sum(DailyJobWorkEntry.quantity_completed)).filter_by(
            job_work_id=assignment.job_work_id,
            worker_name=assignment.member_name
        ).scalar() or 0
        
        # Update progress percentage based on new assigned quantity
        if new_assigned_qty > 0:
            assignment.progress_percentage = min(100, (total_completed / new_assigned_qty) * 100)
            assignment.completion_percentage = assignment.progress_percentage
            
            # Update status based on new progress
            if assignment.progress_percentage >= 100:
                assignment.status = 'completed'
                assignment.completion_date = datetime.utcnow()
            elif assignment.progress_percentage > 0:
                assignment.status = 'in_progress'
            else:
                assignment.status = 'assigned'
        
        assignment.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Check if job work completion status needs updating
        job_work = assignment.job_work
        job_work.check_and_update_completion_status()
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Assigned quantity updated from {old_assigned_qty} to {new_assigned_qty}',
            'new_progress': assignment.progress_percentage
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@jobwork_bp.route('/remove-team-assignment/<int:assignment_id>')
@login_required
def remove_team_assignment(assignment_id):
    """Remove a team member from job work"""
    assignment = JobWorkTeamAssignment.query.get_or_404(assignment_id)
    job_id = assignment.job_work_id
    employee_name = assignment.employee.name
    
    db.session.delete(assignment)
    db.session.commit()
    
    flash(f'Removed {employee_name} from team assignment.', 'success')
    return redirect(url_for('jobwork.team_assignments', job_id=job_id))

@jobwork_bp.route('/worker-productivity')
@login_required
def worker_productivity():
    """Daily worker productivity tracking dashboard"""
    from sqlalchemy import desc, and_
    from datetime import date, timedelta
    
    # Get date filter parameters
    date_from = request.args.get('date_from', '', type=str)
    date_to = request.args.get('date_to', '', type=str)
    worker_filter = request.args.get('worker_name', '', type=str)
    
    # Set default date range (last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    if date_from:
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to:
        try:
            end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Build query for daily entries within date range
    query = DailyJobWorkEntry.query.filter(
        and_(
            DailyJobWorkEntry.work_date >= start_date,
            DailyJobWorkEntry.work_date <= end_date
        )
    )
    
    if worker_filter:
        query = query.filter(DailyJobWorkEntry.worker_name.ilike(f'%{worker_filter}%'))
    
    daily_entries = query.all()
    
    # Calculate productivity metrics per worker
    worker_productivity = {}
    for entry in daily_entries:
        worker = entry.worker_name
        if worker not in worker_productivity:
            worker_productivity[worker] = {
                'total_hours': 0,
                'total_quantity': 0,
                'total_days': 0,
                'job_works': set(),
                'entries': [],
                'avg_quality_score': 0,
                'good_quality_count': 0,
                'needs_rework_count': 0,
                'defective_count': 0
            }
        
        worker_productivity[worker]['total_hours'] += entry.hours_worked
        worker_productivity[worker]['total_quantity'] += entry.quantity_completed
        worker_productivity[worker]['job_works'].add(entry.job_work.job_number)
        worker_productivity[worker]['entries'].append(entry)
        
        # Track quality metrics
        if entry.quality_status == 'good':
            worker_productivity[worker]['good_quality_count'] += 1
        elif entry.quality_status == 'needs_rework':
            worker_productivity[worker]['needs_rework_count'] += 1
        elif entry.quality_status == 'defective':
            worker_productivity[worker]['defective_count'] += 1
    
    # Calculate derived metrics
    for worker, data in worker_productivity.items():
        data['total_days'] = len(set(entry.work_date for entry in data['entries']))
        data['avg_hours_per_day'] = data['total_hours'] / data['total_days'] if data['total_days'] > 0 else 0
        data['productivity_rate'] = data['total_quantity'] / data['total_hours'] if data['total_hours'] > 0 else 0
        data['job_works'] = list(data['job_works'])
        
        # Calculate quality score (percentage of good quality work)
        total_entries = len(data['entries'])
        data['quality_score'] = (data['good_quality_count'] / total_entries * 100) if total_entries > 0 else 0
    
    # Sort workers by productivity rate
    sorted_workers = sorted(worker_productivity.items(), key=lambda x: x[1]['productivity_rate'], reverse=True)
    
    # Get unique worker names for filter
    all_workers = db.session.query(DailyJobWorkEntry.worker_name).distinct().all()
    worker_names = [w[0] for w in all_workers]
    
    return render_template('jobwork/worker_productivity.html', 
                         worker_productivity=sorted_workers,
                         worker_names=worker_names,
                         date_from=date_from or start_date.strftime('%Y-%m-%d'),
                         date_to=date_to or end_date.strftime('%Y-%m-%d'),
                         worker_filter=worker_filter,
                         total_workers=len(sorted_workers))

@jobwork_bp.route('/api/job-work/<int:job_id>/team-assignments')
@login_required
def get_job_team_assignments(job_id):
    """API endpoint to get team assignments for a job work"""
    job = JobWork.query.get_or_404(job_id)
    
    # Get team assignments for this job
    assignments = JobWorkTeamAssignment.query.filter_by(job_work_id=job_id).all()
    
    team_data = []
    for assignment in assignments:
        team_data.append({
            'id': assignment.id,
            'employee_id': assignment.employee_id,
            'member_name': assignment.member_name,
            'assigned_quantity': float(assignment.assigned_quantity),
            'completion_percentage': float(assignment.completion_percentage),
            'status': assignment.status,
            'member_role': assignment.member_role,
            'employee_code': assignment.employee.employee_code if assignment.employee else 'N/A'
        })
    
    return jsonify({
        'success': True,
        'job_number': job.job_number,
        'item_name': job.item.name,
        'unit_of_measure': job.item.unit_of_measure,
        'is_team_work': job.is_team_work,
        'team_assignments': team_data,
        'job_id': job_id
    })

@jobwork_bp.route('/api/quick-assign-worker', methods=['POST'])
@login_required
def quick_assign_worker():
    """Quick API to assign a worker to a job work from daily entry form"""
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        worker_name = data.get('worker_name')
        worker_role = data.get('worker_role', 'Worker')
        assigned_quantity = data.get('assigned_quantity', 1.0)
        
        if not job_id or not worker_name:
            return jsonify({'success': False, 'message': 'Job ID and worker name are required'}), 400
        
        job = JobWork.query.get_or_404(job_id)
        
        # Check if worker is already assigned
        existing_assignment = JobWorkTeamAssignment.query.filter_by(
            job_work_id=job_id,
            member_name=worker_name
        ).first()
        
        if existing_assignment:
            return jsonify({'success': False, 'message': f'{worker_name} is already assigned to this job'}), 400
        
        # Find employee by name if exists
        employee = Employee.query.filter(Employee.name.ilike(f'%{worker_name}%')).first()
        
        # Create new assignment
        assignment = JobWorkTeamAssignment(
            job_work_id=job_id,
            employee_id=employee.id if employee else None,
            member_name=worker_name,
            assigned_quantity=assigned_quantity,
            estimated_hours=8.0,  # Default 8 hours
            member_role=worker_role,
            start_date=datetime.utcnow().date(),
            target_completion=job.expected_return,
            status='assigned',
            notes=f'Quick assignment from daily entry form',
            assigned_by=current_user.id
        )
        
        # Mark job as team work if not already
        if not job.is_team_work:
            job.is_team_work = True
            job.max_team_members = max(job.max_team_members or 1, 2)
        
        db.session.add(assignment)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{worker_name} assigned successfully to {job.job_number}',
            'assignment_id': assignment.id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@jobwork_bp.route('/sync-quantities')
@login_required
def sync_all_quantities():
    """Admin utility to sync all job work quantities with inspection data"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('jobwork.dashboard'))
    
    corrected_jobs = []
    total_jobs = JobWork.query.count()
    
    for job in JobWork.query.all():
        if job.sync_quantity_received():
            corrected_jobs.append(job.job_number)
    
    if corrected_jobs:
        db.session.commit()
        flash(f'Corrected quantity mismatches for {len(corrected_jobs)} jobs: {", ".join(corrected_jobs)}', 'success')
    else:
        flash(f'All {total_jobs} job work quantities are accurate. No corrections needed.', 'info')
    
    return redirect(url_for('jobwork.dashboard'))

@jobwork_bp.route('/cancel/<int:job_id>', methods=['POST'])
@login_required
def cancel_job_work(job_id):
    """Cancel a job work (mark as cancelled but preserve record)"""
    try:
        job = JobWork.query.get_or_404(job_id)
        
        # Only allow cancelling jobs that are sent or partially received
        if job.status not in ['sent', 'partial_received']:
            return jsonify({
                'success': False, 
                'message': f'Cannot cancel job work with status: {job.status}'
            }), 400
        
        # Check if user can cancel this job (admin or creator)
        if not current_user.is_admin() and job.created_by != current_user.id:
            return jsonify({
                'success': False, 
                'message': 'You can only cancel job works you created'
            }), 403
        
        # Update status to cancelled
        old_status = job.status
        job.status = 'cancelled'
        
        # If materials were moved to WIP, return them to raw materials
        if job.item and hasattr(job.item, 'qty_wip') and job.item.qty_wip >= job.quantity_sent:
            # Move materials back from WIP to Raw
            job.item.qty_wip = (job.item.qty_wip or 0) - job.quantity_sent
            job.item.qty_raw = (job.item.qty_raw or 0) + job.quantity_sent
        
        # Add cancellation note
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cancellation_note = f"\n[CANCELLED {current_time}] Job work cancelled by {current_user.username}. Previous status: {old_status}"
        job.notes = (job.notes or '') + cancellation_note
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Job work {job.job_number} has been cancelled successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': f'Error cancelling job work: {str(e)}'
        }), 500

@jobwork_bp.route('/delete/<int:job_id>', methods=['GET', 'DELETE'])
@login_required
def delete_job_work(job_id):
    """Permanently delete a job work and all related data"""
    try:
        job = JobWork.query.get_or_404(job_id)
        
        # Only admin can delete job works
        if not current_user.is_admin():
            if request.method == 'GET':
                flash('Only administrators can delete job works', 'error')
                return redirect(url_for('jobwork.list_job_works'))
            return jsonify({
                'success': False, 
                'message': 'Only administrators can delete job works'
            }), 403
        
        job_number = job.job_number
        
        # If materials are in WIP, return them to raw materials
        if job.item and hasattr(job.item, 'qty_wip') and job.item.qty_wip >= job.quantity_sent:
            job.item.qty_wip = (job.item.qty_wip or 0) - job.quantity_sent
            job.item.qty_raw = (job.item.qty_raw or 0) + job.quantity_sent
        
        # Delete related records (cascading should handle most, but let's be explicit)
        from models.grn import GRN, GRNLineItem
        from models import MaterialInspection, DailyJobWorkEntry, JobWorkTeamAssignment
        
        # Delete GRN line items first
        grns = GRN.query.filter_by(job_work_id=job_id).all()
        for grn in grns:
            GRNLineItem.query.filter_by(grn_id=grn.id).delete()
            db.session.delete(grn)
        
        # Delete material inspections
        MaterialInspection.query.filter_by(job_work_id=job_id).delete()
        
        # Delete daily work entries
        DailyJobWorkEntry.query.filter_by(job_work_id=job_id).delete()
        
        # Delete team assignments
        JobWorkTeamAssignment.query.filter_by(job_work_id=job_id).delete()
        
        # Delete job work processes (for multi-process jobs)
        try:
            from models import JobWorkProcess
            JobWorkProcess.query.filter_by(job_work_id=job_id).delete()
        except ImportError:
            pass  # Model might not exist in all versions
        
        # Finally delete the main job work record
        db.session.delete(job)
        db.session.commit()
        
        if request.method == 'GET':
            flash(f'Job work {job_number} has been permanently deleted', 'success')
            return redirect(url_for('jobwork.list_job_works'))
        
        return jsonify({
            'success': True, 
            'message': f'Job work {job_number} has been permanently deleted'
        })
        
    except Exception as e:
        db.session.rollback()
        if request.method == 'GET':
            flash(f'Error deleting job work: {str(e)}', 'error')
            return redirect(url_for('jobwork.list_job_works'))
        return jsonify({
            'success': False, 
            'message': f'Error deleting job work: {str(e)}'
        }), 500

@jobwork_bp.route('/generate-challan/<int:job_id>')
@login_required
def generate_challan(job_id):
    """Generate Job Work Challan PDF"""
    from flask import make_response
    job = JobWork.query.get_or_404(job_id)
    
    # Get company settings for sender information
    company_settings = CompanySettings.query.first()
    
    # Get job work processes if it's a multi-process job
    processes = []
    try:
        from models import JobWorkProcess
        processes = JobWorkProcess.query.filter_by(job_work_id=job_id).order_by(JobWorkProcess.sequence_number).all()
    except ImportError:
        pass
    
    return render_template('jobwork/challan.html', 
                         job=job, 
                         company_settings=company_settings,
                         processes=processes)

# Batch Tracking API Endpoints
@jobwork_bp.route('/api/batches/by-item/<int:item_id>')
@login_required
def get_batches_by_item(item_id):
    """Get available batches for a specific item"""
    try:
        # Filter batches with available quantities (raw + finished)
        batches = ItemBatch.query.filter_by(item_id=item_id).all()
        
        # Filter batches with available quantity using Python (since available_quantity is a property)
        available_batches = [batch for batch in batches if batch.available_quantity > 0]
        
        batch_data = []
        for batch in available_batches:
            # Debug batch quantities
            print(f"Batch {batch.batch_number}: raw={batch.qty_raw}, finished={batch.qty_finished}, available={batch.available_quantity}")
            
            batch_data.append({
                'id': batch.id,
                'batch_number': batch.batch_number,
                'qty_available': batch.available_quantity,  # Use property
                'available_quantity': batch.available_quantity,  # Duplicate for compatibility
                'qty_raw': batch.qty_raw or 0,
                'qty_finished': batch.qty_finished or 0,
                'manufacture_date': batch.manufacture_date.isoformat() if batch.manufacture_date else None,
                'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
                'quality_status': batch.quality_status or 'good',
                'storage_location': batch.storage_location or 'Default'
            })
        
        return jsonify({
            'success': True,
            'batches': batch_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching batches: {str(e)}'
        }), 500

@jobwork_bp.route('/api/batch/<int:batch_id>/details')
@login_required
def get_batch_details(batch_id):
    """Get detailed information about a specific batch"""
    try:
        batch = ItemBatch.query.get_or_404(batch_id)
        
        return jsonify({
            'success': True,
            'batch': {
                'id': batch.id,
                'batch_number': batch.batch_number,
                'item_id': batch.item_id,
                'item_name': batch.item.name if batch.item else 'Unknown',
                'qty_available': batch.available_quantity,  # Use property
                'qty_total': batch.total_quantity,  # Use property
                'manufacture_date': batch.manufacture_date.isoformat() if batch.manufacture_date else None,
                'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
                'quality_status': batch.quality_status or 'good',
                'storage_location': batch.storage_location or 'Default',
                'supplier_batch': batch.supplier_batch or '',
                'purchase_rate': float(batch.purchase_rate) if batch.purchase_rate else 0.0
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching batch details: {str(e)}'
        }), 500

@jobwork_bp.route('/batch-return', methods=['GET', 'POST'])
@login_required
def batch_return():
    """Process job work batch returns"""
    form = JobWorkBatchReturnForm()
    
    if form.validate_on_submit():
        try:
            # Get the batch record
            batch_record = JobWorkBatch.query.get_or_404(form.batch_record_id.data)
            
            # Validate quantities
            total_processed = form.quantity_finished.data + form.quantity_scrap.data + form.quantity_returned_unused.data
            if total_processed > batch_record.quantity_issued:
                flash('Total processed quantity cannot exceed issued quantity', 'error')
                return render_template('jobwork/batch_return.html', form=form)
            
            # Complete the return process
            success, message = batch_record.complete_return(
                form.quantity_finished.data,
                form.quantity_scrap.data,
                form.quantity_returned_unused.data,
                form.output_batch_code.data,
                form.qc_notes.data
            )
            
            if success:
                # Update additional fields
                batch_record.quality_status = form.quality_status.data
                batch_record.inspected_by = current_user.id
                batch_record.inspected_at = datetime.utcnow()
                
                # Add return notes to batch
                if form.return_notes.data:
                    batch_record.batch_notes = (batch_record.batch_notes or '') + f"\nReturn Notes: {form.return_notes.data}"
                
                db.session.commit()
                flash(f'Batch return processed successfully. {message}', 'success')
                return redirect(url_for('jobwork.batch_tracking'))
            else:
                flash(f'Error processing batch return: {message}', 'error')
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing batch return: {str(e)}', 'error')
    
    return render_template('jobwork/batch_return.html', form=form)

@jobwork_bp.route('/api/job-work/<int:job_work_id>/batches')
@login_required
def get_job_work_batches(job_work_id):
    """Get batch records for a specific job work"""
    try:
        batches = JobWorkBatch.query.filter_by(job_work_id=job_work_id).filter(
            JobWorkBatch.status.in_(['issued', 'in_progress'])
        ).all()
        
        batch_data = []
        for batch in batches:
            batch_data.append({
                'id': batch.id,
                'process_name': batch.process_name,
                'input_batch_number': batch.input_batch.batch_number if batch.input_batch else 'N/A',
                'quantity_issued': batch.quantity_issued,
                'issue_date': batch.issue_date.isoformat() if batch.issue_date else None,
                'status': batch.status,
                'days_in_process': batch.days_in_process
            })
        
        return jsonify({
            'success': True,
            'batches': batch_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching job work batches: {str(e)}'
        }), 500

@jobwork_bp.route('/batch-tracking')
@login_required
def batch_tracking():
    """Dashboard for batch tracking overview"""
    # Get active batch records
    active_batches = JobWorkBatch.query.filter(
        JobWorkBatch.status.in_(['issued', 'in_progress'])
    ).order_by(JobWorkBatch.issue_date.desc()).all()
    
    # Get completed batch records for the last 30 days
# timedelta already imported at top
    thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
    recent_returns = JobWorkBatch.query.filter(
        JobWorkBatch.status == 'returned',
        JobWorkBatch.return_date >= thirty_days_ago
    ).order_by(JobWorkBatch.return_date.desc()).all()
    
    # Calculate statistics
    stats = {
        'active_batches': len(active_batches),
        'pending_returns': len([b for b in active_batches if b.status == 'issued']),
        'in_progress': len([b for b in active_batches if b.status == 'in_progress']),
        'recent_returns': len(recent_returns),
        'total_material_out': sum(b.quantity_issued for b in active_batches),
        'avg_yield_rate': sum(b.yield_percentage for b in recent_returns) / len(recent_returns) if recent_returns else 0
    }
    
    return render_template('jobwork/batch_tracking.html', 
                         active_batches=active_batches,
                         recent_returns=recent_returns,
                         stats=stats)

@jobwork_bp.route('/batch/<int:batch_id>/details')
@login_required
def batch_details(batch_id):
    """View detailed information about a specific batch record"""
    batch = JobWorkBatch.query.get_or_404(batch_id)
    
    # Get related data
    input_batch_history = []
    if batch.input_batch:
        # Get history of this batch through various processes
        related_batches = JobWorkBatch.query.filter_by(
            input_batch_id=batch.input_batch_id
        ).order_by(JobWorkBatch.created_at).all()
        input_batch_history = related_batches
    
    return render_template('jobwork/batch_details.html', 
                         batch=batch,
                         input_batch_history=input_batch_history)


