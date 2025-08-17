"""
Performance Optimization - Database Indexes
Critical indexes for Tally-like performance
"""

from sqlalchemy import text
from app import db

def create_performance_indexes():
    """Create critical indexes for optimal performance"""
    
    indexes = [
        # Inventory Batch indexes
        "CREATE INDEX IF NOT EXISTS idx_inventory_batches_item_id ON inventory_batches(item_id)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_batches_created_at ON inventory_batches(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_batches_expiry_date ON inventory_batches(expiry_date)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_batches_inspection_status ON inventory_batches(inspection_status)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_batches_qty_raw ON inventory_batches(qty_raw)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_batches_qty_finished ON inventory_batches(qty_finished)",
        
        # Batch Movement indexes
        "CREATE INDEX IF NOT EXISTS idx_batch_movements_timestamp ON batch_movements(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_batch_movements_batch_id ON batch_movements(batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_batch_movements_item_id ON batch_movements(item_id)",
        "CREATE INDEX IF NOT EXISTS idx_batch_movements_movement_type ON batch_movements(movement_type)",
        
        # Item indexes
        "CREATE INDEX IF NOT EXISTS idx_items_current_stock ON items(current_stock)",
        "CREATE INDEX IF NOT EXISTS idx_items_minimum_stock ON items(minimum_stock)",
        "CREATE INDEX IF NOT EXISTS idx_items_code ON items(code)",
        
        # GRN indexes
        "CREATE INDEX IF NOT EXISTS idx_grn_line_items_item_id ON grn_line_items(item_id)",
        "CREATE INDEX IF NOT EXISTS idx_grn_line_items_grn_id ON grn_line_items(grn_id)",
        "CREATE INDEX IF NOT EXISTS idx_grn_received_date ON grn(received_date)",
        "CREATE INDEX IF NOT EXISTS idx_grn_status ON grn(status)",
        
        # Purchase Order indexes
        "CREATE INDEX IF NOT EXISTS idx_purchase_orders_status ON purchase_orders(status)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_orders_created_at ON purchase_orders(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_po_items_item_id ON purchase_order_items(item_id)",
        "CREATE INDEX IF NOT EXISTS idx_po_items_po_id ON purchase_order_items(purchase_order_id)",
        
        # Sales Order indexes
        "CREATE INDEX IF NOT EXISTS idx_sales_orders_status ON sales_orders(status)",
        "CREATE INDEX IF NOT EXISTS idx_sales_orders_created_at ON sales_orders(created_at)",
        
        # Job Work indexes
        "CREATE INDEX IF NOT EXISTS idx_job_works_status ON job_works(status)",
        "CREATE INDEX IF NOT EXISTS idx_job_works_created_at ON job_works(created_at)",
        
        # Production indexes
        "CREATE INDEX IF NOT EXISTS idx_productions_status ON productions(status)",
        "CREATE INDEX IF NOT EXISTS idx_productions_created_at ON productions(created_at)",
        
        # Employee indexes
        "CREATE INDEX IF NOT EXISTS idx_employees_is_active ON employees(is_active)",
        
        # BOM indexes
        "CREATE INDEX IF NOT EXISTS idx_bom_product_id ON bom(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_bom_is_active ON bom(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_bom_items_bom_id ON bom_items(bom_id)",
        "CREATE INDEX IF NOT EXISTS idx_bom_items_item_id ON bom_items(item_id)",
        
        # Job Card indexes
        "CREATE INDEX IF NOT EXISTS idx_job_cards_status ON job_cards(status)",
        "CREATE INDEX IF NOT EXISTS idx_job_cards_production_id ON job_cards(production_order_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_cards_assigned_worker ON job_cards(assigned_worker_id)",
    ]
    
    try:
        for index_sql in indexes:
            db.session.execute(text(index_sql))
        db.session.commit()
        print(f"✓ Created {len(indexes)} performance indexes successfully")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating indexes: {e}")
        return False

def analyze_table_performance():
    """Analyze table sizes and query performance"""
    
    analysis_queries = [
        "SELECT 'inventory_batches' as table_name, COUNT(*) as row_count FROM inventory_batches",
        "SELECT 'batch_movements' as table_name, COUNT(*) as row_count FROM batch_movements", 
        "SELECT 'items' as table_name, COUNT(*) as row_count FROM items",
        "SELECT 'grn' as table_name, COUNT(*) as row_count FROM grn",
        "SELECT 'grn_line_items' as table_name, COUNT(*) as row_count FROM grn_line_items",
        "SELECT 'purchase_orders' as table_name, COUNT(*) as row_count FROM purchase_orders",
        "SELECT 'job_works' as table_name, COUNT(*) as row_count FROM job_works",
        "SELECT 'productions' as table_name, COUNT(*) as row_count FROM productions",
    ]
    
    results = {}
    try:
        for query in analysis_queries:
            result = db.session.execute(text(query)).fetchone()
            results[result[0]] = result[1]
        
        print("📊 Table Performance Analysis:")
        for table, count in results.items():
            print(f"  {table}: {count:,} rows")
            
        return results
        
    except Exception as e:
        print(f"Error analyzing performance: {e}")
        return {}

def check_slow_queries():
    """Check for potentially slow operations"""
    
    slow_query_checks = [
        # Check for tables without primary key usage
        """
        SELECT COUNT(*) as unindexed_batch_queries 
        FROM inventory_batches 
        WHERE item_id IN (SELECT id FROM items LIMIT 100)
        """,
        
        # Check batch movement frequency
        """
        SELECT COUNT(*) as daily_movements 
        FROM batch_movements 
        WHERE timestamp >= CURRENT_DATE
        """,
        
        # Check large aggregation queries
        """
        SELECT COUNT(DISTINCT item_id) as items_with_batches
        FROM inventory_batches
        WHERE qty_raw > 0 OR qty_finished > 0
        """
    ]
    
    try:
        results = {}
        for i, query in enumerate(slow_query_checks):
            result = db.session.execute(text(query)).fetchone()
            results[f"check_{i+1}"] = result[0]
        
        print("🔍 Slow Query Analysis:")
        print(f"  Unindexed batch queries: {results.get('check_1', 0)}")
        print(f"  Daily movements: {results.get('check_2', 0)}")
        print(f"  Items with active batches: {results.get('check_3', 0)}")
        
        return results
        
    except Exception as e:
        print(f"Error checking slow queries: {e}")
        return {}