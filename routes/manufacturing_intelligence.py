"""
Manufacturing Intelligence Routes
Routes for advanced manufacturing analytics and automation
"""
from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import logging

from services.manufacturing_intelligence import ManufacturingIntelligence
from services.bom_planner import BOMPlanner
from services.uom_converter import UOMConverter
from models import Item, JobWork, Production, BOM, Supplier
from models.intelligence import ManufacturingAlert, SupplierPerformanceMetric
from app import db

logger = logging.getLogger(__name__)

manufacturing_intelligence_bp = Blueprint('manufacturing_intelligence', __name__, url_prefix='/manufacturing-intelligence')

@manufacturing_intelligence_bp.route('/dashboard')
@login_required
def dashboard():
    """Manufacturing Intelligence Dashboard"""
    try:
        intelligence = ManufacturingIntelligence()
        
        # Get real-time insights
        bottleneck_analysis = intelligence.analyze_process_bottlenecks()
        material_flow = intelligence.get_real_time_material_flow()
        
        # Get active alerts
        try:
            active_alerts = ManufacturingAlert.query.filter_by(status='active').order_by(
                ManufacturingAlert.severity.desc(),
                ManufacturingAlert.created_at.desc()
            ).limit(10).all()
        except:
            active_alerts = []
        
        # Dashboard statistics  
        stats = {
            'total_processes': len(bottleneck_analysis.get('processes', [])),
            'active_bottlenecks': bottleneck_analysis.get('processes_with_bottlenecks', 0),
            'active_alerts': len(active_alerts),
            'material_flow_velocity': material_flow.get('flow_velocity', {}).get('recent_completions', 0) if isinstance(material_flow, dict) else 0
        }
        
        return render_template('manufacturing_intelligence/dashboard.html',
                             bottleneck_analysis=bottleneck_analysis,
                             material_flow=material_flow,
                             active_alerts=active_alerts,
                             stats=stats)
                             
    except Exception as e:
        logger.error(f"Error loading manufacturing intelligence dashboard: {e}")
        flash('Error loading manufacturing intelligence dashboard', 'error')
        return redirect(url_for('main.dashboard'))

@manufacturing_intelligence_bp.route('/bottleneck-analysis')
@login_required
def bottleneck_analysis():
    """Detailed bottleneck analysis"""
    try:
        days = request.args.get('days', 7, type=int)
        intelligence = ManufacturingIntelligence()
        analysis = intelligence.analyze_process_bottlenecks(days)
        
        return render_template('manufacturing_intelligence/bottleneck_analysis.html',
                             analysis=analysis, days=days)
                             
    except Exception as e:
        logger.error(f"Error in bottleneck analysis: {e}")
        flash('Error analyzing bottlenecks', 'error')
        return redirect(url_for('manufacturing_intelligence.dashboard'))

@manufacturing_intelligence_bp.route('/material-flow')
@login_required
def material_flow():
    """Real-time material flow visualization"""
    try:
        intelligence = ManufacturingIntelligence()
        flow_data = intelligence.get_real_time_material_flow()
        
        return render_template('manufacturing_intelligence/material_flow.html',
                             flow_data=flow_data)
                             
    except Exception as e:
        logger.error(f"Error getting material flow: {e}")
        flash('Error loading material flow data', 'error')
        return redirect(url_for('manufacturing_intelligence.dashboard'))

@manufacturing_intelligence_bp.route('/bom-planning')
@login_required
def bom_planning():
    """BOM-driven material planning interface"""
    try:
        items_with_bom = db.session.query(Item).join(BOM).filter(BOM.is_active == True).all()
        
        return render_template('manufacturing_intelligence/bom_planning.html',
                             items_with_bom=items_with_bom)
                             
    except Exception as e:
        logger.error(f"Error loading BOM planning: {e}")
        flash('Error loading BOM planning interface', 'error')
        return redirect(url_for('manufacturing_intelligence.dashboard'))

@manufacturing_intelligence_bp.route('/uom-converter')
@login_required
def uom_converter():
    """UOM conversion utility"""
    try:
        return render_template('manufacturing_intelligence/uom_converter.html')
        
    except Exception as e:
        logger.error(f"Error loading UOM converter: {e}")
        flash('Error loading UOM converter', 'error')
        return redirect(url_for('manufacturing_intelligence.dashboard'))

@manufacturing_intelligence_bp.route('/alerts')
@login_required
def alerts():
    """Manufacturing alerts management"""
    try:
        status_filter = request.args.get('status', 'active')
        
        query = ManufacturingAlert.query
        if status_filter != 'all':
            query = query.filter_by(status=status_filter)
        
        alerts = query.order_by(
            ManufacturingAlert.severity.desc(),
            ManufacturingAlert.created_at.desc()
        ).all()
        
        return render_template('manufacturing_intelligence/alerts.html',
                             alerts=alerts, status_filter=status_filter)
                             
    except Exception as e:
        logger.error(f"Error loading alerts: {e}")
        flash('Error loading manufacturing alerts', 'error')
        return redirect(url_for('manufacturing_intelligence.dashboard'))

# API Endpoints

@manufacturing_intelligence_bp.route('/api/analyze-production/<int:item_id>')
@login_required
def api_analyze_production(item_id):
    """API endpoint for production analysis"""
    try:
        planned_quantity = request.args.get('quantity', 1, type=float)
        
        planner = BOMPlanner()
        analysis = planner.analyze_production_requirements(item_id, planned_quantity)
        
        return jsonify(analysis)
        
    except Exception as e:
        logger.error(f"Error in production analysis API: {e}")
        return jsonify({'error': str(e)}), 500

@manufacturing_intelligence_bp.route('/api/purchase-suggestions', methods=['POST'])
@login_required
def api_purchase_suggestions():
    """Generate purchase suggestions from shortage analysis"""
    try:
        data = request.get_json()
        shortage_analysis = data.get('shortage_analysis', {})
        
        planner = BOMPlanner()
        suggestions = planner.generate_purchase_suggestions(shortage_analysis)
        
        return jsonify({'suggestions': suggestions})
        
    except Exception as e:
        logger.error(f"Error generating purchase suggestions: {e}")
        return jsonify({'error': str(e)}), 500

@manufacturing_intelligence_bp.route('/api/convert-uom', methods=['POST'])
@login_required
def api_convert_uom():
    """UOM conversion API"""
    try:
        data = request.get_json()
        quantity = float(data.get('quantity', 0))
        from_uom = data.get('from_uom', '')
        to_uom = data.get('to_uom', '')
        conversion_factor = data.get('conversion_factor')
        
        if conversion_factor:
            conversion_factor = float(conversion_factor)
        
        converted = UOMConverter.convert_quantity(quantity, from_uom, to_uom, conversion_factor)
        
        if converted is not None:
            return jsonify({
                'success': True,
                'original_quantity': quantity,
                'original_uom': from_uom,
                'converted_quantity': converted,
                'converted_uom': to_uom,
                'conversion_factor': conversion_factor
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Conversion not possible between these units'
            })
            
    except Exception as e:
        logger.error(f"Error in UOM conversion API: {e}")
        return jsonify({'success': False, 'error': str(e)})

@manufacturing_intelligence_bp.route('/api/material-flow-data')
@login_required
def api_material_flow_data():
    """Real-time material flow data API"""
    try:
        intelligence = ManufacturingIntelligence()
        flow_data = intelligence.get_real_time_material_flow()
        
        return jsonify(flow_data)
        
    except Exception as e:
        logger.error(f"Error getting material flow data: {e}")
        return jsonify({'error': str(e)}), 500

@manufacturing_intelligence_bp.route('/api/generate-alerts', methods=['POST'])
@login_required
def api_generate_alerts():
    """Generate predictive alerts"""
    try:
        intelligence = ManufacturingIntelligence()
        alerts_result = intelligence.generate_predictive_alerts()
        
        return jsonify(alerts_result)
        
    except Exception as e:
        logger.error(f"Error generating alerts: {e}")
        return jsonify({'error': str(e)}), 500

@manufacturing_intelligence_bp.route('/api/acknowledge-alert/<int:alert_id>', methods=['POST'])
@login_required
def api_acknowledge_alert(alert_id):
    """Acknowledge a manufacturing alert"""
    try:
        alert = ManufacturingAlert.query.get_or_404(alert_id)
        
        alert.status = 'acknowledged'
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = current_user.id
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Alert acknowledged successfully'})
        
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@manufacturing_intelligence_bp.route('/api/material-forecast/<int:item_id>')
@login_required
def api_material_forecast(item_id):
    """Get material forecast for specific item"""
    try:
        days_ahead = request.args.get('days', 30, type=int)
        
        planner = BOMPlanner()
        forecast = planner.get_material_forecast(days_ahead)
        
        # Filter for specific item if requested
        item_forecast = None
        if forecast.get('forecast'):
            item_forecast = next((f for f in forecast['forecast'] if f['material_id'] == item_id), None)
        
        return jsonify({
            'item_id': item_id,
            'forecast_period': days_ahead,
            'forecast': item_forecast
        })
        
    except Exception as e:
        logger.error(f"Error getting material forecast: {e}")
        return jsonify({'error': str(e)}), 500