/**
 * Universal Preview System for Factory Management Forms
 * Provides preview functionality across all forms in the application
 */

// Main preview function generator
function createPreviewFunction(formConfig) {
    return function() {
        const form = document.querySelector('form');
        if (!form) {
            console.error('No form found for preview');
            return;
        }
        
        const formData = new FormData(form);
        const previewData = {};
        
        // Extract form data based on configuration
        for (const [key, config] of Object.entries(formConfig.fields)) {
            if (config.type === 'select') {
                const select = form.querySelector(`select[name="${key}"]`);
                if (select && select.selectedIndex >= 0) {
                    previewData[key] = select.options[select.selectedIndex].text;
                }
            } else {
                previewData[key] = formData.get(key) || '';
            }
        }
        
        // Generate preview content
        const previewContent = generatePreviewHTML(previewData, formConfig);
        
        // Show preview modal
        showPreviewModal(previewContent, formConfig.title);
    };
}

// Generate HTML for preview content
function generatePreviewHTML(data, config) {
    let html = '<div class="row">';
    
    const fields = Object.entries(config.fields);
    const leftFields = fields.slice(0, Math.ceil(fields.length / 2));
    const rightFields = fields.slice(Math.ceil(fields.length / 2));
    
    // Left column
    html += '<div class="col-md-6">';
    for (const [key, fieldConfig] of leftFields) {
        html += generateFieldHTML(key, data[key], fieldConfig);
    }
    html += '</div>';
    
    // Right column
    html += '<div class="col-md-6">';
    for (const [key, fieldConfig] of rightFields) {
        html += generateFieldHTML(key, data[key], fieldConfig);
    }
    html += '</div>';
    
    html += '</div>';
    
    // Add calculations if present
    if (config.calculations) {
        html += '<hr><div class="row"><div class="col-12">';
        html += '<h6><i class="fas fa-calculator"></i> Calculations</h6>';
        for (const calc of config.calculations) {
            const value = calculateValue(calc, data);
            html += `<p class="bg-success text-white p-2 rounded"><strong>${calc.label}: ${value}</strong></p>`;
        }
        html += '</div></div>';
    }
    
    return html;
}

// Generate HTML for individual field
function generateFieldHTML(key, value, config) {
    const displayValue = value || config.default || 'Not set';
    const icon = config.icon || 'fa-info';
    
    let formattedValue = displayValue;
    if (config.format === 'currency') {
        formattedValue = `₹${parseFloat(displayValue || 0).toFixed(2)}`;
    } else if (config.format === 'date') {
        formattedValue = displayValue || 'Not set';
    }
    
    return `
        <h6><i class="fas ${icon}"></i> ${config.label}</h6>
        <p class="bg-light p-2 rounded">${formattedValue}</p>
    `;
}

// Calculate derived values
function calculateValue(calc, data) {
    try {
        switch (calc.type) {
            case 'multiply':
                const val1 = parseFloat(data[calc.field1] || 0);
                const val2 = parseFloat(data[calc.field2] || 0);
                return `₹${(val1 * val2).toFixed(2)}`;
            case 'sum':
                const sum = calc.fields.reduce((total, field) => {
                    return total + parseFloat(data[field] || 0);
                }, 0);
                return `₹${sum.toFixed(2)}`;
            default:
                return 'N/A';
        }
    } catch (error) {
        return 'Error calculating';
    }
}

// Show preview modal
function showPreviewModal(content, title) {
    // Create modal if it doesn't exist
    let modal = document.getElementById('universalPreviewModal');
    if (!modal) {
        modal = createPreviewModal();
        document.body.appendChild(modal);
    }
    
    // Update modal content
    document.getElementById('previewModalTitle').textContent = title;
    document.getElementById('previewModalContent').innerHTML = content;
    
    // Show modal
    new bootstrap.Modal(modal).show();
}

// Create preview modal DOM element
function createPreviewModal() {
    const modalHTML = `
        <div class="modal fade" id="universalPreviewModal" tabindex="-1" aria-labelledby="previewModalTitle" aria-hidden="true">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="previewModalTitle">
                            <i class="fas fa-eye"></i> Preview
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div id="previewModalContent">
                            <!-- Preview content will be loaded here -->
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" onclick="document.querySelector('form').submit()">
                            <i class="fas fa-save"></i> Save
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    const modalDiv = document.createElement('div');
    modalDiv.innerHTML = modalHTML;
    return modalDiv.firstElementChild;
}

// Form configurations for different modules
const FORM_CONFIGS = {
    // Purchase Order Preview
    purchase_order: {
        title: 'Purchase Order Preview',
        fields: {
            po_number: { label: 'PO Number', icon: 'fa-hashtag' },
            supplier_name: { label: 'Supplier', icon: 'fa-building', type: 'select' },
            po_date: { label: 'PO Date', icon: 'fa-calendar', format: 'date' },
            expected_delivery: { label: 'Expected Delivery', icon: 'fa-truck', format: 'date' },
            notes: { label: 'Notes', icon: 'fa-sticky-note', default: 'No notes added' }
        }
    },
    
    // Sales Order Preview
    sales_order: {
        title: 'Sales Order Preview',
        fields: {
            so_number: { label: 'SO Number', icon: 'fa-hashtag' },
            customer_name: { label: 'Customer', icon: 'fa-user', type: 'select' },
            so_date: { label: 'SO Date', icon: 'fa-calendar', format: 'date' },
            delivery_date: { label: 'Delivery Date', icon: 'fa-truck', format: 'date' },
            notes: { label: 'Notes', icon: 'fa-sticky-note', default: 'No notes added' }
        }
    },
    
    // Production Preview
    production: {
        title: 'Production Order Preview',
        fields: {
            production_number: { label: 'Production Number', icon: 'fa-hashtag' },
            item_name: { label: 'Item to Produce', icon: 'fa-cogs', type: 'select' },
            planned_quantity: { label: 'Planned Quantity', icon: 'fa-cubes' },
            production_date: { label: 'Production Date', icon: 'fa-calendar', format: 'date' },
            status: { label: 'Status', icon: 'fa-flag', type: 'select' },
            notes: { label: 'Notes', icon: 'fa-sticky-note', default: 'No notes added' }
        }
    },
    
    // Employee Preview
    employee: {
        title: 'Employee Preview',
        fields: {
            employee_code: { label: 'Employee Code', icon: 'fa-id-card' },
            name: { label: 'Name', icon: 'fa-user' },
            department: { label: 'Department', icon: 'fa-building' },
            designation: { label: 'Designation', icon: 'fa-briefcase' },
            phone: { label: 'Phone', icon: 'fa-phone' },
            email: { label: 'Email', icon: 'fa-envelope' },
            salary: { label: 'Salary', icon: 'fa-rupee-sign', format: 'currency' }
        }
    },
    
    // Factory Expense Preview
    factory_expense: {
        title: 'Factory Expense Preview',
        fields: {
            expense_number: { label: 'Expense Number', icon: 'fa-hashtag' },
            category: { label: 'Category', icon: 'fa-tags', type: 'select' },
            description: { label: 'Description', icon: 'fa-info' },
            amount: { label: 'Amount', icon: 'fa-rupee-sign', format: 'currency' },
            expense_date: { label: 'Expense Date', icon: 'fa-calendar', format: 'date' },
            vendor_name: { label: 'Vendor', icon: 'fa-building' }
        }
    },
    
    // Inventory Item Preview
    inventory_item: {
        title: 'Inventory Item Preview',
        fields: {
            code: { label: 'Item Code', icon: 'fa-barcode' },
            name: { label: 'Item Name', icon: 'fa-box' },
            description: { label: 'Description', icon: 'fa-info' },
            unit_of_measure: { label: 'Unit of Measure', icon: 'fa-balance-scale' },
            material_classification: { label: 'Material Classification', icon: 'fa-tag', type: 'select' },
            current_stock: { label: 'Current Stock', icon: 'fa-cubes' },
            unit_price: { label: 'Unit Price', icon: 'fa-rupee-sign', format: 'currency' },
            hsn_code: { label: 'HSN Code', icon: 'fa-code' },
            gst_rate: { label: 'GST Rate', icon: 'fa-percentage' }
        }
    }
};

// Initialize preview system for specific form
function initializePreviewSystem(formType) {
    if (!FORM_CONFIGS[formType]) {
        console.error(`Form configuration not found for: ${formType}`);
        return;
    }
    
    // Create preview function for this form type
    window.previewForm = createPreviewFunction(FORM_CONFIGS[formType]);
    
    console.log(`Preview system initialized for: ${formType}`);
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializePreviewSystem,
        createPreviewFunction,
        FORM_CONFIGS
    };
}