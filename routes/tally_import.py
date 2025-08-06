"""
Tally Import Routes
Handles Tally XML data import functionality
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from services.tally_import_service import TallyImportService
import os

bp = Blueprint('tally_import', __name__, url_prefix='/tally')

@bp.route('/')
@login_required
def import_dashboard():
    """Tally import dashboard"""
    return render_template('tally/import_dashboard.html')

@bp.route('/import-master-data')
@login_required
def import_master_data_direct():
    """Direct Master Data import - one-click solution"""
    try:
        # Use the fixed import service with proper Flask context
        from services.tally_import_fixed import TallyImportService
        
        # Import the complete Tally data directly
        result = TallyImportService.import_full_tally_data('attached_assets/Master_1754420946221.xml')
        
        if result['success']:
            message = f"✅ MASTER DATA IMPORT SUCCESSFUL!\n\n"
            message += f"• Account Groups Imported: {result['groups_imported']}\n"
            message += f"• Ledger Accounts Imported: {result['accounts_imported']}\n" 
            message += f"• Stock Items Imported: {result['items_imported']}\n\n"
            message += "Your authentic Tally data is now integrated with the Factory Management System!"
            
            flash(message, 'success')
        else:
            flash(f"Import failed: {result['message']}", 'error')
            
    except Exception as e:
        flash(f"Import error: {str(e)}", 'error')
    
    return redirect(url_for('tally_import.import_dashboard'))

@bp.route('/upload', methods=['POST'])
@login_required
def upload_tally_file():
    """Handle Tally XML file upload and import"""
    try:
        if 'tally_file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('tally_import.import_dashboard'))
        
        file = request.files['tally_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('tally_import.import_dashboard'))
        
        if file and file.filename.lower().endswith('.xml'):
            # Save uploaded file temporarily
            upload_folder = 'temp_uploads'
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, file.filename)
            file.save(file_path)
            
            # Process the file
            results = TallyImportService.import_full_tally_data(file_path)
            
            # Clean up temp file
            os.remove(file_path)
            
            if results['success']:
                flash(results['message'], 'success')
            else:
                flash(f"Import failed: {results['message']}", 'error')
        else:
            flash('Please upload a valid XML file', 'error')
    
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
    
    return redirect(url_for('tally_import.import_dashboard'))

@bp.route('/process-existing/<filename>')
@login_required
def process_existing_file(filename):
    """Process existing Tally XML file"""
    try:
        file_path = os.path.join('attached_assets', filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': 'File not found'
            })
        
        # Process the file with better error handling
        try:
            results = TallyImportService.import_full_tally_data(file_path)
            return jsonify(results)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'XML parsing error: {str(e)}. The Tally XML file may contain invalid characters. Try exporting fresh data from Tally.'
            })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error processing file: {str(e)}'
        })

@bp.route('/preview/<filename>')
@login_required
def preview_tally_file(filename):
    """Preview Tally XML file content"""
    try:
        file_path = os.path.join('attached_assets', filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': 'File not found'
            })
        
        # Read and parse the file for preview
        extracted_data = TallyImportService.parse_tally_xml(file_path)
        
        preview_data = {
            'success': True,
            'summary': {
                'groups_count': len(extracted_data['groups']),
                'ledgers_count': len(extracted_data['ledgers']),
                'items_count': len(extracted_data['items']),
                'vouchers_count': len(extracted_data['vouchers'])
            },
            'sample_data': {
                'groups': extracted_data['groups'][:5],  # First 5 groups
                'ledgers': extracted_data['ledgers'][:5],  # First 5 ledgers
                'items': extracted_data['items'][:5]  # First 5 items
            }
        }
        
        return jsonify(preview_data)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error previewing file: {str(e)}'
        })