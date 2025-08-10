#!/usr/bin/env python3
"""
Create sample nested BOM data to demonstrate the nested BOM functionality
"""

from app import app, db
from models import Item, BOM, BOMItem
from datetime import datetime

def create_nested_bom_demo():
    with app.app_context():
        try:
            # Get existing items
            castor_wheel = Item.query.filter_by(name='castor wheel').first()
            mounted_plate = Item.query.filter_by(name='Mounted Plate').first()
            ms_sheet = Item.query.filter_by(name='Ms sheet').first()
            bearing = Item.query.filter_by(name='Bearing Balls').first()
            
            if not all([castor_wheel, mounted_plate, ms_sheet]):
                print("Required items not found")
                return
            
            # 1. Create/Update BOM for Mounted Plate (sub-component)
            mounted_plate_bom = BOM.query.filter_by(product_id=mounted_plate.id, is_active=True).first()
            if not mounted_plate_bom:
                mounted_plate_bom = BOM(
                    bom_code='BOM-MOUNTED-PLATE-001',
                    product_id=mounted_plate.id,
                    status='active',
                    is_active=True,
                    output_quantity=1.0,
                    description='BOM for Mounted Plate assembly',
                    labor_cost_per_unit=25.0,
                    overhead_cost_per_unit=10.0
                )
                db.session.add(mounted_plate_bom)
                db.session.flush()  # Get the ID
                
                # Add components to Mounted Plate BOM
                if ms_sheet:
                    bom_item1 = BOMItem(
                        bom_id=mounted_plate_bom.id,
                        item_id=ms_sheet.id,
                        quantity_required=0.8,
                        unit='kg',
                        unit_cost=55.0,
                        remarks='Main plate material'
                    )
                    db.session.add(bom_item1)
                
                if bearing:
                    bom_item2 = BOMItem(
                        bom_id=mounted_plate_bom.id,
                        item_id=bearing.id,
                        quantity_required=4.0,
                        unit='Pcs',
                        unit_cost=12.50,
                        remarks='Corner mounting bearings'
                    )
                    db.session.add(bom_item2)
                
                print(f"Created BOM for Mounted Plate: {mounted_plate_bom.bom_code}")
            
            # 2. Create/Update BOM for Castor Wheel (parent assembly)
            castor_bom = BOM.query.filter_by(product_id=castor_wheel.id, is_active=True).first()
            if castor_bom:
                # Check if mounted plate is already a component
                existing_component = BOMItem.query.filter_by(
                    bom_id=castor_bom.id, 
                    item_id=mounted_plate.id
                ).first()
                
                if not existing_component:
                    # Add mounted plate as a component with nested BOM
                    nested_component = BOMItem(
                        bom_id=castor_bom.id,
                        item_id=mounted_plate.id,
                        quantity_required=1.0,
                        unit='Pcs',
                        unit_cost=125.0,
                        remarks='Sub-assembly with own BOM'
                    )
                    db.session.add(nested_component)
                    print(f"Added Mounted Plate to Castor Wheel BOM - this will show nested BOM functionality")
            
            db.session.commit()
            
            # Verify the setup
            print("\n=== Nested BOM Setup Complete ===")
            print(f"Mounted Plate BOM ID: {mounted_plate_bom.id if mounted_plate_bom else 'None'}")
            print(f"Mounted Plate active_bom: {mounted_plate.active_bom is not None}")
            
            if castor_bom:
                print(f"Castor Wheel BOM: {castor_bom.bom_code}")
                for item in castor_bom.items:
                    has_sub_bom = item.item.active_bom is not None
                    print(f"  - {item.item.name}: {item.quantity_required} {item.unit} [Sub-BOM: {has_sub_bom}]")
            
            print("\nNow when you edit the Castor Wheel BOM, you should see:")
            print("1. 'Has Sub-BOM' badge next to Mounted Plate in the dropdown")
            print("2. Expandable sub-BOM section when Mounted Plate is added")
            print("3. View/Edit sub-BOM buttons")
            
        except Exception as e:
            print(f"Error: {e}")
            db.session.rollback()

if __name__ == "__main__":
    create_nested_bom_demo()