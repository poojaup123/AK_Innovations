#!/usr/bin/env python3
"""
Create Nested BOM Structure with Sample Inventory Data
Creates realistic manufacturing BOMs with sub-assemblies and components
"""

import os
import sys
from datetime import datetime, date
from decimal import Decimal

# Add the project root to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from models import Item, Supplier, BOM, BOMItem
from models.batch import InventoryBatch

def create_nested_bom_data():
    """Create comprehensive nested BOM structure with inventory"""
    
    app = create_app()
    with app.app_context():
        print("Creating nested BOM structure with sample inventory...")
        
        try:
            # Create suppliers first
            suppliers = []
            supplier_data = [
                {"name": "Metal Works Ltd", "contact_person": "John Smith", "phone": "+91-9876543210", "email": "john@metalworks.com", "address": "123 Industrial Area, Mumbai", "partner_type": "supplier"},
                {"name": "Electronics Hub", "contact_person": "Sarah Wilson", "phone": "+91-8765432109", "email": "sarah@electronhub.com", "address": "456 Tech Park, Bangalore", "partner_type": "supplier"},
                {"name": "Component Solutions", "contact_person": "Mike Johnson", "phone": "+91-7654321098", "email": "mike@compsol.com", "address": "789 Parts Street, Chennai", "partner_type": "supplier"},
                {"name": "Fastener Industries", "contact_person": "Lisa Chen", "phone": "+91-6543210987", "email": "lisa@fastener.com", "address": "321 Hardware Lane, Pune", "partner_type": "supplier"}
            ]
            
            for sup_data in supplier_data:
                supplier = Supplier.query.filter_by(name=sup_data["name"]).first()
                if not supplier:
                    supplier = Supplier(**sup_data)
                    db.session.add(supplier)
                    suppliers.append(supplier)
                    print(f"Created supplier: {supplier.name}")
            
            db.session.commit()
            
            # Create comprehensive item hierarchy
            items_data = [
                # Raw Materials (Level 0)
                {"code": "RM001", "name": "Aluminum Sheet 2mm", "unit_of_measure": "SQM", "current_stock": 0.0, "minimum_stock": 50.0},
                {"code": "RM002", "name": "Stainless Steel Rod 12mm", "unit_of_measure": "MTR", "current_stock": 0.0, "minimum_stock": 100.0},
                {"code": "RM003", "name": "Copper Wire 2.5mm", "unit_of_measure": "MTR", "current_stock": 0.0, "minimum_stock": 200.0},
                {"code": "RM004", "name": "Plastic Granules ABS", "unit_of_measure": "KG", "current_stock": 0.0, "minimum_stock": 25.0},
                {"code": "RM005", "name": "Rubber Gasket Material", "unit_of_measure": "MTR", "current_stock": 0.0, "minimum_stock": 50.0},
                
                # Electronic Components (Level 0)
                {"code": "EC001", "name": "Microcontroller ATmega328", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 20.0},
                {"code": "EC002", "name": "LCD Display 16x2", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 10.0},
                {"code": "EC003", "name": "Power Supply Module 12V", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 15.0},
                {"code": "EC004", "name": "Push Button Switch", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 50.0},
                {"code": "EC005", "name": "LED Indicator Red", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 100.0},
                {"code": "EC006", "name": "Resistor 220 Ohm", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 200.0},
                {"code": "EC007", "name": "Capacitor 100uF", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 100.0},
                
                # Fasteners & Hardware (Level 0)
                {"code": "HW001", "name": "M6 x 20mm Hex Bolt", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 500.0},
                {"code": "HW002", "name": "M6 Hex Nut", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 500.0},
                {"code": "HW003", "name": "M4 x 15mm Screw", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 1000.0},
                {"code": "HW004", "name": "Washer 6mm", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 1000.0},
                
                # Sub-Assemblies (Level 1)
                {"code": "SA001", "name": "Control Panel Assembly", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 5.0},
                {"code": "SA002", "name": "Motor Housing Assembly", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 10.0},
                {"code": "SA003", "name": "Power Distribution Unit", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 8.0},
                {"code": "SA004", "name": "Sensor Module Assembly", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 15.0},
                
                # Finished Products (Level 2)
                {"code": "FG001", "name": "Industrial Automation Controller", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 2.0},
                {"code": "FG002", "name": "Smart Motor Drive System", "unit_of_measure": "PCS", "current_stock": 0.0, "minimum_stock": 3.0}
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
            
            # Create inventory batches for raw materials and components
            batch_data = [
                # Raw Material Batches
                {"item_code": "RM001", "batch_code": "RM001-2025-001", "qty_raw": 120.0, "location": "STORE-A", "supplier_batch": "AL-2025-0156"},
                {"item_code": "RM002", "batch_code": "RM002-2025-001", "qty_raw": 300.0, "location": "STORE-A", "supplier_batch": "SS-2025-0087"},
                {"item_code": "RM003", "batch_code": "RM003-2025-001", "qty_raw": 800.0, "location": "STORE-B", "supplier_batch": "CU-2025-0234"},
                {"item_code": "RM004", "batch_code": "RM004-2025-001", "qty_raw": 50.0, "location": "STORE-C", "supplier_batch": "PL-2025-0098"},
                {"item_code": "RM005", "batch_code": "RM005-2025-001", "qty_raw": 150.0, "location": "STORE-A", "supplier_batch": "RB-2025-0045"},
                
                # Electronic Component Batches
                {"item_code": "EC001", "batch_code": "EC001-2025-001", "qty_raw": 50.0, "location": "ELECTRONICS", "supplier_batch": "MCU-2025-0123"},
                {"item_code": "EC002", "batch_code": "EC002-2025-001", "qty_raw": 30.0, "location": "ELECTRONICS", "supplier_batch": "LCD-2025-0067"},
                {"item_code": "EC003", "batch_code": "EC003-2025-001", "qty_raw": 40.0, "location": "ELECTRONICS", "supplier_batch": "PSU-2025-0089"},
                {"item_code": "EC004", "batch_code": "EC004-2025-001", "qty_raw": 150.0, "location": "ELECTRONICS", "supplier_batch": "BTN-2025-0234"},
                {"item_code": "EC005", "batch_code": "EC005-2025-001", "qty_raw": 300.0, "location": "ELECTRONICS", "supplier_batch": "LED-2025-0156"},
                {"item_code": "EC006", "batch_code": "EC006-2025-001", "qty_raw": 800.0, "location": "ELECTRONICS", "supplier_batch": "RES-2025-0345"},
                {"item_code": "EC007", "batch_code": "EC007-2025-001", "qty_raw": 400.0, "location": "ELECTRONICS", "supplier_batch": "CAP-2025-0178"},
                
                # Hardware Batches
                {"item_code": "HW001", "batch_code": "HW001-2025-001", "qty_raw": 1500.0, "location": "HARDWARE", "supplier_batch": "BOLT-2025-0456"},
                {"item_code": "HW002", "batch_code": "HW002-2025-001", "qty_raw": 1500.0, "location": "HARDWARE", "supplier_batch": "NUT-2025-0789"},
                {"item_code": "HW003", "batch_code": "HW003-2025-001", "qty_raw": 3000.0, "location": "HARDWARE", "supplier_batch": "SCR-2025-0234"},
                {"item_code": "HW004", "batch_code": "HW004-2025-001", "qty_raw": 3000.0, "location": "HARDWARE", "supplier_batch": "WSH-2025-0567"}
            ]
            
            for batch_info in batch_data:
                item = items.get(batch_info["item_code"])
                if item:
                    batch = InventoryBatch.query.filter_by(batch_code=batch_info["batch_code"]).first()
                    if not batch:
                        batch = InventoryBatch(
                            item_id=item.id,
                            batch_code=batch_info["batch_code"],
                            qty_raw=batch_info["qty_raw"],
                            uom=item.unit_of_measure,
                            location=batch_info["location"],
                            supplier_batch_no=batch_info["supplier_batch"],
                            purchase_rate=50.0,  # Default purchase rate
                            mfg_date=date(2025, 1, 15),
                            source_type='purchase'
                        )
                        db.session.add(batch)
                        print(f"Created batch: {batch.batch_code} - {batch_info['qty_raw']} {item.unit_of_measure}")
            
            db.session.commit()
            
            # Create Nested BOM Structure
            print("\nCreating nested BOM structure...")
            
            # Level 1 BOMs - Sub-Assemblies
            bom_structures = [
                # Control Panel Assembly BOM
                {
                    "item_code": "SA001",
                    "name": "Control Panel Assembly",
                    "components": [
                        {"code": "EC002", "quantity": 1.0, "notes": "Main display unit"},
                        {"code": "EC004", "quantity": 4.0, "notes": "Start, Stop, Reset, Emergency buttons"},
                        {"code": "EC005", "quantity": 6.0, "notes": "Status indicators"},
                        {"code": "RM001", "quantity": 0.25, "notes": "Panel faceplate"},
                        {"code": "HW003", "quantity": 8.0, "notes": "Component mounting screws"},
                        {"code": "HW004", "quantity": 8.0, "notes": "Mounting washers"}
                    ]
                },
                
                # Motor Housing Assembly BOM
                {
                    "item_code": "SA002", 
                    "name": "Motor Housing Assembly",
                    "components": [
                        {"code": "RM001", "quantity": 0.8, "notes": "Housing panels"},
                        {"code": "RM002", "quantity": 2.0, "notes": "Support brackets"},
                        {"code": "RM005", "quantity": 1.5, "notes": "Sealing gaskets"},
                        {"code": "HW001", "quantity": 12.0, "notes": "Assembly bolts"},
                        {"code": "HW002", "quantity": 12.0, "notes": "Assembly nuts"},
                        {"code": "HW004", "quantity": 24.0, "notes": "Locking washers"}
                    ]
                },
                
                # Power Distribution Unit BOM
                {
                    "item_code": "SA003",
                    "name": "Power Distribution Unit", 
                    "components": [
                        {"code": "EC003", "quantity": 1.0, "notes": "Main power supply"},
                        {"code": "EC007", "quantity": 8.0, "notes": "Filter capacitors"},
                        {"code": "EC006", "quantity": 12.0, "notes": "Current limiting resistors"},
                        {"code": "RM003", "quantity": 5.0, "notes": "Internal wiring"},
                        {"code": "RM001", "quantity": 0.15, "notes": "Enclosure panel"},
                        {"code": "HW003", "quantity": 6.0, "notes": "Component mounting"}
                    ]
                },
                
                # Sensor Module Assembly BOM
                {
                    "item_code": "SA004",
                    "name": "Sensor Module Assembly",
                    "components": [
                        {"code": "EC001", "quantity": 1.0, "notes": "Processing unit"},
                        {"code": "EC006", "quantity": 6.0, "notes": "Pull-up resistors"},
                        {"code": "EC007", "quantity": 4.0, "notes": "Decoupling capacitors"},
                        {"code": "RM003", "quantity": 2.0, "notes": "Sensor connections"},
                        {"code": "RM004", "quantity": 0.05, "notes": "Protective housing"},
                        {"code": "HW003", "quantity": 4.0, "notes": "PCB mounting screws"}
                    ]
                }
            ]
            
            # Create Level 1 BOMs (Sub-assemblies)
            for bom_data in bom_structures:
                item = items.get(bom_data["item_code"])
                if item:
                    bom = BOM.query.filter_by(item_id=item.id).first()
                    if not bom:
                        bom = BOM(
                            item_id=item.id,
                            version="1.0",
                            status="active",
                            description=f"BOM for {bom_data['name']}",
                            labor_cost_per_unit=150.0,
                            overhead_percentage=15.0,
                            scrap_percentage=2.0
                        )
                        db.session.add(bom)
                        db.session.flush()  # Get BOM ID
                        
                        # Add BOM components
                        for comp in bom_data["components"]:
                            comp_item = items.get(comp["code"])
                            if comp_item:
                                bom_item = BOMItem(
                                    bom_id=bom.id,
                                    item_id=comp_item.id,
                                    quantity_required=comp["quantity"],
                                    uom=comp_item.uom,
                                    notes=comp["notes"]
                                )
                                db.session.add(bom_item)
                        
                        print(f"Created BOM for {bom_data['name']} with {len(bom_data['components'])} components")
            
            db.session.commit()
            
            # Level 2 BOMs - Finished Products (using sub-assemblies)
            finished_bom_structures = [
                # Industrial Automation Controller
                {
                    "item_code": "FG001",
                    "name": "Industrial Automation Controller",
                    "components": [
                        {"code": "SA001", "quantity": 1.0, "notes": "Main control interface"},
                        {"code": "SA003", "quantity": 1.0, "notes": "Power management system"},
                        {"code": "SA004", "quantity": 2.0, "notes": "Input/Output sensor modules"},
                        {"code": "RM001", "quantity": 1.2, "notes": "Main chassis panels"},
                        {"code": "RM003", "quantity": 8.0, "notes": "Inter-module wiring"},
                        {"code": "HW001", "quantity": 16.0, "notes": "Chassis assembly bolts"},
                        {"code": "HW002", "quantity": 16.0, "notes": "Chassis assembly nuts"}
                    ]
                },
                
                # Smart Motor Drive System  
                {
                    "item_code": "FG002",
                    "name": "Smart Motor Drive System",
                    "components": [
                        {"code": "SA001", "quantity": 1.0, "notes": "User interface panel"},
                        {"code": "SA002", "quantity": 1.0, "notes": "Motor housing assembly"},
                        {"code": "SA003", "quantity": 1.0, "notes": "Drive power electronics"},
                        {"code": "SA004", "quantity": 3.0, "notes": "Feedback sensor modules"},
                        {"code": "RM002", "quantity": 4.0, "notes": "Structural support rods"},
                        {"code": "RM005", "quantity": 3.0, "notes": "Environmental sealing"},
                        {"code": "HW001", "quantity": 20.0, "notes": "Main assembly bolts"},
                        {"code": "HW002", "quantity": 20.0, "notes": "Main assembly nuts"},
                        {"code": "HW004", "quantity": 40.0, "notes": "Vibration dampening washers"}
                    ]
                }
            ]
            
            # Create Level 2 BOMs (Finished products)
            for bom_data in finished_bom_structures:
                item = items.get(bom_data["item_code"])
                if item:
                    bom = BOM.query.filter_by(item_id=item.id).first()
                    if not bom:
                        bom = BOM(
                            item_id=item.id,
                            version="1.0",
                            status="active",
                            description=f"Complete BOM for {bom_data['name']}",
                            labor_cost_per_unit=800.0,  # Higher labor cost for finished products
                            overhead_percentage=25.0,   # Higher overhead for complex assembly
                            scrap_percentage=1.5        # Lower scrap rate for careful final assembly
                        )
                        db.session.add(bom)
                        db.session.flush()
                        
                        # Add BOM components
                        for comp in bom_data["components"]:
                            comp_item = items.get(comp["code"])
                            if comp_item:
                                bom_item = BOMItem(
                                    bom_id=bom.id,
                                    item_id=comp_item.id,
                                    quantity_required=comp["quantity"],
                                    uom=comp_item.uom,
                                    notes=comp["notes"]
                                )
                                db.session.add(bom_item)
                        
                        print(f"Created finished product BOM for {bom_data['name']} with {len(bom_data['components'])} components")
            
            db.session.commit()
            
            # Summary
            print(f"\n=== NESTED BOM CREATION COMPLETED ===")
            print(f"✓ Created {len(supplier_data)} suppliers")
            print(f"✓ Created {len(items_data)} items across hierarchy:")
            print(f"  - Raw Materials & Components: {len([i for i in items_data if i['category'] in ['Raw Material', 'Electronics', 'Hardware']])}")
            print(f"  - Sub-Assemblies: {len([i for i in items_data if i['category'] == 'Sub-Assembly'])}")
            print(f"  - Finished Products: {len([i for i in items_data if i['category'] == 'Finished Goods'])}")
            print(f"✓ Created {len(batch_data)} inventory batches with realistic stock levels")
            print(f"✓ Created {len(bom_structures) + len(finished_bom_structures)} BOMs:")
            print(f"  - Level 1 BOMs (Sub-assemblies): {len(bom_structures)}")
            print(f"  - Level 2 BOMs (Finished products): {len(finished_bom_structures)}")
            
            print(f"\n=== BOM HIERARCHY ===")
            print(f"Level 0: Raw Materials, Electronics, Hardware")
            print(f"Level 1: Sub-Assemblies (using Level 0 components)")
            print(f"Level 2: Finished Products (using Level 0 + Level 1 components)")
            print(f"\nThis creates true nested BOMs where finished products contain sub-assemblies!")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating nested BOM data: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    create_nested_bom_data()