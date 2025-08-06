"""
Tally Data Import Service
Handles import of Tally XML data into Factory Management System
"""
import xml.etree.ElementTree as ET
import chardet
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class TallyImportService:
    """Service for importing Tally XML data"""
    
    @staticmethod
    def detect_encoding(file_path):
        """Detect file encoding"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                return result['encoding']
        except Exception as e:
            logger.error(f"Error detecting encoding: {e}")
            return 'utf-8'
    
    @staticmethod
    def read_xml_file(file_path):
        """Read XML file with proper encoding detection"""
        # Tally files are commonly UTF-16 encoded
        encodings_to_try = [
            'utf-16',
            'utf-16-le', 
            'utf-16-be',
            TallyImportService.detect_encoding(file_path),
            'utf-8',
            'iso-8859-1',
            'windows-1252'
        ]
        
        for encoding in encodings_to_try:
            if encoding:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        logger.info(f"Successfully read file with encoding: {encoding}")
                        return content
                except Exception as e:
                    logger.debug(f"Failed to read with {encoding}: {e}")
                    continue
        
        raise ValueError("Unable to read XML file with any supported encoding")
    
    @staticmethod
    def parse_tally_xml(file_path):
        """Parse Tally XML file and extract data"""
        try:
            content = TallyImportService.read_xml_file(file_path)
            
            # Clean invalid XML characters that Tally sometimes exports
            import re
            
            # Step 1: Remove BOM and invisible characters
            content = content.replace('\ufeff', '').replace('\ufffe', '')
            
            # Step 2: Handle problematic character references more carefully
            def safe_char_replacement(match):
                try:
                    char_code = int(match.group(1))
                    # Valid XML character ranges: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
                    if char_code in [9, 10, 13] or (32 <= char_code <= 126):
                        return chr(char_code)
                    elif char_code == 4:  # Specific issue in your Tally file
                        return ' '  # Replace with space
                    else:
                        return ''  # Remove invalid characters
                except:
                    return ''
            
            content = re.sub(r'&#([0-9]+);', safe_char_replacement, content)
            
            # Step 3: Remove remaining control characters but preserve XML structure
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
            
            # Step 4: Clean up any malformed XML entities
            content = re.sub(r'&(?![a-zA-Z0-9#][a-zA-Z0-9]*;)', '&amp;', content)
            
            # Parse XML with error recovery
            try:
                root = ET.fromstring(content)
            except ET.ParseError as e:
                # If parsing fails, try alternative approach
                logger.warning(f"XML parsing failed: {e}. Attempting recovery...")
                
                # Try using xml.dom.minidom for more lenient parsing
                from xml.dom import minidom
                try:
                    dom = minidom.parseString(content.encode('utf-8'))
                    # Convert back to ElementTree
                    root = ET.fromstring(dom.toxml().encode('utf-8'))
                except:
                    # Last resort: use regular expressions to extract key data
                    logger.warning("Using regex-based data extraction as fallback")
                    return TallyImportService.extract_data_with_regex(content)
            
            extracted_data = {
                'ledgers': [],
                'groups': [],
                'vouchers': [],
                'items': [],
                'companies': []
            }
            
            # Extract ledgers using XML tree
            for ledger in root.findall('.//LEDGER'):
                name_elem = ledger.find('NAME')
                parent_elem = ledger.find('PARENT')
                balance_elem = ledger.find('OPENINGBALANCE')
                
                if name_elem is not None and name_elem.text and name_elem.text.strip():
                    ledger_data = {
                        'name': name_elem.text.strip(),
                        'parent': parent_elem.text.strip() if parent_elem is not None and parent_elem.text else '',
                        'opening_balance': balance_elem.text.strip() if balance_elem is not None and balance_elem.text else '0',
                        'is_revenue': 'No',
                        'is_deemedpositive': 'No'
                    }
                    extracted_data['ledgers'].append(ledger_data)
            
            # Extract groups using XML tree
            for group in root.findall('.//GROUP'):
                name_elem = group.find('NAME')
                under_elem = group.find('UNDER')
                nature_elem = group.find('NATURE')
                
                if name_elem is not None and name_elem.text and name_elem.text.strip():
                    group_data = {
                        'name': name_elem.text.strip(),
                        'parent': under_elem.text.strip() if under_elem is not None and under_elem.text else '',
                        'nature': nature_elem.text.strip() if nature_elem is not None and nature_elem.text else ''
                    }
                    extracted_data['groups'].append(group_data)
            
            logger.info(f"Extracted {len(extracted_data['ledgers'])} ledgers and {len(extracted_data['groups'])} groups")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error parsing Tally XML: {e}")
            # Fallback to regex extraction
            return TallyImportService.extract_data_with_regex(TallyImportService.read_xml_file(file_path))
    
    @staticmethod
    def extract_data_with_regex(content):
        """Extract Tally data using regex when XML parsing fails"""
        import re
        
        extracted_data = {
            'ledgers': [],
            'groups': [],
            'vouchers': [],
            'items': [],
            'companies': []
        }
        
        # Extract ledger accounts using regex
        ledger_pattern = r'<LEDGER>(.*?)</LEDGER>'
        ledgers = re.findall(ledger_pattern, content, re.DOTALL)
        
        for ledger_text in ledgers:
            name_match = re.search(r'<NAME>(.*?)</NAME>', ledger_text, re.DOTALL)
            parent_match = re.search(r'<PARENT>(.*?)</PARENT>', ledger_text, re.DOTALL)
            balance_match = re.search(r'<OPENINGBALANCE>(.*?)</OPENINGBALANCE>', ledger_text, re.DOTALL)
            
            if name_match and name_match.group(1).strip():
                ledger_data = {
                    'name': name_match.group(1).strip(),
                    'parent': parent_match.group(1).strip() if parent_match else '',
                    'opening_balance': balance_match.group(1).strip() if balance_match else '0',
                    'is_revenue': 'No',
                    'is_deemedpositive': 'No'
                }
                extracted_data['ledgers'].append(ledger_data)
        
        # Extract groups using regex
        group_pattern = r'<GROUP>(.*?)</GROUP>'
        groups = re.findall(group_pattern, content, re.DOTALL)
        
        for group_text in groups:
            name_match = re.search(r'<NAME>(.*?)</NAME>', group_text, re.DOTALL)
            under_match = re.search(r'<UNDER>(.*?)</UNDER>', group_text, re.DOTALL)
            nature_match = re.search(r'<NATURE>(.*?)</NATURE>', group_text, re.DOTALL)
            
            if name_match and name_match.group(1).strip():
                group_data = {
                    'name': name_match.group(1).strip(),
                    'parent': under_match.group(1).strip() if under_match else '',
                    'nature': nature_match.group(1).strip() if nature_match else ''
                }
                extracted_data['groups'].append(group_data)
        
        return extracted_data
    
    @staticmethod
    def import_account_groups(groups_data):
        """Import account groups from Tally data"""
        from app import db
        from models.accounting import AccountGroup
        
        imported_count = 0
        
        # Map Tally group types to our system
        group_type_mapping = {
            'Assets': 'assets',
            'Liabilities': 'liabilities', 
            'Income': 'income',
            'Expenses': 'expenses',
            'Capital Account': 'equity'
        }
        
        for group_data in groups_data:
            try:
                # Check if group already exists
                existing_group = AccountGroup.query.filter_by(name=group_data['name']).first()
                if existing_group:
                    continue
                
                # Determine group type
                group_type = 'assets'  # Default
                for tally_type, our_type in group_type_mapping.items():
                    if tally_type.lower() in group_data['nature'].lower():
                        group_type = our_type
                        break
                
                # Generate unique code for group
                base_code = group_data['name'][:10].upper().replace(' ', '_').replace('.', '_').replace('(', '').replace(')', '').replace('&', 'AND')
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
                    # Create a default group if parent not found
                    group = AccountGroup.query.filter_by(name='Current Assets').first()
                
                if not group:
                    continue
                
                # Determine account type from group
                account_type_mapping = {
                    'assets': 'current_asset',
                    'liabilities': 'current_liability',
                    'income': 'income',
                    'expenses': 'expense',
                    'equity': 'equity'
                }
                account_type = account_type_mapping.get(group.group_type, 'current_asset')
                
                # Parse opening balance
                opening_balance = 0
                try:
                    balance_str = ledger_data['opening_balance'].replace(',', '')
                    opening_balance = float(balance_str) if balance_str else 0
                except:
                    opening_balance = 0
                
                # Generate unique code for account
                base_code = ledger_data['name'][:15].upper().replace(' ', '_').replace('.', '_').replace('(', '').replace(')', '').replace('&', 'AND')
                unique_code = base_code
                counter = 1
                while Account.query.filter_by(code=unique_code).first():
                    unique_code = f"{base_code}_{counter}"
                    counter += 1
                
                # Create new account
                new_account = Account(
                    name=ledger_data['name'],
                    code=unique_code,
                    account_group_id=group.id,
                    account_type=account_type,
                    current_balance=opening_balance
                )
                
                db.session.add(new_account)
                imported_count += 1
                
            except Exception as e:
                logger.error(f"Error importing ledger {ledger_data['name']}: {e}")
                continue
        
        db.session.commit()
        return imported_count
    
    @staticmethod
    def import_items(items_data):
        """Import stock items from Tally data"""
        from app import db
        from models import Item
        
        imported_count = 0
        
        for item_data in items_data:
            try:
                # Check if item already exists
                existing_item = Item.query.filter_by(name=item_data['name']).first()
                if existing_item:
                    continue
                
                # Parse opening values
                opening_qty = 0
                opening_value = 0
                try:
                    opening_qty = float(item_data['opening_balance'].replace(',', '')) if item_data['opening_balance'] else 0
                    opening_value = float(item_data['opening_value'].replace(',', '')) if item_data['opening_value'] else 0
                except:
                    pass
                
                # Calculate unit price
                unit_price = opening_value / opening_qty if opening_qty > 0 else 0
                
                # Create new item
                new_item = Item(
                    name=item_data['name'],
                    description=f"Imported from Tally - {item_data['parent']}",
                    unit_of_measurement=item_data['base_units'] or 'Nos',
                    unit_price=unit_price,
                    current_stock=opening_qty,
                    item_type='raw_material'  # Default type
                )
                
                db.session.add(new_item)
                imported_count += 1
                
            except Exception as e:
                logger.error(f"Error importing item {item_data['name']}: {e}")
                continue
        
        db.session.commit()
        return imported_count
    
    @staticmethod
    def import_full_tally_data(file_path):
        """Import complete Tally data from XML file"""
        try:
            logger.info(f"Starting Tally data import from {file_path}")
            
            # Parse XML data
            extracted_data = TallyImportService.parse_tally_xml(file_path)
            
            results = {
                'groups_imported': 0,
                'accounts_imported': 0,
                'items_imported': 0,
                'success': True,
                'message': ''
            }
            
            # Import in correct order
            if extracted_data['groups']:
                results['groups_imported'] = TallyImportService.import_account_groups(extracted_data['groups'])
            
            if extracted_data['ledgers']:
                results['accounts_imported'] = TallyImportService.import_accounts(extracted_data['ledgers'])
            
            if extracted_data['items']:
                results['items_imported'] = TallyImportService.import_items(extracted_data['items'])
            
            results['message'] = f"Successfully imported {results['groups_imported']} groups, {results['accounts_imported']} accounts, and {results['items_imported']} items from Tally"
            
            logger.info(results['message'])
            return results
            
        except Exception as e:
            logger.error(f"Error in Tally data import: {e}")
            return {
                'groups_imported': 0,
                'accounts_imported': 0,
                'items_imported': 0,
                'success': False,
                'message': f"Import failed: {str(e)}"
            }