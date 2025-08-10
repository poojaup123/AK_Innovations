#!/usr/bin/env python3
"""
Create demo data to showcase automatic BOM cost calculation from GRN, Job Work, and HR modules
This script demonstrates how costs are automatically pulled from authentic data sources
"""

import sys
import os
from datetime import datetime, date
from decimal import Decimal

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import *

def create_cost_calculation_demo():
    """Create comprehensive demo data showing cost calculation from GRN, Job Work, and HR"""
    
    with app.app_context():
        print("🏭 Creating BOM Cost Calculation Demo Data")
        print("=" * 60)
        
        # 1. Create Items (Raw Materials and Products)
        print("📦 Creating Items...")
        
        # Raw Materials
        steel_sheet = Item(
            name="Steel Sheet 2mm",
            code="STL-SHT-2MM",
            item_type="raw_material",
            category="Metal",
            unit="KG",
            current_stock=500.0,
            min_stock_level=50.0,
            cost_price=85.50,
            created_at=datetime.now()
        )
        
        wheel_rubber = Item(
            name="Rubber Wheel 100mm",
            code="WHL-RUB-100",
            item_type="raw_material", 
            category="Rubber",
            unit="PCS",
            current_stock=200.0,
            min_stock_level=25.0,
            cost_price=45.00,
            created_at=datetime.now()
        )
        
        anchor_bolt = Item(
            name="Anchor Bolt M8x25",
            code="ABT-M8-25",
            item_type="raw_material",
            category="Fasteners",
            unit="PCS", 
            current_stock=1000.0,
            min_stock_level=100.0,
            cost_price=3.50,
            created_at=datetime.now()
        )
        
        # Final Product
        castor_wheel = Item(
            name="Heavy Duty Castor Wheel",
            code="HDC-WHEEL-001",
            item_type="finished_goods",
            category="Castor Assembly",
            unit="SET",
            current_stock=50.0,
            min_stock_level=10.0,
            created_at=datetime.now()
        )
        
        db.session.add_all([steel_sheet, wheel_rubber, anchor_bolt, castor_wheel])
        db.session.commit()
        
        # 2. Create Suppliers for GRN cost tracking
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
            is_active=True,
            created_at=datetime.now()
        )
        
        rubber_supplier = Supplier(
            name="Apollo Rubber Components",
            code="ARC-001", 
            partner_type="supplier",
            contact_person="Priya Sharma",
            email="sales@apollorubber.com",
            phone="9123456789",
            address="Sector 15, Pune",
            gst_number="27FGHIJ5678K2L6",
            is_active=True,
            created_at=datetime.now()
        )
        
        # Job Work Vendor
        coating_vendor = Supplier(
            name="Precision Zinc Coating",
            code="PZC-001",
            partner_type="vendor",
            contact_person="Amit Patel",
            email="jobs@precisionzinc.com", 
            phone="9765432108",
            address="MIDC Nashik",
            gst_number="27KLMNO9012P3Q7",
            is_active=True,
            created_at=datetime.now()
        )
        
        db.session.add_all([steel_supplier, rubber_supplier, coating_vendor])
        db.session.commit()
        
        # 3. Create Employees for HR cost tracking  
        print("👥 Creating Employees...")
        
        # Departments first
        manufacturing_dept = Department(
            name="Manufacturing",
            code="MFG",
            is_active=True,
            created_at=datetime.now()
        )
        
        assembly_dept = Department(
            name="Assembly",
            code="ASM", 
            is_active=True,
            created_at=datetime.now()
        )
        
        db.session.add_all([manufacturing_dept, assembly_dept])
        db.session.commit()
        
        # Employees with different hourly rates
        machinist = Employee(
            emp_code="EMP-001",
            name="Suresh Machinist",
            department_id=manufacturing_dept.id,
            designation="Senior Machinist",
            hourly_rate=150.00,  # ₹150 per hour
            monthly_salary=32000.00,
            is_active=True,
            date_of_joining=date(2023, 1, 15),
            created_at=datetime.now()
        )
        
        assembler = Employee(
            emp_code="EMP-002", 
            name="Ravi Assembler",
            department_id=assembly_dept.id,
            designation="Assembly Technician",
            hourly_rate=120.00,  # ₹120 per hour
            monthly_salary=25000.00,
            is_active=True,
            date_of_joining=date(2023, 3, 1),
            created_at=datetime.now()
        )
        
        db.session.add_all([machinist, assembler])
        db.session.commit()
        
        # 4. Create GRN entries with actual costs
        print("📋 Creating GRN entries with real cost data...")
        
        # Purchase Order first
        steel_po = PurchaseOrder(
            po_number="PO-2024-001",
            supplier_id=steel_supplier.id,
            po_date=date.today(),
            status="approved",
            total_amount=25650.00,  # 300 KG * ₹85.50
            created_at=datetime.now()
        )
        db.session.add(steel_po)
        db.session.commit()
        
        # GRN for Steel with actual costs
        steel_grn = GRN(
            grn_number="GRN-2024-001", 
            po_id=steel_po.id,
            supplier_id=steel_supplier.id,
            grn_date=date.today(),
            status="received",
            total_amount=25650.00,
            created_at=datetime.now()
        )
        db.session.add(steel_grn)
        db.session.commit()
        
        # GRN Item with cost per unit
        steel_grn_item = GRNItem(
            grn_id=steel_grn.id,
            item_id=steel_sheet.id,
            ordered_quantity=300.0,
            received_quantity=300.0, 
            unit_rate=85.50,  # Actual cost from supplier
            total_amount=25650.00,
            created_at=datetime.now()
        )
        db.session.add(steel_grn_item)
        
        # Rubber GRN
        rubber_po = PurchaseOrder(
            po_number="PO-2024-002",
            supplier_id=rubber_supplier.id,
            po_date=date.today(),
            status="approved", 
            total_amount=4500.00,  # 100 PCS * ₹45
            created_at=datetime.now()
        )
        db.session.add(rubber_po)
        db.session.commit()
        
        rubber_grn = GRN(
            grn_number="GRN-2024-002",
            po_id=rubber_po.id,
            supplier_id=rubber_supplier.id,
            grn_date=date.today(),
            status="received",
            total_amount=4500.00,
            created_at=datetime.now()
        )
        db.session.add(rubber_grn)
        db.session.commit()
        
        rubber_grn_item = GRNItem(
            grn_id=rubber_grn.id,
            item_id=wheel_rubber.id,
            ordered_quantity=100.0,
            received_quantity=100.0,
            unit_rate=45.00,  # Actual cost from supplier
            total_amount=4500.00,
            created_at=datetime.now()
        )
        db.session.add(rubber_grn_item)
        db.session.commit()
        
        # 5. Create Job Work entries with costs
        print("⚙️ Creating Job Work entries...")
        
        zinc_coating_job = JobWork(
            job_number="JOB-2024-001",
            item_id=steel_sheet.id,
            vendor_id=coating_vendor.id,
            process_name="Zinc Coating",
            quantity_sent=50.0,  # 50 KG of steel parts
            rate_per_unit=15.00,  # ₹15 per KG coating
            total_cost=750.00,  # 50 * 15
            job_date=date.today(),
            status="completed",
            created_at=datetime.now()
        )
        db.session.add(zinc_coating_job)
        db.session.commit()
        
        # 6. Create Time Tracking entries for labor costs
        print("⏰ Creating Time Tracking for labor costs...")
        
        machining_time = TimeTracking(
            employee_id=machinist.id,
            work_date=date.today(),
            hours_worked=8.0,
            hourly_rate=150.00,
            total_amount=1200.00,  # 8 hours * ₹150
            work_description="Machining castor wheel components",
            created_at=datetime.now()
        )
        
        assembly_time = TimeTracking(
            employee_id=assembler.id,
            work_date=date.today(), 
            hours_worked=6.0,
            hourly_rate=120.00,
            total_amount=720.00,  # 6 hours * ₹120
            work_description="Assembly of castor wheels", 
            created_at=datetime.now()
        )
        
        db.session.add_all([machining_time, assembly_time])
        db.session.commit()
        
        # 7. Create Enhanced BOM with cost references
        print("📋 Creating Enhanced BOM with cost calculations...")
        
        castor_bom = BOM(
            bom_code="BOM-HDC-001",
            product_id=castor_wheel.id,
            output_quantity=1.0,
            version="1.0", 
            effective_date=date.today(),
            bom_status="active",
            lead_time_days=3.0,
            auto_cost_calculation=True,
            batch_tracking_enabled=True,
            is_active=True,
            created_at=datetime.now()
        )
        db.session.add(castor_bom)
        db.session.commit()
        
        # BOM Items with cost references
        steel_bom_item = BOMItem(
            bom_id=castor_bom.id,
            material_id=steel_sheet.id,
            qty_required=2.5,  # 2.5 KG steel per castor
            unit_cost=85.50,  # From GRN
            component_type="raw_material",
            component_source="purchase",
            batch_tracking_required=True,
            assigned_department_id=manufacturing_dept.id,
            created_at=datetime.now()
        )
        
        rubber_bom_item = BOMItem(
            bom_id=castor_bom.id,
            material_id=wheel_rubber.id,
            qty_required=1.0,  # 1 rubber wheel per castor
            unit_cost=45.00,  # From GRN  
            component_type="raw_material",
            component_source="purchase",
            batch_tracking_required=True,
            assigned_department_id=assembly_dept.id,
            created_at=datetime.now()
        )
        
        bolt_bom_item = BOMItem(
            bom_id=castor_bom.id,
            material_id=anchor_bolt.id,
            qty_required=4.0,  # 4 bolts per castor
            unit_cost=3.50,  # Standard cost
            component_type="raw_material",
            component_source="purchase",
            batch_tracking_required=False,
            created_at=datetime.now()
        )
        
        db.session.add_all([steel_bom_item, rubber_bom_item, bolt_bom_item])
        db.session.commit()
        
        # 8. Create BOM Processes with labor cost references
        print("⚡ Creating BOM Processes...")
        
        machining_process = BOMProcess(
            bom_id=castor_bom.id,
            step_number=1,
            process_name="Machining",
            department_id=manufacturing_dept.id,
            lead_time_days=1.0,
            labor_rate_per_hour=150.00,  # From HR
            estimated_hours=2.0,  # 2 hours per unit
            cost_per_unit=300.00,  # 2 * 150
            is_outsourced=False,
            created_at=datetime.now()
        )
        
        coating_process = BOMProcess(
            bom_id=castor_bom.id,
            step_number=2,
            process_name="Zinc Coating",
            vendor_id=coating_vendor.id,
            lead_time_days=1.0,
            cost_per_unit=15.00,  # From Job Work rate
            is_outsourced=True,
            created_at=datetime.now()
        )
        
        assembly_process = BOMProcess(
            bom_id=castor_bom.id,
            step_number=3,
            process_name="Assembly",
            department_id=assembly_dept.id,
            lead_time_days=1.0,
            labor_rate_per_hour=120.00,  # From HR
            estimated_hours=1.5,  # 1.5 hours per unit
            cost_per_unit=180.00,  # 1.5 * 120
            is_outsourced=False,
            created_at=datetime.now()
        )
        
        db.session.add_all([machining_process, coating_process, assembly_process])
        db.session.commit()
        
        # 9. Calculate and display cost breakdown
        print("\n💰 COST CALCULATION SUMMARY")
        print("=" * 50)
        
        # Raw Material Costs (from GRN)
        steel_cost = 2.5 * 85.50  # qty * GRN unit rate
        rubber_cost = 1.0 * 45.00
        bolt_cost = 4.0 * 3.50
        raw_material_cost = steel_cost + rubber_cost + bolt_cost
        
        print(f"📦 Raw Material Costs (from GRN):")
        print(f"   Steel Sheet: {2.5} KG × ₹{85.50} = ₹{steel_cost:.2f}")
        print(f"   Rubber Wheel: {1.0} PCS × ₹{45.00} = ₹{rubber_cost:.2f}")
        print(f"   Anchor Bolts: {4.0} PCS × ₹{3.50} = ₹{bolt_cost:.2f}")
        print(f"   Total Raw Material: ₹{raw_material_cost:.2f}")
        
        # Job Work Costs
        job_work_cost = 15.00  # Zinc coating per unit
        print(f"\n⚙️ Job Work Costs:")
        print(f"   Zinc Coating: ₹{job_work_cost:.2f}")
        
        # Labor Costs (from HR Module)
        labor_cost = 300.00 + 180.00  # Machining + Assembly
        print(f"\n👥 Labor Costs (from HR Module):")
        print(f"   Machining: 2.0 hrs × ₹{150.00} = ₹{300.00}")
        print(f"   Assembly: 1.5 hrs × ₹{120.00} = ₹{180.00}")
        print(f"   Total Labor: ₹{labor_cost:.2f}")
        
        # Total Cost
        total_cost = raw_material_cost + job_work_cost + labor_cost
        print(f"\n🎯 TOTAL COST PER UNIT: ₹{total_cost:.2f}")
        print(f"   Raw Material: ₹{raw_material_cost:.2f} ({raw_material_cost/total_cost*100:.1f}%)")
        print(f"   Job Work: ₹{job_work_cost:.2f} ({job_work_cost/total_cost*100:.1f}%)")
        print(f"   Labor: ₹{labor_cost:.2f} ({labor_cost/total_cost*100:.1f}%)")
        
        print(f"\n✅ Demo data created successfully!")
        print(f"   - Items: {Item.query.count()}")
        print(f"   - Suppliers: {Supplier.query.count()}")
        print(f"   - Employees: {Employee.query.count()}")
        print(f"   - GRN Entries: {GRN.query.count()}")
        print(f"   - Job Work Entries: {JobWork.query.count()}")
        print(f"   - Time Tracking: {TimeTracking.query.count()}")
        print(f"   - BOMs: {BOM.query.count()}")
        print(f"   - BOM Items: {BOMItem.query.count()}")
        print(f"   - BOM Processes: {BOMProcess.query.count()}")

if __name__ == "__main__":
    create_cost_calculation_demo()