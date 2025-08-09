from models import db, Production, JobCard, BOMProcess, BOMItem, BOM, Item
from flask_login import current_user
from datetime import date, timedelta
import logging

class ProductionService:
    """Service for production-related operations and job card generation"""
    
    @staticmethod
    def auto_generate_job_cards_from_bom(production_id):
        """
        Generate job cards from BOM components that need manufacturing (sub-assemblies)
        Returns number of job cards created
        """
        try:
            production = Production.query.get(production_id)
            if not production or not production.bom_id:
                return 0
            
            # Get BOM components that need manufacturing
            bom_components = BOMItem.query.filter_by(bom_id=production.bom_id).all()
            if not bom_components:
                logging.info(f"No BOM components found for production {production.production_number}")
                return 0
            
            created_count = 0
            current_date = date.today()
            
            for sequence, bom_component in enumerate(bom_components, 1):
                # Skip components without items
                component_item = bom_component.item
                if not component_item:
                    continue
                
                # Check if this component has its own BOM (indicates manufacturing needed)
                component_bom = BOM.query.filter_by(product_id=component_item.id).first()
                if not component_bom:
                    logging.info(f"Skipping {component_item.name} - no BOM found (likely purchased item)")
                    continue
                
                # Calculate target date with buffer
                buffer_days = sequence  # Stagger job cards by 1 day each
                target_date = current_date + timedelta(days=buffer_days)
                
                # Generate unique job card number
                job_card_number = JobCard.generate_job_card_number(
                    production.production_number, 
                    sequence
                )
                
                # Calculate component quantity needed
                component_quantity = production.quantity_planned * bom_component.quantity_required
                
                # Create job card for manufacturing this component
                job_card = JobCard(
                    job_card_number=job_card_number,
                    production_id=production_id,
                    item_id=component_item.id,  # Component being manufactured
                    bom_item_id=bom_component.id,  # Link to BOM component
                    process_name=f"Manufacture {component_item.name}",
                    process_sequence=sequence,
                    operation_description=f"Manufacture {component_quantity} units of {component_item.name} ({component_item.code}) for {production.production_number}",
                    planned_quantity=component_quantity,
                    target_completion_date=target_date,
                    priority='medium',
                    production_notes=f"Auto-generated from BOM component: {component_item.name} (BOM: {component_bom.bom_code})",
                    created_by_id=current_user.id if current_user and current_user.is_authenticated else 1
                )
                
                db.session.add(job_card)
                created_count += 1
                logging.info(f"Created job card: {job_card_number} for component: {component_item.name}")
            
            db.session.commit()
            logging.info(f"Successfully created {created_count} job cards for production {production.production_number}")
            return created_count
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error auto-generating job cards for production {production_id}: {e}")
            raise e
    
    @staticmethod
    def _should_outsource_process(process_name):
        """Determine if a process should be outsourced based on common patterns"""
        outsource_keywords = [
            'coating', 'plating', 'anodizing', 'painting', 'heat treatment',
            'surface treatment', 'finishing', 'galvanizing', 'powder coating'
        ]
        
        process_lower = process_name.lower()
        return any(keyword in process_lower for keyword in outsource_keywords)
    
    @staticmethod
    def generate_smart_job_cards_from_suggestions(production_id, smart_suggestions):
        """
        Generate job cards based on smart suggestions from AI analysis
        """
        try:
            if not smart_suggestions or smart_suggestions.get('error'):
                return 0
            
            production = Production.query.get(production_id)
            if not production:
                return 0
            
            process_suggestions = smart_suggestions.get('process_suggestions', [])
            if not process_suggestions:
                return 0
            
            created_count = 0
            current_date = date.today()
            
            for sequence, process_suggestion in enumerate(process_suggestions, 1):
                # Calculate timeline based on suggestions
                timeline_suggestions = smart_suggestions.get('timeline_suggestions', {})
                buffer_days = max(1, int(timeline_suggestions.get('estimated_days', 1) / len(process_suggestions)))
                target_date = current_date + timedelta(days=buffer_days * sequence)
                
                job_card_number = JobCard.generate_job_card_number(
                    production.production_number, 
                    sequence
                )
                
                # Get cost estimates for this process
                cost_estimates = smart_suggestions.get('cost_estimates', {})
                estimated_cost = cost_estimates.get('total_estimated_cost', 0) / len(process_suggestions)
                
                # Create job card with smart suggestions
                job_card = JobCard(
                    job_card_number=job_card_number,
                    production_id=production_id,
                    item_id=production.item_id,
                    process_name=process_suggestion['process_name'],
                    process_sequence=process_suggestion['step_number'],
                    operation_description=process_suggestion['operation_description'],
                    planned_quantity=production.quantity_planned,
                    setup_time_minutes=process_suggestion.get('estimated_time', 30),
                    run_time_minutes=process_suggestion.get('estimated_time', 60),
                    target_completion_date=target_date,
                    priority='medium',
                    estimated_cost=estimated_cost,
                    production_notes=f"AI-Generated: {process_suggestion.get('outsource_reason', 'Smart suggestion based job card')}",
                    created_by_id=current_user.id if current_user and current_user.is_authenticated else 1
                )
                
                # Set vendor if outsourcing is suggested
                if process_suggestion.get('suggested_job_type') == 'outsourced' and process_suggestion.get('suggested_vendor'):
                    job_card.assigned_vendor_id = process_suggestion.get('suggested_vendor')
                
                db.session.add(job_card)
                created_count += 1
            
            db.session.commit()
            logging.info(f"Created {created_count} smart job cards for production {production.production_number}")
            return created_count
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating smart job cards for production {production_id}: {e}")
            raise e