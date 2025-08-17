"""
CLI Commands for Performance Optimization
Manages database indexes and performance analysis
"""

import click
from flask.cli import with_appcontext
from utils.performance_indexes import (
    create_performance_indexes, 
    analyze_table_performance, 
    check_slow_queries
)
from utils.query_cache import QueryCache, warm_dashboard_cache, setup_cache_cleanup

@click.command()
@with_appcontext
def create_indexes():
    """Create performance indexes for optimal query speed"""
    click.echo("🚀 Creating performance indexes...")
    
    success = create_performance_indexes()
    if success:
        click.echo("✅ Performance indexes created successfully!")
    else:
        click.echo("❌ Failed to create some indexes")

@click.command()
@with_appcontext
def analyze_performance():
    """Analyze database performance and table sizes"""
    click.echo("📊 Analyzing database performance...")
    
    # Table analysis
    table_stats = analyze_table_performance()
    
    # Slow query analysis
    slow_query_stats = check_slow_queries()
    
    # Cache statistics
    cache_stats = QueryCache.get_stats()
    
    click.echo("\n📈 Performance Analysis Complete!")
    click.echo(f"Cache Hit Ratio: {cache_stats.get('cache_hit_ratio', 0):.2%}")
    click.echo(f"Cache Entries: {cache_stats.get('total_entries', 0)}")

@click.command()
@with_appcontext
def warm_cache():
    """Warm up application cache for faster response times"""
    click.echo("🔥 Warming up application cache...")
    
    success = warm_dashboard_cache()
    if success:
        click.echo("✅ Cache warmed successfully!")
    else:
        click.echo("⚠️  Some cache warming failed")

@click.command()
@with_appcontext
def clear_cache():
    """Clear all cached data"""
    click.echo("🧹 Clearing application cache...")
    
    QueryCache.clear_all()
    click.echo("✅ Cache cleared successfully!")

@click.command()
@with_appcontext
def setup_performance():
    """Complete performance setup - indexes, cache, and analysis"""
    click.echo("⚡ Setting up complete performance optimization...")
    
    # Create indexes
    click.echo("1/4 Creating database indexes...")
    create_performance_indexes()
    
    # Setup cache cleanup
    click.echo("2/4 Setting up cache management...")
    setup_cache_cleanup()
    
    # Warm cache
    click.echo("3/4 Warming up cache...")
    warm_dashboard_cache()
    
    # Final analysis
    click.echo("4/4 Running performance analysis...")
    analyze_table_performance()
    
    click.echo("🎉 Performance optimization complete!")
    click.echo("Your app should now run with Tally-like speed!")

def register_cli_commands(app):
    """Register all CLI commands with Flask app"""
    app.cli.add_command(create_indexes)
    app.cli.add_command(analyze_performance)
    app.cli.add_command(warm_cache)
    app.cli.add_command(clear_cache)
    app.cli.add_command(setup_performance)