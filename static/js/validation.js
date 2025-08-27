/**
 * Enhanced Validation and User Experience JavaScript
 * Provides real-time validation, confirmation dialogs, and better UX
 */

// Custom validation utilities
const ValidationUtils = {
    // Phone number validation for Indian numbers
    validatePhone: function(phone) {
        const phonePattern = /^[6-9]\d{9}$/;
        return phonePattern.test(phone.replace(/\D/g, ''));
    },

    // GST number validation
    validateGST: function(gst) {
        const gstPattern = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
        return gstPattern.test(gst.toUpperCase());
    },

    // PAN number validation
    validatePAN: function(pan) {
        const panPattern = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;
        return panPattern.test(pan.toUpperCase());
    },

    // IFSC code validation
    validateIFSC: function(ifsc) {
        const ifscPattern = /^[A-Z]{4}0[A-Z0-9]{6}$/;
        return ifscPattern.test(ifsc.toUpperCase());
    },

    // Item code validation (alphanumeric, no special chars except hyphen/underscore)
    validateItemCode: function(code) {
        const codePattern = /^[A-Za-z0-9_-]+$/;
        return codePattern.test(code);
    },

    // Percentage validation
    validatePercentage: function(value, min = 0, max = 100) {
        const num = parseFloat(value);
        return !isNaN(num) && num >= min && num <= max;
    }
};

// Real-time validation feedback
function setupRealTimeValidation() {
    // Phone number validation
    $('input[name*="phone"], input[id*="phone"]').on('blur', function() {
        const phone = $(this).val().trim();
        if (phone && !ValidationUtils.validatePhone(phone)) {
            showFieldError($(this), 'Please enter a valid 10-digit mobile number starting with 6-9');
        } else {
            clearFieldError($(this));
        }
    });

    // GST number validation
    $('input[name*="gst"], input[id*="gst"]').on('blur', function() {
        const gst = $(this).val().trim();
        if (gst && !ValidationUtils.validateGST(gst)) {
            showFieldError($(this), 'Please enter a valid GST number (e.g., 29ABCDE1234F1Z9)');
        } else {
            clearFieldError($(this));
        }
    });

    // PAN number validation
    $('input[name*="pan"], input[id*="pan"]').on('blur', function() {
        const pan = $(this).val().trim();
        if (pan && !ValidationUtils.validatePAN(pan)) {
            showFieldError($(this), 'Please enter a valid PAN number (e.g., ABCDE1234F)');
        } else {
            clearFieldError($(this));
        }
    });

    // IFSC code validation
    $('input[name*="ifsc"], input[id*="ifsc"]').on('blur', function() {
        const ifsc = $(this).val().trim();
        if (ifsc && !ValidationUtils.validateIFSC(ifsc)) {
            showFieldError($(this), 'Please enter a valid IFSC code (e.g., SBIN0001234)');
        } else {
            clearFieldError($(this));
        }
    });

    // Item code validation
    $('input[name*="code"], input[id*="code"]').on('blur', function() {
        const code = $(this).val().trim();
        if (code && !ValidationUtils.validateItemCode(code)) {
            showFieldError($(this), 'Item code can only contain letters, numbers, hyphens, and underscores');
        } else {
            clearFieldError($(this));
        }
    });

    // Percentage fields validation
    $('input[name*="rate"], input[name*="percent"], input[id*="rate"], input[id*="percent"]').on('blur', function() {
        const value = $(this).val().trim();
        const fieldName = $(this).attr('name') || $(this).attr('id');
        
        if (value && !ValidationUtils.validatePercentage(value)) {
            showFieldError($(this), 'Please enter a valid percentage between 0 and 100');
        } else {
            clearFieldError($(this));
        }
    });

    // Required field validation
    $('input[required], select[required], textarea[required]').on('blur', function() {
        const value = $(this).val().trim();
        if (!value) {
            const fieldName = $(this).closest('.form-group').find('label').text() || $(this).attr('placeholder') || 'This field';
            showFieldError($(this), `${fieldName.replace('*', '')} is required`);
        } else {
            clearFieldError($(this));
        }
    });

    // Numeric field validation
    $('input[type="number"], input[step]').on('blur', function() {
        const value = $(this).val().trim();
        const min = parseFloat($(this).attr('min'));
        const max = parseFloat($(this).attr('max'));
        
        if (value && isNaN(parseFloat(value))) {
            showFieldError($(this), 'Please enter a valid number');
        } else if (!isNaN(min) && parseFloat(value) < min) {
            showFieldError($(this), `Value must be at least ${min}`);
        } else if (!isNaN(max) && parseFloat(value) > max) {
            showFieldError($(this), `Value must not exceed ${max}`);
        } else {
            clearFieldError($(this));
        }
    });
}

// Show field-specific error
function showFieldError(field, message) {
    clearFieldError(field);
    field.addClass('is-invalid');
    field.after(`<div class="invalid-feedback d-block">${message}</div>`);
}

// Clear field error
function clearFieldError(field) {
    field.removeClass('is-invalid');
    field.next('.invalid-feedback').remove();
}

// Enhanced confirmation dialogs
function confirmAction(message, title = 'Confirm Action', confirmText = 'Yes, Continue', cancelText = 'Cancel') {
    return new Promise((resolve) => {
        const modalHtml = `
            <div class="modal fade" id="confirmModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header border-0">
                            <h5 class="modal-title text-warning">
                                <i class="fas fa-exclamation-triangle me-2"></i>${title}
                            </h5>
                        </div>
                        <div class="modal-body">
                            <p class="mb-0">${message}</p>
                        </div>
                        <div class="modal-footer border-0">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${cancelText}</button>
                            <button type="button" class="btn btn-danger" id="confirmActionBtn">${confirmText}</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if any
        $('#confirmModal').remove();
        
        // Add modal to page
        $('body').append(modalHtml);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        modal.show();
        
        // Handle confirm
        $('#confirmActionBtn').on('click', function() {
            modal.hide();
            resolve(true);
        });
        
        // Handle cancel/dismiss
        $('#confirmModal').on('hidden.bs.modal', function() {
            $(this).remove();
            resolve(false);
        });
    });
}

// Setup delete confirmation for all delete buttons
function setupDeleteConfirmations() {
    $(document).on('click', '[data-confirm-delete]', function(e) {
        e.preventDefault();
        const deleteUrl = $(this).attr('href') || $(this).data('href');
        const itemName = $(this).data('item-name') || 'this item';
        
        confirmAction(
            `Are you sure you want to delete ${itemName}? This action cannot be undone.`,
            'Delete Confirmation',
            'Yes, Delete',
            'Cancel'
        ).then((confirmed) => {
            if (confirmed) {
                if ($(this).closest('form').length) {
                    $(this).closest('form').submit();
                } else {
                    window.location.href = deleteUrl;
                }
            }
        });
    });
}

// Setup form submission confirmations
function setupFormConfirmations() {
    $(document).on('click', '[data-confirm-submit]', function(e) {
        e.preventDefault();
        const form = $(this).closest('form');
        const message = $(this).data('confirm-message') || 'Are you sure you want to submit this form?';
        
        confirmAction(message).then((confirmed) => {
            if (confirmed) {
                form.submit();
            }
        });
    });
}

// Enhanced toast notifications
function showToast(message, type = 'info', duration = 5000) {
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="${duration}">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${getToastIcon(type)} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    let toastContainer = $('#toast-container');
    if (!toastContainer.length) {
        $('body').append('<div id="toast-container" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
        toastContainer = $('#toast-container');
    }
    
    toastContainer.append(toastHtml);
    const toastElement = toastContainer.find('.toast').last();
    const toast = new bootstrap.Toast(toastElement[0]);
    toast.show();
    
    // Remove toast element after it's hidden
    toastElement.on('hidden.bs.toast', function() {
        $(this).remove();
    });
}

function getToastIcon(type) {
    const icons = {
        'success': 'check-circle',
        'danger': 'exclamation-triangle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle',
        'primary': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

// Form enhancement utilities
function enhanceFormUX() {
    // Auto-format phone numbers
    $('input[name*="phone"], input[id*="phone"]').on('input', function() {
        let value = $(this).val().replace(/\D/g, '');
        if (value.length <= 10) {
            $(this).val(value);
        }
    });

    // Auto-uppercase GST and PAN fields
    $('input[name*="gst"], input[name*="pan"], input[id*="gst"], input[id*="pan"]').on('input', function() {
        $(this).val($(this).val().toUpperCase());
    });

    // Auto-format IFSC codes
    $('input[name*="ifsc"], input[id*="ifsc"]').on('input', function() {
        $(this).val($(this).val().toUpperCase());
    });

    // Prevent negative values in number inputs where min=0
    $('input[type="number"][min="0"]').on('keydown', function(e) {
        if (e.key === '-' || e.key === 'e' || e.key === 'E') {
            e.preventDefault();
        }
    });

    // Auto-calculate totals if needed
    $('input[name*="quantity"], input[name*="price"], input[name*="rate"]').on('blur', function() {
        calculateRowTotal($(this));
    });
}

function calculateRowTotal(element) {
    const row = element.closest('tr, .form-row, .row');
    const qty = parseFloat(row.find('input[name*="quantity"]').val()) || 0;
    const price = parseFloat(row.find('input[name*="price"], input[name*="rate"]').val()) || 0;
    const totalField = row.find('input[name*="total"], .total-display');
    
    if (totalField.length && (qty > 0 || price > 0)) {
        const total = qty * price;
        if (totalField.is('input')) {
            totalField.val(total.toFixed(2));
        } else {
            totalField.text('₹' + total.toFixed(2));
        }
    }
}

// Initialize all validation and UX enhancements
$(document).ready(function() {
    setupRealTimeValidation();
    setupDeleteConfirmations();
    setupFormConfirmations();
    enhanceFormUX();
    
    // Convert flash messages to toasts
    $('.alert').each(function() {
        const message = $(this).text().trim();
        let type = 'info';
        
        if ($(this).hasClass('alert-success')) type = 'success';
        else if ($(this).hasClass('alert-danger')) type = 'danger';
        else if ($(this).hasClass('alert-warning')) type = 'warning';
        
        if (message) {
            showToast(message, type);
        }
        
        $(this).hide();
    });
    
    console.log('✅ Enhanced validation and UX features loaded');
});