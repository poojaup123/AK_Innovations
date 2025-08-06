from flask import Blueprint, render_template, request, jsonify, make_response
from flask_login import login_required
from app import db
from models.accounting import Account, JournalEntry, Voucher, VoucherType
from models.accounting import CostCenter, InventoryValuation
from models import Supplier, Item, ItemBatch
from datetime import datetime, timedelta, date
from sqlalchemy import func, and_, or_
from decimal import Decimal
import json

accounting_reports_bp = Blueprint('accounting_reports', __name__, url_prefix='/accounting/reports')

@accounting_reports_bp.route('/advanced-dashboard')
@login_required
def advanced_dashboard():
    """Advanced accounting reports dashboard"""
    try:
        # Get date range from query params
        end_date = request.args.get('end_date', date.today().isoformat())
        start_date = request.args.get('start_date', (date.today() - timedelta(days=30)).isoformat())
        
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        # Department-wise expenses
        dept_expenses = db.session.query(
            CostCenter.name,
            func.sum(JournalEntry.amount).label('total_expense')
        ).join(
            # This would need proper join through expense allocations
            JournalEntry
        ).filter(
            JournalEntry.transaction_date.between(start_date, end_date),
            JournalEntry.entry_type == 'debit'
        ).group_by(CostCenter.name).all()
        
        # Customer/Vendor aging
        aging_data = get_aging_analysis(start_date, end_date)
        
        # Inventory valuation trends
        inventory_trends = get_inventory_valuation_trends(start_date, end_date)
        
        # GST summary
        gst_summary = get_gst_summary(start_date, end_date)
        
        return render_template('accounting/reports/advanced_dashboard.html',
                             dept_expenses=dept_expenses,
                             aging_data=aging_data,
                             inventory_trends=inventory_trends,
                             gst_summary=gst_summary,
                             start_date=start_date,
                             end_date=end_date)
                             
    except Exception as e:
        return render_template('accounting/reports/advanced_dashboard.html',
                             error=str(e))

@accounting_reports_bp.route('/department-costs')
@login_required
def department_costs():
    """Department-wise cost analysis"""
    try:
        # Get filters
        period = request.args.get('period', 'current_month')
        cost_center_id = request.args.get('cost_center_id', '')
        
        # Calculate date range based on period
        if period == 'current_month':
            start_date = date.today().replace(day=1)
            end_date = date.today()
        elif period == 'last_month':
            last_month = date.today().replace(day=1) - timedelta(days=1)
            start_date = last_month.replace(day=1)
            end_date = last_month
        elif period == 'current_year':
            start_date = date.today().replace(month=1, day=1)
            end_date = date.today()
        else:
            start_date = date.today() - timedelta(days=30)
            end_date = date.today()
        
        # Get all cost centers
        cost_centers = CostCenter.query.filter_by(is_active=True).all()
        
        # Department-wise cost data
        cost_data = []
        for center in cost_centers:
            if cost_center_id and str(center.id) != cost_center_id:
                continue
                
            # Get expenses for this cost center
            # This would need proper implementation with expense allocation
            expenses = db.session.query(
                func.sum(JournalEntry.amount).label('total')
            ).filter(
                JournalEntry.transaction_date.between(start_date, end_date),
                JournalEntry.entry_type == 'debit'
                # Add proper cost center filtering
            ).scalar() or 0
            
            cost_data.append({
                'center': center,
                'actual_expense': float(expenses),
                'monthly_budget': float(center.monthly_budget),
                'yearly_budget': float(center.yearly_budget),
                'budget_utilization': (float(expenses) / float(center.monthly_budget) * 100) if center.monthly_budget > 0 else 0
            })
        
        return render_template('accounting/reports/department_costs.html',
                             cost_data=cost_data,
                             cost_centers=cost_centers,
                             period=period,
                             cost_center_id=cost_center_id,
                             start_date=start_date,
                             end_date=end_date)
                             
    except Exception as e:
        return render_template('accounting/reports/department_costs.html',
                             error=str(e))

@accounting_reports_bp.route('/aging-analysis')
@login_required
def aging_analysis():
    """Customer and vendor aging analysis"""
    try:
        analysis_type = request.args.get('type', 'receivables')  # receivables or payables
        
        if analysis_type == 'receivables':
            aging_data = get_customer_aging()
        else:
            aging_data = get_vendor_aging()
        
        return render_template('accounting/reports/aging_analysis.html',
                             aging_data=aging_data,
                             analysis_type=analysis_type)
                             
    except Exception as e:
        return render_template('accounting/reports/aging_analysis.html',
                             error=str(e))

@accounting_reports_bp.route('/inventory-valuation-comparison')
@login_required
def inventory_valuation_comparison():
    """Compare inventory values using different methods"""
    try:
        # Get latest valuations for each item
        subquery = db.session.query(
            InventoryValuation.item_id,
            func.max(InventoryValuation.created_at).label('latest_date')
        ).group_by(InventoryValuation.item_id).subquery()
        
        valuations = db.session.query(InventoryValuation).join(
            subquery,
            and_(
                InventoryValuation.item_id == subquery.c.item_id,
                InventoryValuation.created_at == subquery.c.latest_date
            )
        ).filter(InventoryValuation.quantity > 0).all()
        
        # Calculate totals by method
        totals = {
            'fifo': sum(v.quantity * (v.fifo_rate or 0) for v in valuations),
            'lifo': sum(v.quantity * (v.lifo_rate or 0) for v in valuations),
            'moving_average': sum(v.quantity * (v.moving_avg_rate or 0) for v in valuations),
            'standard_cost': sum(v.quantity * (v.standard_cost_rate or 0) for v in valuations)
        }
        
        return render_template('accounting/reports/inventory_valuation_comparison.html',
                             valuations=valuations,
                             totals=totals)
                             
    except Exception as e:
        return render_template('accounting/reports/inventory_valuation_comparison.html',
                             error=str(e))

@accounting_reports_bp.route('/gst-detailed')
@login_required
def gst_detailed():
    """Detailed GST report with GSTR1/GSTR3B data"""
    try:
        # Get filters
        month = request.args.get('month', str(date.today().month))
        year = request.args.get('year', str(date.today().year))
        
        start_date = date(int(year), int(month), 1)
        if int(month) == 12:
            end_date = date(int(year) + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(int(year), int(month) + 1, 1) - timedelta(days=1)
        
        # Get GST data
        gst_data = get_detailed_gst_data(start_date, end_date)
        
        return render_template('accounting/reports/gst_detailed.html',
                             gst_data=gst_data,
                             month=month,
                             year=year,
                             start_date=start_date,
                             end_date=end_date)
                             
    except Exception as e:
        return render_template('accounting/reports/gst_detailed.html',
                             error=str(e))

@accounting_reports_bp.route('/api/department-chart-data')
@login_required
def department_chart_data():
    """API endpoint for department expense chart data"""
    try:
        period = request.args.get('period', 'current_month')
        
        # Calculate date range
        if period == 'current_month':
            start_date = date.today().replace(day=1)
            end_date = date.today()
        else:
            start_date = date.today() - timedelta(days=30)
            end_date = date.today()
        
        # Get department expenses
        cost_centers = CostCenter.query.filter_by(is_active=True).all()
        chart_data = {
            'labels': [cc.name for cc in cost_centers],
            'datasets': [{
                'label': 'Expenses',
                'data': [],
                'backgroundColor': [
                    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                    '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                ]
            }]
        }
        
        for center in cost_centers:
            # Get expenses (would need proper implementation)
            expenses = 0  # Placeholder
            chart_data['datasets'][0]['data'].append(expenses)
        
        return jsonify(chart_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_aging_analysis(start_date, end_date):
    """Get customer/vendor aging analysis"""
    # Placeholder implementation
    return {
        'customers': [],
        'vendors': []
    }

def get_inventory_valuation_trends(start_date, end_date):
    """Get inventory valuation trends"""
    # Placeholder implementation
    return []

def get_gst_summary(start_date, end_date):
    """Get GST summary data"""
    # Placeholder implementation
    return {
        'input_gst': 0,
        'output_gst': 0,
        'net_gst': 0
    }

def get_customer_aging():
    """Get customer aging data"""
    # Placeholder implementation
    return []

def get_vendor_aging():
    """Get vendor aging data"""
    # Placeholder implementation
    return []

def get_detailed_gst_data(start_date, end_date):
    """Get detailed GST data for GSTR reports"""
    # Placeholder implementation
    return {
        'gstr1': [],
        'gstr3b': {}
    }