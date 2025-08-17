"""
Optimized Batch Tracking Queries
High-performance queries for Tally-like speed
"""

from datetime import datetime, date, timedelta
from sqlalchemy import text, func, desc
from flask import current_app
from typing import Dict, List, Any

from app import db
from models.batch import InventoryBatch, BatchMovement
from models import Item
from utils.query_cache import cached_query, QueryCache

class OptimizedBatchQueries:
    """
    High-performance batch tracking queries optimized for speed
    """
    
    @staticmethod
    def get_dashboard_stats_fast() -> Dict[str, int]:
        """
        Ultra-fast dashboard statistics using optimized SQL
        Single query for all batch statistics
        """
        try:
            # Single optimized query for all statistics
            stats_sql = text("""
                WITH batch_stats AS (
                    SELECT 
                        COUNT(*) as total_batches,
                        COUNT(CASE WHEN (qty_raw > 0 OR qty_wip > 0 OR qty_finished > 0) THEN 1 END) as active_batches,
                        COUNT(CASE WHEN expiry_date < CURRENT_DATE THEN 1 END) as expired_batches,
                        COUNT(CASE WHEN qty_inspection > 0 THEN 1 END) as pending_inspection
                    FROM inventory_batches
                ),
                movement_stats AS (
                    SELECT COUNT(*) as movements_today
                    FROM batch_movements 
                    WHERE DATE(timestamp) = CURRENT_DATE
                )
                SELECT 
                    b.total_batches,
                    b.active_batches, 
                    b.expired_batches,
                    b.pending_inspection,
                    m.movements_today
                FROM batch_stats b
                CROSS JOIN movement_stats m
            """)
            
            result = db.session.execute(stats_sql).fetchone()
            
            return {
                'total_batches': result[0] or 0,
                'active_batches': result[1] or 0,
                'expired_batches': result[2] or 0,
                'pending_inspection': result[3] or 0,
                'movements_today': result[4] or 0
            }
            
        except Exception as e:
            current_app.logger.error(f"Error in batch dashboard stats: {e}")
            return {
                'total_batches': 0,
                'active_batches': 0,
                'expired_batches': 0,
                'pending_inspection': 0,
                'movements_today': 0
            }
    
    @staticmethod
    def get_recent_movements_fast(date_from: date, date_to: date, limit: int = 10) -> List[Dict]:
        """
        Fast recent movements with optimized joins
        """
        try:
            movements_sql = text("""
                SELECT 
                    bm.id,
                    bm.timestamp,
                    bm.quantity,
                    bm.from_state,
                    bm.to_state,
                    bm.movement_type,
                    bm.notes,
                    ib.batch_code,
                    i.name as item_name,
                    u.username
                FROM batch_movements bm
                LEFT JOIN inventory_batches ib ON bm.batch_id = ib.id
                LEFT JOIN items i ON bm.item_id = i.id  
                LEFT JOIN users u ON bm.user_id = u.id
                WHERE bm.timestamp >= :date_from 
                AND bm.timestamp <= :date_to
                ORDER BY bm.timestamp DESC
                LIMIT :limit
            """)
            
            results = db.session.execute(movements_sql, {
                'date_from': datetime.combine(date_from, datetime.min.time()),
                'date_to': datetime.combine(date_to, datetime.max.time()),
                'limit': limit
            }).fetchall()
            
            return [
                {
                    'id': row[0],
                    'timestamp': row[1],
                    'quantity': row[2],
                    'from_state': row[3],
                    'to_state': row[4],
                    'movement_type': row[5],
                    'notes': row[6],
                    'batch_code': row[7],
                    'item_name': row[8],
                    'username': row[9]
                }
                for row in results
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting recent movements: {e}")
            return []
    
    @staticmethod
    def get_batch_status_summary_fast() -> List[Dict]:
        """
        Fast batch status summary with single query
        """
        try:
            status_sql = text("""
                SELECT 
                    inspection_status,
                    COUNT(*) as count,
                    COALESCE(SUM(qty_raw + qty_wip + qty_finished), 0) as total_qty
                FROM inventory_batches
                GROUP BY inspection_status
                ORDER BY count DESC
            """)
            
            results = db.session.execute(status_sql).fetchall()
            
            return [
                {
                    'inspection_status': row[0] or 'unknown',
                    'count': row[1],
                    'total_qty': row[2]
                }
                for row in results
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting batch status summary: {e}")
            return []
    
    @staticmethod
    def get_low_stock_items_fast(limit: int = 5) -> List[Dict]:
        """
        Fast low stock items using optimized query
        """
        try:
            low_stock_sql = text("""
                SELECT 
                    i.id,
                    i.name,
                    i.code,
                    COALESCE(SUM(ib.qty_raw + ib.qty_finished), 0) as available_qty,
                    i.minimum_stock
                FROM items i
                LEFT JOIN inventory_batches ib ON i.id = ib.item_id
                WHERE i.minimum_stock > 0
                GROUP BY i.id, i.name, i.code, i.minimum_stock
                HAVING COALESCE(SUM(ib.qty_raw + ib.qty_finished), 0) <= i.minimum_stock
                ORDER BY (COALESCE(SUM(ib.qty_raw + ib.qty_finished), 0) / NULLIF(i.minimum_stock, 0)) ASC
                LIMIT :limit
            """)
            
            results = db.session.execute(low_stock_sql, {'limit': limit}).fetchall()
            
            return [
                {
                    'id': row[0],
                    'name': row[1],
                    'code': row[2],
                    'available_qty': row[3],
                    'minimum_stock': row[4]
                }
                for row in results
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting low stock items: {e}")
            return []
    
    @staticmethod
    def get_expiring_batches_fast(days_ahead: int = 30, limit: int = 10) -> List[Dict]:
        """
        Fast expiring batches query
        """
        try:
            expiring_sql = text("""
                SELECT 
                    ib.id,
                    ib.batch_code,
                    ib.expiry_date,
                    (ib.qty_raw + ib.qty_wip + ib.qty_finished) as total_quantity,
                    i.name as item_name,
                    CASE 
                        WHEN ib.expiry_date < CURRENT_DATE THEN 'expired'
                        WHEN ib.expiry_date <= CURRENT_DATE + INTERVAL ':days days' THEN 'expiring_soon'
                        ELSE 'ok'
                    END as status
                FROM inventory_batches ib
                JOIN items i ON ib.item_id = i.id
                WHERE ib.expiry_date IS NOT NULL
                AND ib.expiry_date <= CURRENT_DATE + INTERVAL ':days days'
                AND (ib.qty_raw > 0 OR ib.qty_wip > 0 OR ib.qty_finished > 0)
                ORDER BY ib.expiry_date ASC
                LIMIT :limit
            """)
            
            results = db.session.execute(expiring_sql, {
                'days': days_ahead,
                'limit': limit
            }).fetchall()
            
            return [
                {
                    'id': row[0],
                    'batch_code': row[1],
                    'expiry_date': row[2],
                    'total_quantity': row[3],
                    'item_name': row[4],
                    'status': row[5]
                }
                for row in results
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting expiring batches: {e}")
            return []
    
    @staticmethod
    def get_movement_analysis_fast(date_from: date, limit: int = 10) -> List[Dict]:
        """
        Fast movement type analysis
        """
        try:
            analysis_sql = text("""
                SELECT 
                    movement_type,
                    COUNT(*) as count,
                    COALESCE(SUM(quantity), 0) as total_qty
                FROM batch_movements
                WHERE timestamp >= :date_from
                GROUP BY movement_type
                ORDER BY count DESC
                LIMIT :limit
            """)
            
            results = db.session.execute(analysis_sql, {
                'date_from': datetime.combine(date_from, datetime.min.time()),
                'limit': limit
            }).fetchall()
            
            return [
                {
                    'movement_type': row[0],
                    'count': row[1],
                    'total_qty': row[2]
                }
                for row in results
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting movement analysis: {e}")
            return []
    
    @staticmethod
    def get_item_batch_summary_fast(item_id: int) -> Dict:
        """
        Fast item batch summary for specific item
        """
        try:
            summary_sql = text("""
                SELECT 
                    COUNT(*) as total_batches,
                    COALESCE(SUM(qty_raw), 0) as total_raw,
                    COALESCE(SUM(qty_wip), 0) as total_wip,
                    COALESCE(SUM(qty_finished), 0) as total_finished,
                    COALESCE(SUM(qty_scrap), 0) as total_scrap,
                    COALESCE(SUM(qty_inspection), 0) as total_inspection,
                    COUNT(CASE WHEN expiry_date < CURRENT_DATE THEN 1 END) as expired_batches
                FROM inventory_batches
                WHERE item_id = :item_id
            """)
            
            result = db.session.execute(summary_sql, {'item_id': item_id}).fetchone()
            
            if result:
                return {
                    'total_batches': result[0],
                    'total_raw': result[1],
                    'total_wip': result[2],
                    'total_finished': result[3],
                    'total_scrap': result[4],
                    'total_inspection': result[5],
                    'expired_batches': result[6],
                    'available_for_production': result[1] + result[3],  # raw + finished
                    'available_for_dispatch': result[3]  # finished only
                }
            
            return {
                'total_batches': 0,
                'total_raw': 0,
                'total_wip': 0,
                'total_finished': 0,
                'total_scrap': 0,
                'total_inspection': 0,
                'expired_batches': 0,
                'available_for_production': 0,
                'available_for_dispatch': 0
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting item batch summary: {e}")
            return {}

    @staticmethod
    def search_batches_fast(query: str, item_id: int = None, limit: int = 20) -> List[Dict]:
        """
        Fast batch search with minimal data
        """
        try:
            base_sql = """
                SELECT 
                    ib.id,
                    ib.batch_code,
                    ib.qty_raw,
                    ib.qty_wip,
                    ib.qty_finished,
                    ib.location,
                    ib.expiry_date,
                    i.name as item_name
                FROM inventory_batches ib
                JOIN items i ON ib.item_id = i.id
                WHERE 1=1
            """
            
            params = {}
            
            if query:
                base_sql += " AND (ib.batch_code ILIKE :query OR ib.supplier_batch_no ILIKE :query)"
                params['query'] = f'%{query}%'
            
            if item_id:
                base_sql += " AND ib.item_id = :item_id"
                params['item_id'] = item_id
            
            base_sql += " ORDER BY ib.created_at DESC LIMIT :limit"
            params['limit'] = limit
            
            results = db.session.execute(text(base_sql), params).fetchall()
            
            return [
                {
                    'id': row[0],
                    'batch_code': row[1],
                    'qty_raw': row[2] or 0,
                    'qty_wip': row[3] or 0,
                    'qty_finished': row[4] or 0,
                    'location': row[5],
                    'expiry_date': row[6].isoformat() if row[6] else None,
                    'item_name': row[7],
                    'is_expired': row[6] < date.today() if row[6] else False,
                    'total_available': (row[2] or 0) + (row[4] or 0)
                }
                for row in results
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error searching batches: {e}")
            return []