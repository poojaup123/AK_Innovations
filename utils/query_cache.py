"""
Query Caching System for Tally-like Performance
Implements intelligent caching to reduce database load
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Callable
from functools import wraps

# Simple in-memory cache
_cache_store: Dict[str, Dict[str, Any]] = {}

class QueryCache:
    """Intelligent query caching system"""
    
    @staticmethod
    def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate unique cache key"""
        key_data = {
            'function': func_name,
            'args': str(args),
            'kwargs': sorted(kwargs.items()) if kwargs else {}
        }
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    @staticmethod
    def get(cache_key: str) -> Optional[Any]:
        """Get cached value if still valid"""
        if cache_key in _cache_store:
            cache_entry = _cache_store[cache_key]
            
            # Check if cache is still valid
            if time.time() < cache_entry['expires_at']:
                cache_entry['hits'] += 1
                cache_entry['last_accessed'] = time.time()
                return cache_entry['data']
            else:
                # Cache expired, remove it
                del _cache_store[cache_key]
        
        return None
    
    @staticmethod
    def set(cache_key: str, data: Any, duration_seconds: int = 300) -> None:
        """Cache data with expiration"""
        _cache_store[cache_key] = {
            'data': data,
            'expires_at': time.time() + duration_seconds,
            'created_at': time.time(),
            'last_accessed': time.time(),
            'hits': 0
        }
    
    @staticmethod
    def invalidate_pattern(pattern: str) -> int:
        """Invalidate cache entries matching pattern"""
        keys_to_remove = [
            key for key in _cache_store.keys() 
            if pattern in key
        ]
        
        for key in keys_to_remove:
            del _cache_store[key]
        
        return len(keys_to_remove)
    
    @staticmethod
    def clear_all() -> None:
        """Clear entire cache"""
        _cache_store.clear()
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Get cache statistics"""
        now = time.time()
        total_entries = len(_cache_store)
        total_hits = sum(entry['hits'] for entry in _cache_store.values())
        
        expired_count = sum(
            1 for entry in _cache_store.values() 
            if now >= entry['expires_at']
        )
        
        return {
            'total_entries': total_entries,
            'total_hits': total_hits,
            'expired_entries': expired_count,
            'cache_hit_ratio': total_hits / max(total_entries, 1),
            'memory_usage_bytes': len(str(_cache_store))
        }

def cached_query(cache_key_func: Callable = None, duration: int = 300):
    """
    Decorator for caching query results
    
    Args:
        cache_key_func: Function to generate cache key
        duration: Cache duration in seconds (default 5 minutes)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key_func:
                cache_key = cache_key_func(*args, **kwargs)
            else:
                cache_key = QueryCache._generate_cache_key(
                    func.__name__, args, kwargs
                )
            
            # Try to get from cache
            cached_result = QueryCache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            QueryCache.set(cache_key, result, duration)
            
            return result
        
        return wrapper
    return decorator

def cache_dashboard_stats(duration: int = 600):
    """Cache dashboard statistics for 10 minutes"""
    def cache_key_func(*args, **kwargs):
        return f"dashboard_stats_{datetime.now().strftime('%Y%m%d_%H%M')}"
    
    return cached_query(cache_key_func, duration)

def cache_batch_movements(duration: int = 300):
    """Cache batch movements for 5 minutes"""
    def cache_key_func(*args, **kwargs):
        date_str = kwargs.get('date_from', 'recent')
        return f"batch_movements_{date_str}"
    
    return cached_query(cache_key_func, duration)

def cache_item_batches(duration: int = 180):
    """Cache item batch data for 3 minutes"""
    def cache_key_func(item_id, *args, **kwargs):
        return f"item_batches_{item_id}"
    
    return cached_query(cache_key_func, duration)

def invalidate_inventory_cache():
    """Invalidate all inventory-related cache entries"""
    patterns = ['dashboard_stats', 'batch_movements', 'item_batches', 'inventory']
    
    total_invalidated = 0
    for pattern in patterns:
        total_invalidated += QueryCache.invalidate_pattern(pattern)
    
    return total_invalidated

# Cache warming functions
def warm_dashboard_cache():
    """Pre-warm frequently accessed dashboard data"""
    try:
        from services.query_optimizer import DashboardQueries
        
        # Warm up dashboard stats
        DashboardQueries.get_dashboard_stats()
        
        # Warm up recent activities
        DashboardQueries.get_recent_activities()
        
        return True
    except Exception as e:
        print(f"Error warming dashboard cache: {e}")
        return False

def setup_cache_cleanup():
    """Setup automatic cache cleanup"""
    import threading
    import time
    
    def cleanup_expired_cache():
        while True:
            time.sleep(600)  # Clean every 10 minutes
            
            now = time.time()
            expired_keys = [
                key for key, entry in _cache_store.items()
                if now >= entry['expires_at']
            ]
            
            for key in expired_keys:
                del _cache_store[key]
            
            if expired_keys:
                print(f"🧹 Cleaned {len(expired_keys)} expired cache entries")
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_expired_cache, daemon=True)
    cleanup_thread.start()