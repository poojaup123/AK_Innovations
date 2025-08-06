import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
from app import db
from models import User

@click.command()
@with_appcontext
def init_db_command():
    """Clear existing data and create new tables."""
    db.create_all()
    
    # Initialize default data
    from models.uom import UnitOfMeasure
    from models import ItemType, Employee, NotificationSettings
    from models.department import Department
    from models.settings import Company, SystemSettings
    from models.accounting import AccountGroup, Account, VoucherType
    
    # Initialize all default data
    UnitOfMeasure.ensure_default_units()
    ItemType.get_default_types()
    Employee.create_default_employee()
    NotificationSettings.create_default_settings()
    Department.create_default_departments()
    Company.create_default_company()
    SystemSettings.create_defaults()
    
    # Initialize accounting data
    AccountGroup.create_default_groups()
    Account.create_default_accounts()
    VoucherType.create_default_types()
    
    click.echo('Initialized the database with default data.')

@click.command()
@click.option('--username', prompt=True, help='Admin username')
@click.option('--email', prompt=True, help='Admin email')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
@with_appcontext
def create_admin_command(username, email, password):
    """Create an admin user."""
    if User.query.filter_by(username=username).first():
        click.echo(f'User {username} already exists.')
        return
    
    admin = User(
        username=username,
        email=email,
        role='admin'
    )
    admin.set_password(password)
    
    db.session.add(admin)
    db.session.commit()
    click.echo(f'Admin user {username} created successfully.')
