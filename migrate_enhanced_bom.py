#!/usr/bin/env python3
"""
Migration script to add enhanced BOM fields to existing database
"""
import sqlite3
import os
from pathlib import Path

def migrate_enhanced_bom_fields():
    """Add enhanced BOM fields to the database"""
    
    # Find the database file
    db_path = None
    possible_paths = [
        'instance/factory.db',
        'factory.db',
        'database.db',
        'app.db'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        # Check in instance directory
        instance_dir = Path('instance')
        if instance_dir.exists():
            for db_file in instance_dir.glob('*.db'):
                db_path = str(db_file)
                break
    
    if not db_path:
        print("No SQLite database found. Creating new database structure.")
        return False
    
    print(f"Found database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the new columns already exist
        cursor.execute("PRAGMA table_info(boms)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add enhanced BOM fields if they don't exist
        new_columns = [
            ('allow_partial_production', 'BOOLEAN DEFAULT 1'),
            ('allow_substitute_items', 'BOOLEAN DEFAULT 0'),
            ('auto_create_job_work', 'BOOLEAN DEFAULT 0'),
            ('auto_batch_assignment', 'BOOLEAN DEFAULT 1')
        ]
        
        for column_name, column_def in new_columns:
            if column_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE boms ADD COLUMN {column_name} {column_def}")
                    print(f"Added column: {column_name}")
                except sqlite3.OperationalError as e:
                    print(f"Error adding column {column_name}: {e}")
        
        # Check if we need to add component type fields to bom_items
        cursor.execute("PRAGMA table_info(bom_items)")
        bom_items_columns = [column[1] for column in cursor.fetchall()]
        
        # Add enhanced BOMItem fields if they don't exist
        bom_item_new_columns = [
            ('component_type', "VARCHAR(20) DEFAULT 'raw_material'"),
            ('is_phantom', 'BOOLEAN DEFAULT 0'),
            ('is_packing_material', 'BOOLEAN DEFAULT 0')
        ]
        
        for column_name, column_def in bom_item_new_columns:
            if column_name not in bom_items_columns:
                try:
                    cursor.execute(f"ALTER TABLE bom_items ADD COLUMN {column_name} {column_def}")
                    print(f"Added BOM item column: {column_name}")
                except sqlite3.OperationalError as e:
                    print(f"Error adding BOM item column {column_name}: {e}")
        
        # Check if we need to add enhanced process fields to bom_processes
        try:
            cursor.execute("PRAGMA table_info(bom_processes)")
            process_columns = [column[1] for column in cursor.fetchall()]
            
            # Add enhanced BOMProcess fields if they don't exist
            process_new_columns = [
                ('lead_time_days', 'FLOAT DEFAULT 1.0'),
                ('machine_setup_time', 'FLOAT DEFAULT 0.0'),
                ('process_priority', 'INTEGER DEFAULT 1'),
                ('operator_skill_required', "VARCHAR(20) DEFAULT 'basic'")
            ]
            
            for column_name, column_def in process_new_columns:
                if column_name not in process_columns:
                    try:
                        cursor.execute(f"ALTER TABLE bom_processes ADD COLUMN {column_name} {column_def}")
                        print(f"Added BOM process column: {column_name}")
                    except sqlite3.OperationalError as e:
                        print(f"Error adding BOM process column {column_name}: {e}")
        
        except sqlite3.OperationalError:
            print("bom_processes table doesn't exist yet - will be created automatically")
        
        conn.commit()
        conn.close()
        print("Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False

if __name__ == "__main__":
    migrate_enhanced_bom_fields()