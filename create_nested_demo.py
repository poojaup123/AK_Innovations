#!/usr/bin/env python3
"""
Create nested demo data showing cost calculation from existing data
"""

import sys
import os
from datetime import datetime, date

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import *

def show_cost_calculation_demo():
    """Show how costs are calculated from existing data in the system"""
    
    with app.app_context():
        print("🏭 BOM Cost Calculation Demo from Real Data")
        print("=" * 60)
        
        # Show existing data in system
        print("📊 Current System Data:")
        
        # Count existing records
        items_count = Item.query.count()
        boms_count = BOM.query.count()
        bom_items_count = BOMItem.query.count()
        suppliers_count = Supplier.query.count()
        departments_count = Department.query.count()
        
        print(f"   Items: {items_count}")
        print(f"   BOMs: {boms_count}")
        print(f"   BOM Items: {bom_items_count}")
        print(f"   Suppliers: {suppliers_count}")
        print(f"   Departments: {departments_count}")
        
        if boms_count > 0:
            print("\n📋 Existing BOMs:")
            boms = BOM.query.limit(3).all()
            for bom in boms:
                print(f"   • {bom.bom_code}: {bom.product.name if bom.product else 'No Product'}")
                
                # Show BOM items with costs
                bom_items = BOMItem.query.filter_by(bom_id=bom.id).limit(5).all()
                total_material_cost = 0
                
                for item in bom_items:
                    line_cost = item.qty_required * (item.unit_cost or 0)
                    total_material_cost += line_cost
                    print(f"     - {item.material.name}: {item.qty_required} × ₹{item.unit_cost or 0:.2f} = ₹{line_cost:.2f}")
                
                # Show processes if any
                processes = BOMProcess.query.filter_by(bom_id=bom.id).all()
                total_process_cost = 0
                
                if processes:
                    print(f"     Process Costs:")
                    for process in processes:
                        process_cost = process.cost_per_unit or 0
                        total_process_cost += process_cost
                        process_type = "Outsourced" if process.is_outsourced else "In-house"
                        print(f"     - {process.process_name} ({process_type}): ₹{process_cost:.2f}")
                
                # Calculate overhead (12%)
                overhead_cost = (total_material_cost + total_process_cost) * 0.12
                total_cost = total_material_cost + total_process_cost + overhead_cost
                
                print(f"     Total Material: ₹{total_material_cost:.2f}")
                print(f"     Total Process: ₹{total_process_cost:.2f}")
                print(f"     Overhead (12%): ₹{overhead_cost:.2f}")
                print(f"     TOTAL COST: ₹{total_cost:.2f}")
                print()
        
        # Show the conceptual calculation
        print("💰 COST CALCULATION METHODOLOGY")
        print("=" * 40)
        
        print("1. 📦 Raw Material Costs (from GRN):")
        print("   • System pulls latest unit rates from GRN entries")
        print("   • Multiplies by quantity required in BOM")
        print("   • Automatic updates when new GRNs are received")
        
        print("\n2. ⚙️ Process Costs:")
        print("   • In-house processes: Labor rates from HR Module")
        print("   • Outsourced processes: Rates from Job Work Forms")
        print("   • Multiplied by estimated hours or per-unit rates")
        
        print("\n3. 🏢 Overhead Costs:")
        print("   • Calculated as percentage of material + process costs")
        print("   • Based on expense data from accounting module")
        print("   • Configurable percentage per product category")
        
        print("\n4. 🔄 Real-time Updates:")
        print("   • Costs recalculate when source data changes")
        print("   • GRN updates → Material cost changes")
        print("   • HR updates → Labor cost changes") 
        print("   • Job Work updates → Outsourcing cost changes")
        
        print(f"\n✨ Example Calculation for Heavy Duty Castor Wheel:")
        print(f"   Raw Materials:  ₹272.75 (Steel ₹213.75 + Rubber ₹45.00 + Bolts ₹14.00)")
        print(f"   Job Work:       ₹37.50  (Zinc coating 2.5kg × ₹15/kg)")
        print(f"   Labor:          ₹480.00 (Machining 2h × ₹150 + Assembly 1.5h × ₹120)")
        print(f"   Overheads:      ₹94.83  (12% of ₹790.25)")
        print(f"   TOTAL COST:     ₹885.08")
        
        print(f"\n🌟 Enhanced BOM Features Available:")
        print(f"   ✓ Component source tracking (In-house vs Purchase)")
        print(f"   ✓ Department and machine assignment")
        print(f"   ✓ Vendor assignment for outsourced processes")
        print(f"   ✓ Lead time tracking")
        print(f"   ✓ Batch tracking configuration")
        print(f"   ✓ Partial production capability")
        print(f"   ✓ Automatic cost calculation")
        print(f"   ✓ Real-time cost updates")
        
        print(f"\n🔗 Try the Enhanced BOM Form at: /production/enhanced-bom")

if __name__ == "__main__":
    show_cost_calculation_demo()