"""
Cost Calculation Routes

API endpoints for BOM-based cost calculation, vendor comparison, and cost management
"""

from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
import logging

from models import db, Item, BOM, JobWorkRate, Supplier
from services.cost_calculator import (
    calculate_item_cost, 
    get_vendor_comparison, 
    update_costs_after_rate_change,
    analyze_cost_variance
)

logger = logging.getLogger(__name__)

cost_calculation_bp = Blueprint('cost_calculation', __name__, url_prefix='/cost_calculation')


@cost_calculation_bp.route('/calculate/<int:item_id>')
@login_required
def calculate_item_cost_api(item_id):
    """API endpoint to calculate BOM cost for an item"""
    try:
        quantity = float(request.args.get('quantity', 1.0))
        force_recalculate = request.args.get('force', 'false').lower() == 'true'
        
        result = calculate_item_cost(item_id, quantity, force_recalculate)
        
        if result.get('success', True):
            # Update database with calculated cost
            item = Item.query.get(item_id)
            if item and item.cost_source == 'bom_calculated':
                item.bom_calculated_cost = result['total_cost_per_unit']
                item.last_cost_calculation = datetime.utcnow()
                item.cost_calculation_status = 'current'
                db.session.commit()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error calculating cost for item {item_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'total_cost_per_unit': 0.0
        }), 500


@cost_calculation_bp.route('/vendor_comparison/<int:item_id>/<process_type>')
@login_required
def vendor_comparison_api(item_id, process_type):
    """API endpoint for vendor cost comparison"""
    try:
        quantity = float(request.args.get('quantity', 1.0))
        
        comparison = get_vendor_comparison(item_id, process_type, quantity)
        
        return jsonify({
            'success': True,
            'item_id': item_id,
            'process_type': process_type,
            'quantity': quantity,
            'vendors': comparison
        })
        
    except Exception as e:
        logger.error(f"Error getting vendor comparison: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'vendors': []
        }), 500


@cost_calculation_bp.route('/update_costs_after_rate_change/<int:rate_id>')
@login_required
def update_costs_rate_change_api(rate_id):
    """API endpoint to update costs after job work rate change"""
    try:
        update_results = update_costs_after_rate_change(rate_id)
        
        # Commit database changes
        db.session.commit()
        
        return jsonify({
            'success': True,
            'rate_id': rate_id,
            'affected_items': len(update_results),
            'update_results': update_results
        })
        
    except Exception as e:
        logger.error(f"Error updating costs after rate change: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'affected_items': 0
        }), 500


@cost_calculation_bp.route('/variance_analysis/<int:item_id>', methods=['POST'])
@login_required
def cost_variance_analysis_api(item_id):
    """API endpoint for cost variance analysis"""
    try:
        data = request.get_json()
        actual_costs = data.get('actual_costs', {})
        
        analysis = analyze_cost_variance(item_id, actual_costs)
        
        return jsonify({
            'success': True,
            **analysis
        })
        
    except Exception as e:
        logger.error(f"Error analyzing cost variance: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cost_calculation_bp.route('/dashboard')
@login_required
def cost_dashboard():
    """Cost calculation dashboard"""
    try:
        # Get items with BOM-calculated cost source
        bom_calculated_items = Item.query.filter(
            Item.cost_source == 'bom_calculated'
        ).order_by(Item.name).all()
        
        # Get items that need cost calculation
        outdated_items = [
            item for item in bom_calculated_items 
            if item.cost_calculation_needed
        ]
        
        # Get recent cost updates
        recent_updates = Item.query.filter(
            Item.cost_source == 'bom_calculated',
            Item.last_cost_calculation.isnot(None)
        ).order_by(Item.last_cost_calculation.desc()).limit(10).all()
        
        # Get vendor rates summary
        active_rates = JobWorkRate.query.filter(
            JobWorkRate.is_active == True
        ).count()
        
        return render_template('cost_calculation/dashboard.html',
                             bom_calculated_items=bom_calculated_items,
                             outdated_items=outdated_items,
                             recent_updates=recent_updates,
                             active_rates=active_rates)
        
    except Exception as e:
        logger.error(f"Error loading cost dashboard: {str(e)}")
        flash(f'Error loading cost dashboard: {str(e)}', 'error')
        return redirect(url_for('inventory.items'))


@cost_calculation_bp.route('/item_cost_detail/<int:item_id>')
@login_required
def item_cost_detail(item_id):
    """Detailed cost breakdown for a specific item"""
    try:
        item = Item.query.get_or_404(item_id)
        
        if item.cost_source != 'bom_calculated':
            flash('This item does not use BOM-calculated pricing', 'warning')
            return redirect(url_for('cost_calculation.cost_dashboard'))
        
        # Get detailed cost breakdown
        cost_breakdown = calculate_item_cost(item_id, 1.0, force_recalculate=True)
        
        # Get vendor comparisons for outsourced processes
        vendor_comparisons = {}
        if cost_breakdown.get('success', True) and 'process_costs' in cost_breakdown:
            for process in cost_breakdown['process_costs']['details']:
                if process['cost_type'] == 'outsourced':
                    process_type = process['process_name']
                    vendor_comparisons[process_type] = get_vendor_comparison(
                        item_id, process_type, 1.0
                    )
        
        return render_template('cost_calculation/item_detail.html',
                             item=item,
                             cost_breakdown=cost_breakdown,
                             vendor_comparisons=vendor_comparisons)
        
    except Exception as e:
        logger.error(f"Error loading item cost detail: {str(e)}")
        flash(f'Error loading cost details: {str(e)}', 'error')
        return redirect(url_for('cost_calculation.cost_dashboard'))


@cost_calculation_bp.route('/bulk_update_costs', methods=['POST'])
@login_required
def bulk_update_costs():
    """Bulk update costs for all BOM-calculated items"""
    try:
        items_to_update = Item.query.filter(
            Item.cost_source == 'bom_calculated'
        ).all()
        
        update_results = []
        errors = []
        
        for item in items_to_update:
            try:
                old_cost = item.bom_calculated_cost or 0.0
                result = calculate_item_cost(item.id, 1.0, force_recalculate=True)
                
                if result.get('success', True):
                    new_cost = result['total_cost_per_unit']
                    cost_change = new_cost - old_cost
                    
                    item.bom_calculated_cost = new_cost
                    item.last_cost_calculation = datetime.utcnow()
                    item.cost_calculation_status = 'current'
                    
                    update_results.append({
                        'item_id': item.id,
                        'item_name': item.name,
                        'old_cost': old_cost,
                        'new_cost': new_cost,
                        'cost_change': cost_change
                    })
                else:
                    errors.append(f"Failed to calculate cost for {item.name}: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                errors.append(f"Error updating {item.name}: {str(e)}")
        
        db.session.commit()
        
        flash(f'Successfully updated {len(update_results)} items. {len(errors)} errors occurred.', 
              'success' if len(errors) == 0 else 'warning')
        
        if errors:
            for error in errors[:5]:  # Show first 5 errors
                flash(error, 'error')
        
        return redirect(url_for('cost_calculation.cost_dashboard'))
        
    except Exception as e:
        logger.error(f"Error in bulk cost update: {str(e)}")
        flash(f'Bulk update failed: {str(e)}', 'error')
        return redirect(url_for('cost_calculation.cost_dashboard'))


@cost_calculation_bp.route('/set_item_cost_source/<int:item_id>', methods=['POST'])
@login_required
def set_item_cost_source(item_id):
    """Set the cost source for an item"""
    try:
        item = Item.query.get_or_404(item_id)
        
        cost_source = request.form.get('cost_source', 'manual')
        manual_override = request.form.get('manual_cost_override')
        
        if cost_source not in ['manual', 'bom_calculated', 'hybrid']:
            flash('Invalid cost source', 'error')
            return redirect(request.referrer or url_for('inventory.items'))
        
        item.cost_source = cost_source
        
        if cost_source == 'hybrid' and manual_override:
            try:
                item.manual_cost_override = float(manual_override)
            except ValueError:
                flash('Invalid manual cost override value', 'error')
                return redirect(request.referrer or url_for('inventory.items'))
        
        if cost_source == 'bom_calculated':
            # Check if item has an active BOM
            bom = BOM.query.filter_by(product_id=item_id, is_active=True).first()
            if not bom:
                flash('Cannot set to BOM-calculated: No active BOM found for this item', 'error')
                return redirect(request.referrer or url_for('inventory.items'))
            
            # Calculate initial BOM cost
            result = calculate_item_cost(item_id, 1.0, force_recalculate=True)
            if result.get('success', True):
                item.bom_calculated_cost = result['total_cost_per_unit']
                item.last_cost_calculation = datetime.utcnow()
                item.cost_calculation_status = 'current'
            else:
                flash(f'Failed to calculate BOM cost: {result.get("error", "Unknown error")}', 'error')
                return redirect(request.referrer or url_for('inventory.items'))
        
        db.session.commit()
        flash(f'Cost source updated for {item.name}', 'success')
        
        return redirect(request.referrer or url_for('inventory.items'))
        
    except Exception as e:
        logger.error(f"Error setting cost source: {str(e)}")
        flash(f'Error updating cost source: {str(e)}', 'error')
        return redirect(request.referrer or url_for('inventory.items'))


@cost_calculation_bp.route('/cost_trends')
@login_required
def cost_trends():
    """Cost trends and analysis dashboard"""
    try:
        # Get items with recent cost changes
        recent_changes = Item.query.filter(
            Item.cost_source == 'bom_calculated',
            Item.last_cost_calculation.isnot(None)
        ).order_by(Item.last_cost_calculation.desc()).limit(50).all()
        
        # Group by date for trend analysis
        cost_trends_data = {}
        for item in recent_changes:
            date_key = item.last_cost_calculation.strftime('%Y-%m-%d')
            if date_key not in cost_trends_data:
                cost_trends_data[date_key] = []
            
            cost_trends_data[date_key].append({
                'item_name': item.name,
                'cost': item.bom_calculated_cost,
                'status': item.cost_calculation_status
            })
        
        return render_template('cost_calculation/trends.html',
                             cost_trends_data=cost_trends_data,
                             recent_changes=recent_changes)
        
    except Exception as e:
        logger.error(f"Error loading cost trends: {str(e)}")
        flash(f'Error loading cost trends: {str(e)}', 'error')
        return redirect(url_for('cost_calculation.cost_dashboard'))


# Register error handlers
@cost_calculation_bp.errorhandler(404)
def not_found_error(error):
    return jsonify({'success': False, 'error': 'Resource not found'}), 404


@cost_calculation_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500