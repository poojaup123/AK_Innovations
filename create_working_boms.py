#!/usr/bin/env python3
"""
Create working BOMs with proper pricing to demonstrate the automatic price update system
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import Item, BOM, BOMItem, BOMProcess, UnitOfMeasure
from app import db

def create_sample_data():
    """Create sample BOMs with realistic manufacturing data"""
    app = create_app()
    with app.app_context():
        print("🔧 Creating sample BOMs and items...")
        
        try:
            # Clear existing BOMs if any
            BOM.query.delete()
            BOMItem.query.delete()
            BOMProcess.query.delete()
            
            # Create UOMs if they don't exist
            uom_pcs = UnitOfMeasure.query.filter_by(symbol='pcs').first()
            if not uom_pcs:
                uom_pcs = UnitOfMeasure(
                    name='Pieces',
                    symbol='pcs',
                    category='Count'
                )
                db.session.add(uom_pcs)
            
            uom_kg = UnitOfMeasure.query.filter_by(symbol='kg').first()
            if not uom_kg:
                uom_kg = UnitOfMeasure(
                    name='Kilograms',
                    symbol='kg',
                    category='Weight'
                )
                db.session.add(uom_kg)
            
            # Create items if they don't exist
            items_data = [
                {'code': 'ITEM-0001', 'name': 'Ms Sheet', 'unit_price': 35.0, 'item_type': 'raw_material'},
                {'code': 'ITEM-0002', 'name': 'Bolt M6x20', 'unit_price': 2.5, 'item_type': 'raw_material'},
                {'code': 'ITEM-0003', 'name': 'Base Plate', 'unit_price': 7.0, 'item_type': 'product'},
                {'code': 'ITEM-0004', 'name': 'Mounted Plate', 'unit_price': 7.0, 'item_type': 'product'},
                {'code': 'ITEM-0005', 'name': 'Castor Wheel', 'unit_price': 150.0, 'item_type': 'finished_goods'}
            ]
            
            items = {}
            for item_data in items_data:
                item = Item.query.filter_by(code=item_data['code']).first()
                if not item:
                    item = Item(
                        code=item_data['code'],
                        name=item_data['name'],
                        unit_price=item_data['unit_price'],
                        item_type=item_data['item_type'],
                        unit_weight=0.5 if 'Sheet' in item_data['name'] else 0.1,
                        unit_of_measure='kg' if 'Sheet' in item_data['name'] else 'pcs'
                    )
                    db.session.add(item)
                items[item_data['code']] = item
            
            db.session.commit()
            
            # Create BOM for Base Plate (ITEM-0003)
            base_plate_bom = BOM(
                bom_code='BOM-BASE-001',
                product=items['ITEM-0003'],
                output_uom=uom_pcs,
                version='1.0',
                status='active',
                is_active=True,
                output_quantity=1.0,
                unit_weight=0.5,
                unit_weight_uom='kg',
                estimated_scrap_percent=3.0,
                labor_cost_per_unit=1.5,
                overhead_percentage=15.0,
                freight_cost_per_unit=0.5,
                markup_percentage=20.0,
                description='Base plate manufactured from MS sheet'
            )
            db.session.add(base_plate_bom)
            db.session.flush()  # Get the ID
            
            # Add BOM items for Base Plate
            base_plate_item = BOMItem(
                bom=base_plate_bom,
                material=items['ITEM-0001'],  # Ms Sheet
                quantity_required=0.6,  # kg
                uom='kg',
                wastage_percent=5.0,
                notes='Cut to size for base plate'
            )
            db.session.add(base_plate_item)
            
            # Add manufacturing process for Base Plate
            cutting_process = BOMProcess(
                bom=base_plate_bom,
                step_number=1,
                process_name='Cutting',
                process_description='Cut MS sheet to required dimensions',
                machine_name='Plasma Cutter',
                setup_time_minutes=10.0,
                cycle_time_minutes=5.0,
                labor_cost_per_hour=150.0,
                machine_cost_per_hour=50.0,
                estimated_scrap_percent=2.0
            )
            db.session.add(cutting_process)
            
            # Create BOM for Mounted Plate (ITEM-0004)
            mounted_plate_bom = BOM(
                bom_code='BOM-MOUNT-001',
                product=items['ITEM-0004'],
                output_uom=uom_pcs,
                version='1.0',
                status='active',
                is_active=True,
                output_quantity=1.0,
                unit_weight=0.6,
                unit_weight_uom='kg',
                estimated_scrap_percent=2.0,
                labor_cost_per_unit=2.0,
                overhead_percentage=15.0,
                freight_cost_per_unit=0.75,
                markup_percentage=20.0,
                description='Mounted plate with bolts'
            )
            db.session.add(mounted_plate_bom)
            db.session.flush()
            
            # Add BOM items for Mounted Plate (uses Base Plate + Bolts)
            mounted_base_item = BOMItem(
                bom=mounted_plate_bom,
                material=items['ITEM-0003'],  # Base Plate
                quantity_required=1.0,  # pcs
                uom='pcs',
                wastage_percent=0.0,
                notes='Base plate assembly'
            )
            db.session.add(mounted_base_item)
            
            mounted_bolt_item = BOMItem(
                bom=mounted_plate_bom,
                material=items['ITEM-0002'],  # Bolt M6x20
                quantity_required=4.0,  # pcs
                uom='pcs',
                wastage_percent=5.0,
                notes='Mounting bolts'
            )
            db.session.add(mounted_bolt_item)
            
            # Add manufacturing process for Mounted Plate
            drilling_process = BOMProcess(
                bom=mounted_plate_bom,
                step_number=1,
                process_name='Drilling',
                process_description='Drill holes and mount bolts',
                machine_name='Drilling Machine',
                setup_time_minutes=5.0,
                cycle_time_minutes=8.0,
                labor_cost_per_hour=150.0,
                machine_cost_per_hour=40.0,
                estimated_scrap_percent=1.0
            )
            db.session.add(drilling_process)
            
            # Create BOM for Castor Wheel (ITEM-0005) - uses Mounted Plate
            castor_wheel_bom = BOM(
                bom_code='BOM-CASTOR-001',
                product=items['ITEM-0005'],
                output_uom=uom_pcs,
                version='1.0',
                status='active',
                is_active=True,
                output_quantity=1.0,
                unit_weight=1.2,
                unit_weight_uom='kg',
                estimated_scrap_percent=1.0,
                labor_cost_per_unit=5.0,
                overhead_percentage=20.0,
                freight_cost_per_unit=2.0,
                markup_percentage=25.0,
                description='Complete castor wheel assembly'
            )
            db.session.add(castor_wheel_bom)
            db.session.flush()
            
            # Add BOM items for Castor Wheel
            castor_plate_item = BOMItem(
                bom=castor_wheel_bom,
                material=items['ITEM-0004'],  # Mounted Plate
                quantity_required=1.0,  # pcs
                uom='pcs',
                wastage_percent=0.0,
                notes='Mounted plate base'
            )
            db.session.add(castor_plate_item)
            
            # Add assembly process for Castor Wheel
            assembly_process = BOMProcess(
                bom=castor_wheel_bom,
                step_number=1,
                process_name='Assembly',
                process_description='Final assembly of castor wheel',
                machine_name='Assembly Station',
                setup_time_minutes=15.0,
                cycle_time_minutes=20.0,
                labor_cost_per_hour=180.0,
                machine_cost_per_hour=25.0,
                estimated_scrap_percent=0.5
            )
            db.session.add(assembly_process)
            
            db.session.commit()
            
            print("✅ Sample BOMs created successfully!")
            print("\n📋 Created BOMs:")
            print(f"   1. {base_plate_bom.bom_code} - {base_plate_bom.product.name}")
            print(f"   2. {mounted_plate_bom.bom_code} - {mounted_plate_bom.product.name}")
            print(f"   3. {castor_wheel_bom.bom_code} - {castor_wheel_bom.product.name}")
            
            # Now trigger automatic price updates
            print("\n🔄 Triggering automatic price updates...")
            updated_items = BOM.update_all_item_prices_from_bom()
            
            if updated_items:
                print(f"\n💰 Updated prices for {len(updated_items)} items:")
                for item in updated_items:
                    print(f"   {item['item_code']}: ₹{item['old_price']:.2f} → ₹{item['new_price']:.2f}")
            else:
                print("\n📊 All prices are already up to date")
            
            print("\n🎉 BOM creation and pricing completed!")
            print("\n🌐 You can now access:")
            print(f"   - BOM List: /production/bom")
            print(f"   - Edit Base Plate BOM: /production/bom/edit/{base_plate_bom.id}")
            print(f"   - Edit Mounted Plate BOM: /production/bom/edit/{mounted_plate_bom.id}")
            print(f"   - Edit Castor Wheel BOM: /production/bom/edit/{castor_wheel_bom.id}")
            
        except Exception as e:
            print(f"❌ Error creating sample data: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False
        
        return True

if __name__ == "__main__":
    success = create_sample_data()
    exit_code = 0 if success else 1
    sys.exit(exit_code)