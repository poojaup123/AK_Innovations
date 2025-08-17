"""
User-friendly price visibility service for role-based access control.
Provides clean, simple methods to control what pricing information users can see.
"""

from flask_login import current_user
from markupsafe import Markup

class PriceVisibilityService:
    """Service to manage price visibility in a user-friendly way"""
    
    @staticmethod
    def can_see_price(user=None):
        """Check if user can see individual item prices"""
        if user is None:
            user = current_user
        return user.is_authenticated and user.can_view_prices()
    
    @staticmethod
    def can_see_totals(user=None):
        """Check if user can see financial totals and valuations"""
        if user is None:
            user = current_user
        return user.is_authenticated and user.can_view_financial_values()
    
    @staticmethod
    def can_see_cost_analysis(user=None):
        """Check if user can see cost breakdowns and profitability"""
        if user is None:
            user = current_user
        return user.is_authenticated and user.can_view_cost_analysis()
    
    @staticmethod
    def format_price_display(price, user=None, show_currency=True):
        """
        Format price for display based on user permissions.
        Returns appropriate display string or hidden indicator.
        """
        if user is None:
            user = current_user
        
        if not user.is_authenticated:
            return "Hidden"
        
        if not user.can_view_prices():
            return '<span class="text-muted" title="Price hidden based on your permissions"><i class="fas fa-eye-slash"></i> Hidden</span>'
        
        if price is None or price == 0:
            return "—"
        
        currency_symbol = "₹" if show_currency else ""
        formatted_price = f"{currency_symbol}{price:,.2f}"
        
        return formatted_price
    
    @staticmethod
    def format_total_display(total, user=None, show_currency=True):
        """
        Format total/valuation for display based on user permissions.
        Shows different levels of detail based on user role.
        """
        if user is None:
            user = current_user
        
        if not user.is_authenticated:
            return "Hidden"
        
        if not user.can_view_financial_values():
            return '<span class="text-muted" title="Financial totals hidden based on your permissions"><i class="fas fa-eye-slash"></i> Hidden</span>'
        
        if total is None or total == 0:
            return "—"
        
        currency_symbol = "₹" if show_currency else ""
        formatted_total = f"{currency_symbol}{total:,.2f}"
        
        return formatted_total
    
    @staticmethod
    def get_price_column_header(user=None):
        """Get appropriate column header based on user permissions"""
        if user is None:
            user = current_user
        
        if not user.is_authenticated or not user.can_view_prices():
            return "Rate"  # Generic term
        
        return "Unit Price"
    
    @staticmethod
    def get_total_column_header(user=None):
        """Get appropriate total column header based on user permissions"""
        if user is None:
            user = current_user
        
        if not user.is_authenticated or not user.can_view_financial_values():
            return "Total"  # Generic term
        
        return "Amount"
    
    @staticmethod
    def hide_price_fields():
        """Check if price input fields should be hidden in forms"""
        return not current_user.is_authenticated or not current_user.can_modify_prices()
    
    @staticmethod
    def get_user_price_role_display(user=None):
        """Get user-friendly description of user's price access level"""
        if user is None:
            user = current_user
        
        if not user.is_authenticated:
            return "Guest - No Price Access"
        
        if user.is_admin():
            return "Administrator - Full Access"
        
        level = user.get_price_display_level()
        
        role_descriptions = {
            'full': 'Manager - Full Financial Access',
            'financial': 'Supervisor - Financial Values Access',
            'prices': 'Staff - Basic Price Access',
            'none': 'Operator - No Price Access'
        }
        
        return role_descriptions.get(level, 'Staff - Limited Access')
    
    @staticmethod
    def create_price_access_badge(user=None):
        """Create a user-friendly badge showing user's price access level"""
        if user is None:
            user = current_user
        
        if not user.is_authenticated:
            return '<span class="badge bg-secondary">No Access</span>'
        
        if user.is_admin():
            return '<span class="badge bg-success"><i class="fas fa-crown"></i> Full Access</span>'
        
        level = user.get_price_display_level()
        
        badges = {
            'full': '<span class="badge bg-primary"><i class="fas fa-chart-line"></i> Manager</span>',
            'financial': '<span class="badge bg-info"><i class="fas fa-calculator"></i> Financial</span>',
            'prices': '<span class="badge bg-warning"><i class="fas fa-tag"></i> Basic</span>',
            'none': '<span class="badge bg-secondary"><i class="fas fa-eye-slash"></i> Hidden</span>'
        }
        
        return Markup(badges.get(level, '<span class="badge bg-light">Limited</span>'))

# Template helper functions
def init_price_visibility_helpers(app):
    """Initialize Jinja2 template helpers for price visibility"""
    
    @app.template_global()
    def can_see_price():
        return PriceVisibilityService.can_see_price()
    
    @app.template_global()
    def can_see_totals():
        return PriceVisibilityService.can_see_totals()
    
    @app.template_global()
    def can_see_cost_analysis():
        return PriceVisibilityService.can_see_cost_analysis()
    
    @app.template_filter()
    def format_price(price, show_currency=True):
        return Markup(PriceVisibilityService.format_price_display(price, show_currency=show_currency))
    
    @app.template_filter()
    def format_total(total, show_currency=True):
        return Markup(PriceVisibilityService.format_total_display(total, show_currency=show_currency))
    
    @app.template_global()
    def price_column_header():
        return PriceVisibilityService.get_price_column_header()
    
    @app.template_global()
    def total_column_header():
        return PriceVisibilityService.get_total_column_header()
    
    @app.template_global()
    def user_price_role():
        return PriceVisibilityService.get_user_price_role_display()
    
    @app.template_global()
    def price_access_badge():
        return PriceVisibilityService.create_price_access_badge()
    
    @app.template_global()
    def hide_price_fields():
        return PriceVisibilityService.hide_price_fields()