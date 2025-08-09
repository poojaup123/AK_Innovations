# Factory Management System - Flask Application

## Overview
This Flask-based Factory Management System is designed for small to medium manufacturing companies. It provides modular dashboards for managing inventory, purchase orders, sales, HR, job work, production, and reporting. The system aims to streamline operations, enhance material tracking from raw materials to finished goods, and provide real-time manufacturing intelligence. Key capabilities include comprehensive enterprise-wide batch tracking, multi-state inventory tracking, BOM-driven production planning, comprehensive quality control, detailed expense management, and a flexible reporting system with complete material traceability through all manufacturing processes. The business vision is to empower manufacturing SMEs with an affordable, comprehensive, and user-friendly solution to optimize their factory operations, reduce waste, and improve efficiency.

## User Preferences
Preferred communication style: Simple, everyday language.
UI/UX Preferences: Compact, horizontally-arranged dashboard cards with consistent sizing and professional spacing throughout the application. Clean, slim action buttons with minimal text and clear icons for better user experience.

## System Architecture

### UI/UX Decisions
The application features a responsive Bootstrap 5 interface with a dark theme. It employs a dashboard-driven navigation with modular template inheritance, consistent styling across all tables (including sticky headers and responsive scrolling), and intelligent form layouts that dynamically show/hide fields based on user selections. Visual cues like color-coded badges, progress indicators, and intuitive icons are used. A customizable dashboard allows users to reorder and toggle the visibility of modules.

### Technical Implementations
The system is built on a Flask backend using a modern application factory pattern with a professional `app/` package structure (`models/`, `routes/`, `services/`, and `utils/` directories). It uses SQLAlchemy ORM for database interactions, supporting both SQLite for development and PostgreSQL for production. Flask-Login manages authentication with role-based access control (Admin/Staff). Flask-WTF handles form validation and CSRF protection.

Core features include:
- **Multi-State Inventory:** Tracks items in Raw Material, Work in Progress (WIP), Finished Goods, and Scrap states, with process-specific WIP tracking.
- **BOM-Driven Manufacturing:** Supports Bill of Materials for production planning, including material availability checks, automatic labor cost and scrap calculations, and BOM-driven material reservations.
- **Unified Job Work System:** A single, comprehensive form manages all job work types (in-house/outsourced, single/multi-process), integrating with GRN for material receipt and inventory updates.
- **Automated Workflows:** Features automated Purchase Order status progression, automatic inventory updates, and GRN-based material receipt.
- **Data Integrity & Automation:** Implements auto-generation for all unique codes, real-time stock validation, mechanisms to detect and correct data inconsistencies, and comprehensive accounting automation that creates proper journal entries for all financial transactions across modules.
- **Process Management:** Detailed tracking of manufacturing processes within BOMs, including step-by-step workflow, cost calculations, and individual process scrap tracking.
- **Comprehensive Management Modules:** Includes robust systems for Employee Management, Department Management, Supplier/Business Partner Management, and Job Work Rates.
- **Reporting & Analytics:** Features a custom report builder, real-time dashboards for manufacturing intelligence, quality control KPIs, and expense analysis.
- **Integrated Accounting System:** Implements a comprehensive Tally-like accounting system with Chart of Accounts, Journal Entry engine for automatic double-entry bookkeeping, GST-compliant invoice generation, automatic transaction recording, financial reporting (Trial Balance, P&L, Balance Sheet), Bank & Cash management, and comprehensive accounting automation. All financial operations across the entire ERP system are managed through a centralized accounting section with automatic double-entry bookkeeping.
- **Professional Invoice Management:** Complete invoice creation and management system with Tally-style professional layouts, dynamic item management, automatic GST calculations, invoice finalization with accounting integration, and comprehensive print templates. Supports both sales and purchase invoices with proper tax handling and party management.
- **3-Step GRN Workflow:** Enterprise-grade procurement workflow with GRN Clearing Account, GST Input Tax tracking, automated voucher generation, and complete Purchase-to-Payment cycle management. Features intelligent template handling for both Job Work and Purchase Order based GRNs.
- **Authentic Accounting Architecture:** Pure accounting section that remains 100% untouched while all business modules integrate through a dedicated service, using existing authentic account codes without creating duplicates.
- **Advanced Sheet Nesting Optimization:** AI-powered irregular shape nesting using OpenCV, scikit-image, and polygon3 libraries for complex manufacturing scenarios. Features image-based shape detection, multi-angle rotation optimization, scrap calculation, SVG layout generation, and comprehensive efficiency analysis with history tracking.
- **Visual Component Scanning System:** Comprehensive AI-powered component detection from product images using computer vision. Features automatic component identification, inventory matching, dimension estimation, SVG layout generation, and BOM creation from detected components. Includes detection history, processing statistics, and integration with existing inventory management.
- **Technical Drawing Analysis:** CAD file processing system supporting DXF/DWG/STP/STEP formats for precise component extraction. Features geometry-based component detection, annotation processing, dimension extraction, title block information parsing, filename analysis for 3D models, and BOM creation from technical drawings. Includes specialized detection for mechanical fasteners like anchor nuts, bolts, and security components. Complements photo-based detection with engineering precision.
- **Daily Production Entry System:** Comprehensive daily production tracking with quantity recording, quality metrics (good/defective/scrap), shift management, automatic inventory updates based on BOM consumption, and production progress tracking. Features clean, compact action buttons for improved user experience and streamlined workflow integration.

### System Design Choices
- **Application Factory Pattern:** Modern Flask architecture with proper package structure and organized separation of concerns.
- **Domain-Driven Model Organization:** Models are organized by business domain (core, accounting, batch, bom, grn, jobwork) for better maintainability.
- **Modular Blueprint Architecture:** Promotes code organization and scalability by separating features into distinct modules with proper URL prefixes.
- **Unified Data Models:** A single `suppliers` table manages all business partners (suppliers, customers, vendors, transporters) via a `partner_type` field.
- **Transactional Consistency:** Critical operations include comprehensive transaction handling to ensure data integrity.
- **API-First Design:** Many features leverage dedicated API endpoints for real-time data fetching, supporting dynamic frontend interactions.
- **Security:** CSRF protection, input validation, environment-based configuration, and role-based access control are fundamental design choices.
- **Professional Code Structure:** Clean separation of `models/`, `routes/`, `services/`, and `utils/` ensures maintainable, enterprise-grade architecture.

## External Dependencies

### Core Flask Ecosystem
- **Flask-SQLAlchemy**: Database ORM
- **Flask-Login**: User session management
- **Flask-WTF**: Form handling and CSRF protection
- **Werkzeug**: Security utilities and middleware

### Frontend Libraries
- **Bootstrap 5**: UI framework
- **Font Awesome**: Icon library
- **Jinja2**: Template engine
- **Chart.js**: For data visualization

### Communication & Notification Services
- **Twilio**: For SMS and WhatsApp notifications
- **SendGrid**: For email notifications

### PDF Generation
- **WeasyPrint**: For server-side PDF generation from HTML templates

### Optimization Libraries
- **Rectpack**: Python library for 2D rectangle packing optimization.

### Data Export & Integration
- **OpenPyXL (or similar)**: For Excel data export functionality.
- **Tally TDL standards**: For XML export to Tally accounting software.