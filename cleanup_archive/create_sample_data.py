#!/usr/bin/env python3
"""
Comprehensive Sample Data Creation Script for Factory Management System
Creates realistic sample data for all modules and tests integration
"""

from app import app, db
from models import *
from models.uom import *
from models.document import *
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from decimal import Decimal
import random

def create_sample_data():
    """Create comprehensive sample data for all modules"""
    
    with app.app_context():
        print("🚀 Creating comprehensive sample data...")
        
        # 1. Create Admin User
        print("\n📋 Creating admin user...")
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@akinnovations.com',
                role='admin'
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
        
        # 2. Create Staff Users
        print("👥 Creating staff users...")
        staff_users = [
            {'username': 'manager1', 'email': 'manager@akinnovations.com', 'role': 'admin'},
            {'username': 'staff1', 'email': 'staff1@akinnovations.com', 'role': 'staff'},
            {'username': 'staff2', 'email': 'staff2@akinnovations.com', 'role': 'staff'},
        ]
        
        for user_data in staff_users:
            user = User.query.filter_by(username=user_data['username']).first()
            if not user:
                user = User(**user_data)
                user.set_password('password123')
                db.session.add(user)
        
        db.session.commit()
        
        # 3. Create Company Settings
        print("🏢 Setting up company information...")
        settings = CompanySettings.get_settings()
        settings.company_name = "AK Innovations Pvt Ltd"
        settings.address_line1 = "Industrial Area, Phase-2"
        settings.address_line2 = "Manufacturing Hub"
        settings.city = "Mumbai"
        settings.state = "Maharashtra"
        settings.pin_code = "400001"
        settings.phone = "+91-9876543210"
        settings.gst_number = "27ABCDE1234F1Z5"
        settings.arn_number = "AA271234567890A"
        db.session.commit()
        
        # 4. Create Comprehensive Suppliers (Business Partners)
        print("🤝 Creating business partners...")
        suppliers_data = [
            {
                'name': 'Steel Suppliers Ltd',
                'contact_person': 'Rajesh Kumar',
                'phone': '+91-9876543211',
                'email': 'rajesh@steelsuppliers.com',
                'gst_number': '27STEEL1234F1Z5',
                'address': 'Steel Market, Andheri East',
                'city': 'Mumbai',
                'state': 'Maharashtra',
                'pin_code': '400069',
                'partner_type': 'supplier'
            },
            {
                'name': 'Mumbai Engineering Works',
                'contact_person': 'Priya Sharma',
                'phone': '+91-9876543212',
                'email': 'priya@mumbaieng.com',
                'gst_number': '27MUMENG1234F1Z5',
                'address': 'Engineering Complex, Kurla',
                'city': 'Mumbai',
                'state': 'Maharashtra',
                'pin_code': '400070',
                'partner_type': 'both'
            },
            {
                'name': 'Industrial Components Co',
                'contact_person': 'Amit Patel',
                'phone': '+91-9876543213',
                'email': 'amit@indcomp.com',
                'gst_number': '27INDCOM1234F1Z5',
                'address': 'Component Market, Bandra',
                'city': 'Mumbai',
                'state': 'Maharashtra',
                'pin_code': '400050',
                'partner_type': 'supplier'
            },
            {
                'name': 'Precision Tools Ltd',
                'contact_person': 'Sunita Desai',
                'phone': '+91-9876543214',
                'email': 'sunita@precisiontools.com',
                'gst_number': '27PREC1234F1Z5',
                'partner_type': 'customer'
            },
            {
                'name': 'Manufacturing Solutions Inc',
                'contact_person': 'Vikram Singh',
                'phone': '+91-9876543215',
                'email': 'vikram@mansol.com',
                'gst_number': '27MANSOL1234F1Z5',
                'partner_type': 'customer'
            }
        ]
        
        for supplier_data in suppliers_data:
            supplier = Supplier.query.filter_by(name=supplier_data['name']).first()
            if not supplier:
                supplier = Supplier(**supplier_data)
                db.session.add(supplier)
        
        db.session.commit()
        
        # 5. Create Items with UOM Integration
        print("📦 Creating inventory items...")
        items_data = [
            {
                'name': 'Steel Rod 12mm',
                'description': 'High grade steel rods for construction',
                'unit_of_measure': 'Kg',
                'hsn_code': '72142000',
                'gst_rate': 18.0,
                'current_stock': 500.0,
                'minimum_stock': 100.0,
                'unit_price': 55.0,
                'item_type': 'material'
            },
            {
                'name': 'Metal Bracket L-Type',
                'description': 'L-shaped metal brackets for mounting',
                'unit_of_measure': 'Pcs',
                'hsn_code': '73181500',
                'gst_rate': 18.0,
                'current_stock': 200.0,
                'minimum_stock': 50.0,
                'unit_price': 25.0,
                'item_type': 'material'
            },
            {
                'name': 'Castor Wheel 50mm',
                'description': 'Heavy duty castor wheels',
                'unit_of_measure': 'Pcs',
                'hsn_code': '87089900',
                'gst_rate': 18.0,
                'current_stock': 150.0,
                'minimum_stock': 30.0,
                'unit_price': 45.0,
                'item_type': 'product'
            },
            {
                'name': 'Industrial Paint',
                'description': 'High quality industrial paint',
                'unit_of_measure': 'L',
                'hsn_code': '32081010',
                'gst_rate': 18.0,
                'current_stock': 80.0,
                'minimum_stock': 20.0,
                'unit_price': 150.0,
                'item_type': 'material'
            },
            {
                'name': 'Electrical Cable 2.5mm',
                'description': 'Copper electrical cables',
                'unit_of_measure': 'M',
                'hsn_code': '85444290',
                'gst_rate': 18.0,
                'current_stock': 1000.0,
                'minimum_stock': 200.0,
                'unit_price': 12.0,
                'item_type': 'material'
            },
            {
                'name': 'Ball Bearing 608',
                'description': 'Standard ball bearings',
                'unit_of_measure': 'Pcs',
                'hsn_code': '84821000',
                'gst_rate': 18.0,
                'current_stock': 300.0,
                'minimum_stock': 75.0,
                'unit_price': 35.0,
                'item_type': 'material'
            }
        ]
        
        for item_data in items_data:
            # Generate unique item code
            item_count = Item.query.count() + 1
            item_data['code'] = f"ITEM-{item_count:04d}"
            
            item = Item.query.filter_by(name=item_data['name']).first()
            if not item:
                item = Item(**item_data)
                db.session.add(item)
        
        db.session.commit()
        
        # 6. Create Employees for HR Testing
        print("👨‍💼 Creating employees...")
        employees_data = [
            {
                'name': 'Ramesh Gupta',
                'designation': 'Production Manager',
                'department': 'Production',
                'email': 'ramesh@akinnovations.com',
                'phone': '+91-9876543220',
                'salary': 45000.0,
                'hire_date': datetime.now() - timedelta(days=365),
                'is_active': True
            },
            {
                'name': 'Kavita Singh',
                'designation': 'Quality Inspector',
                'department': 'Quality Control',
                'email': 'kavita@akinnovations.com',
                'phone': '+91-9876543221',
                'salary': 35000.0,
                'hire_date': datetime.now() - timedelta(days=200),
                'is_active': True
            },
            {
                'name': 'Suresh Patil',
                'designation': 'Machine Operator',
                'department': 'Production',
                'email': 'suresh@akinnovations.com',
                'phone': '+91-9876543222',
                'salary': 28000.0,
                'hire_date': datetime.now() - timedelta(days=180),
                'is_active': True
            },
            {
                'name': 'Meera Joshi',
                'designation': 'Inventory Clerk',
                'department': 'Inventory',
                'email': 'meera@akinnovations.com',
                'phone': '+91-9876543223',
                'salary': 25000.0,
                'hire_date': datetime.now() - timedelta(days=150),
                'is_active': True
            }
        ]
        
        for emp_data in employees_data:
            # Generate unique employee code
            emp_count = Employee.query.count() + 1
            emp_data['employee_code'] = f"EMP-{emp_count:04d}"
            
            employee = Employee.query.filter_by(name=emp_data['name']).first()
            if not employee:
                employee = Employee(**emp_data)
                db.session.add(employee)
        
        db.session.commit()
        
        # 7. Create Bill of Materials (BOM)
        print("🔧 Creating Bill of Materials...")
        # Get items for BOM
        castor_wheel = Item.query.filter_by(name='Castor Wheel 50mm').first()
        metal_bracket = Item.query.filter_by(name='Metal Bracket L-Type').first()
        ball_bearing = Item.query.filter_by(name='Ball Bearing 608').first()
        steel_rod = Item.query.filter_by(name='Steel Rod 12mm').first()
        
        if castor_wheel and metal_bracket and ball_bearing and steel_rod:
            # BOM for Castor Wheel
            castor_bom = BOM.query.filter_by(product_id=castor_wheel.id).first()
            if not castor_bom:
                castor_bom = BOM(
                    product_id=castor_wheel.id,
                    version='1.0',
                    description='Standard castor wheel assembly',
                    total_cost=42.94,
                    is_active=True
                )
                db.session.add(castor_bom)
                db.session.commit()
                
                # BOM Items
                bom_items = [
                    {
                        'bom_id': castor_bom.id,
                        'material_id': metal_bracket.id,
                        'quantity': 1.0,
                        'unit_cost': 25.0,
                        'total_cost': 25.0
                    },
                    {
                        'bom_id': castor_bom.id,
                        'material_id': ball_bearing.id,
                        'quantity': 2.0,
                        'unit_cost': 35.0,
                        'total_cost': 70.0
                    },
                    {
                        'bom_id': castor_bom.id,
                        'material_id': steel_rod.id,
                        'quantity': 0.1,
                        'unit_cost': 55.0,
                        'total_cost': 5.5
                    }
                ]
                
                for bom_item_data in bom_items:
                    bom_item = BOMItem(**bom_item_data)
                    db.session.add(bom_item)
        
        db.session.commit()
        
        # 8. Create Purchase Orders with Different Statuses
        print("📋 Creating purchase orders...")
        suppliers = Supplier.query.filter(Supplier.partner_type.in_(['supplier', 'both'])).all()
        items = Item.query.all()
        
        po_statuses = ['draft', 'pending_approval', 'approved', 'sent', 'received', 'completed']
        
        for i in range(6):
            supplier = random.choice(suppliers)
            status = po_statuses[i]
            
            # Generate PO number
            po_count = PurchaseOrder.query.count() + 1
            current_year = datetime.now().year
            po_number = f"PO-{current_year}-{po_count:04d}"
            
            po = PurchaseOrder(
                po_number=po_number,
                supplier_id=supplier.id,
                po_date=datetime.now() - timedelta(days=random.randint(1, 30)),
                delivery_date=datetime.now() + timedelta(days=random.randint(7, 21)),
                status=status,
                notes=f'Sample Purchase Order {i+1} for {supplier.name}',
                total_amount=0.0,
                created_by=admin_user.id
            )
            db.session.add(po)
            db.session.commit()
            
            # Add PO Items
            selected_items = random.sample(items, random.randint(2, 4))
            total_amount = 0.0
            
            for item in selected_items:
                quantity = random.randint(10, 100)
                rate = item.unit_price * random.uniform(0.9, 1.1)  # Slight price variation
                amount = quantity * rate
                total_amount += amount
                
                po_item = PurchaseOrderItem(
                    purchase_order_id=po.id,
                    item_id=item.id,
                    quantity=quantity,
                    unit_price=rate,
                    total_price=amount,
                    hsn_code=item.hsn_code,
                    gst_rate=item.gst_rate,
                    specification=f'Standard {item.name} as per specifications'
                )
                db.session.add(po_item)
            
            po.total_amount = total_amount
            db.session.commit()
        
        # 9. Create Sales Orders
        print("💰 Creating sales orders...")
        customers = Supplier.query.filter(Supplier.partner_type.in_(['customer', 'both'])).all()
        
        so_statuses = ['draft', 'confirmed', 'in_production', 'ready', 'dispatched']
        
        for i in range(5):
            customer = random.choice(customers)
            status = so_statuses[i]
            
            # Generate SO number
            so_count = SalesOrder.query.count() + 1
            current_year = datetime.now().year
            so_number = f"SO-{current_year}-{so_count:04d}"
            
            so = SalesOrder(
                so_number=so_number,
                customer_id=customer.id,
                order_date=datetime.now() - timedelta(days=random.randint(1, 20)),
                delivery_date=datetime.now() + timedelta(days=random.randint(10, 30)),
                status=status,
                notes=f'Sample Sales Order {i+1} for {customer.name}',
                total_amount=0.0,
                created_by=admin_user.id
            )
            db.session.add(so)
            db.session.commit()
            
            # Add SO Items
            selected_items = random.sample(items[:3], random.randint(1, 3))  # Focus on products
            total_amount = 0.0
            
            for item in selected_items:
                quantity = random.randint(5, 50)
                rate = item.unit_price * random.uniform(1.2, 1.5)  # Sales markup
                amount = quantity * rate
                total_amount += amount
                
                so_item = SalesOrderItem(
                    sales_order_id=so.id,
                    item_id=item.id,
                    quantity=quantity,
                    unit_price=rate,
                    total_price=amount,
                    hsn_code=item.hsn_code,
                    gst_rate=item.gst_rate,
                    specification=f'Customer specification for {item.name}'
                )
                db.session.add(so_item)
            
            so.total_amount = total_amount
            db.session.commit()
        
        # 10. Create Production Orders
        print("🏭 Creating production orders...")
        production_statuses = ['planned', 'in_progress', 'completed', 'on_hold']
        
        for i in range(4):
            status = production_statuses[i]
            
            # Generate Production number
            prod_count = Production.query.count() + 1
            current_year = datetime.now().year
            prod_number = f"PROD-{current_year}-{prod_count:04d}"
            
            production = Production(
                production_number=prod_number,
                item_id=castor_wheel.id if castor_wheel else items[0].id,
                planned_quantity=random.randint(50, 200),
                production_date=datetime.now() + timedelta(days=random.randint(1, 14)),
                status=status,
                notes=f'Sample Production Order {i+1}',
                created_by=admin_user.id
            )
            
            if status in ['completed', 'in_progress']:
                production.produced_quantity = random.randint(30, production.planned_quantity)
                production.good_quantity = int(production.produced_quantity * 0.95)
                production.damaged_quantity = production.produced_quantity - production.good_quantity
            
            db.session.add(production)
        
        db.session.commit()
        
        # 11. Create Job Work Orders
        print("🔧 Creating job work orders...")
        jobwork_statuses = ['planned', 'materials_sent', 'in_progress', 'completed']
        
        for i in range(4):
            status = jobwork_statuses[i]
            
            # Generate Job Work number
            job_count = JobWork.query.count() + 1
            current_year = datetime.now().year
            job_number = f"JOB-{current_year}-{job_count:04d}"
            
            vendor = random.choice(suppliers)
            selected_item = random.choice(items)
            
            jobwork = JobWork(
                job_number=job_number,
                vendor_id=vendor.id,
                item_id=selected_item.id,
                description=f'Job work for {selected_item.name}',
                quantity_sent=random.randint(20, 100),
                rate_per_unit=random.randint(10, 50),
                expected_delivery=datetime.now() + timedelta(days=random.randint(7, 21)),
                status=status,
                notes=f'Sample Job Work {i+1}',
                created_by=admin_user.id
            )
            
            if status in ['completed', 'in_progress']:
                jobwork.quantity_received = random.randint(15, jobwork.quantity_sent)
            
            db.session.add(jobwork)
        
        db.session.commit()
        
        # 12. Create Quality Issues
        print("🛡️ Creating quality issues...")
        quality_severities = ['low', 'medium', 'high', 'critical']
        quality_statuses = ['open', 'investigating', 'resolved', 'closed']
        issue_types = ['damage', 'malfunction', 'defect', 'contamination', 'dimension_error']
        
        for i in range(8):
            # Generate Quality Issue number
            qi_count = QualityIssue.query.count() + 1
            current_year = datetime.now().year
            qi_number = f"QI-{current_year}-{qi_count:04d}"
            
            selected_item = random.choice(items)
            
            quality_issue = QualityIssue(
                issue_number=qi_number,
                item_id=selected_item.id,
                issue_type=random.choice(issue_types),
                severity=random.choice(quality_severities),
                description=f'Quality issue with {selected_item.name} - sample issue {i+1}',
                quantity_affected=random.randint(5, 50),
                cost_impact=random.randint(1000, 10000),
                status=random.choice(quality_statuses),
                reported_by=admin_user.id,
                created_at=datetime.now() - timedelta(days=random.randint(1, 30))
            )
            
            if quality_issue.status in ['resolved', 'closed']:
                quality_issue.resolved_date = datetime.now() - timedelta(days=random.randint(1, 15))
                quality_issue.resolution = f'Sample resolution for issue {i+1}'
            
            db.session.add(quality_issue)
        
        db.session.commit()
        
        # 13. Create Material Inspections
        print("🔍 Creating material inspections...")
        pos = PurchaseOrder.query.all()
        
        for po in pos[:3]:  # Create inspections for first 3 POs
            for po_item in po.items[:2]:  # Inspect first 2 items from each PO
                # Generate Inspection number
                inspect_count = MaterialInspection.query.count() + 1
                current_year = datetime.now().year
                inspect_number = f"INSPECT-{current_year}-{inspect_count:04d}"
                
                inspected_qty = int(po_item.quantity * 0.8)  # Inspect 80% of received
                passed_qty = int(inspected_qty * 0.95)  # 95% pass rate
                damaged_qty = inspected_qty - passed_qty
                
                inspection = MaterialInspection(
                    inspection_number=inspect_number,
                    purchase_order_id=po.id,
                    item_id=po_item.item_id,
                    inspected_quantity=inspected_qty,
                    passed_quantity=passed_qty,
                    damaged_quantity=damaged_qty,
                    inspector_notes=f'Sample inspection for {po_item.item.name}',
                    inspection_date=datetime.now() - timedelta(days=random.randint(1, 10)),
                    inspector_id=admin_user.id
                )
                db.session.add(inspection)
        
        db.session.commit()
        
        # 14. Create Factory Expenses
        print("💸 Creating factory expenses...")
        expense_categories = ['utilities', 'maintenance', 'materials', 'transport', 'overhead']
        expense_statuses = ['pending', 'approved', 'paid']
        
        for i in range(10):
            # Generate Expense number
            exp_count = FactoryExpense.query.count() + 1
            current_year = datetime.now().year
            exp_number = f"EXP-{current_year}-{exp_count:04d}"
            
            base_amount = random.randint(5000, 50000)
            tax_amount = base_amount * 0.18  # 18% GST
            
            expense = FactoryExpense(
                expense_number=exp_number,
                category=random.choice(expense_categories),
                description=f'Sample factory expense {i+1}',
                base_amount=base_amount,
                tax_amount=tax_amount,
                total_amount=base_amount + tax_amount,
                expense_date=datetime.now() - timedelta(days=random.randint(1, 30)),
                status=random.choice(expense_statuses),
                created_by=admin_user.id
            )
            
            if random.choice([True, False]):  # Some expenses have vendors
                expense.vendor_id = random.choice(suppliers).id
                expense.invoice_number = f'INV-{random.randint(1000, 9999)}'
            
            db.session.add(expense)
        
        db.session.commit()
        
        # 15. Create Employee Salary Records
        print("💰 Creating salary records...")
        employees = Employee.query.all()
        
        for employee in employees:
            # Generate Salary number
            sal_count = SalaryRecord.query.count() + 1
            current_year = datetime.now().year
            sal_number = f"SAL-{current_year}-{sal_count:04d}"
            
            basic_salary = employee.salary
            overtime_hours = random.randint(0, 20)
            overtime_amount = overtime_hours * 200
            bonus = random.randint(0, 5000)
            deductions = random.randint(1000, 3000)
            
            salary_record = SalaryRecord(
                salary_number=sal_number,
                employee_id=employee.id,
                month=datetime.now().month,
                year=datetime.now().year,
                basic_salary=basic_salary,
                overtime_hours=overtime_hours,
                overtime_amount=overtime_amount,
                bonus=bonus,
                deductions=deductions,
                gross_salary=basic_salary + overtime_amount + bonus,
                net_salary=basic_salary + overtime_amount + bonus - deductions,
                status='approved',
                created_by=admin_user.id
            )
            db.session.add(salary_record)
        
        db.session.commit()
        
        print("\n✅ Sample data creation completed successfully!")
        print("\n📊 Summary of created data:")
        print(f"👤 Users: {User.query.count()}")
        print(f"🤝 Business Partners: {Supplier.query.count()}")
        print(f"📦 Items: {Item.query.count()}")
        print(f"👨‍💼 Employees: {Employee.query.count()}")
        print(f"📋 Purchase Orders: {PurchaseOrder.query.count()}")
        print(f"💰 Sales Orders: {SalesOrder.query.count()}")
        print(f"🏭 Production Orders: {Production.query.count()}")
        print(f"🔧 Job Work Orders: {JobWork.query.count()}")
        print(f"🛡️ Quality Issues: {QualityIssue.query.count()}")
        print(f"🔍 Material Inspections: {MaterialInspection.query.count()}")
        print(f"💸 Factory Expenses: {FactoryExpense.query.count()}")
        print(f"💰 Salary Records: {SalaryRecord.query.count()}")
        print(f"🔧 BOMs: {BOM.query.count()}")
        print(f"📏 UOM Units: {UnitOfMeasure.query.count()}")
        print(f"🔄 UOM Conversions: {UOMConversion.query.count()}")

if __name__ == '__main__':
    create_sample_data()