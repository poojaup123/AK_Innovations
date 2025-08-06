# Factory Management System

A comprehensive Flask-based Factory Management System designed for small to medium manufacturing companies. The application provides modular dashboards for managing various aspects of factory operations including inventory, purchase orders, sales, HR, job work, production, and reporting.

## Features

### Core Modules
- **User Authentication** - Role-based access control (Admin/Staff)
- **Inventory Management** - Stock tracking with unit conversions and low stock alerts
- **Purchase Orders** - Supplier management and procurement tracking
- **Sales Orders** - Customer management and order processing
- **Job Work** - External job work tracking and vendor management
- **Production** - Manufacturing orders with BOM (Bill of Materials) support
- **HR Management** - Employee records and salary tracking
- **Reporting** - Comprehensive reports with CSV export functionality

### Technical Features
- Modern Flask architecture with blueprint modularity
- PostgreSQL database with SQLAlchemy ORM
- Bootstrap 5 dark theme UI
- Role-based access control
- CSRF protection and secure session management
- Responsive design for mobile and desktop
- Unit conversion system for inventory management

## Quick Start

### Prerequisites
- Python 3.11 or higher
- PostgreSQL (or SQLite for development)
- Git

### Installation

1. **Download files**
   ```bash
   # Download all project files to a folder
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements-local.txt
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

5. **Create admin user (first time only)**
   ```bash
   python cli.py create-admin
   ```

6. **Access the application**
   Open your browser to `http://localhost:5000`

## Development with VS Code

### Setup
1. Open the project in VS Code
2. Install recommended extensions (Python, Jinja)
3. Copy `.env.example` to `.env` and configure your settings
4. Use the provided VS Code configuration:
   - **Launch configurations** for debugging
   - **Tasks** for common operations
   - **Settings** optimized for Flask development

### Available VS Code Tasks
- `Ctrl+Shift+P` → "Tasks: Run Task"
  - **Setup Development Environment** - Complete setup
  - **Run Flask App** - Start development server
  - **Create Admin User** - Initialize admin account
  - **Install Dependencies** - Install Python packages

### Debugging
1. Set breakpoints in your Python code
2. Press `F5` or use "Run and Debug" panel
3. Choose "Flask App - Development" configuration

## Database Configuration

### SQLite (Development)
```bash
DATABASE_URL=sqlite:///factory.db
```

### PostgreSQL (Production)
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/factory_db
```

## Project Structure

```
factory-management-system/
├── app.py              # Flask application factory
├── main.py             # Application entry point
├── models.py           # Database models
├── forms.py            # WTForms form definitions
├── config.py           # Configuration settings
├── cli.py              # CLI commands
├── routes/             # Blueprint routes
│   ├── auth.py         # Authentication routes
│   ├── inventory.py    # Inventory management
│   ├── purchase.py     # Purchase orders
│   ├── sales.py        # Sales orders
│   ├── jobwork.py      # Job work tracking
│   ├── production.py   # Production management
│   ├── hr.py           # HR management
│   └── reports.py      # Reporting system
├── templates/          # Jinja2 templates
│   ├── base.html       # Base template
│   ├── auth/           # Authentication templates
│   ├── inventory/      # Inventory templates
│   └── ...             # Other module templates
├── static/             # Static assets
│   ├── css/            # Stylesheets
│   ├── js/             # JavaScript files
│   └── images/         # Images
└── .vscode/            # VS Code configuration
    ├── launch.json     # Debug configurations
    ├── tasks.json      # Task definitions
    └── settings.json   # Editor settings
```

## Usage

### First Time Setup
1. Create an admin user: `python cli.py create-admin`
2. Login with admin credentials
3. Navigate through the dashboard to explore modules
4. Add inventory items, suppliers, customers as needed
5. Create purchase orders, sales orders, and production orders

### Key Workflows
1. **Inventory Management**: Add items → Set reorder levels → Monitor stock
2. **Purchase Process**: Create PO → Receive goods → Update inventory
3. **Sales Process**: Create SO → Process orders → Update stock
4. **Production**: Create production orders → Consume materials → Produce goods
5. **Reporting**: Generate reports → Filter data → Export to CSV

## API Endpoints

The application follows RESTful conventions with these main routes:

- `/auth/` - Authentication (login, logout)
- `/inventory/` - Inventory management
- `/purchase/` - Purchase order management
- `/sales/` - Sales order management
- `/jobwork/` - Job work tracking
- `/production/` - Production management
- `/hr/` - HR management
- `/reports/` - Reporting system

## Security Features

- Password hashing with Werkzeug security
- CSRF protection via Flask-WTF
- Session-based authentication with Flask-Login
- Role-based access control
- Input validation and sanitization
- Secure cookie configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
1. Check the documentation
2. Review the code comments
3. Create an issue in the repository

## Technical Stack

- **Backend**: Flask, SQLAlchemy, Flask-Login, Flask-WTF
- **Database**: PostgreSQL (with SQLite option)
- **Frontend**: Bootstrap 5, Jinja2, JavaScript
- **Deployment**: Gunicorn, Docker support
- **Development**: VS Code configuration included