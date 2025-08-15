#!/usr/bin/env python3
"""
Create working BOMs with proper UOM handling
"""

import os
import sys
from datetime import datetime, date

# Add the project root to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from models import Item, Supplier, BOM, BOMItem, UnitOfMeasure
from models.batch import InventoryBatch

def create_working_boms():
    """Create working BOMs with proper UOM references"""
    
    app = create_app()
    with app.app_context():
        print("Creating working BOMs with proper UOM handling...")
        
        try:
            # First ensure we have some UOMs
            uoms_data = [
                {"code": "PCS", "name": "Pieces", "description": "Count of individual items"},
                {"code": "KG", "name": "Kilograms", "description": "Weight in kilograms"},
                {"code": "SQM", "name": "Square Meters", "description": "Area in square meters"},
                {"code": "MTR", "name": "Meters", "description": "Length in meters"}
            ]
            
            uoms = {}
            for uom_data in uoms_data:
                uom = UnitOfMeasure.query.filter_by(code=uom_data["code"]).first()
                if not uom:
                    uom = UnitOfMeasure(**uom_data)
                    db.session.add(uom)
                uoms[uom_data["code"]] = uom
                print(f"Ensured UOM: {uom.code} - {uom.name}")
            
            db.session.commit()
            
            # Create or get items
            items_data = [
                {"code": "RM001", "name": "Aluminum Sheet", "unit_of_measure": "SQM"},
                {"code": "EC001", "name": "Microcontroller", "unit_of_measure": "PCS"},
                {"code": "HW001", "name": "Hex Bolt M6", "unit_of_measure": "PCS"},
                {"code": "SA001", "name": "Control Panel", "unit_of_measure": "PCS"},
                {"code": "FG001", "name": "Smart Controller", "unit_of_measure": "PCS"}
            ]
            
            items = {}
            for item_data in items_data:
                item = Item.query.filter_by(code=item_data["code"]).first()
                if not item:
                    item = Item(
                        code=item_data["code"],
                        name=item_data["name"],
                        unit_of_measure=item_data["unit_of_measure"],
                        current_stock=100.0,
                        minimum_stock=10.0
                    )
                    db.session.add(item)
                    print(f"Created item: {item.code} - {item.name}")
                items[item_data["code"]] = item
            
            db.session.commit()
            
            # Create inventory batches
            batch_data = [
                {"item_code": "RM001", "batch_code": "RM001-2025-001", "qty_raw": 50.0},
                {"item_code": "EC001", "batch_code": "EC001-2025-001", "qty_raw": 100.0},
                {"item_code": "HW001", "batch_code": "HW001-2025-001", "qty_raw": 500.0}
            ]
            
            for batch_info in batch_data:
                item = items[batch_info["item_code"]]
                batch = InventoryBatch.query.filter_by(batch_code=batch_info["batch_code"]).first()
                if not batch:
                    batch = InventoryBatch(
                        item_id=item.id,
                        batch_code=batch_info["batch_code"],
                        qty_raw=batch_info["qty_raw"],
                        uom=item.unit_of_measure,
                        location="STORE-A",
                        purchase_rate=50.0,
                        mfg_date=date(2025, 1, 15),
                        source_type='purchase'
                    )
                    db.session.add(batch)
                    print(f"Created batch: {batch.batch_code}")
            
            db.session.commit()
            
            # Create Level 1 BOM - Sub-assembly (SA001)
            sa001_item = items["SA001"]
            bom1 = BOM.query.filter_by(product_id=sa001_item.id).first()
            if not bom1:
                bom1 = BOM(
                    bom_code=f"BOM-{sa001_item.code}-001",
                    product_id=sa001_item.id,
                    version="1.0",
                    status="active",
                    description="Control Panel Sub-assembly BOM",
                    labor_cost_per_unit=100.0,
                    overhead_percentage=10.0
                )
                db.session.add(bom1)
                db.session.flush()
                
                # Add components to Level 1 BOM with proper UOM IDs
                components1 = [
                    {"item": items["RM001"], "qty": 0.5, "uom_code": "SQM"},
                    {"item": items["EC001"], "qty": 1.0, "uom_code": "PCS"},
                    {"item": items["HW001"], "qty": 4.0, "uom_code": "PCS"}
                ]
                
                for comp in components1:
                    uom = uoms[comp["uom_code"]]
                    bom_item = BOMItem(
                        bom_id=bom1.id,
                        material_id=comp["item"].id,
                        qty_required=comp["qty"],
                        uom_id=uom.id,
                        unit=comp["uom_code"]
                    )
                    db.session.add(bom_item)
                
                print(f"Created Level 1 BOM for {sa001_item.name}")
            
            # Create Level 2 BOM - Finished product (FG001) using sub-assembly
            fg001_item = items["FG001"]
            bom2 = BOM.query.filter_by(product_id=fg001_item.id).first()
            if not bom2:
                bom2 = BOM(
                    bom_code=f"BOM-{fg001_item.code}-001",
                    product_id=fg001_item.id,
                    version="1.0",
                    status="active",
                    description="Smart Controller Finished Product BOM - NESTED BOM",
                    labor_cost_per_unit=200.0,
                    overhead_percentage=15.0
                )
                db.session.add(bom2)
                db.session.flush()
                
                # Add components to Level 2 BOM (includes sub-assembly)
                components2 = [
                    {"item": items["SA001"], "qty": 1.0, "uom_code": "PCS"},  # This is the nested part!
                    {"item": items["RM001"], "qty": 0.3, "uom_code": "SQM"},  # Additional direct materials
                    {"item": items["HW001"], "qty": 8.0, "uom_code": "PCS"}   # Additional hardware
                ]
                
                for comp in components2:
                    uom = uoms[comp["uom_code"]]
                    bom_item = BOMItem(
                        bom_id=bom2.id,
                        material_id=comp["item"].id,
                        qty_required=comp["qty"],
                        uom_id=uom.id,
                        unit=comp["uom_code"]
                    )
                    db.session.add(bom_item)
                
                print(f"Created Level 2 BOM for {fg001_item.name} - NESTED BOM!")
            
            db.session.commit()
            
            print("\n=== SUCCESS: NESTED BOM STRUCTURE CREATED ===")
            print("✓ 2 BOMs created successfully")
            print("✓ Nested BOM structure implemented")
            print("✓ Inventory batches created")
            print("✓ Ready for production planning")
            
            # Summary of what was created
            all_boms = BOM.query.all()
            print(f"\nTotal BOMs in system: {len(all_boms)}")
            for bom in all_boms:
                item_count = len(bom.items)
                print(f"- {bom.bom_code}: {bom.product.name} ({item_count} components)")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    create_working_boms()