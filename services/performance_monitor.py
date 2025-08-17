"""
Performance Monitoring and Optimization
Real-time performance tracking for Tally-like speed
"""

import time
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any
from flask import current_app, g, request
from functools import wraps

# Performance metrics storage
_performance_metrics = {
    'page_load_times': [],
    'database_query_times': [],
    'memory_usage': [],
    'cpu_usage': [],
    'slow_requests': [],
    'cache_stats': {'hits': 0, 'misses': 0}
}

class PerformanceMonitor:
    """
    Monitor application performance in real-time
    """
    
    @staticmethod
    def start_request_timer():
        """Start timing a request"""
        g.start_time = time.time()
    
    @staticmethod
    def end_request_timer():
        """End timing and record performance metrics"""
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            
            # Record page load time
            _performance_metrics['page_load_times'].append({
                'timestamp': datetime.now(),
                'duration': duration,
                'endpoint': request.endpoint or 'unknown',
                'method': request.method
            })
            
            # Keep only last 100 records
            if len(_performance_metrics['page_load_times']) > 100:
                _performance_metrics['page_load_times'] = _performance_metrics['page_load_times'][-100:]
            
            # Flag slow requests (> 2 seconds)
            if duration > 2.0:
                _performance_metrics['slow_requests'].append({
                    'timestamp': datetime.now(),
                    'duration': duration,
                    'endpoint': request.endpoint or 'unknown',
                    'url': request.url,
                    'method': request.method
                })
    
    @staticmethod
    def record_query_time(duration: float, query_type: str = 'unknown'):
        """Record database query execution time"""
        _performance_metrics['database_query_times'].append({
            'timestamp': datetime.now(),
            'duration': duration,
            'query_type': query_type
        })
        
        # Keep only last 50 records
        if len(_performance_metrics['database_query_times']) > 50:
            _performance_metrics['database_query_times'] = _performance_metrics['database_query_times'][-50:]
    
    @staticmethod
    def record_system_metrics():
        """Record system resource usage"""
        if not PSUTIL_AVAILABLE:
            return
            
        try:
            # CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            
            _performance_metrics['cpu_usage'].append({
                'timestamp': datetime.now(),
                'cpu_percent': cpu_percent
            })
            
            _performance_metrics['memory_usage'].append({
                'timestamp': datetime.now(),
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / 1024 / 1024
            })
            
            # Keep only last 60 records (for 1 hour if recorded every minute)
            for metric_list in ['cpu_usage', 'memory_usage']:
                if len(_performance_metrics[metric_list]) > 60:
                    _performance_metrics[metric_list] = _performance_metrics[metric_list][-60:]
                    
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error recording system metrics: {e}")
    
    @staticmethod
    def get_performance_summary() -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        
        # Calculate average page load time (last hour)
        recent_loads = [
            load for load in _performance_metrics['page_load_times']
            if load['timestamp'] >= last_hour
        ]
        
        avg_load_time = sum(load['duration'] for load in recent_loads) / len(recent_loads) if recent_loads else 0
        
        # Calculate average query time (last hour)
        recent_queries = [
            query for query in _performance_metrics['database_query_times']
            if query['timestamp'] >= last_hour
        ]
        
        avg_query_time = sum(query['duration'] for query in recent_queries) / len(recent_queries) if recent_queries else 0
        
        # Get recent slow requests
        recent_slow = [
            req for req in _performance_metrics['slow_requests']
            if req['timestamp'] >= last_hour
        ]
        
        # System metrics (only if psutil available)
        current_cpu = 0
        current_memory = 0
        if PSUTIL_AVAILABLE and _performance_metrics['cpu_usage']:
            current_cpu = _performance_metrics['cpu_usage'][-1]['cpu_percent']
        if PSUTIL_AVAILABLE and _performance_metrics['memory_usage']:
            current_memory = _performance_metrics['memory_usage'][-1]['memory_percent']
        
        return {
            'avg_page_load_time': round(avg_load_time, 3),
            'avg_query_time': round(avg_query_time, 3),
            'slow_requests_count': len(recent_slow),
            'current_cpu_percent': current_cpu,
            'current_memory_percent': current_memory,
            'total_requests': len(recent_loads),
            'total_queries': len(recent_queries),
            'cache_hit_ratio': _performance_metrics['cache_stats']['hits'] / max(
                _performance_metrics['cache_stats']['hits'] + _performance_metrics['cache_stats']['misses'], 1
            ),
            'performance_grade': PerformanceMonitor._calculate_performance_grade(avg_load_time, current_cpu, current_memory)
        }
    
    @staticmethod
    def _calculate_performance_grade(avg_load_time: float, cpu_percent: float, memory_percent: float) -> str:
        """Calculate overall performance grade"""
        score = 100
        
        # Deduct points for slow page loads
        if avg_load_time > 0.5:  # Tally-like target: < 0.5 seconds
            score -= min(50, (avg_load_time - 0.5) * 100)
        
        # Deduct points for high CPU usage
        if cpu_percent > 70:
            score -= (cpu_percent - 70)
        
        # Deduct points for high memory usage
        if memory_percent > 80:
            score -= (memory_percent - 80)
        
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    @staticmethod
    def get_slowest_endpoints() -> List[Dict]:
        """Get the slowest endpoints in the last hour"""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        
        recent_loads = [
            load for load in _performance_metrics['page_load_times']
            if load['timestamp'] >= last_hour
        ]
        
        # Group by endpoint and calculate average times
        endpoint_times = {}
        for load in recent_loads:
            endpoint = load['endpoint']
            if endpoint not in endpoint_times:
                endpoint_times[endpoint] = []
            endpoint_times[endpoint].append(load['duration'])
        
        # Calculate averages and sort
        endpoint_averages = [
            {
                'endpoint': endpoint,
                'avg_duration': sum(times) / len(times),
                'request_count': len(times),
                'slowest_request': max(times)
            }
            for endpoint, times in endpoint_times.items()
        ]
        
        return sorted(endpoint_averages, key=lambda x: x['avg_duration'], reverse=True)[:10]

def performance_timer(func):
    """Decorator to time function execution"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start_time
            PerformanceMonitor.record_query_time(duration, func.__name__)
    return wrapper

def setup_performance_monitoring(app):
    """Setup performance monitoring for Flask app"""
    
    @app.before_request
    def before_request():
        PerformanceMonitor.start_request_timer()
    
    @app.after_request
    def after_request(response):
        PerformanceMonitor.end_request_timer()
        return response
    
    # Start system metrics collection thread (only if psutil available)
    if PSUTIL_AVAILABLE:
        def collect_system_metrics():
            while True:
                time.sleep(60)  # Collect every minute
                PerformanceMonitor.record_system_metrics()
        
        metrics_thread = threading.Thread(target=collect_system_metrics, daemon=True)
        metrics_thread.start()
        print("🚀 Performance monitoring enabled with system metrics - Tally-like speed tracking active!")
    else:
        print("🚀 Performance monitoring enabled (basic) - Tally-like speed tracking active!")

def get_optimization_recommendations() -> List[str]:
    """Get actionable optimization recommendations"""
    recommendations = []
    summary = PerformanceMonitor.get_performance_summary()
    
    if summary['avg_page_load_time'] > 1.0:
        recommendations.append("📈 Page load times are slow. Consider enabling caching and optimizing database queries.")
    
    if summary['avg_query_time'] > 0.1:
        recommendations.append("🗄️ Database queries are slow. Check if indexes are properly created.")
    
    if summary['current_cpu_percent'] > 80:
        recommendations.append("⚡ High CPU usage detected. Consider optimizing heavy computations.")
    
    if summary['current_memory_percent'] > 85:
        recommendations.append("🧠 High memory usage. Consider implementing better caching strategies.")
    
    if summary['slow_requests_count'] > 5:
        recommendations.append("🐌 Multiple slow requests detected. Review the slowest endpoints.")
    
    if summary['cache_hit_ratio'] < 0.7:
        recommendations.append("💾 Low cache hit ratio. Consider caching more frequently accessed data.")
    
    if not recommendations:
        recommendations.append("✅ Performance looks good! Your app is running at Tally-like speed.")
    
    return recommendations