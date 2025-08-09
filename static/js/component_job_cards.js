/**
 * Component Job Cards JavaScript Module
 * Handles all client-side interactions for the Component Job Cards system
 */

// Global functions for modals and interactions
function updateProgress(cardId) {
    const modal = new bootstrap.Modal(document.getElementById('progressModal'));
    document.getElementById('progressCardId').value = cardId;
    
    // Reset form
    document.getElementById('progressQuantity').value = '';
    document.getElementById('progressNotes').value = '';
    
    modal.show();
}

function assignCard(cardId) {
    const modal = new bootstrap.Modal(document.getElementById('assignModal'));
    document.getElementById('assignCardId').value = cardId;
    
    // Reset form
    document.getElementById('assignWorker').value = '';
    document.getElementById('assignVendor').value = '';
    document.getElementById('assignDepartment').value = '';
    
    modal.show();
}

function holdCard(cardId) {
    const modal = new bootstrap.Modal(document.getElementById('holdModal'));
    document.getElementById('holdCardId').value = cardId;
    
    // Reset form
    document.getElementById('holdReason').value = '';
    document.getElementById('holdNotes').value = '';
    
    modal.show();
}

function resumeCard(cardId) {
    const modal = new bootstrap.Modal(document.getElementById('resumeModal'));
    document.getElementById('resumeCardId').value = cardId;
    
    // Reset form
    document.getElementById('resumeNotes').value = '';
    
    modal.show();
}

function completeCard(cardId) {
    const modal = new bootstrap.Modal(document.getElementById('completeModal'));
    document.getElementById('completeCardId').value = cardId;
    
    // Reset form
    document.getElementById('completeActualQuantity').value = '';
    document.getElementById('completeScrapQuantity').value = '0';
    document.getElementById('completeQualityNotes').value = '';
    
    modal.show();
}

// Form submission functions
function submitProgress() {
    const cardId = document.getElementById('progressCardId').value;
    const quantity = document.getElementById('progressQuantity').value;
    const notes = document.getElementById('progressNotes').value;
    
    if (!quantity || quantity <= 0) {
        showAlert('Please enter a valid quantity', 'warning');
        return;
    }
    
    showLoading(true);
    
    fetch(`/job-cards/update-progress/${cardId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            quantity_consumed: parseFloat(quantity),
            notes: notes
        })
    })
    .then(response => response.json())
    .then(data => {
        showLoading(false);
        if (data.success) {
            showAlert(data.message, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        showLoading(false);
        console.error('Error:', error);
        showAlert('Error updating progress', 'danger');
    });
}

function submitAssignment() {
    const cardId = document.getElementById('assignCardId').value;
    const workerId = document.getElementById('assignWorker').value;
    const vendorId = document.getElementById('assignVendor').value;
    const department = document.getElementById('assignDepartment').value;
    
    if (!workerId && !vendorId) {
        showAlert('Please select either a worker or vendor', 'warning');
        return;
    }
    
    showLoading(true);
    
    fetch(`/job-cards/assign/${cardId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            worker_id: workerId || null,
            vendor_id: vendorId || null,
            department: department
        })
    })
    .then(response => response.json())
    .then(data => {
        showLoading(false);
        if (data.success) {
            showAlert(data.message, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        showLoading(false);
        console.error('Error:', error);
        showAlert('Error assigning job card', 'danger');
    });
}

function submitHold() {
    const cardId = document.getElementById('holdCardId').value;
    const reason = document.getElementById('holdReason').value;
    const notes = document.getElementById('holdNotes').value;
    
    if (!reason) {
        showAlert('Please select a reason for holding the job card', 'warning');
        return;
    }
    
    showLoading(true);
    
    fetch(`/job-cards/hold/${cardId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            reason: reason,
            notes: notes
        })
    })
    .then(response => response.json())
    .then(data => {
        showLoading(false);
        if (data.success) {
            showAlert(data.message, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        showLoading(false);
        console.error('Error:', error);
        showAlert('Error holding job card', 'danger');
    });
}

function submitResume() {
    const cardId = document.getElementById('resumeCardId').value;
    const notes = document.getElementById('resumeNotes').value;
    
    showLoading(true);
    
    fetch(`/job-cards/resume/${cardId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            notes: notes
        })
    })
    .then(response => response.json())
    .then(data => {
        showLoading(false);
        if (data.success) {
            showAlert(data.message, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        showLoading(false);
        console.error('Error:', error);
        showAlert('Error resuming job card', 'danger');
    });
}

function submitComplete() {
    const cardId = document.getElementById('completeCardId').value;
    const actualQuantity = document.getElementById('completeActualQuantity').value;
    const scrapQuantity = document.getElementById('completeScrapQuantity').value;
    const qualityNotes = document.getElementById('completeQualityNotes').value;
    
    showLoading(true);
    
    fetch(`/job-cards/complete/${cardId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            actual_quantity: actualQuantity ? parseFloat(actualQuantity) : null,
            scrap_quantity: parseFloat(scrapQuantity) || 0,
            quality_notes: qualityNotes
        })
    })
    .then(response => response.json())
    .then(data => {
        showLoading(false);
        if (data.success) {
            showAlert(data.message, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        showLoading(false);
        console.error('Error:', error);
        showAlert('Error completing job card', 'danger');
    });
}

// Utility functions
function showAlert(message, type = 'info') {
    // Create alert element if it doesn't exist
    const alertContainer = document.getElementById('alert-container') || createAlertContainer();
    
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    alertContainer.innerHTML = alertHtml;
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alert = alertContainer.querySelector('.alert');
        if (alert) {
            alert.remove();
        }
    }, 5000);
}

function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alert-container';
    container.className = 'position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1060';
    document.body.appendChild(container);
    return container;
}

function showLoading(show) {
    const loadingSpinner = document.getElementById('loading-spinner') || createLoadingSpinner();
    loadingSpinner.style.display = show ? 'flex' : 'none';
}

function createLoadingSpinner() {
    const spinner = document.createElement('div');
    spinner.id = 'loading-spinner';
    spinner.className = 'position-fixed top-50 start-50 translate-middle';
    spinner.style.zIndex = '1070';
    spinner.style.display = 'none';
    spinner.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;
    document.body.appendChild(spinner);
    return spinner;
}

// Auto-refresh functionality for live status pages
let autoRefreshInterval;

function startAutoRefresh(intervalSeconds = 30) {
    stopAutoRefresh(); // Clear any existing interval
    autoRefreshInterval = setInterval(() => {
        location.reload();
    }, intervalSeconds * 1000);
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Set up assignment modal toggle functionality
    const workerRadio = document.getElementById('assignToWorker');
    const vendorRadio = document.getElementById('assignToVendor');
    
    if (workerRadio && vendorRadio) {
        function toggleAssignmentSections() {
            const workerSection = document.getElementById('workerSection');
            const vendorSection = document.getElementById('vendorSection');
            
            if (workerRadio.checked) {
                workerSection.style.display = 'block';
                vendorSection.style.display = 'none';
                document.getElementById('assignVendor').value = '';
            } else {
                workerSection.style.display = 'none';
                vendorSection.style.display = 'block';
                document.getElementById('assignWorker').value = '';
            }
        }
        
        workerRadio.addEventListener('change', toggleAssignmentSections);
        vendorRadio.addEventListener('change', toggleAssignmentSections);
        
        // Initialize
        toggleAssignmentSections();
    }
    
    // Set up auto-refresh toggle for Today's Jobs page
    const autoRefreshToggle = document.getElementById('autoRefresh');
    if (autoRefreshToggle) {
        // Initial setup
        if (autoRefreshToggle.checked) {
            startAutoRefresh(30);
        }
        
        // Toggle functionality
        autoRefreshToggle.addEventListener('change', function() {
            if (this.checked) {
                startAutoRefresh(30);
            } else {
                stopAutoRefresh();
            }
        });
    }
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        stopAutoRefresh();
    });
});

// Export functions for global access
window.jobCards = {
    updateProgress,
    assignCard,
    holdCard,
    resumeCard,
    completeCard,
    submitProgress,
    submitAssignment,
    submitHold,
    submitResume,
    submitComplete,
    showAlert,
    showLoading,
    startAutoRefresh,
    stopAutoRefresh
};