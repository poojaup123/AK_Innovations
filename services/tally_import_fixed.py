"""
Fixed Tally Import Service - handles UTF-16 encoding and proper data extraction
"""
import os
import re
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class TallyImportService:
    
    @staticmethod  
    def read_xml_file(file_path):
        """Read and clean XML file content - handles UTF-16 Tally encoding"""
        try:
            # First try UTF-16 (common for Tally XML exports)
            try:
                with open(file_path, 'r', encoding='utf-16') as file:
                    content = file.read()
                print(f"✓ Successfully read XML file with UTF-16 encoding ({len(content)} chars)")
            except (UnicodeError, UnicodeDecodeError):
                # Fallback to UTF-8
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
                print(f"✓ Successfully read XML file with UTF-8 encoding ({len(content)} chars)")
                
            return content
            
        except Exception as e:
            print(f"Error reading XML file: {e}")
            return None
    
    @staticmethod
    def extract_data_with_regex(content):
        """Extract groups and ledgers using regex patterns optimized for Tally XML"""
        extracted_data = {
            'groups': [],
            'ledgers': []
        }
        
        if not content:
            return extracted_data
        
        # Extract GROUP tags
        group_pattern = r'<GROUP[^>]*NAME="([^"]+)"[^>]*>.*?</GROUP>'
        group_matches = re.findall(group_pattern, content, re.DOTALL | re.IGNORECASE)
        
        for group_name in group_matches:
            group_data = {
                'name': group_name.strip(),
                'parent': '',
                'nature': 'Assets'  # Default nature
            }
            extracted_data['groups'].append(group_data)
        
        # Extract LEDGER tags
        ledger_pattern = r'<LEDGER[^>]*NAME="([^"]+)"[^>]*>(.*?)</LEDGER>'
        ledger_matches = re.findall(ledger_pattern, content, re.DOTALL | re.IGNORECASE)
        
        for ledger_name, ledger_content in ledger_matches:
            # Extract parent group
            parent_match = re.search(r'<PARENT>([^<]+)</PARENT>', ledger_content, re.IGNORECASE)
            parent = parent_match.group(1).strip() if parent_match else 'Current Assets'
            
            # Extract opening balance  
            balance_match = re.search(r'<OPENINGBALANCE>([^<]+)</OPENINGBALANCE>', ledger_content, re.IGNORECASE)
            opening_balance = balance_match.group(1).strip() if balance_match else '0'
            
            ledger_data = {
                'name': ledger_name.strip(),
                'parent': parent,
                'opening_balance': opening_balance
            }
            extracted_data['ledgers'].append(ledger_data)
        
        print(f"✓ Extracted {len(extracted_data['groups'])} groups and {len(extracted_data['ledgers'])} ledgers")
        return extracted_data
    
    @staticmethod
    def import_account_groups(groups_data):
        """Import account groups from Tally data"""
        from app import db
        from models.accounting import AccountGroup
        
        imported_count = 0
        
        # Standard group types mapping
        group_type_mapping = {
            'Assets': 'assets',
            'Liabilities': 'liabilities', 
            'Income': 'income',
            'Expenses': 'expenses',
            'Capital': 'equity'
        }
        
        for group_data in groups_data:
            try:
                # Check if group already exists
                existing_group = AccountGroup.query.filter_by(name=group_data['name']).first()
                if existing_group:
                    continue
                
                # Determine group type based on common Tally group names
                group_type = 'assets'  # Default
                group_name_lower = group_data['name'].lower()
                
                if any(word in group_name_lower for word in ['asset', 'cash', 'bank', 'debtor', 'stock']):
                    group_type = 'assets'
                elif any(word in group_name_lower for word in ['liability', 'creditor', 'loan', 'payable']):
                    group_type = 'liabilities'
                elif any(word in group_name_lower for word in ['income', 'sales', 'revenue']):
                    group_type = 'income'
                elif any(word in group_name_lower for word in ['expense', 'cost']):
                    group_type = 'expenses'
                elif any(word in group_name_lower for word in ['capital', 'equity', 'reserve']):
                    group_type = 'equity'
                
                # Generate unique code
                base_code = group_data['name'][:10].upper().replace(' ', '_').replace('-', '_')
                unique_code = base_code
                counter = 1
                while AccountGroup.query.filter_by(code=unique_code).first():
                    unique_code = f"{base_code}_{counter}"
                    counter += 1
                
                # Create new group
                new_group = AccountGroup(
                    name=group_data['name'],
                    code=unique_code,
                    group_type=group_type
                )
                
                db.session.add(new_group)
                imported_count += 1
                
            except Exception as e:
                logger.error(f"Error importing group {group_data['name']}: {e}")
                continue
        
        db.session.commit()
        return imported_count
    
    @staticmethod
    def import_accounts(ledgers_data):
        """Import accounts from Tally ledger data"""
        from app import db
        from models.accounting import Account, AccountGroup
        
        imported_count = 0
        
        for ledger_data in ledgers_data:
            try:
                # Check if account already exists
                existing_account = Account.query.filter_by(name=ledger_data['name']).first()
                if existing_account:
                    continue
                
                # Find or create account group
                group = AccountGroup.query.filter_by(name=ledger_data['parent']).first()
                if not group:
                    # Try to find a similar group or create default
                    group = AccountGroup.query.filter_by(name='Current Assets').first()
                    if not group:
                        # Create Current Assets group if it doesn't exist
                        group = AccountGroup(
                            name='Current Assets',
                            code='CUR_ASSETS',
                            group_type='assets'
                        )
                        db.session.add(group)
                        db.session.flush()  # Get the ID
                
                # Parse opening balance
                opening_balance = 0
                try:
                    balance_str = ledger_data['opening_balance'].replace(',', '').replace('₹', '').strip()
                    # Handle negative balances
                    if balance_str.startswith('-') or '(Dr)' in balance_str:
                        opening_balance = -abs(float(re.sub(r'[^\d.]', '', balance_str)))
                    else:
                        opening_balance = float(re.sub(r'[^\d.]', '', balance_str))
                except (ValueError, AttributeError):
                    opening_balance = 0
                
                # Determine account type
                account_type_mapping = {
                    'assets': 'current_asset',
                    'liabilities': 'current_liability',
                    'income': 'income',
                    'expenses': 'expense',
                    'equity': 'equity'
                }
                account_type = account_type_mapping.get(group.group_type, 'current_asset')
                
                # Generate unique code
                base_code = ledger_data['name'][:10].upper().replace(' ', '_').replace('-', '_')
                unique_code = base_code
                counter = 1
                while Account.query.filter_by(code=unique_code).first():
                    unique_code = f"{base_code}_{counter}"
                    counter += 1
                
                # Create new account
                new_account = Account(
                    name=ledger_data['name'],
                    code=unique_code,
                    account_type=account_type,
                    group_id=group.id,
                    opening_balance=Decimal(str(opening_balance)),
                    current_balance=Decimal(str(opening_balance))
                )
                
                db.session.add(new_account)
                imported_count += 1
                
            except Exception as e:
                logger.error(f"Error importing account {ledger_data['name']}: {e}")
                continue
        
        db.session.commit()
        return imported_count
    
    @staticmethod
    def import_full_tally_data(file_path):
        """Import complete Tally Master Data"""
        try:
            result = {
                'success': False,
                'message': '',
                'groups_imported': 0,
                'accounts_imported': 0, 
                'items_imported': 0
            }
            
            # Read XML content with proper encoding
            content = TallyImportService.read_xml_file(file_path)
            if not content:
                result['message'] = 'Failed to read XML file'
                return result
                
            # Extract data using regex
            extracted_data = TallyImportService.extract_data_with_regex(content)
            
            # Import groups first
            if extracted_data['groups']:
                result['groups_imported'] = TallyImportService.import_account_groups(extracted_data['groups'])
            
            # Import accounts
            if extracted_data['ledgers']:
                result['accounts_imported'] = TallyImportService.import_accounts(extracted_data['ledgers'])
            
            # Set success status
            if result['groups_imported'] > 0 or result['accounts_imported'] > 0:
                result['success'] = True
                result['message'] = f'Successfully imported {result["groups_imported"]} groups and {result["accounts_imported"]} accounts'
            else:
                result['message'] = 'No data was imported - check XML file format'
                
            return result
            
        except Exception as e:
            logger.error(f'Tally import error: {e}')
            return {
                'success': False,
                'message': f'Import error: {str(e)}',
                'groups_imported': 0,
                'accounts_imported': 0,
                'items_imported': 0
            }