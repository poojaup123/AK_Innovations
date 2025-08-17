"""
Database Query Optimization Service

This service provides optimized database query patterns and caching mechanisms
to improve performance across the factory management system.
"""

from functools import wraps
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_, case
from sqlalchemy.orm import joinedload, selectinload
from app import db
from models import Item, PurchaseOrder, SalesOrder, JobWork, Production, Employee
from models.accounting import Account, AccountGroup, Voucher, JournalEntry
from models.job_card import JobCard


class QueryOptimizer:
    """Database query optimization utilities"""
    
    # Cache for frequently accessed data
    _cache = {}
    _cache_timestamps = {}
    CACHE_DURATION = 300  # 5 minutes
    
    @classmethod
    def get_cached_data(cls, key):
        """Get data from cache if valid"""
        if key in cls._cache:
            timestamp = cls._cache_timestamps.get(key)
            if timestamp and (datetime.now() - timestamp).seconds < cls.CACHE_DURATION:
                return cls._cache[key]
        return None
    
    @classmethod
    def set_cached_data(cls, key, data):
        """Store data in cache"""
        cls._cache[key] = data
        cls._cache_timestamps[key] = datetime.now()
    
    @classmethod
    def clear_cache(cls, pattern=None):
        """Clear cache entries matching pattern or all if pattern is None"""
        if pattern:
            keys_to_remove = [k for k in cls._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del cls._cache[key]
                if key in cls._cache_timestamps:
                    del cls._cache_timestamps[key]
        else:
            cls._cache.clear()
            cls._cache_timestamps.clear()


def cached_query(cache_key_func=None, duration=300):
    """Decorator for caching query results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key_func:
                cache_key = cache_key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}_{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = QueryOptimizer.get_cached_data(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            QueryOptimizer.set_cached_data(cache_key, result)
            return result
        return wrapper
    return decorator


class DashboardQueries:
    """Optimized queries for dashboard statistics"""
    
    @staticmethod
    def get_dashboard_stats():
        """Get all dashboard statistics in optimized queries"""
        # Single query to get all counts
        stats = db.session.query(
            func.count(Item.id).label('total_items'),
            func.sum(
                case(
                    (Item.current_stock <= Item.minimum_stock, 1),
                    else_=0
                )
            ).label('low_stock_items')
        ).first()
        
        # Order status counts - separate queries to avoid cartesian products
        purchase_order_stats = db.session.query(
            func.count(PurchaseOrder.id).label('open_purchase_orders')
        ).filter(PurchaseOrder.status == 'open').scalar() or 0
        
        sales_order_stats = db.session.query(
            func.count(SalesOrder.id).label('pending_sales_orders')
        ).filter(SalesOrder.status == 'pending').scalar() or 0
        
        # Job work and production counts - separate queries to avoid cartesian products
        active_employees = db.session.query(
            func.count(Employee.id)
        ).filter(Employee.is_active == True).scalar() or 0
        
        open_job_works = db.session.query(
            func.count(JobWork.id)
        ).filter(JobWork.status == 'sent').scalar() or 0
        
        planned_productions = db.session.query(
            func.count(Production.id)
        ).filter(Production.status == 'planned').scalar() or 0
        
        return {
            'total_items': getattr(stats, 'total_items', 0) or 0,
            'low_stock_items': getattr(stats, 'low_stock_items', 0) or 0,
            'open_purchase_orders': purchase_order_stats,
            'pending_sales_orders': sales_order_stats,
            'active_employees': active_employees,
            'open_job_works': open_job_works,
            'planned_productions': planned_productions
        }
    
    @staticmethod
    def get_recent_activities():
        """Get recent activities with optimized loading"""
        recent_pos = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).limit(5).all()
        recent_sos = SalesOrder.query.order_by(SalesOrder.created_at.desc()).limit(5).all()
        
        low_stock_items = Item.query.filter(
            Item.current_stock <= Item.minimum_stock
        ).limit(10).all()
        
        return {
            'recent_pos': recent_pos,
            'recent_sos': recent_sos,
            'low_stock_items': low_stock_items
        }


class AccountingQueries:
    """Optimized queries for accounting operations"""
    
    @staticmethod
    @cached_query(lambda: "account_balances", duration=300)
    def get_account_balances():
        """Get account balances by type in optimized queries"""
        # Single query to get all account balances by type
        balance_query = db.session.query(
            AccountGroup.group_type,
            func.sum(
                func.case(
                    (Account.current_balance.isnot(None), Account.current_balance),
                    else_=0
                )
            ).label('total_balance')
        ).join(Account).filter(
            Account.is_active == True,
            AccountGroup.is_active == True
        ).group_by(AccountGroup.group_type).all()
        
        balances = {item.group_type: float(item.total_balance or 0) for item in balance_query}
        
        return {
            'total_assets': abs(balances.get('assets', 0)),
            'total_liabilities': balances.get('liabilities', 0),
            'total_income': abs(balances.get('income', 0)),
            'total_expenses': abs(balances.get('expenses', 0))
        }
    
    @staticmethod
    @cached_query(lambda date_filter: f"monthly_vouchers_{date_filter}", duration=600)
    def get_monthly_vouchers(year, month):
        """Get monthly voucher count efficiently"""
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month + 1, 1)
        
        return Voucher.query.filter(
            Voucher.created_at >= month_start,
            Voucher.created_at < month_end
        ).count()


class ProductionQueries:
    """Optimized queries for production operations"""
    
    @staticmethod
    def get_optimized_job_cards(status_filter=None, search=None):
        """Get job cards with optimized loading"""
        query = db.session.query(JobCard).options(
            joinedload(JobCard.production),
            joinedload(JobCard.item),
            joinedload(JobCard.assigned_worker),
            joinedload(JobCard.assigned_vendor)
        )
        
        if status_filter:
            query = query.filter(JobCard.status == status_filter)
        
        if search:
            query = query.filter(
                or_(
                    JobCard.job_card_number.contains(search),
                    JobCard.item.has(Item.name.contains(search))
                )
            )
        
        return query.all()
    
    @staticmethod
    @cached_query(lambda: "production_metrics", duration=180)
    def get_production_metrics():
        """Get production metrics in optimized query"""
        today = datetime.now().date()
        
        metrics = db.session.query(
            func.count(Production.id).label('total_productions'),
            func.sum(
                case(
                    (Production.status == 'planned', 1),
                    else_=0
                )
            ).label('planned_productions'),
            func.sum(
                case(
                    (Production.status == 'in_progress', 1),
                    else_=0
                )
            ).label('in_progress_productions'),
            func.sum(
                case(
                    (Production.status == 'completed', 1),
                    else_=0
                )
            ).label('completed_productions')
        ).first()
        
        return {
            'total_productions': getattr(metrics, 'total_productions', 0) or 0,
            'planned_productions': getattr(metrics, 'planned_productions', 0) or 0,
            'in_progress_productions': getattr(metrics, 'in_progress_productions', 0) or 0,
            'completed_productions': getattr(metrics, 'completed_productions', 0) or 0
        }


# Context processor for common template variables
def inject_common_context():
    """Inject commonly used variables into all templates"""
    try:
        # Only calculate if user is authenticated
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            return {
                'current_year': datetime.now().year,
                'current_date': datetime.now().date(),
                'app_version': '2.0.0',
                'debug_mode': False
            }
    except:
        pass
    return {}


# Query optimization decorators
def optimize_queries(func):
    """Decorator to enable query optimization"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Enable SQLAlchemy query optimization for SQLite
        try:
            from sqlalchemy import text
            db.session.execute(text("PRAGMA cache_size = 8000"))
        except:
            pass  # Skip for non-SQLite databases
        return func(*args, **kwargs)
    return wrapper


def bulk_insert_optimized(model_class, data_list, batch_size=1000):
    """Optimized bulk insert for large datasets"""
    try:
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            db.session.bulk_insert_mappings(model_class, batch)
            db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Bulk insert error: {e}")
        return False