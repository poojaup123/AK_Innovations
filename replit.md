# Factory Management System - Flask Application

## Overview
This Flask-based Factory Management System is designed for small to medium manufacturing companies. It provides modular dashboards for managing inventory, purchase orders, sales, HR, job work, production, and reporting. The system aims to streamline operations, enhance material tracking from raw materials to finished goods, and provide real-time manufacturing intelligence. Key capabilities include comprehensive enterprise-wide batch tracking, multi-state inventory tracking, BOM-driven production planning, comprehensive quality control, detailed expense management, and a flexible reporting system with complete material traceability through all manufacturing processes. The business vision is to empower manufacturing SMEs with an affordable, comprehensive, and user-friendly solution to optimize their factory operations, reduce waste, and improve efficiency.

## User Preferences
Preferred communication style: Simple, everyday language.
UI/UX Preferences: Compact, horizontally-arranged dashboard cards with consistent sizing and professional spacing throughout the application. Job Card Summary should appear on the right side of forms, not at the bottom.
Enhanced User Experience: Implemented comprehensive user-friendly features including global search, breadcrumb navigation, recently viewed sections, floating quick action buttons, auto-save functionality, toast notifications, keyboard shortcuts, and beautiful gradient stat cards for improved usability and modern interface design.

## Recent Changes (August 2025)
**Module Reorganization**: Restructured the application modules for better logical organization:
- **Production Section**: Now contains BOM Management, Production Orders, Manufacturing Intelligence, and Daily Production Status
- **Job Work Section**: Reorganized to include Job Work Orders, Job Cards Management, Multi-Process Job Work, Team Management, and Job Work GRN
- **Navigation Updates**: Updated sidebar navigation to reflect the new module organization with job cards properly grouped under job work
- **URL Structure**: Updated blueprint URL prefixes to organize job card routes under `/jobwork/` path structure

This reorganization provides clearer separation between:
- Production = Manufacturing your own products using BOMs
- Job Work = Work done by teams/vendors including detailed job cards and outsourcing

## System Architecture

### Performance Optimizations
The system is optimized for Tally-like seamless performance through systematic optimizations including database indexes, query optimization, intelligent caching with smart invalidation, real-time performance monitoring, optimized data loading, and ultra-fast batch queries via direct SQL.

### UI/UX Decisions
The application features a responsive Bootstrap 5 interface with a modern design. It employs a dashboard-driven navigation with modular template inheritance, consistent styling across all tables, and intelligent form layouts. Visual cues like color-coded badges, progress indicators, and intuitive icons are used. A customizable dashboard allows users to reorder and toggle module visibility. A professional modal system prevents black overlay issues.

Enhanced User Experience Features (August 2025):
- Global search functionality with keyboard shortcuts (Ctrl+K)
- Breadcrumb navigation showing current location path
- Recently viewed section with smart memory management
- Floating quick action buttons for common tasks (Add Item, Create Job Work, Purchase Orders)
- Beautiful gradient stat cards with icons replacing plain cards
- Auto-save functionality with visual feedback indicators
- Toast notification system for user actions
- Enhanced loading states with progress indicators
- Improved sidebar with hover effects and click protection
- Keyboard shortcuts for power users (Ctrl+H for home, Ctrl+N for new item)

### Technical Implementations
The system is built on a Flask backend using an application factory pattern with a professional `app/` package structure. It uses SQLAlchemy ORM for database interactions, supporting SQLite for development and PostgreSQL for production. Flask-Login manages authentication with role-based access control, and Flask-WTF handles form validation and CSRF protection.

Core features include:
- **Multi-State Inventory:** Tracks items in Raw Material, Work in Progress (WIP), Finished Goods, and Scrap states.
- **BOM-Driven Manufacturing:** Supports Bill of Materials for production planning, material availability checks, automatic labor cost and scrap calculations, and BOM-driven material reservations.
- **Unified Job Work System:** Manages all job work types (in-house/outsourced, single/multi-process), integrating with GRN.
- **Automated Workflows:** Features automated Purchase Order status progression, automatic inventory updates, and GRN-based material receipt.
- **Data Integrity & Automation:** Implements auto-generation for unique codes, real-time stock validation, data inconsistency correction, and comprehensive accounting automation.
- **Process Management:** Detailed tracking of manufacturing processes within BOMs, including step-by-step workflow, cost calculations, and individual process scrap tracking.
- **Comprehensive Management Modules:** Includes systems for Employee, Department, Supplier/Business Partner, and Job Work Rates management.
- **Reporting & Analytics:** Features a custom report builder, real-time dashboards for manufacturing intelligence, quality control KPIs, and expense analysis.
- **Integrated Accounting System:** Implements a comprehensive Tally-like accounting system with Chart of Accounts, Journal Entry engine for automatic double-entry bookkeeping, GST-compliant invoice generation, and financial reporting.
- **Professional Invoice Management:** Complete invoice creation and management system with Tally-style professional layouts, dynamic item management, and automatic GST calculations.
- **3-Step GRN Workflow:** Enterprise-grade procurement workflow with GRN Clearing Account, GST Input Tax tracking, and automated voucher generation.
- **Authentic Accounting Architecture:** Pure accounting section that remains untouched, with business modules integrating through a dedicated service.
- **Advanced Sheet Nesting Optimization:** AI-powered irregular shape nesting using OpenCV, scikit-image, and polygon3 for complex manufacturing scenarios.
- **Visual Component Scanning System:** AI-powered component detection from product images using computer vision, including automatic identification, inventory matching, and BOM creation.
- **Technical Drawing Analysis:** CAD file processing system supporting DXF/DWG/STP/STEP formats for precise component extraction and BOM creation.
- **Job Card-Based Production Tracking:** Comprehensive job card system for breaking down production orders into sub-components and process steps, featuring sequential material-flow manufacturing logic and outsourced quantity tracking.
- **Job Card-Job Work Integration System:** Seamless integration between Job Cards and Job Work for dynamic workflow transitions between in-house and outsourced manufacturing processes.
- **Enhanced Process-Level Scrap Tracking System:** Comprehensive scrap tracking at the manufacturing process level with intelligent material source logic and accurate UOM conversion.
- **BOM Output Quantity Synchronization System:** Automatic synchronization of BOM output quantity with the final manufacturing process output quantity.
- **Unified Batch Tracking Integration:** Complete integration of batch tracking across all modules for comprehensive traceability from supplier to customer.
- **Enhanced Job Work Creation Interface:** Modern 4-step wizard interface with real-time Job Card and GRN integration, smart material selection with automatic stock validation, and comprehensive batch tracking capabilities.

### System Design Choices
- **Application Factory Pattern:** Modern Flask architecture with proper package structure and organized separation of concerns.
- **Domain-Driven Model Organization:** Models are organized by business domain for better maintainability.
- **Modular Blueprint Architecture:** Promotes code organization and scalability by separating features into distinct modules.
- **Unified Data Models:** A single `suppliers` table manages all business partners via a `partner_type` field.
- **Transactional Consistency:** Critical operations include comprehensive transaction handling to ensure data integrity.
- **API-First Design:** Many features leverage dedicated API endpoints for real-time data fetching.
- **Security:** CSRF protection, input validation, environment-based configuration, and role-based access control are fundamental.
- **Professional Code Structure:** Clean separation of `models/`, `routes/`, `services/`, and `utils/` ensures maintainable architecture.

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
- **OpenCV**: For image processing in AI features.
- **scikit-image**: For image processing in AI features.
- **polygon3**: For polygon manipulation in AI features.

### Data Export & Integration
- **OpenPyXL (or similar)**: For Excel data export functionality.
- **Tally TDL standards**: For XML export to Tally accounting software.