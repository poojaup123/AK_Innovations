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
    const phoneInputs = document.querySelectorAll('input[name*="phone"], input[id*="phone"]');
    phoneInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const phone = this.value.trim();
            if (phone && !ValidationUtils.validatePhone(phone)) {
                showFieldError(this, 'Please enter a valid 10-digit mobile number starting with 6-9');
            } else {
                clearFieldError(this);
            }
        });
    });

    // GST number validation
    const gstInputs = document.querySelectorAll('input[name*="gst"], input[id*="gst"]');
    gstInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const gst = this.value.trim();
            if (gst && !ValidationUtils.validateGST(gst)) {
                showFieldError(this, 'Please enter a valid GST number (e.g., 29ABCDE1234F1Z9)');
            } else {
                clearFieldError(this);
            }
        });
    });

    // PAN number validation
    const panInputs = document.querySelectorAll('input[name*="pan"], input[id*="pan"]');
    panInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const pan = this.value.trim();
            if (pan && !ValidationUtils.validatePAN(pan)) {
                showFieldError(this, 'Please enter a valid PAN number (e.g., ABCDE1234F)');
            } else {
                clearFieldError(this);
            }
        });
    });

    // IFSC code validation
    const ifscInputs = document.querySelectorAll('input[name*="ifsc"], input[id*="ifsc"]');
    ifscInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const ifsc = this.value.trim();
            if (ifsc && !ValidationUtils.validateIFSC(ifsc)) {
                showFieldError(this, 'Please enter a valid IFSC code (e.g., SBIN0001234)');
            } else {
                clearFieldError(this);
            }
        });
    });

    // Item code validation
    const codeInputs = document.querySelectorAll('input[name*="code"], input[id*="code"]');
    codeInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const code = this.value.trim();
            if (code && !ValidationUtils.validateItemCode(code)) {
                showFieldError(this, 'Item code can only contain letters, numbers, hyphens, and underscores');
            } else {
                clearFieldError(this);
            }
        });
    });

    // Percentage fields validation
    const percentInputs = document.querySelectorAll('input[name*="rate"], input[name*="percent"], input[id*="rate"], input[id*="percent"]');
    percentInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const value = this.value.trim();
            
            if (value && !ValidationUtils.validatePercentage(value)) {
                showFieldError(this, 'Please enter a valid percentage between 0 and 100');
            } else {
                clearFieldError(this);
            }
        });
    });

    // Required field validation
    const requiredInputs = document.querySelectorAll('input[required], select[required], textarea[required]');
    requiredInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const value = this.value.trim();
            if (!value) {
                const formGroup = this.closest('.form-group');
                const label = formGroup ? formGroup.querySelector('label') : null;
                const fieldName = (label ? label.textContent : (this.getAttribute('placeholder') || 'This field'));
                showFieldError(this, `${fieldName.replace('*', '')} is required`);
            } else {
                clearFieldError(this);
            }
        });
    });

    // Numeric field validation
    const numericInputs = document.querySelectorAll('input[type="number"], input[step]');
    numericInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const value = this.value.trim();
            const min = parseFloat(this.getAttribute('min'));
            const max = parseFloat(this.getAttribute('max'));
            
            if (value && isNaN(parseFloat(value))) {
                showFieldError(this, 'Please enter a valid number');
            } else if (!isNaN(min) && parseFloat(value) < min) {
                showFieldError(this, `Value must be at least ${min}`);
            } else if (!isNaN(max) && parseFloat(value) > max) {
                showFieldError(this, `Value must not exceed ${max}`);
            } else {
                clearFieldError(this);
            }
        });
    });
}

// Show field-specific error
function showFieldError(field, message) {
    clearFieldError(field);
    field.classList.add('is-invalid');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'invalid-feedback d-block';
    errorDiv.textContent = message;
    field.parentNode.insertBefore(errorDiv, field.nextSibling);
}

// Clear field error
function clearFieldError(field) {
    field.classList.remove('is-invalid');
    const errorFeedback = field.parentNode.querySelector('.invalid-feedback');
    if (errorFeedback) {
        errorFeedback.remove();
    }
}

// Enhanced confirmation dialogs
function confirmAction(message, title = 'Confirm Action', confirmText = 'Yes, Continue', cancelText = 'Cancel') {
    return new Promise((resolve) => {
        const modalHtml = `
            <div class="modal fade" id="confirmModal" tabindex="-1" aria-labelledby="confirmModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="confirmModalLabel">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${cancelText}</button>
                            <button type="button" class="btn btn-danger" id="confirmActionBtn">${confirmText}</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existingModal = document.getElementById('confirmModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        modal.show();
        
        // Handle confirm action
        document.getElementById('confirmActionBtn').addEventListener('click', function() {
            modal.hide();
            resolve(true);
        });
        
        // Handle modal hidden event
        document.getElementById('confirmModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
            resolve(false);
        });
    });
}

// Confirm delete handler
function setupConfirmDelete() {
    document.addEventListener('click', function(e) {
        if (e.target.hasAttribute('data-confirm-delete')) {
            e.preventDefault();
            const deleteUrl = e.target.getAttribute('href') || e.target.getAttribute('data-href');
            const itemName = e.target.getAttribute('data-item-name') || 'this item';
            
            confirmAction(
                `Are you sure you want to delete ${itemName}? This action cannot be undone.`,
                'Confirm Delete',
                'Yes, Delete',
                'Cancel'
            ).then(confirmed => {
                if (confirmed) {
                    if (e.target.closest('form')) {
                        e.target.closest('form').submit();
                    } else {
                        window.location.href = deleteUrl;
                    }
                }
            });
        }
    });
}

// Confirm form submission
function setupConfirmSubmit() {
    document.addEventListener('click', function(e) {
        if (e.target.hasAttribute('data-confirm-submit')) {
            e.preventDefault();
            const form = e.target.closest('form');
            const message = e.target.getAttribute('data-confirm-message') || 'Are you sure you want to submit this form?';
            
            confirmAction(message).then(confirmed => {
                if (confirmed && form) {
                    form.submit();
                }
            });
        }
    });
}

// Enhanced toast notifications
function showToast(message, type = 'info', duration = 5000) {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        document.body.insertAdjacentHTML('beforeend', '<div id="toast-container" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
        toastContainer = document.getElementById('toast-container');
    }

    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: duration });
    
    toast.show();
    
    // Remove toast after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

// Input enhancement utilities
function setupInputEnhancements() {
    // Phone number formatting
    const phoneInputs = document.querySelectorAll('input[name*="phone"], input[id*="phone"]');
    phoneInputs.forEach(input => {
        input.addEventListener('input', function() {
            let value = this.value.replace(/\D/g, '');
            if (value.length > 10) {
                this.value = value.substring(0, 10);
            }
        });
    });

    // Auto-uppercase for GST and PAN
    const uppercaseInputs = document.querySelectorAll('input[name*="gst"], input[name*="pan"], input[id*="gst"], input[id*="pan"]');
    uppercaseInputs.forEach(input => {
        input.addEventListener('input', function() {
            this.value = this.value.toUpperCase();
        });
    });

    // Auto-uppercase for IFSC
    const ifscInputs = document.querySelectorAll('input[name*="ifsc"], input[id*="ifsc"]');
    ifscInputs.forEach(input => {
        input.addEventListener('input', function() {
            this.value = this.value.toUpperCase();
        });
    });

    // Prevent negative numbers for positive-only fields
    const positiveInputs = document.querySelectorAll('input[type="number"][min="0"]');
    positiveInputs.forEach(input => {
        input.addEventListener('keydown', function(e) {
            if (e.key === '-' || e.key === 'e' || e.key === 'E') {
                e.preventDefault();
            }
        });
    });

    // Auto-calculate totals for quantity/price fields
    const calculationInputs = document.querySelectorAll('input[name*="quantity"], input[name*="price"], input[name*="rate"]');
    calculationInputs.forEach(input => {
        input.addEventListener('blur', function() {
            calculateRowTotal(this);
        });
    });
}

// Row total calculation
function calculateRowTotal(element) {
    const row = element.closest('tr') || element.closest('.row') || element.closest('.form-row');
    if (!row) return;

    const qtyField = row.querySelector('input[name*="quantity"]');
    const priceField = row.querySelector('input[name*="price"], input[name*="rate"]');
    const totalField = row.querySelector('input[name*="total"], .total-display');

    if (qtyField && priceField && totalField) {
        const qty = parseFloat(qtyField.value) || 0;
        const price = parseFloat(priceField.value) || 0;
        const total = (qty * price).toFixed(2);
        
        if (totalField.tagName === 'INPUT') {
            totalField.value = total;
        } else {
            totalField.textContent = total;
        }
    }
}

// Initialize all validation and enhancement features
document.addEventListener('DOMContentLoaded', function() {
    setupRealTimeValidation();
    setupConfirmDelete();
    setupConfirmSubmit();
    setupInputEnhancements();
    
    // Convert server-side flash messages to toasts
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        const message = alert.textContent.trim();
        let type = 'info';
        
        if (alert.classList.contains('alert-success')) type = 'success';
        else if (alert.classList.contains('alert-danger')) type = 'danger';
        else if (alert.classList.contains('alert-warning')) type = 'warning';
        
        if (message) {
            showToast(message, type);
        }
        
        // Hide original alert
        alert.style.display = 'none';
    });
});

// Global validation function for forms
function validateForm(formElement) {
    let isValid = true;
    const requiredFields = formElement.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            showFieldError(field, 'This field is required');
            isValid = false;
        } else {
            clearFieldError(field);
        }
    });
    
    return isValid;
}

// Export utilities for global use
window.ValidationUtils = ValidationUtils;
window.showToast = showToast;
window.confirmAction = confirmAction;
window.validateForm = validateForm;
window.showFieldError = showFieldError;
window.clearFieldError = clearFieldError;