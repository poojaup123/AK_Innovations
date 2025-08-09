from models import db, Production, Item, BOM, BOMItem, BOMProcess, Employee, Supplier
from models.job_card import JobCard
from models.batch import InventoryBatch
from sqlalchemy import func
import logging

class SmartJobCardSuggestions:
    """
    Intelligent service that generates comprehensive job card suggestions
    based on production orders, BOMs, inventory levels, and historical data
    """
    
    @staticmethod
    def generate_comprehensive_suggestions(production_id):
        """
        Generate complete job card suggestions for a production order
        Returns all requirements, materials, processes, and intelligent recommendations
        """
        try:
            production = Production.query.get(production_id)
            if not production:
                return {'error': 'Production order not found'}
            
            # Get main BOM for the production item
            main_bom = BOM.query.filter_by(
                product_id=production.item_id, 
                is_active=True
            ).first()
            
            if not main_bom:
                return SmartJobCardSuggestions._generate_simple_suggestions(production)
            
            suggestions = {
                'production_info': {
                    'production_number': production.production_number,
                    'item_name': production.produced_item.name,
                    'planned_quantity': production.quantity_planned,
                    'target_completion': getattr(production, 'target_completion_date', None),
                    'priority': getattr(production, 'priority', 'medium')
                },
                'bom_analysis': SmartJobCardSuggestions._analyze_bom_structure(main_bom),
                'material_requirements': SmartJobCardSuggestions._calculate_material_requirements(main_bom, production.quantity_planned),
                'process_suggestions': SmartJobCardSuggestions._suggest_processes(main_bom),
                'resource_assignments': SmartJobCardSuggestions._suggest_resource_assignments(main_bom),
                'timeline_suggestions': SmartJobCardSuggestions._calculate_timeline_suggestions(main_bom, production.quantity_planned),
                'inventory_availability': SmartJobCardSuggestions._check_inventory_availability(main_bom, production.quantity_planned),
                'cost_estimates': SmartJobCardSuggestions._estimate_costs(main_bom, production.quantity_planned),
                'quality_requirements': SmartJobCardSuggestions._suggest_quality_requirements(main_bom),
                'outsourcing_recommendations': SmartJobCardSuggestions._suggest_outsourcing_opportunities(main_bom)
            }
            
            return suggestions
            
        except Exception as e:
            logging.error(f"Error generating smart suggestions: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def _analyze_bom_structure(bom):
        """Analyze BOM structure and provide intelligent insights"""
        bom_items = BOMItem.query.filter_by(bom_id=bom.id).all()
        processes = BOMProcess.query.filter_by(bom_id=bom.id).order_by(BOMProcess.step_number).all()
        
        return {
            'total_components': len(bom_items),
            'total_processes': len(processes),
            'complexity_level': 'High' if len(processes) > 5 else 'Medium' if len(processes) > 2 else 'Simple',
            'components_breakdown': [
                {
                    'item_name': item.item.name,
                    'item_code': item.item.code,
                    'quantity_required': item.quantity_required,
                    'unit_cost': getattr(item.item, 'unit_cost', None) or getattr(item.item, 'cost_per_unit', None) or 0,
                    'total_cost': (item.quantity_required * (getattr(item.item, 'unit_cost', None) or getattr(item.item, 'cost_per_unit', None) or 0)),
                    'category': getattr(item.item, 'category', None) or getattr(item.item, 'item_category', None) or 'General'
                }
                for item in bom_items
            ],
            'process_flow': [
                {
                    'step': process.step_number,
                    'process_name': process.process_name,
                    'operation': process.operation_description,
                    'setup_time': process.setup_time_minutes or 0,
                    'run_time': process.run_time_minutes or 0,
                    'skill_required': process.skill_level or 'Standard'
                }
                for process in processes
            ]
        }
    
    @staticmethod
    def _calculate_material_requirements(bom, production_quantity):
        """Calculate exact material requirements with inventory consideration"""
        bom_items = BOMItem.query.filter_by(bom_id=bom.id).all()
        requirements = []
        
        for bom_item in bom_items:
            total_required = bom_item.quantity_required * production_quantity
            
            # Check current inventory
            available_inventory = InventoryBatch.query.filter_by(
                item_id=bom_item.item_id
            ).with_entities(
                func.sum(InventoryBatch.qty_raw_material + InventoryBatch.qty_finished).label('total_available')
            ).scalar() or 0
            
            shortage = max(0, total_required - available_inventory)
            
            requirements.append({
                'item_id': bom_item.item_id,
                'item_name': bom_item.item.name,
                'item_code': bom_item.item.code,
                'unit_required': bom_item.quantity_required,
                'total_required': total_required,
                'available_inventory': available_inventory,
                'shortage': shortage,
                'need_procurement': shortage > 0,
                'unit_cost': bom_item.item.unit_cost or 0,
                'total_cost': total_required * (bom_item.item.unit_cost or 0),
                'preferred_supplier': bom_item.item.preferred_supplier_id,
                'uom': bom_item.item.base_uom or 'PCS'
            })
        
        return requirements
    
    @staticmethod
    def _suggest_processes(bom):
        """Suggest process routing and job card breakdown"""
        processes = BOMProcess.query.filter_by(bom_id=bom.id).order_by(BOMProcess.step_number).all()
        suggestions = []
        
        for process in processes:
            # Determine if process should be in-house or outsourced
            outsource_suggestion = SmartJobCardSuggestions._should_outsource_process(process)
            
            suggestions.append({
                'process_id': process.id,
                'step_number': process.step_number,
                'process_name': process.process_name,
                'operation_description': process.operation_description,
                'estimated_time': (process.setup_time_minutes or 0) + (process.run_time_minutes or 0),
                'skill_level': process.skill_level or 'Standard',
                'suggested_job_type': 'outsourced' if outsource_suggestion['should_outsource'] else 'in_house',
                'outsource_reason': outsource_suggestion['reason'],
                'suggested_vendor': outsource_suggestion.get('vendor_id'),
                'quality_requirements': process.quality_requirements or 'Standard inspection',
                'special_instructions': process.special_instructions
            })
        
        return suggestions
    
    @staticmethod
    def _should_outsource_process(process):
        """Intelligent decision on whether to outsource a process"""
        process_name_lower = process.process_name.lower()
        
        # Common outsourcing patterns
        if any(keyword in process_name_lower for keyword in ['coating', 'plating', 'painting', 'heat treatment', 'anodizing']):
            # Find suitable vendor
            suitable_vendors = Supplier.query.filter(
                Supplier.partner_type.in_(['vendor', 'both']),
                Supplier.is_active == True,
                Supplier.services.contains(process.process_name)
            ).all()
            
            if suitable_vendors:
                return {
                    'should_outsource': True,
                    'reason': 'Specialized process requiring external expertise',
                    'vendor_id': suitable_vendors[0].id
                }
        
        # Check if in-house capacity exists
        if process.setup_time_minutes and process.setup_time_minutes > 120:  # More than 2 hours setup
            return {
                'should_outsource': True,
                'reason': 'High setup time suggests specialized equipment'
            }
        
        return {
            'should_outsource': False,
            'reason': 'Standard process suitable for in-house production'
        }
    
    @staticmethod
    def _suggest_resource_assignments(bom):
        """Suggest worker and machine assignments based on process requirements"""
        processes = BOMProcess.query.filter_by(bom_id=bom.id).all()
        assignments = []
        
        for process in processes:
            # Find suitable workers based on skill level
            suitable_workers = Employee.query.filter(
                Employee.is_active == True,
                Employee.skill_level == (process.skill_level or 'Standard')
            ).all()
            
            assignments.append({
                'process_id': process.id,
                'process_name': process.process_name,
                'suggested_workers': [
                    {
                        'worker_id': worker.id,
                        'worker_name': worker.name,
                        'skill_level': worker.skill_level,
                        'availability_score': 85  # Could be calculated based on current workload
                    }
                    for worker in suitable_workers[:3]  # Top 3 suggestions
                ],
                'machine_requirements': process.machine_requirements or 'Standard equipment',
                'workstation_suggestion': SmartJobCardSuggestions._suggest_workstation(process)
            })
        
        return assignments
    
    @staticmethod
    def _suggest_workstation(process):
        """Suggest optimal workstation based on process type"""
        process_name = process.process_name.lower()
        
        if any(keyword in process_name for keyword in ['cutting', 'machining']):
            return 'CNC/Machining Center'
        elif any(keyword in process_name for keyword in ['welding', 'assembly']):
            return 'Assembly Workstation'
        elif any(keyword in process_name for keyword in ['quality', 'inspection']):
            return 'Quality Control Station'
        else:
            return 'General Production Area'
    
    @staticmethod
    def _calculate_timeline_suggestions(bom, production_quantity):
        """Calculate realistic timeline suggestions"""
        processes = BOMProcess.query.filter_by(bom_id=bom.id).order_by(BOMProcess.step_number).all()
        
        total_setup_time = sum(p.setup_time_minutes or 0 for p in processes)
        total_run_time = sum((p.run_time_minutes or 0) * production_quantity for p in processes)
        buffer_time = (total_setup_time + total_run_time) * 0.2  # 20% buffer
        
        return {
            'total_setup_time_minutes': total_setup_time,
            'total_production_time_minutes': total_run_time,
            'buffer_time_minutes': buffer_time,
            'total_estimated_minutes': total_setup_time + total_run_time + buffer_time,
            'estimated_days': ((total_setup_time + total_run_time + buffer_time) / 480),  # 8 hour workday
            'suggested_start_date': 'Today',
            'parallel_processes': SmartJobCardSuggestions._identify_parallel_processes(processes)
        }
    
    @staticmethod
    def _identify_parallel_processes(processes):
        """Identify processes that can run in parallel"""
        parallel_opportunities = []
        
        for i, process in enumerate(processes):
            if i < len(processes) - 1:
                next_process = processes[i + 1]
                # Simple logic: if processes don't depend on each other directly
                if process.process_name.lower() != next_process.process_name.lower():
                    parallel_opportunities.append({
                        'process_1': process.process_name,
                        'process_2': next_process.process_name,
                        'time_savings_minutes': min(process.run_time_minutes or 0, next_process.run_time_minutes or 0) * 0.5
                    })
        
        return parallel_opportunities
    
    @staticmethod
    def _check_inventory_availability(bom, production_quantity):
        """Check real-time inventory availability"""
        bom_items = BOMItem.query.filter_by(bom_id=bom.id).all()
        availability_status = {
            'overall_status': 'available',
            'items_status': [],
            'procurement_needed': []
        }
        
        for bom_item in bom_items:
            required_qty = bom_item.quantity_required * production_quantity
            
            # Get current inventory levels
            current_inventory = db.session.query(
                func.sum(
                    InventoryBatch.qty_raw_material + 
                    InventoryBatch.qty_finished
                )
            ).filter_by(item_id=bom_item.item_id).scalar() or 0
            
            status = 'sufficient' if current_inventory >= required_qty else 'insufficient'
            shortage = max(0, required_qty - current_inventory)
            
            item_status = {
                'item_name': bom_item.item.name,
                'required_quantity': required_qty,
                'available_quantity': current_inventory,
                'shortage': shortage,
                'status': status
            }
            
            availability_status['items_status'].append(item_status)
            
            if status == 'insufficient':
                availability_status['overall_status'] = 'partial'
                availability_status['procurement_needed'].append(item_status)
        
        return availability_status
    
    @staticmethod
    def _estimate_costs(bom, production_quantity):
        """Estimate total production costs"""
        bom_items = BOMItem.query.filter_by(bom_id=bom.id).all()
        processes = BOMProcess.query.filter_by(bom_id=bom.id).all()
        
        material_cost = sum(
            (item.quantity_required * production_quantity * (item.item.unit_cost or 0))
            for item in bom_items
        )
        
        # Estimate labor cost (assuming ₹10 per minute)
        labor_cost = sum(
            ((process.setup_time_minutes or 0) + (process.run_time_minutes or 0) * production_quantity) * 10 / 60
            for process in processes
        )
        
        overhead_cost = (material_cost + labor_cost) * 0.15  # 15% overhead
        
        return {
            'material_cost': material_cost,
            'labor_cost': labor_cost,
            'overhead_cost': overhead_cost,
            'total_estimated_cost': material_cost + labor_cost + overhead_cost,
            'cost_per_unit': (material_cost + labor_cost + overhead_cost) / production_quantity if production_quantity > 0 else 0
        }
    
    @staticmethod
    def _suggest_quality_requirements(bom):
        """Suggest quality control requirements"""
        processes = BOMProcess.query.filter_by(bom_id=bom.id).all()
        
        return {
            'inspection_points': [
                {
                    'process': process.process_name,
                    'inspection_type': 'dimensional' if 'machining' in process.process_name.lower() else 'visual',
                    'critical': any(keyword in process.process_name.lower() for keyword in ['final', 'assembly', 'finishing'])
                }
                for process in processes
            ],
            'overall_quality_level': 'High' if len(processes) > 3 else 'Standard'
        }
    
    @staticmethod
    def _suggest_outsourcing_opportunities(bom):
        """Identify potential outsourcing opportunities with vendor recommendations"""
        processes = BOMProcess.query.filter_by(bom_id=bom.id).all()
        opportunities = []
        
        for process in processes:
            outsource_check = SmartJobCardSuggestions._should_outsource_process(process)
            if outsource_check['should_outsource']:
                opportunities.append({
                    'process_name': process.process_name,
                    'reason': outsource_check['reason'],
                    'estimated_savings': '15-25%',  # Could be calculated
                    'recommended_vendors': SmartJobCardSuggestions._get_recommended_vendors(process)
                })
        
        return opportunities
    
    @staticmethod
    def _get_recommended_vendors(process):
        """Get recommended vendors for a specific process"""
        vendors = Supplier.query.filter(
            Supplier.partner_type.in_(['vendor', 'both']),
            Supplier.is_active == True
        ).limit(3).all()
        
        return [
            {
                'vendor_id': vendor.id,
                'vendor_name': vendor.name,
                'contact_person': vendor.contact_person,
                'rating': 4.2,  # Could be from historical data
                'lead_time_days': 5  # Could be from vendor profile
            }
            for vendor in vendors
        ]
    
    @staticmethod
    def _generate_simple_suggestions(production):
        """Generate basic suggestions for items without BOM"""
        return {
            'production_info': {
                'production_number': production.production_number,
                'item_name': production.produced_item.name,
                'planned_quantity': production.quantity_planned,
                'target_completion': getattr(production, 'target_completion_date', None),
                'priority': getattr(production, 'priority', 'medium')
            },
            'simple_job_card': {
                'process_name': f"Production - {production.produced_item.name}",
                'estimated_time_hours': production.quantity_planned * 0.5,  # Basic estimate
                'skill_required': 'Standard',
                'quality_check': 'Visual inspection required'
            },
            'material_requirements': [{
                'item_name': production.produced_item.name,
                'quantity_required': production.quantity_planned,
                'unit_cost': getattr(production.produced_item, 'unit_cost', None) or getattr(production.produced_item, 'cost_per_unit', None) or 0
            }]
        }
    
    @staticmethod
    def _generate_production_notes(suggestions):
        """Generate comprehensive production notes with all intelligent suggestions"""
        notes = []
        
        # BOM Analysis Summary
        if suggestions.get('bom_analysis'):
            bom = suggestions['bom_analysis']
            notes.append(f"📋 BOM Analysis: {bom['total_components']} components, {bom['total_processes']} processes")
            notes.append(f"   Complexity: {bom['complexity_level']}")
        
        # Material Requirements
        if suggestions.get('material_requirements'):
            total_materials = len(suggestions['material_requirements'])
            shortages = len([m for m in suggestions['material_requirements'] if m['need_procurement']])
            notes.append(f"📦 Materials: {total_materials} items required")
            if shortages > 0:
                notes.append(f"   ⚠️ {shortages} items need procurement")
        
        # Process Recommendations
        if suggestions.get('process_suggestions'):
            outsourced = len([p for p in suggestions['process_suggestions'] if p['suggested_job_type'] == 'outsourced'])
            if outsourced > 0:
                notes.append(f"🏭 Outsourcing: {outsourced} processes recommended for external vendors")
        
        # Timeline Estimates
        if suggestions.get('timeline_suggestions'):
            timeline = suggestions['timeline_suggestions']
            estimated_days = timeline.get('estimated_days', 0)
            notes.append(f"⏱️ Timeline: {estimated_days:.1f} days estimated")
        
        # Cost Estimates
        if suggestions.get('cost_estimates'):
            cost = suggestions['cost_estimates']
            notes.append(f"💰 Cost: ₹{cost['total_estimated_cost']:.2f} total (₹{cost['cost_per_unit']:.2f}/unit)")
        
        # Quality Requirements
        if suggestions.get('quality_requirements'):
            quality = suggestions['quality_requirements']
            notes.append(f"🔍 Quality: {quality['overall_quality_level']} level inspection required")
        
        # Inventory Status
        if suggestions.get('inventory_availability'):
            inventory = suggestions['inventory_availability']
            if inventory['overall_status'] != 'available':
                notes.append(f"📊 Inventory: {len(inventory['procurement_needed'])} items need procurement")
        
        return "\n".join(notes)