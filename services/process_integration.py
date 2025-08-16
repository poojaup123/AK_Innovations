"""
Process Integration Service
Handles intelligent integration between Manufacturing Process Workflows and BOM system
Automatically populates Scrap Management and Labor Costs from process definitions
"""

from models import BOM, BOMProcess, db
from datetime import datetime

class ProcessIntegrationService:
    """Service for intelligent BOM-Process integration"""
    
    @staticmethod
    def sync_bom_from_processes(bom_id):
        """
        Synchronize BOM costs and scrap data from manufacturing process workflows
        This is the core intelligence that populates BOM from process definitions
        """
        bom = BOM.query.get(bom_id)
        if not bom or not bom.processes:
            return False
        
        # Calculate totals from processes
        total_labor_cost = 0.0
        total_scrap_percent = 0.0
        total_time_hours = 0.0
        process_notes = []
        final_output_weight = None
        last_process = None
        
        # Sort processes by step number to find the last process
        sorted_processes = sorted(bom.processes, key=lambda p: p.step_number)
        
        for process in sorted_processes:
            # Labor cost calculation
            if process.cost_per_unit:
                total_labor_cost += process.cost_per_unit
            
            # Scrap percentage accumulation
            if process.estimated_scrap_percent:
                total_scrap_percent += process.estimated_scrap_percent
            
            # Time calculation
            if process.total_time_minutes:
                total_time_hours += process.total_time_minutes / 60.0
            
            # Collect process notes
            if process.notes:
                process_notes.append(f"{process.process_name}: {process.notes}")
            
            # Track the last process for final weight calculation
            last_process = process
        
        # Get final output quantity and weight from the last process (highest step number)
        final_output_quantity = None
        if last_process:
            # Sync output quantity from the last process
            if hasattr(last_process, 'output_quantity') and last_process.output_quantity:
                final_output_quantity = last_process.output_quantity
            
            # Check for various possible field names for output weight
            output_weight_field = None
            if hasattr(last_process, 'output_unit_weight') and last_process.output_unit_weight:
                output_weight_field = last_process.output_unit_weight
            elif hasattr(last_process, 'output_weight') and last_process.output_weight:
                output_weight_field = last_process.output_weight
            elif hasattr(last_process, 'unit_output_weight') and last_process.unit_output_weight:
                output_weight_field = last_process.unit_output_weight
            
            if output_weight_field:
                final_output_weight = output_weight_field
                
                # Convert to kg if needed (assuming BOM weight is stored in kg)
                weight_conversions = {
                    'g': 0.001,    # grams to kg
                    'lbs': 0.453592,  # pounds to kg
                    'oz': 0.0283495,  # ounces to kg
                    'ton': 1000,   # tons to kg
                    'kg': 1.0      # kg to kg (no conversion)
                }
                
                # Check for UOM field variations
                uom = 'kg'  # default
                if hasattr(last_process, 'output_weight_uom'):
                    uom = getattr(last_process, 'output_weight_uom', 'kg')
                elif hasattr(last_process, 'output_unit_weight_uom'):
                    uom = getattr(last_process, 'output_unit_weight_uom', 'kg')
                elif hasattr(last_process, 'unit_output_weight_uom'):
                    uom = getattr(last_process, 'unit_output_weight_uom', 'kg')
                
                conversion_factor = weight_conversions.get(uom, 1.0)
                final_output_weight = final_output_weight * conversion_factor
        
        # Update BOM with calculated values
        bom.labor_cost_per_unit = total_labor_cost
        bom.estimated_scrap_percent = total_scrap_percent
        bom.labor_hours_per_unit = total_time_hours
        
        # Update BOM output quantity from last process output
        if final_output_quantity is not None and final_output_quantity > 0:
            bom.output_quantity = final_output_quantity
        
        # Update BOM final product unit weight from last process output
        if final_output_weight is not None:
            bom.unit_weight = final_output_weight
        
        # Add process integration note
        process_integration_note = f"Auto-calculated from {len(bom.processes)} manufacturing processes on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        if bom.remarks:
            bom.remarks += f"\n\n[Process Integration] {process_integration_note}"
        else:
            bom.remarks = f"[Process Integration] {process_integration_note}"
        
        if process_notes:
            bom.remarks += f"\n\nProcess Notes:\n" + "\n".join(process_notes[:3])  # Limit to first 3 notes
        
        # Create accounting cost allocation entry for BOM
        try:
            from services.authentic_accounting_integration import AuthenticAccountingIntegration
            # Use authentic accounting integration for BOM cost allocation
            overhead_account = AuthenticAccountingIntegration.get_overhead_account() 
            wip_account = AuthenticAccountingIntegration.get_inventory_account('wip')
            
            if overhead_account and wip_account and bom.labor_cost_per_unit:
                entries = [
                    {'account': wip_account, 'type': 'debit', 'amount': bom.labor_cost_per_unit, 'narration': f'BOM labor cost allocation - {bom.item_name}'},
                    {'account': overhead_account, 'type': 'credit', 'amount': bom.labor_cost_per_unit, 'narration': f'BOM labor cost allocation - {bom.item_name}'}
                ]
                AuthenticAccountingIntegration.create_simple_voucher('JNL', bom.bom_number, f'BOM Cost Allocation - {bom.item_name}', entries)
        except Exception as e:
            print(f"Warning: Failed to create BOM accounting entry: {str(e)}")
        
        # Recalculate and update all process costs with correct unit weights
        for process in bom.processes:
            if process.cost_unit == 'per_kg':
                # Force recalculation of converted cost
                process.converted_cost = process.converted_cost_per_unit
        
        db.session.commit()
        return True
    
    @staticmethod
    def calculate_process_driven_scrap(bom):
        """Calculate scrap quantity based on process definitions and material weights"""
        if not bom.processes:
            return 0.0
        
        total_material_weight = 0.0
        for item in bom.items:
            if hasattr(item, 'material') and item.material and item.material.unit_weight:
                material_weight = item.material.unit_weight * (item.qty_required or item.quantity_required or 0)
                total_material_weight += material_weight
        
        # Calculate scrap based on process percentages
        calculated_scrap_percent = bom.calculated_scrap_percent
        if calculated_scrap_percent > 0 and total_material_weight > 0:
            return total_material_weight * (calculated_scrap_percent / 100)
        
        return 0.0
    
    @staticmethod
    def update_bom_scrap_quantity(bom_id):
        """Update BOM scrap quantity based on process-driven calculations"""
        bom = BOM.query.get(bom_id)
        if not bom:
            return False
        
        calculated_scrap = ProcessIntegrationService.calculate_process_driven_scrap(bom)
        if calculated_scrap > 0:
            bom.scrap_quantity = calculated_scrap
            bom.scrap_uom = 'kg'  # Default to weight-based scrap
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def get_process_summary(bom):
        """Get summary of process-driven calculations for display"""
        if not bom or not bom.processes:
            return {
                'has_processes': False,
                'message': 'No manufacturing processes defined'
            }
        
        return {
            'has_processes': True,
            'process_count': len(bom.processes),
            'total_labor_cost': bom.total_process_cost_per_unit,
            'calculated_scrap_percent': bom.calculated_scrap_percent,
            'total_time_hours': bom.calculated_total_manufacturing_time,
            'complexity': bom.manufacturing_complexity,
            'processes': [
                {
                    'step': p.step_number,
                    'name': p.process_name,
                    'labor_cost': p.labor_cost_per_unit,
                    'scrap_percent': p.estimated_scrap_percent or 0,
                    'time_minutes': p.total_time_minutes,
                    'is_outsourced': p.is_outsourced
                } for p in sorted(bom.processes, key=lambda x: x.step_number)
            ]
        }
    
    @staticmethod
    def auto_sync_enabled(bom):
        """Check if automatic sync from processes is enabled/beneficial"""
        if not bom or not bom.processes:
            return False
        
        # Enable auto-sync if:
        # 1. Processes exist with labor costs or scrap percentages
        # 2. Manual BOM values are zero/empty (indicating processes should drive values)
        has_process_data = any(
            (p.labor_cost_per_unit and p.labor_cost_per_unit > 0) or 
            (p.estimated_scrap_percent and p.estimated_scrap_percent > 0)
            for p in bom.processes
        )
        
        manual_values_empty = (
            (not bom.labor_cost_per_unit or bom.labor_cost_per_unit == 0) and
            (not bom.estimated_scrap_percent or bom.estimated_scrap_percent == 0)
        )
        
        return has_process_data and manual_values_empty
    
    @staticmethod
    def generate_process_workflow_report(bom):
        """Generate detailed report of process workflow integration"""
        summary = ProcessIntegrationService.get_process_summary(bom)
        
        if not summary['has_processes']:
            return "No manufacturing process workflow defined for this BOM."
        
        report = f"""
Manufacturing Process Workflow Integration Report
BOM: {bom.bom_code}
Product: {bom.product.name if bom.product else 'Unknown'}

Process Summary:
- Total Processes: {summary['process_count']}
- Manufacturing Complexity: {summary['complexity']}
- Total Processing Time: {summary['total_time_hours']:.2f} hours
- Process-Driven Labor Cost: ₹{summary['total_labor_cost']:.2f} per unit
- Process-Driven Scrap Rate: {summary['calculated_scrap_percent']:.2f}%

Process Breakdown:
"""
        
        for process in summary['processes']:
            report += f"""
Step {process['step']}: {process['name']}
  - Labor Cost: ₹{process['labor_cost']:.2f}
  - Scrap Rate: {process['scrap_percent']:.1f}%
  - Time: {process['time_minutes']:.1f} minutes
  - Type: {'Outsourced' if process['is_outsourced'] else 'In-House'}
"""
        
        # Integration status
        auto_sync = ProcessIntegrationService.auto_sync_enabled(bom)
        report += f"""
Integration Status:
- Auto-Sync from Processes: {'Enabled' if auto_sync else 'Disabled'}
- Current Labor Cost Source: {'Process Workflow' if bom.total_process_cost_per_unit > 0 else 'Manual Entry'}
- Current Scrap Source: {'Process Workflow' if bom.calculated_scrap_percent > 0 else 'Manual Entry'}
"""
        
        return report