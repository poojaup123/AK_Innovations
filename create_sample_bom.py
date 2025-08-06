#!/usr/bin/env python3
"""
Simple script to create two nested BOMs successfully
"""

import os
import sys
from datetime import datetime, date

# Add the project root to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from models import Item, Supplier, BOM, BOMItem
from models.batch import InventoryBatch

def create_sample_boms():
    """Create sample nested BOMs"""
    
    app = create_app()
    with app.app_context():
        print("Creating sample nested BOMs...")
        
        try:
            # Just create the most basic nested BOM structure
            
            # Check if items exist, if not create them
            items_to_check = [
                {"code": "RM001", "name": "Aluminum Sheet", "unit_of_measure": "SQM"},
                {"code": "EC001", "name": "Microcontroller", "unit_of_measure": "PCS"},
                {"code": "HW001", "name": "Hex Bolt M6", "unit_of_measure": "PCS"},
                {"code": "SA001", "name": "Control Panel", "unit_of_measure": "PCS"},
                {"code": "FG001", "name": "Smart Controller", "unit_of_measure": "PCS"}
            ]
            
            items = {}
            for item_data in items_to_check:
                item = Item.query.filter_by(code=item_data["code"]).first()
                if not item:
                    item = Item(
                        code=item_data["code"],
                        name=item_data["name"],
                        unit_of_measure=item_data["unit_of_measure"],
                        current_stock=0.0,
                        minimum_stock=10.0
                    )
                    db.session.add(item)
                    print(f"Created item: {item.code} - {item.name}")
                items[item_data["code"]] = item
            
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
                    description="Control Panel Sub-assembly BOM"
                )
                db.session.add(bom1)
                db.session.flush()
                
                # Add components to Level 1 BOM
                components1 = [
                    {"item": items["RM001"], "qty": 0.5},
                    {"item": items["EC001"], "qty": 1.0},
                    {"item": items["HW001"], "qty": 4.0}
                ]
                
                for comp in components1:
                    bom_item = BOMItem(
                        bom_id=bom1.id,
                        material_id=comp["item"].id,
                        quantity_required=comp["qty"]
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
                    description="Smart Controller Finished Product BOM"
                )
                db.session.add(bom2)
                db.session.flush()
                
                # Add components to Level 2 BOM (includes sub-assembly)
                components2 = [
                    {"item": items["SA001"], "qty": 1.0},  # This is the nested part!
                    {"item": items["RM001"], "qty": 0.3},  # Additional direct materials
                    {"item": items["HW001"], "qty": 8.0}   # Additional hardware
                ]
                
                for comp in components2:
                    bom_item = BOMItem(
                        bom_id=bom2.id,
                        material_id=comp["item"].id,
                        quantity_required=comp["qty"]
                    )
                    db.session.add(bom_item)
                
                print(f"Created Level 2 BOM for {fg001_item.name}")
            
            db.session.commit()
            
            print("\n=== SUCCESS: NESTED BOM STRUCTURE CREATED ===")
            print("Level 1 BOM: SA001 (Control Panel) contains:")
            print("  - RM001 (Aluminum Sheet): 0.5 SQM")
            print("  - EC001 (Microcontroller): 1.0 PCS")
            print("  - HW001 (Hex Bolt): 4.0 PCS")
            print("\nLevel 2 BOM: FG001 (Smart Controller) contains:")
            print("  - SA001 (Control Panel): 1.0 PCS ← NESTED BOM!")
            print("  - RM001 (Aluminum Sheet): 0.3 SQM")
            print("  - HW001 (Hex Bolt): 8.0 PCS")
            print("\nWhen you produce 1 unit of FG001, you need:")
            print("  - 1 unit of SA001 (which itself needs 0.5 SQM RM001 + 1 PCS EC001 + 4 PCS HW001)")
            print("  - Plus direct materials: 0.3 SQM RM001 + 8 PCS HW001")
            print("  - Total RM001 needed: 0.5 + 0.3 = 0.8 SQM")
            print("  - Total HW001 needed: 4 + 8 = 12 PCS")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    create_sample_boms()