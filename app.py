import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    # Use PostgreSQL database from environment
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///factory.db")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Middleware
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # type: ignore
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Import models
    from models import User, Item, Supplier, PurchaseOrder, SalesOrder, Employee, JobWork, Production, BOM, NotificationSettings, CompanySettings, QualityIssue, QualityControlLog, FactoryExpense
    from models.document import Document, DocumentAccessLog
    from models.uom import UnitOfMeasure, UOMConversion, ItemUOMConversion, UOMConversionLog
    from models.department import Department
    from models.batch import InventoryBatch, BatchMovement
    from models.batch import BatchMovementLedger, BatchConsumptionReport
    from models.settings import Company, UserCompanyAccess, SystemSettings, InventorySettings, AccountingSettings, ProductionSettings, JobWorkSettings
    from models.accounting import Account, AccountGroup, Voucher, VoucherType, JournalEntry, Invoice, InvoiceItem
    from models.accounting import AdvancedAccountingSettings, CostCenter, LedgerMapping, PaymentMethod, InventoryValuation
    from models.grn import GRNWorkflowStatus, VendorInvoice, VendorInvoiceGRNLink

    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.inventory import inventory_bp
    from routes.purchase import purchase_bp
    from routes.sales import sales_bp
    from routes.jobwork import jobwork_bp
    from routes.jobwork_rates import jobwork_rates_bp
    from routes.production import production_bp
    from routes.component_job_cards import component_job_cards_bp
    from routes.hr import hr_bp
    from routes.reports import reports_bp
    from routes.settings import settings_bp
    from routes.admin import admin_bp
    from routes.quality import quality_bp
    from routes.material_inspection import material_inspection
    from routes.expenses import expenses_bp
    from routes.documents import documents_bp
    
    # Import GRN blueprint if available
    try:
        from routes.grn import grn_bp
        from models.grn import GRN, GRNLineItem
    except ImportError:
        grn_bp = None
    
    # Import accounting blueprint
    try:
        from routes.accounting import accounting_bp
        from routes.inventory_valuation import inventory_valuation_bp
        from models.accounting import (AccountGroup, Account, VoucherType, Voucher, 
                                     JournalEntry, Invoice, InvoiceItem, TaxMaster, BankAccount)
        app.register_blueprint(accounting_bp, url_prefix='/accounting')
        app.register_blueprint(inventory_valuation_bp)
    except ImportError as e:
        print(f"Accounting module import error: {e}")
        accounting_bp = None
    from routes.uom import uom_bp
    from routes.batch_tracking import batch_tracking_bp
    from routes.tally import tally_bp
    from routes.packing import packing_bp
    from routes.tally_import import bp as tally_import_bp
    from routes.live_status import live_status_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    
    # Register unified inventory routes
    # Unified inventory system removed - using standard inventory with multi-state view
    app.register_blueprint(purchase_bp, url_prefix='/purchase')
    app.register_blueprint(sales_bp, url_prefix='/sales')
    app.register_blueprint(jobwork_bp, url_prefix='/jobwork')
    app.register_blueprint(jobwork_rates_bp, url_prefix='/jobwork-rates')
    app.register_blueprint(production_bp, url_prefix='/production')
    app.register_blueprint(component_job_cards_bp)
    app.register_blueprint(hr_bp, url_prefix='/hr')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(quality_bp, url_prefix='/quality')
    app.register_blueprint(material_inspection, url_prefix='/inspection')
    app.register_blueprint(expenses_bp, url_prefix='/expenses')
    app.register_blueprint(documents_bp, url_prefix='/documents')
    app.register_blueprint(uom_bp, url_prefix='/uom')
    app.register_blueprint(batch_tracking_bp, url_prefix='/batch-tracking')
    app.register_blueprint(tally_bp, url_prefix='/tally')
    app.register_blueprint(packing_bp, url_prefix='/packing')
    app.register_blueprint(tally_import_bp, url_prefix='/tally')
    app.register_blueprint(live_status_bp)
    from routes.backup import backup_bp
    app.register_blueprint(backup_bp, url_prefix='/backup')
    
    # Import and register advanced settings blueprint
    from routes.settings_advanced import settings_advanced_bp
    app.register_blueprint(settings_advanced_bp)
    
    # Import and register dashboard settings blueprint
    from routes.dashboard_settings import dashboard_settings_bp
    app.register_blueprint(dashboard_settings_bp)
    
    # Register GRN blueprint if available
    if grn_bp:
        app.register_blueprint(grn_bp, url_prefix='/grn')
    

    
    # Register Component Scanning blueprint
    try:
        from routes.component_scanning import component_scanning_bp
        app.register_blueprint(component_scanning_bp, url_prefix='/component-scanning')
    except ImportError as e:
        print(f"Component Scanning module import error: {e}")
    
    # Register GRN Workflow blueprint
    try:
        from routes.grn_workflow import grn_workflow_bp
        app.register_blueprint(grn_workflow_bp, url_prefix='/grn-workflow')
    except ImportError as e:
        print(f"GRN Workflow blueprint import error: {e}")
    
    # Register Multi-Process Job Work blueprint
    from routes.multi_process_jobwork import multi_process_jobwork_bp
    app.register_blueprint(multi_process_jobwork_bp)
    
    # Register Item Types blueprint
    from routes.item_types import item_types_bp
    app.register_blueprint(item_types_bp)
    
    # Register Department blueprint
    from routes.department import department_bp
    app.register_blueprint(department_bp, url_prefix='/departments')
    
    # Register Manufacturing Intelligence blueprint
    # Manufacturing Intelligence integrated into live_status unified dashboard
    # from routes.manufacturing_intelligence import manufacturing_intelligence_bp  
    # app.register_blueprint(manufacturing_intelligence_bp)
    
    # Register PO/SO Accounting blueprints
    from routes.po_accounting import po_accounting_bp
    from routes.so_accounting import so_accounting_bp
    app.register_blueprint(po_accounting_bp, url_prefix='/po_accounting')
    app.register_blueprint(so_accounting_bp, url_prefix='/so_accounting')
    

    
    # Placeholder routes removed during cleanup - modules now have actual routes
    
    # Register notifications blueprint
    from routes.notifications import notifications_bp
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    
    # Register help blueprint
    from routes.help import help_bp
    app.register_blueprint(help_bp, url_prefix='/help')
    
    # Register drawing upload blueprint
    from routes.drawing_upload import drawing_upload_bp
    app.register_blueprint(drawing_upload_bp, url_prefix='/component-scanning')
    
    # Template context processors
    @app.context_processor
    def utility_processor():
        from utils.documents import get_file_icon, format_file_size
        return dict(get_file_icon=get_file_icon, format_file_size=format_file_size)
    
    # Import all models to ensure they are registered with SQLAlchemy
    import models  # Main models (already imported)
    import models.dashboard  # Dashboard preference models
    import models.custom_reports  # Custom report models
    import models.intelligence  # Manufacturing intelligence models
    import models.document  # Document upload models
    import models.notifications  # Notification system models
    import models.visual_scanning  # Component scanning models
    
    # Register CLI commands
    from cli import init_db_command, create_admin_command
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin_command)
    
    # Start notification scheduler in production
    if not app.debug:
        from services.scheduler import notification_scheduler
        notification_scheduler.start()
    
    return app

app = create_app()
