#!/usr/bin/env python3
"""
Create sample data for nested BOM demonstration
"""

import os
import sys
from datetime import datetime, date

# Add the project root to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from models import Item, Supplier, BOM, BOMItem
from models.uom import UnitOfMeasure
from models.batch import InventoryBatch

def create_sample_data():
    """Create sample data including UOMs, Items, and nested BOMs"""
    
    app = create_app()
    with app.app_context():
        print("Creating comprehensive sample data for nested BOM demonstration...")
        
        try:
            # Create basic UOMs first
            uoms_data = [
                {"name": "Pieces", "symbol": "PCS", "category": "Count", "description": "Individual items"},
                {"name": "Kilograms", "symbol": "KG", "category": "Weight", "description": "Weight in kilograms"},
                {"name": "Square Meters", "symbol": "SQM", "category": "Area", "description": "Area measurement"},
                {"name": "Meters", "symbol": "MTR", "category": "Length", "description": "Length measurement"},
                {"name": "Liters", "symbol": "LTR", "category": "Volume", "description": "Volume measurement"}
            ]
            
            for uom_data in uoms_data:
                uom = UnitOfMeasure.query.filter_by(symbol=uom_data["symbol"]).first()
                if not uom:
                    uom = UnitOfMeasure(**uom_data)
                    db.session.add(uom)
                    print(f"Created UOM: {uom.symbol} - {uom.name}")
            
            db.session.commit()
            
            # Create suppliers
            suppliers_data = [
                {"name": "Metal Works Ltd", "contact_person": "John Smith", "phone": "+91-9876543210", "email": "john@metalworks.com", "address": "123 Industrial Area, Mumbai", "partner_type": "supplier"},
                {"name": "Electronics Hub", "contact_person": "Sarah Wilson", "phone": "+91-8765432109", "email": "sarah@electronhub.com", "address": "456 Tech Park, Bangalore", "partner_type": "supplier"}
            ]
            
            for sup_data in suppliers_data:
                supplier = Supplier.query.filter_by(name=sup_data["name"]).first()
                if not supplier:
                    supplier = Supplier(**sup_data)
                    db.session.add(supplier)
                    print(f"Created supplier: {supplier.name}")
            
            db.session.commit()
            
            # Create items hierarchy for nested BOM
            items_data = [
                # Raw Materials
                {"code": "RM001", "name": "Aluminum Sheet 2mm", "unit_of_measure": "SQM", "item_type": "raw_material", "current_stock": 0.0, "minimum_stock": 10.0, "purchase_price": 150.0, "unit_price": 150.0},
                {"code": "RM002", "name": "Steel Rod 12mm", "unit_of_measure": "MTR", "item_type": "raw_material", "current_stock": 0.0, "minimum_stock": 20.0, "purchase_price": 80.0, "unit_price": 80.0},
                {"code": "RM003", "name": "Copper Wire", "unit_of_measure": "MTR", "item_type": "raw_material", "current_stock": 0.0, "minimum_stock": 50.0, "purchase_price": 25.0, "unit_price": 25.0},
                
                # Electronic Components
                {"code": "EC001", "name": "Microcontroller", "unit_of_measure": "PCS", "item_type": "raw_material", "current_stock": 0.0, "minimum_stock": 5.0, "purchase_price": 500.0, "unit_price": 500.0},
                {"code": "EC002", "name": "LCD Display", "unit_of_measure": "PCS", "item_type": "raw_material", "current_stock": 0.0, "minimum_stock": 3.0, "purchase_price": 800.0, "unit_price": 800.0},
                {"code": "EC003", "name": "Push Button", "unit_of_measure": "PCS", "item_type": "raw_material", "current_stock": 0.0, "minimum_stock": 20.0, "purchase_price": 15.0, "unit_price": 15.0},
                
                # Hardware
                {"code": "HW001", "name": "M6 Hex Bolt", "unit_of_measure": "PCS", "item_type": "raw_material", "current_stock": 0.0, "minimum_stock": 100.0, "purchase_price": 2.0, "unit_price": 2.0},
                {"code": "HW002", "name": "M6 Hex Nut", "unit_of_measure": "PCS", "item_type": "raw_material", "current_stock": 0.0, "minimum_stock": 100.0, "purchase_price": 1.5, "unit_price": 1.5},
                
                # Sub-Assemblies (Level 1)
                {"code": "SA001", "name": "Control Panel Assembly", "unit_of_measure": "PCS", "item_type": "semi_finished_good", "current_stock": 0.0, "minimum_stock": 2.0, "purchase_price": 0.0, "unit_price": 1500.0},
                {"code": "SA002", "name": "Housing Assembly", "unit_of_measure": "PCS", "item_type": "semi_finished_good", "current_stock": 0.0, "minimum_stock": 3.0, "purchase_price": 0.0, "unit_price": 800.0},
                
                # Finished Products (Level 2)
                {"code": "FG001", "name": "Industrial Controller", "unit_of_measure": "PCS", "item_type": "finished_good", "current_stock": 0.0, "minimum_stock": 1.0, "purchase_price": 0.0, "unit_price": 5000.0},
                {"code": "FG002", "name": "Smart Motor Drive", "unit_of_measure": "PCS", "item_type": "finished_good", "current_stock": 0.0, "minimum_stock": 1.0, "purchase_price": 0.0, "unit_price": 8000.0}
            ]
            
            items = {}
            for item_data in items_data:
                item = Item.query.filter_by(code=item_data["code"]).first()
                if not item:
                    item = Item(**item_data)
                    db.session.add(item)
                    items[item_data["code"]] = item
                    print(f"Created item: {item.code} - {item.name}")
                else:
                    items[item_data["code"]] = item
            
            db.session.commit()
            
            # Create inventory batches for raw materials
            raw_materials = ["RM001", "RM002", "RM003", "EC001", "EC002", "EC003", "HW001", "HW002"]
            for item_code in raw_materials:
                item = items[item_code]
                batch_code = f"{item_code}-2025-001"
                
                batch = InventoryBatch.query.filter_by(batch_code=batch_code).first()
                if not batch:
                    qty_raw = 100.0 if item_code.startswith('HW') else (50.0 if item_code.startswith('EC') else 20.0)
                    
                    batch = InventoryBatch(
                        item_id=item.id,
                        batch_code=batch_code,
                        qty_raw=qty_raw,
                        uom=item.unit_of_measure,
                        location="STORE-A",
                        purchase_rate=item.purchase_price,
                        mfg_date=date(2025, 1, 15),
                        source_type='purchase'
                    )
                    db.session.add(batch)
                    print(f"Created inventory batch: {batch_code} - {qty_raw} {item.unit_of_measure}")
            
            db.session.commit()
            
            print("\n=== SAMPLE DATA CREATION COMPLETED ===")
            print(f"✓ Created UOMs, Suppliers, Items, and Inventory Batches")
            print(f"✓ Ready for BOM creation through web interface")
            print(f"\nNow you can:")
            print(f"1. Go to Production → BOM")
            print(f"2. Create Level 1 BOM for SA001 (Control Panel Assembly)")
            print(f"3. Create Level 2 BOM for FG001 (Industrial Controller) using SA001")
            print(f"4. This will demonstrate nested BOM functionality!")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating sample data: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    create_sample_data()