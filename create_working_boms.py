#!/usr/bin/env python3
"""
Create working BOM demo data with proper model structure
"""

import sys
import os
from datetime import datetime, date

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import *

def create_working_bom_demo():
    """Create working BOM data that integrates with existing system"""
    
    with app.app_context():
        print("🏭 Creating Working BOM Demo with Cost Integration")
        print("=" * 60)
        
        # Check if items exist, if not create them
        steel_sheet = Item.query.filter_by(code='STL-SHT-2MM').first()
        if not steel_sheet:
            print("📦 Creating Items...")
            steel_sheet = Item(
                name="Steel Sheet 2mm",
                code="STL-SHT-2MM",
                description="High grade steel sheet for manufacturing",
                unit_of_measure="KG",
                current_stock=500.0,
                minimum_stock=50.0
            )
            db.session.add(steel_sheet)
        
        wheel_rubber = Item.query.filter_by(code='WHL-RUB-100').first()
        if not wheel_rubber:
            wheel_rubber = Item(
                name="Rubber Wheel 100mm",
                code="WHL-RUB-100",
                description="Industrial rubber wheel 100mm diameter",
                unit_of_measure="PCS",
                current_stock=200.0,
                minimum_stock=25.0
            )
            db.session.add(wheel_rubber)
        
        anchor_bolt = Item.query.filter_by(code='ABT-M8-25').first()
        if not anchor_bolt:
            anchor_bolt = Item(
                name="Anchor Bolt M8x25",
                code="ABT-M8-25",
                description="M8 x 25mm anchor bolt with hex head",
                unit_of_measure="PCS",
                current_stock=1000.0,
                minimum_stock=100.0
            )
            db.session.add(anchor_bolt)
        
        castor_wheel = Item.query.filter_by(code='HDC-WHEEL-001').first()
        if not castor_wheel:
            castor_wheel = Item(
                name="Heavy Duty Castor Wheel",
                code="HDC-WHEEL-001",
                description="Heavy duty castor wheel assembly",
                unit_of_measure="SET",
                current_stock=50.0,
                minimum_stock=10.0
            )
            db.session.add(castor_wheel)
        
        db.session.commit()
        
        # Create departments if they don't exist
        manufacturing_dept = Department.query.filter_by(code='MFG').first()
        if not manufacturing_dept:
            print("🏢 Creating Departments...")
            manufacturing_dept = Department(
                name="Manufacturing",
                code="MFG",
                is_active=True
            )
            db.session.add(manufacturing_dept)
        
        assembly_dept = Department.query.filter_by(code='ASM').first()
        if not assembly_dept:
            assembly_dept = Department(
                name="Assembly",
                code="ASM",
                is_active=True
            )
            db.session.add(assembly_dept)
        
        db.session.commit()
        
        # Create suppliers if they don't exist
        steel_supplier = Supplier.query.filter_by(code='MSI-001').first()
        if not steel_supplier:
            print("🏢 Creating Suppliers...")
            steel_supplier = Supplier(
                name="Maharashtra Steel Industries",
                code="MSI-001",
                partner_type="supplier",
                contact_person="Rajesh Kumar",
                email="orders@maharashtrasteel.com",
                phone="9876543210",
                address="Plot 23, Aurangabad Industrial Area",
                gst_number="27ABCDE1234F1Z5",
                is_active=True
            )
            db.session.add(steel_supplier)
        
        coating_vendor = Supplier.query.filter_by(code='PZC-001').first()
        if not coating_vendor:
            coating_vendor = Supplier(
                name="Precision Zinc Coating",
                code="PZC-001",
                partner_type="vendor",
                contact_person="Amit Patel",
                email="jobs@precisionzinc.com",
                phone="9765432108",
                address="MIDC Nashik",
                gst_number="27KLMNO9012P3Q7",
                is_active=True
            )
            db.session.add(coating_vendor)
        
        db.session.commit()
        
        # Create Enhanced BOM
        castor_bom = BOM.query.filter_by(bom_code='BOM-HDC-001').first()
        if castor_bom:
            print("♻️ BOM already exists, skipping creation...")
        else:
            print("📋 Creating Enhanced BOM...")
            castor_bom = BOM(
                bom_code="BOM-HDC-001",
                product_id=castor_wheel.id,
                output_quantity=1.0,
                version="1.0",
                is_active=True
            )
            db.session.add(castor_bom)
            db.session.commit()
            
            # Create BOM Items
            print("📦 Adding BOM Components...")
            
            steel_bom_item = BOMItem(
                bom_id=castor_bom.id,
                material_id=steel_sheet.id,
                qty_required=2.5,
                unit_cost=85.50  # Cost from GRN
            )
            db.session.add(steel_bom_item)
            
            rubber_bom_item = BOMItem(
                bom_id=castor_bom.id,
                material_id=wheel_rubber.id,
                qty_required=1.0,
                unit_cost=45.00  # Cost from GRN
            )
            db.session.add(rubber_bom_item)
            
            bolt_bom_item = BOMItem(
                bom_id=castor_bom.id,
                material_id=anchor_bolt.id,
                qty_required=4.0,
                unit_cost=3.50  # Cost from GRN
            )
            db.session.add(bolt_bom_item)
            
            db.session.commit()
            
            # Create BOM Processes
            print("⚙️ Adding BOM Processes...")
            
            machining_process = BOMProcess(
                bom_id=castor_bom.id,
                step_number=1,
                process_name="Machining",
                cost_per_unit=300.00,  # 2 hrs × ₹150/hr from HR
                is_outsourced=False
            )
            db.session.add(machining_process)
            
            coating_process = BOMProcess(
                bom_id=castor_bom.id,
                step_number=2,
                process_name="Zinc Coating",
                cost_per_unit=37.50,  # 2.5 kg × ₹15/kg from Job Work
                is_outsourced=True
            )
            db.session.add(coating_process)
            
            assembly_process = BOMProcess(
                bom_id=castor_bom.id,
                step_number=3,
                process_name="Assembly",
                cost_per_unit=180.00,  # 1.5 hrs × ₹120/hr from HR
                is_outsourced=False
            )
            db.session.add(assembly_process)
            
            db.session.commit()
        
        # Calculate and display cost summary
        print("\n💰 BOM COST CALCULATION")
        print("=" * 40)
        
        # Get BOM items
        bom_items = BOMItem.query.filter_by(bom_id=castor_bom.id).all()
        total_material_cost = 0
        
        print("📦 Material Costs:")
        for item in bom_items:
            item_cost = item.qty_required * (item.unit_cost or 0)
            total_material_cost += item_cost
            print(f"   {item.material.name}: {item.qty_required} × ₹{item.unit_cost or 0} = ₹{item_cost:.2f}")
        
        print(f"   Total Material: ₹{total_material_cost:.2f}")
        
        # Get process costs
        bom_processes = BOMProcess.query.filter_by(bom_id=castor_bom.id).all()
        total_process_cost = 0
        
        print("\n⚙️ Process Costs:")
        for process in bom_processes:
            process_cost = process.cost_per_unit or 0
            total_process_cost += process_cost
            process_type = "Outsourced" if process.is_outsourced else "In-house"
            print(f"   {process.process_name} ({process_type}): ₹{process_cost:.2f}")
        
        print(f"   Total Process: ₹{total_process_cost:.2f}")
        
        # Calculate overheads (12% of material + process)
        overhead_rate = 0.12
        overhead_cost = (total_material_cost + total_process_cost) * overhead_rate
        print(f"\n🏢 Overheads (12%): ₹{overhead_cost:.2f}")
        
        # Total cost
        total_cost = total_material_cost + total_process_cost + overhead_cost
        print(f"\n🎯 TOTAL COST PER UNIT: ₹{total_cost:.2f}")
        
        # Cost breakdown percentages
        print(f"\n📊 Cost Breakdown:")
        print(f"   Materials: ₹{total_material_cost:.2f} ({(total_material_cost/total_cost)*100:.1f}%)")
        print(f"   Processes: ₹{total_process_cost:.2f} ({(total_process_cost/total_cost)*100:.1f}%)")
        print(f"   Overheads: ₹{overhead_cost:.2f} ({(overhead_cost/total_cost)*100:.1f}%)")
        
        print(f"\n✅ Enhanced BOM Demo Created Successfully!")
        print(f"   - Items: {Item.query.count()}")
        print(f"   - Departments: {Department.query.count()}")
        print(f"   - Suppliers: {Supplier.query.count()}")
        print(f"   - BOMs: {BOM.query.count()}")
        print(f"   - BOM Items: {BOMItem.query.count()}")
        print(f"   - BOM Processes: {BOMProcess.query.count()}")
        
        print(f"\n🌟 Go to /production/enhanced-bom to see the enhanced BOM form!")
        print(f"    The form now shows automatic cost calculation from:")
        print(f"    • GRN data for material costs")
        print(f"    • Job Work rates for outsourced processes")
        print(f"    • HR Module for labor rates")
        print(f"    • Automatic overhead calculations")

if __name__ == "__main__":
    create_working_bom_demo()