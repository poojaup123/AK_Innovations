"""
Enhanced notification models with comprehensive event tracking and admin panel support
"""
from datetime import datetime
from app import db

class NotificationSettings(db.Model):
    """Enhanced notification settings with admin panel controls"""
    __tablename__ = 'notification_settings'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Channel Settings
    email_enabled = db.Column(db.Boolean, default=True)
    sms_enabled = db.Column(db.Boolean, default=True)
    whatsapp_enabled = db.Column(db.Boolean, default=True)
    in_app_enabled = db.Column(db.Boolean, default=True)
    
    # Service Configuration
    sendgrid_api_key = db.Column(db.String(255))
    sender_email = db.Column(db.String(120), default='noreply@akfactory.com')
    sender_name = db.Column(db.String(100), default='AK Innovations Factory')
    
    twilio_account_sid = db.Column(db.String(255))
    twilio_auth_token = db.Column(db.String(255))
    twilio_phone_number = db.Column(db.String(20))
    
    # Event-Specific Settings
    po_notifications = db.Column(db.Boolean, default=True)
    grn_notifications = db.Column(db.Boolean, default=True)
    job_work_notifications = db.Column(db.Boolean, default=True)
    production_notifications = db.Column(db.Boolean, default=True)
    sales_notifications = db.Column(db.Boolean, default=True)
    accounts_notifications = db.Column(db.Boolean, default=True)
    inventory_notifications = db.Column(db.Boolean, default=True)
    hr_notifications = db.Column(db.Boolean, default=True)
    
    # Specific Event Controls
    po_vendor_notification = db.Column(db.Boolean, default=True)
    grn_rejection_notification = db.Column(db.Boolean, default=True)
    job_work_vendor_notification = db.Column(db.Boolean, default=True)
    customer_invoice_notification = db.Column(db.Boolean, default=True)
    payment_overdue_notification = db.Column(db.Boolean, default=True)
    low_stock_notifications = db.Column(db.Boolean, default=True)
    scrap_threshold_notifications = db.Column(db.Boolean, default=True)
    
    # HR Event Controls
    salary_payment_notifications = db.Column(db.Boolean, default=True)
    advance_payment_notifications = db.Column(db.Boolean, default=True)
    employee_joining_notifications = db.Column(db.Boolean, default=True)
    employee_leaving_notifications = db.Column(db.Boolean, default=True)
    attendance_notifications = db.Column(db.Boolean, default=True)
    leave_application_notifications = db.Column(db.Boolean, default=True)
    performance_review_notifications = db.Column(db.Boolean, default=True)
    overtime_notifications = db.Column(db.Boolean, default=True)
    
    # Language and Formatting
    default_language = db.Column(db.String(5), default='EN')  # EN, HIN
    time_format = db.Column(db.String(10), default='24H')  # 12H, 24H
    notification_summary = db.Column(db.String(20), default='immediate')  # immediate, daily, weekly
    
    # Admin Recipients
    admin_email = db.Column(db.String(120))
    admin_phone = db.Column(db.String(20))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_settings(cls):
        """Get notification settings, create default if none exist"""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

class NotificationRecipient(db.Model):
    """Enhanced notification recipients with role-based assignments"""
    __tablename__ = 'notification_recipients'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    
    # Role and Department
    role = db.Column(db.String(50))  # purchase_head, sales_team, qc_head, etc.
    department = db.Column(db.String(50))  # Purchase, Sales, Production, QC, Accounts
    
    # Notification Preferences
    notification_types = db.Column(db.String(100))  # email,sms,whatsapp,in_app
    event_types = db.Column(db.Text)  # Comma-separated event types
    
    # Specific Event Subscriptions
    po_events = db.Column(db.Boolean, default=False)
    grn_events = db.Column(db.Boolean, default=False)
    job_work_events = db.Column(db.Boolean, default=False)
    production_events = db.Column(db.Boolean, default=False)
    sales_events = db.Column(db.Boolean, default=False)
    accounts_events = db.Column(db.Boolean, default=False)
    inventory_events = db.Column(db.Boolean, default=False)
    hr_events = db.Column(db.Boolean, default=False)
    
    # Schedule Settings
    immediate_notifications = db.Column(db.Boolean, default=True)
    daily_summary = db.Column(db.Boolean, default=False)
    weekly_summary = db.Column(db.Boolean, default=False)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_external = db.Column(db.Boolean, default=False)  # For vendors/customers
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class NotificationLog(db.Model):
    """Enhanced notification log with detailed tracking"""
    __tablename__ = 'notification_logs'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic Info
    type = db.Column(db.String(20), nullable=False)  # email, sms, whatsapp, in_app
    recipient = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255))
    message = db.Column(db.Text)
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, sent, delivered, failed
    success = db.Column(db.Boolean, nullable=False)
    response = db.Column(db.Text)
    error_message = db.Column(db.Text)
    
    # Event Context
    event_type = db.Column(db.String(50))  # po_created, grn_rejection, etc.
    event_id = db.Column(db.Integer)  # ID of the related record
    module = db.Column(db.String(30))  # purchase, sales, production, etc.
    
    # Delivery Tracking
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    delivered_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)
    
    # Service Provider Info
    service_provider = db.Column(db.String(50))  # sendgrid, twilio
    provider_message_id = db.Column(db.String(100))
    
    # Recipient Info
    recipient_name = db.Column(db.String(100))
    recipient_role = db.Column(db.String(50))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class NotificationTemplate(db.Model):
    """Customizable notification templates"""
    __tablename__ = 'notification_templates'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Template Identity
    template_code = db.Column(db.String(50), unique=True, nullable=False)
    template_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Category
    module = db.Column(db.String(30), nullable=False)  # purchase, sales, production
    event_type = db.Column(db.String(50), nullable=False)  # created, approved, rejected
    
    # Template Content
    subject_template = db.Column(db.String(255), nullable=False)
    message_template = db.Column(db.Text, nullable=False)
    html_template = db.Column(db.Text)
    
    # Template Variables (JSON format)
    available_variables = db.Column(db.Text)  # JSON list of available variables
    
    # Language and Localization
    language = db.Column(db.String(5), default='EN')
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_system_template = db.Column(db.Boolean, default=True)  # System vs User templates
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class InAppNotification(db.Model):
    """In-app notification system (bell icon alerts)"""
    __tablename__ = 'in_app_notifications'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Target User
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Notification Content
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(30), default='info')  # info, warning, error, success
    
    # Context
    module = db.Column(db.String(30))  # purchase, sales, production
    event_type = db.Column(db.String(50))
    reference_id = db.Column(db.Integer)  # ID of related record
    reference_type = db.Column(db.String(50))  # purchase_order, sales_order, etc.
    
    # URL for action
    action_url = db.Column(db.String(255))
    action_text = db.Column(db.String(50))  # "View Order", "Approve", etc.
    
    # Status
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    
    # Priority
    priority = db.Column(db.String(10), default='normal')  # low, normal, high, urgent
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # Optional expiry
    
    # Relationships
    user = db.relationship('User', backref='in_app_notifications')

class NotificationSchedule(db.Model):
    """Scheduled notifications and recurring alerts"""
    __tablename__ = 'notification_schedules'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Schedule Info
    schedule_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Event Configuration
    event_type = db.Column(db.String(50), nullable=False)
    trigger_condition = db.Column(db.Text)  # JSON condition
    
    # Recipients
    recipient_roles = db.Column(db.Text)  # JSON list of roles
    recipient_ids = db.Column(db.Text)  # JSON list of specific recipient IDs
    
    # Schedule Configuration
    schedule_type = db.Column(db.String(20), default='immediate')  # immediate, scheduled, recurring
    cron_expression = db.Column(db.String(50))  # For recurring schedules
    next_run_at = db.Column(db.DateTime)
    
    # Template
    template_id = db.Column(db.Integer, db.ForeignKey('notification_templates.id'))
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    last_run_at = db.Column(db.DateTime)
    last_run_status = db.Column(db.String(20))
    
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    template = db.relationship('NotificationTemplate', backref='schedules')
    creator = db.relationship('User', backref='notification_schedules')

class NotificationDeliveryStatus(db.Model):
    """Track delivery status for external notifications"""
    __tablename__ = 'notification_delivery_status'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Reference to original notification
    notification_log_id = db.Column(db.Integer, db.ForeignKey('notification_logs.id'))
    
    # Service Provider Tracking
    provider_message_id = db.Column(db.String(100))
    provider_status = db.Column(db.String(50))
    provider_response = db.Column(db.Text)
    
    # Status Updates
    status = db.Column(db.String(20))  # queued, sent, delivered, failed, bounced
    status_updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Delivery Details
    delivered_at = db.Column(db.DateTime)
    bounce_reason = db.Column(db.Text)
    failure_reason = db.Column(db.Text)
    
    # Webhook Data
    webhook_data = db.Column(db.Text)  # JSON webhook response
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    notification_log = db.relationship('NotificationLog', backref='delivery_status')