#!/usr/bin/env python3
"""
Enhanced BOM Migration Script v2 - Add missing fields from BOM design requirements
This script adds all missing fields identified from the user's BOM design document
"""

import sys
sys.path.insert(0, '.')

from main import app
from models import db, BOM, BOMItem
from sqlalchemy import text

def migrate_enhanced_bom_v2():
    """Add missing fields to support comprehensive BOM design requirements"""
    
    with app.app_context():
        print("Starting Enhanced BOM Migration v2...")
        
        # Helper function to check if column exists
        def column_exists(table_name, column_name):
            result = db.session.execute(text(f"""
                SELECT COUNT(*) 
                FROM pragma_table_info('{table_name}') 
                WHERE name = '{column_name}'
            """)).scalar()
            return result > 0
        
        # BOM table enhancements
        bom_migrations = []
        
        # Check and add missing BOM columns
        if not column_exists('boms', 'effective_date'):
            bom_migrations.append("ALTER TABLE boms ADD COLUMN effective_date DATE")
        
        if not column_exists('boms', 'bom_status'):
            bom_migrations.append("ALTER TABLE boms ADD COLUMN bom_status VARCHAR(20) DEFAULT 'draft'")
        
        if not column_exists('boms', 'lead_time_days'):
            bom_migrations.append("ALTER TABLE boms ADD COLUMN lead_time_days FLOAT DEFAULT 1.0")
        
        if not column_exists('boms', 'auto_cost_calculation'):
            bom_migrations.append("ALTER TABLE boms ADD COLUMN auto_cost_calculation BOOLEAN DEFAULT 1")
        
        if not column_exists('boms', 'batch_tracking_enabled'):
            bom_migrations.append("ALTER TABLE boms ADD COLUMN batch_tracking_enabled BOOLEAN DEFAULT 1")
        
        # BOMItem table enhancements
        bom_item_migrations = []
        
        # Check and add missing BOMItem columns
        if not column_exists('bom_items', 'component_source'):
            bom_item_migrations.append("ALTER TABLE bom_items ADD COLUMN component_source VARCHAR(20) DEFAULT 'purchase'")
        
        if not column_exists('bom_items', 'batch_tracking_required'):
            bom_item_migrations.append("ALTER TABLE bom_items ADD COLUMN batch_tracking_required BOOLEAN DEFAULT 1")
        
        if not column_exists('bom_items', 'assigned_department_id'):
            bom_item_migrations.append("ALTER TABLE bom_items ADD COLUMN assigned_department_id INTEGER")
        
        if not column_exists('bom_items', 'assigned_machine_id'):
            bom_item_migrations.append("ALTER TABLE bom_items ADD COLUMN assigned_machine_id INTEGER")
        
        if not column_exists('bom_items', 'assigned_vendor_id'):
            bom_item_migrations.append("ALTER TABLE bom_items ADD COLUMN assigned_vendor_id INTEGER")
        
        # Data update migrations
        data_updates = [
            # Set default effective dates for existing BOMs
            "UPDATE boms SET effective_date = date('now') WHERE effective_date IS NULL",
            
            # Update BOM status based on existing status
            "UPDATE boms SET bom_status = 'active' WHERE status = 'active' AND (bom_status IS NULL OR bom_status = '')",
            "UPDATE boms SET bom_status = 'draft' WHERE status = 'draft' AND (bom_status IS NULL OR bom_status = '')",
            "UPDATE boms SET bom_status = 'draft' WHERE bom_status IS NULL OR bom_status = ''",
            
            # Update component sources based on existing data
            "UPDATE bom_items SET component_source = 'in_house' WHERE component_type = 'sub_assembly' AND (component_source IS NULL OR component_source = '')",
            "UPDATE bom_items SET component_source = 'purchase' WHERE component_type = 'raw_material' AND (component_source IS NULL OR component_source = '')",
            "UPDATE bom_items SET component_source = 'purchase' WHERE component_type = 'packing' AND (component_source IS NULL OR component_source = '')",
            "UPDATE bom_items SET component_source = 'purchase' WHERE component_source IS NULL OR component_source = ''",
            
            # Update batch tracking based on packing materials
            "UPDATE bom_items SET batch_tracking_required = 0 WHERE is_packing_material = 1",
            "UPDATE bom_items SET batch_tracking_required = 1 WHERE batch_tracking_required IS NULL",
        ]
        
        try:
            # Execute BOM table migrations
            if bom_migrations:
                print("Migrating BOM table...")
                for migration in bom_migrations:
                    print(f"  Executing: {migration[:60]}...")
                    db.session.execute(text(migration))
            else:
                print("BOM table already has all required columns")
            
            # Execute BOMItem table migrations
            if bom_item_migrations:
                print("Migrating BOMItem table...")
                for migration in bom_item_migrations:
                    print(f"  Executing: {migration[:60]}...")
                    db.session.execute(text(migration))
            else:
                print("BOMItem table already has all required columns")
            
            # Execute data updates
            print("Updating existing data...")
            for update in data_updates:
                print(f"  Executing: {update[:60]}...")
                db.session.execute(text(update))
            
            # Commit all changes
            db.session.commit()
            print("✅ Enhanced BOM Migration v2 completed successfully!")
            
            # Display summary
            bom_count = db.session.execute(text("SELECT COUNT(*) FROM boms")).scalar()
            bom_item_count = db.session.execute(text("SELECT COUNT(*) FROM bom_items")).scalar()
            
            print(f"\n📊 Migration Summary:")
            print(f"   - BOMs updated: {bom_count}")
            print(f"   - BOM Items updated: {bom_item_count}")
            print(f"   - New fields added: effective_date, bom_status, lead_time_days, auto_cost_calculation, batch_tracking_enabled")
            print(f"   - BOM Item enhancements: component_source, batch_tracking_required, department/machine/vendor assignments")
            
            return True
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            return False

def verify_migration():
    """Verify that all new fields are properly added"""
    
    with app.app_context():
        print("\n🔍 Verifying migration...")
        
        # Check BOM table structure
        bom_columns = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'boms'
            ORDER BY column_name
        """)).fetchall()
        
        # Check BOMItem table structure
        bom_item_columns = db.session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'bom_items'
            ORDER BY column_name
        """)).fetchall()
        
        print("BOM table columns:")
        for col in bom_columns:
            print(f"  - {col[0]}")
        
        print("\nBOM Items table columns:")
        for col in bom_item_columns:
            print(f"  - {col[0]}")
        
        # Check for required new fields
        bom_col_names = [col[0] for col in bom_columns]
        bom_item_col_names = [col[0] for col in bom_item_columns]
        
        required_bom_fields = ['effective_date', 'bom_status', 'lead_time_days', 'auto_cost_calculation', 'batch_tracking_enabled']
        required_bom_item_fields = ['component_source', 'batch_tracking_required', 'assigned_department_id', 'assigned_machine_id', 'assigned_vendor_id']
        
        missing_bom = [field for field in required_bom_fields if field not in bom_col_names]
        missing_bom_item = [field for field in required_bom_item_fields if field not in bom_item_col_names]
        
        if missing_bom:
            print(f"❌ Missing BOM fields: {missing_bom}")
        else:
            print("✅ All required BOM fields present")
        
        if missing_bom_item:
            print(f"❌ Missing BOM Item fields: {missing_bom_item}")
        else:
            print("✅ All required BOM Item fields present")
        
        return len(missing_bom) == 0 and len(missing_bom_item) == 0

if __name__ == "__main__":
    print("Enhanced BOM Migration Script v2")
    print("=" * 50)
    
    # Run migration
    success = migrate_enhanced_bom_v2()
    
    if success:
        # Verify migration
        verify_migration()
        print("\n🎉 Migration completed successfully!")
        print("\nNew Features Available:")
        print("  ✓ Enhanced BOM status management (Draft/Active/Obsolete)")
        print("  ✓ Effective date for BOM validity")
        print("  ✓ Lead time tracking")
        print("  ✓ Component source classification (Purchase/In-house/Outsourced)")
        print("  ✓ Batch tracking configuration per component")
        print("  ✓ Department/Machine/Vendor assignments")
        print("  ✓ Auto cost calculation controls")
    else:
        print("\n❌ Migration failed. Please check the errors above.")
        sys.exit(1)