from flask import current_app
from models import Production, Item, ItemBatch
from models.daily_production import DailyProductionEntry
from app import db
from datetime import date, datetime
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

class DailyProductionService:
    """Service for handling daily production entry and updates"""
    
    @staticmethod
    def validate_material_availability(production, planned_production_qty):
        """
        Validate if sufficient materials are available for production
        
        Args:
            production: Production object
            planned_production_qty: Quantity planned to produce today
            
        Returns:
            dict: Validation result with availability status and details
        """
        from models.bom import BOM, BOMItem
        
        # Check if production has BOM
        if not production.bom_id:
            return {
                'success': True, 
                'message': 'No BOM found for this production. Manual validation required.',
                'warnings': ['No BOM attached - material consumption cannot be tracked automatically']
            }
        
        bom = BOM.query.get(production.bom_id)
        if not bom:
            return {
                'success': False,
                'message': 'BOM not found for this production order'
            }
        
        # Check material availability for each BOM item
        material_shortages = []
        availability_warnings = []
        
        for bom_item in bom.bom_items:
            if bom_item.item_type != 'input':  # Only check input materials
                continue
                
            # Calculate required quantity for today's production
            required_qty = (bom_item.quantity_required / bom.batch_size) * planned_production_qty
            
            # Check available inventory (raw material state)
            available_qty = bom_item.item.qty_raw_material or 0
            
            if available_qty < required_qty:
                shortage = required_qty - available_qty
                material_shortages.append({
                    'item_name': bom_item.item.name,
                    'required': required_qty,
                    'available': available_qty,
                    'shortage': shortage,
                    'unit': bom_item.unit_of_measure
                })
            elif available_qty < (required_qty * 1.1):  # Less than 10% buffer
                availability_warnings.append({
                    'item_name': bom_item.item.name,
                    'required': required_qty,
                    'available': available_qty,
                    'unit': bom_item.unit_of_measure,
                    'message': f'Low stock warning: Only {available_qty:.2f} {bom_item.unit_of_measure} available'
                })
        
        if material_shortages:
            shortage_details = []
            for shortage in material_shortages:
                shortage_details.append(
                    f"• {shortage['item_name']}: Need {shortage['required']:.2f} {shortage['unit']}, "
                    f"Available {shortage['available']:.2f} {shortage['unit']}, "
                    f"Short by {shortage['shortage']:.2f} {shortage['unit']}"
                )
            
            return {
                'success': False,
                'message': f'Material shortage detected for {planned_production_qty} units production:',
                'shortages': material_shortages,
                'details': shortage_details
            }
        
        return {
            'success': True,
            'message': 'All materials available for production',
            'warnings': [w['message'] for w in availability_warnings]
        }

    @staticmethod
    def record_daily_production(production_id, form_data, user_id):
        """
        Record daily production entry and update production totals with material validation
        
        Args:
            production_id: ID of the production order
            form_data: Form data with daily production quantities
            user_id: ID of user recording the production
            
        Returns:
            dict: Success/failure status with message
        """
        try:
            # Get production order
            production = Production.query.get(production_id)
            if not production:
                return {'success': False, 'message': 'Production order not found'}
            
            planned_qty = form_data.get('quantity_produced_today', 0)
            if planned_qty <= 0:
                return {'success': False, 'message': 'Production quantity must be greater than 0'}
            
            # Validate material availability
            validation_result = DailyProductionService.validate_material_availability(
                production, planned_qty
            )
            
            if not validation_result['success']:
                error_msg = validation_result['message']
                if 'details' in validation_result:
                    error_msg += "\n\n" + "\n".join(validation_result['details'])
                error_msg += "\n\nPlease check inventory and ensure sufficient materials are available before recording production."
                return {'success': False, 'message': error_msg}
            
            # Create daily production entry
            daily_entry = DailyProductionEntry(
                production_id=production_id,
                entry_date=form_data.get('production_date', date.today()),
                shift=form_data.get('production_shift', 'day'),
                target_quantity=form_data.get('target_quantity_today', 0),
                actual_quantity=form_data.get('quantity_produced_today', 0),
                good_quantity=form_data.get('quantity_good_today', 0),
                defective_quantity=form_data.get('quantity_defective_today', 0),
                scrap_quantity=form_data.get('quantity_scrap_today', 0),
                weight_produced=form_data.get('weight_produced_today', 0),
                quality_status=form_data.get('quality_control_passed', 'pending'),
                quality_notes=form_data.get('quality_notes', ''),
                production_notes=form_data.get('production_notes', ''),
                material_consumption_notes=form_data.get('material_consumption_notes', ''),
                recorded_by=user_id
            )
            
            db.session.add(daily_entry)
            
            # Update production totals
            production.quantity_produced = (production.quantity_produced or 0) + form_data.get('quantity_produced_today', 0)
            production.quantity_good = (production.quantity_good or 0) + form_data.get('quantity_good_today', 0)
            production.quantity_damaged = (production.quantity_damaged or 0) + form_data.get('quantity_defective_today', 0)
            production.scrap_quantity = (production.scrap_quantity or 0) + form_data.get('quantity_scrap_today', 0)
            production.total_weight_produced = (production.total_weight_produced or 0) + form_data.get('weight_produced_today', 0)
            
            # Update production status based on progress
            if production.quantity_produced >= production.quantity_planned:
                production.status = 'completed'
            elif production.quantity_produced > 0:
                production.status = 'in_progress'
            
            # Update production notes
            today_note = f"\n[{form_data.get('production_date', date.today())}] Daily Production: {form_data.get('quantity_produced_today', 0)} units"
            if form_data.get('production_notes'):
                today_note += f" - {form_data.get('production_notes')}"
            production.notes = (production.notes or "") + today_note
            
            # Update inventory if good items were produced
            good_qty = form_data.get('quantity_good_today', 0)
            if good_qty > 0:
                DailyProductionService._update_finished_goods_inventory(
                    production.item_id, good_qty, production_id, user_id
                )
            
            # Update material consumption from BOM
            if production.bom_id and form_data.get('quantity_produced_today', 0) > 0:
                DailyProductionService._update_material_consumption(
                    production.bom_id, 
                    form_data.get('quantity_produced_today', 0),
                    user_id
                )
            
            db.session.commit()
            
            logger.info(f"Daily production recorded for {production.production_number}: {form_data.get('quantity_produced_today', 0)} units")
            
            return {
                'success': True, 
                'message': f'Daily production recorded successfully. Total produced: {production.quantity_produced}/{production.quantity_planned}',
                'production': production,
                'daily_entry': daily_entry
            }
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error in record_daily_production: {str(e)}")
            return {'success': False, 'message': f'Database error: {str(e)}'}
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in record_daily_production: {str(e)}")
            return {'success': False, 'message': f'Error recording production: {str(e)}'}
    
    @staticmethod
    def _update_finished_goods_inventory(item_id, quantity, production_id, user_id):
        """Update finished goods inventory when production is recorded"""
        try:
            item = Item.query.get(item_id)
            if item:
                # Update finished goods quantity
                item.qty_finished = (item.qty_finished or 0) + quantity
                
                # Create inventory transaction record
                DailyProductionService._create_inventory_transaction(
                    item_id, quantity, 'production_addition', 
                    f'Daily production from order PROD-{production_id}', user_id
                )
                
                logger.info(f"Updated finished goods inventory for {item.name}: +{quantity}")
            
        except Exception as e:
            logger.error(f"Error updating finished goods inventory: {str(e)}")
            raise
    
    @staticmethod
    def _update_material_consumption(bom_id, quantity_produced, user_id):
        """Update raw material inventory based on BOM consumption"""
        try:
            from models import BOM, BOMItem
            
            bom = BOM.query.get(bom_id)
            if not bom:
                return
            
            # Calculate material consumption based on BOM
            for bom_item in bom.items:
                material_consumed = bom_item.quantity_required * quantity_produced
                
                # Update raw material inventory
                item = bom_item.item
                if item and item.qty_raw_material >= material_consumed:
                    item.qty_raw_material -= material_consumed
                    
                    # Create inventory transaction
                    DailyProductionService._create_inventory_transaction(
                        item.id, -material_consumed, 'production_consumption',
                        f'Material consumed in production (BOM: {bom.bom_number})', user_id
                    )
                    
                    logger.info(f"Consumed {material_consumed} units of {item.name} for production")
                else:
                    logger.warning(f"Insufficient raw material for {item.name if item else 'Unknown Item'}")
            
        except Exception as e:
            logger.error(f"Error updating material consumption: {str(e)}")
            # Don't raise here as this is supplementary to main production recording
    
    @staticmethod
    def _create_inventory_transaction(item_id, quantity, transaction_type, description, user_id):
        """Create inventory transaction record for audit trail"""
        try:
            # This would integrate with your inventory transaction system
            # For now, just log the transaction
            logger.info(f"Inventory Transaction: Item {item_id}, Qty {quantity}, Type {transaction_type}")
            
        except Exception as e:
            logger.error(f"Error creating inventory transaction: {str(e)}")
    
    @staticmethod
    def get_daily_production_summary(production_id, start_date=None, end_date=None):
        """Get summary of daily production entries for a production order"""
        try:
            query = DailyProductionEntry.query.filter_by(production_id=production_id)
            
            if start_date:
                query = query.filter(DailyProductionEntry.entry_date >= start_date)
            if end_date:
                query = query.filter(DailyProductionEntry.entry_date <= end_date)
            
            daily_entries = query.order_by(DailyProductionEntry.entry_date.desc()).all()
            
            # Calculate summary statistics
            total_produced = sum(entry.actual_quantity for entry in daily_entries)
            total_good = sum(entry.good_quantity for entry in daily_entries)
            total_defective = sum(entry.defective_quantity for entry in daily_entries)
            total_scrap = sum(entry.scrap_quantity for entry in daily_entries)
            
            quality_rate = (total_good / total_produced * 100) if total_produced > 0 else 0
            defect_rate = (total_defective / total_produced * 100) if total_produced > 0 else 0
            
            return {
                'success': True,
                'daily_entries': daily_entries,
                'summary': {
                    'total_produced': total_produced,
                    'total_good': total_good,
                    'total_defective': total_defective,
                    'total_scrap': total_scrap,
                    'quality_rate': quality_rate,
                    'defect_rate': defect_rate,
                    'days_recorded': len(daily_entries)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting daily production summary: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    @staticmethod
    def get_production_dashboard_data():
        """Get data for production dashboard showing daily production activity"""
        try:
            today = date.today()
            
            # Today's production entries
            today_entries = DailyProductionEntry.query.filter_by(entry_date=today).all()
            
            # Active production orders
            active_productions = Production.query.filter(
                Production.status.in_(['planned', 'in_progress'])
            ).all()
            
            # Recent completions (last 7 days)
            week_ago = today - datetime.timedelta(days=7)
            recent_completions = Production.query.filter(
                Production.status == 'completed',
                Production.updated_at >= week_ago
            ).all()
            
            # Calculate today's totals
            today_total_produced = sum(entry.actual_quantity for entry in today_entries)
            today_total_good = sum(entry.good_quantity for entry in today_entries)
            today_quality_rate = (today_total_good / today_total_produced * 100) if today_total_produced > 0 else 0
            
            return {
                'success': True,
                'dashboard_data': {
                    'today_entries': today_entries,
                    'active_productions': active_productions,
                    'recent_completions': recent_completions,
                    'today_stats': {
                        'total_produced': today_total_produced,
                        'total_good': today_total_good,
                        'quality_rate': today_quality_rate,
                        'entries_count': len(today_entries)
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting production dashboard data: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}