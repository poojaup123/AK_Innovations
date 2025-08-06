from flask import Blueprint, render_template
from flask_login import login_required

# Create blueprint for placeholder modules
placeholder_bp = Blueprint('placeholder', __name__)

@placeholder_bp.route('/reports')
@login_required 
def reports_dashboard():
    """Reports & Analytics dashboard placeholder"""
    return render_template('placeholder.html', 
                         title="Reports & Analytics",
                         description="Business reports and data analytics coming soon",
                         icon="fas fa-chart-bar")

@placeholder_bp.route('/notifications')
@login_required
def notifications_dashboard():
    """Notifications dashboard placeholder"""
    return render_template('placeholder.html',
                         title="Notifications",
                         description="System notifications and alerts management coming soon", 
                         icon="fas fa-bell")

# Register placeholder routes with appropriate blueprint names
# This allows the dashboard modules to work without 404 errors
from flask import current_app

def register_placeholder_routes(app):
    """Register placeholder routes for missing modules"""
    from flask_login import login_required
    
    # Reports placeholder
    @app.route('/reports/dashboard')
    @login_required
    def reports_dashboard():
        return render_template('placeholder.html',
                             title="Reports & Analytics", 
                             description="Comprehensive business reports and analytics dashboard",
                             icon="fas fa-chart-bar",
                             features=[
                                 "Sales and Purchase Analytics",
                                 "Inventory Reports", 
                                 "Production Metrics",
                                 "Financial Summaries",
                                 "Custom Report Builder"
                             ])
    
    # Notifications placeholder  
    @app.route('/notifications/dashboard')
    @login_required
    def notifications_dashboard():
        return render_template('placeholder.html',
                             title="Notifications Center",
                             description="Centralized notification and alert management system",
                             icon="fas fa-bell",
                             features=[
                                 "Real-time System Alerts",
                                 "Low Stock Notifications",
                                 "Order Status Updates", 
                                 "Production Reminders",
                                 "Custom Alert Rules"
                             ])