"""Production Service with complete Job Work integration"""

from app import db
from models.production import ProductionOrder, ProductionProcess
from models import BOM, BOMItem, Item, JobWork
from services.jobwork_automation import JobWorkAutomationService
# from services.grn_service import GRNService  # Temporarily commented out
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ProductionService:
    """Complete production management with job work integration"""
    
    @staticmethod
    def create_production_order(data):
        """Create production order with automatic job work planning"""
        try:
            # Create production order
            production_order = ProductionOrder(
                bom_id=data['bom_id'],
                product_id=data['product_id'],
                quantity_ordered=data['quantity_ordered'],
                order_date=data.get('order_date', datetime.utcnow().date()),
                expected_completion=data.get('expected_completion'),
                priority=data.get('priority', 'normal'),
                notes=data.get('notes', ''),
                created_by=data['created_by']
            )
            
            db.session.add(production_order)
            db.session.flush()  # Get ID without committing
            
            # Multi-level BOM explosion
            materials_required = production_order.explode_bom()
            
            # Create production processes for each required operation
            processes_created = ProductionService._create_production_processes(
                production_order, materials_required
            )
            
            # Calculate material costs
            total_material_cost = sum(
                mat['quantity_required'] * (mat['item'].unit_price or 0)
                for mat in materials_required if mat['type'] == 'raw_material'
            )
            production_order.material_cost = total_material_cost
            
            db.session.commit()
            
            logger.info(f"Created production order {production_order.po_number} with {len(processes_created)} processes")
            
            return {
                'success': True,
                'production_order': production_order,
                'processes_created': len(processes_created),
                'materials_required': len(materials_required)
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating production order: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _create_production_processes(production_order, materials_required):
        """Create production processes with proper sequencing"""
        processes = []
        sequence = 1
        
        # Group materials by process type and create sequential processes
        process_groups = {}
        
        for material in materials_required:
            item = material['item']
            
            # Check if item requires processing
            if hasattr(item, 'default_process') and item.default_process:
                process_type = item.default_process
                
                if process_type not in process_groups:
                    process_groups[process_type] = {
                        'materials': [],
                        'total_qty': 0,
                        'estimated_cost': 0
                    }
                
                process_groups[process_type]['materials'].append(material)
                process_groups[process_type]['total_qty'] += material['quantity_required']
                process_groups[process_type]['estimated_cost'] += (
                    material['quantity_required'] * (item.processing_cost or 0)
                )
        
        # Create processes in logical sequence
        process_sequence = ['cutting', 'machining', 'welding', 'painting', 'assembly']
        
        previous_process = None
        for process_name in process_sequence:
            if process_name in process_groups:
                group = process_groups[process_name]
                
                # Determine if in-house or outsourced
                process_type = 'in_house'  # Default
                assigned_to = 'Production Department'
                
                # Check if any material in group requires outsourcing
                for material in group['materials']:
                    if hasattr(material['item'], 'requires_outsourcing') and material['item'].requires_outsourcing:
                        process_type = 'outsourced'
                        # Get preferred vendor for this process
                        assigned_to = ProductionService._get_preferred_vendor(process_name)
                        break
                
                process = ProductionProcess(
                    production_order_id=production_order.id,
                    sequence_number=sequence,
                    process_name=process_name.title(),
                    process_type=process_type,
                    assigned_to=assigned_to,
                    assigned_type='vendor' if process_type == 'outsourced' else 'department',
                    input_quantity=group['total_qty'],
                    estimated_cost=group['estimated_cost'],
                    status='pending'
                )
                
                # Link to previous process for sequential routing
                if previous_process:
                    process.previous_process_id = previous_process.id
                    previous_process.next_process_id = process.id
                
                db.session.add(process)
                processes.append(process)
                previous_process = process
                sequence += 1
        
        return processes
    
    @staticmethod
    def _get_preferred_vendor(process_name):
        """Get preferred vendor for specific process"""
        from models import Supplier
        
        # Map process to vendor categories or specific vendors
        process_vendor_map = {
            'cutting': 'laser_cutting',
            'machining': 'cnc_machining', 
            'welding': 'fabrication',
            'painting': 'surface_treatment',
            'powder_coating': 'surface_treatment'
        }
        
        vendor_category = process_vendor_map.get(process_name.lower())
        
        if vendor_category:
            # Find vendor with matching capability
            vendor = Supplier.query.filter(
                Supplier.is_active == True,
                Supplier.partner_type.in_(['vendor', 'both']),
                Supplier.capabilities.like(f'%{vendor_category}%')
            ).first()
            
            if vendor:
                return vendor.name
        
        # Fallback to any active vendor
        fallback_vendor = Supplier.query.filter(
            Supplier.is_active == True,
            Supplier.partner_type.in_(['vendor', 'both'])
        ).first()
        
        return fallback_vendor.name if fallback_vendor else 'External Vendor'
    
    @staticmethod
    def start_production_process(process_id, user_id):
        """Start a production process and create corresponding job work"""
        try:
            process = ProductionProcess.query.get(process_id)
            if not process:
                return {'success': False, 'error': 'Process not found'}
            
            if process.status != 'pending':
                return {'success': False, 'error': f'Process is already {process.status}'}
            
            # Create job work for this process
            if process.process_type == 'outsourced':
                job_work_data = {
                    'production_order_id': process.production_order_id,
                    'process_id': process.id,
                    'work_type': 'outsourced',
                    'assigned_to': process.assigned_to,
                    'quantity_to_issue': process.input_quantity,
                    'expected_output': process.input_quantity * 0.95,  # Account for scrap
                    'created_by': user_id
                }
                
                job_work = JobWorkAutomationService.create_from_production_process(
                    process, job_work_data
                )
                
                if job_work:
                    process.job_work_id = job_work.id
                    process.status = 'in_progress'
                    process.start_date = datetime.utcnow().date()
                    
                    db.session.commit()
                    
                    return {
                        'success': True,
                        'process': process,
                        'job_work': job_work,
                        'message': 'Outsourced process started, job work created'
                    }
            else:
                # In-house process
                process.status = 'in_progress'
                process.start_date = datetime.utcnow().date()
                db.session.commit()
                
                return {
                    'success': True,
                    'process': process,
                    'message': 'In-house process started'
                }
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error starting production process: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def complete_production_process(process_id, completion_data):
        """Complete a production process and handle material flow"""
        try:
            process = ProductionProcess.query.get(process_id)
            if not process:
                return {'success': False, 'error': 'Process not found'}
            
            # Update process completion
            process.output_quantity = completion_data['output_quantity']
            process.scrap_quantity = completion_data.get('scrap_quantity', 0)
            process.actual_cost = completion_data.get('actual_cost', process.estimated_cost)
            process.quality_status = completion_data.get('quality_status', 'passed')
            process.quality_remarks = completion_data.get('quality_remarks', '')
            process.status = 'completed'
            process.completion_date = datetime.utcnow().date()
            
            # Auto-forward to next process if exists
            next_job_work = None
            if process.next_process:
                next_job_work = process.forward_to_next_vendor()
            
            # Update production order progress
            process.production_order.update_progress()
            
            db.session.commit()
            
            result = {
                'success': True,
                'process': process,
                'message': 'Process completed successfully'
            }
            
            if next_job_work:
                result['next_job_work'] = next_job_work
                result['message'] += f', auto-forwarded to {process.next_process.assigned_to}'
            
            return result
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error completing production process: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_production_status(production_order_id):
        """Get comprehensive production status with all processes"""
        try:
            production_order = ProductionOrder.query.get(production_order_id)
            if not production_order:
                return {'success': False, 'error': 'Production order not found'}
            
            processes = ProductionProcess.query.filter_by(
                production_order_id=production_order_id
            ).order_by(ProductionProcess.sequence_number).all()
            
            # Calculate overall progress
            total_processes = len(processes)
            completed_processes = len([p for p in processes if p.status == 'completed'])
            progress_percentage = (completed_processes / total_processes * 100) if total_processes > 0 else 0
            
            # Get job works
            job_works = JobWork.query.filter_by(production_order_id=production_order_id).all()
            
            return {
                'success': True,
                'production_order': production_order.to_dict(),
                'processes': [p.to_dict() for p in processes],
                'job_works': [jw.to_dict() for jw in job_works],
                'progress_percentage': progress_percentage,
                'total_processes': total_processes,
                'completed_processes': completed_processes,
                'estimated_completion': ProductionService._calculate_estimated_completion(processes)
            }
            
        except Exception as e:
            logger.error(f"Error getting production status: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _calculate_estimated_completion(processes):
        """Calculate estimated completion date based on process status"""
        try:
            pending_processes = [p for p in processes if p.status in ['pending', 'in_progress']]
            
            if not pending_processes:
                return None
            
            # Simple estimation: 2 days per pending process
            days_remaining = len(pending_processes) * 2
            estimated_date = datetime.now().date() + timedelta(days=days_remaining)
            
            return estimated_date.isoformat()
            
        except:
            return None
    
    @staticmethod
    def get_dashboard_metrics():
        """Get production dashboard metrics"""
        try:
            total_orders = ProductionOrder.query.count()
            active_orders = ProductionOrder.query.filter(
                ProductionOrder.status.in_(['open', 'in_progress', 'partial'])
            ).count()
            completed_orders = ProductionOrder.query.filter_by(status='completed').count()
            
            # Recent orders
            recent_orders = ProductionOrder.query.order_by(
                ProductionOrder.created_at.desc()
            ).limit(5).all()
            
            # Overdue orders
            today = datetime.now().date()
            overdue_orders = ProductionOrder.query.filter(
                ProductionOrder.expected_completion < today,
                ProductionOrder.status != 'completed'
            ).count()
            
            return {
                'total_orders': total_orders,
                'active_orders': active_orders,
                'completed_orders': completed_orders,
                'overdue_orders': overdue_orders,
                'recent_orders': [order.to_dict() for order in recent_orders]
            }
            
        except Exception as e:
            logger.error(f"Error getting production dashboard metrics: {str(e)}")
            return {
                'total_orders': 0,
                'active_orders': 0,
                'completed_orders': 0,
                'overdue_orders': 0,
                'recent_orders': []
            }
    
    @staticmethod
    def calculate_manufacturable_quantity(item_id):
        """Calculate how many units of an item can be made from available raw materials"""
        try:
            from models.batch import InventoryBatch
            from sqlalchemy import func
            
            # First, get direct inventory availability
            direct_available = db.session.query(
                func.sum(
                    (InventoryBatch.qty_raw or 0) + 
                    (InventoryBatch.qty_finished or 0) +
                    (InventoryBatch.qty_wip or 0)
                )
            ).filter_by(item_id=item_id).scalar() or 0
            
            # Check if this item can be manufactured (has a BOM)
            manufacturing_bom = BOM.query.filter_by(
                product_id=item_id, 
                is_active=True
            ).first()
            
            manufacturable_qty = 0
            
            if manufacturing_bom:
                # Get BOM items (raw materials needed)
                bom_items = BOMItem.query.filter_by(bom_id=manufacturing_bom.id).all()
                
                # Calculate maximum manufacturable quantity based on available raw materials
                max_manufacturable = float('inf')
                
                for bom_item in bom_items:
                    # Get available raw material
                    raw_material_available = db.session.query(
                        func.sum(
                            (InventoryBatch.qty_raw or 0) + 
                            (InventoryBatch.qty_finished or 0)
                        )
                    ).filter_by(item_id=bom_item.item_id).scalar() or 0
                    
                    # Add item's current stock as fallback
                    item_stock = bom_item.item.current_stock or 0
                    raw_material_available = max(raw_material_available, item_stock)
                    
                    # Calculate how many units can be made with this raw material
                    material_qty_needed = bom_item.quantity_required or bom_item.qty_required or 1
                    bom_output_qty = manufacturing_bom.output_quantity or 1.0
                    
                    # Units that can be made = (available_raw / material_per_unit) * output_per_bom
                    if material_qty_needed > 0:
                        units_possible = (raw_material_available / material_qty_needed) * bom_output_qty
                        max_manufacturable = min(max_manufacturable, units_possible)
                    else:
                        max_manufacturable = 0
                        break
                
                # Handle infinite case (no materials required)
                if max_manufacturable == float('inf'):
                    max_manufacturable = 0
                else:
                    manufacturable_qty = max(0, int(max_manufacturable))
            
            # Total available = direct inventory + what can be manufactured
            total_available = direct_available + manufacturable_qty
            
            return total_available
            
        except Exception as e:
            logger.error(f"Error calculating manufacturable quantity for item {item_id}: {str(e)}")
            return None  # Fallback to basic inventory check