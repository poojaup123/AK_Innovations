/**
 * Enhanced Filtering System for Factory Management
 * Provides comprehensive filtering with date ranges, status filters, and saved preferences
 */

class EnhancedFilters {
    constructor() {
        this.activeFilters = {};
        this.savedFilters = this.loadSavedFilters();
        this.datePresets = {
            'today': {
                label: 'Today',
                start: () => new Date(),
                end: () => new Date()
            },
            'yesterday': {
                label: 'Yesterday',
                start: () => {
                    const date = new Date();
                    date.setDate(date.getDate() - 1);
                    return date;
                },
                end: () => {
                    const date = new Date();
                    date.setDate(date.getDate() - 1);
                    return date;
                }
            },
            'this_week': {
                label: 'This Week',
                start: () => {
                    const date = new Date();
                    const day = date.getDay();
                    const diff = date.getDate() - day + (day === 0 ? -6 : 1);
                    return new Date(date.setDate(diff));
                },
                end: () => new Date()
            },
            'last_week': {
                label: 'Last Week',
                start: () => {
                    const date = new Date();
                    const day = date.getDay();
                    const diff = date.getDate() - day - 6;
                    return new Date(date.setDate(diff));
                },
                end: () => {
                    const date = new Date();
                    const day = date.getDay();
                    const diff = date.getDate() - day;
                    return new Date(date.setDate(diff));
                }
            },
            'this_month': {
                label: 'This Month',
                start: () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
                end: () => new Date()
            },
            'last_month': {
                label: 'Last Month',
                start: () => new Date(new Date().getFullYear(), new Date().getMonth() - 1, 1),
                end: () => new Date(new Date().getFullYear(), new Date().getMonth(), 0)
            },
            'this_quarter': {
                label: 'This Quarter',
                start: () => {
                    const date = new Date();
                    const quarter = Math.floor(date.getMonth() / 3);
                    return new Date(date.getFullYear(), quarter * 3, 1);
                },
                end: () => new Date()
            },
            'this_year': {
                label: 'This Year',
                start: () => new Date(new Date().getFullYear(), 0, 1),
                end: () => new Date()
            }
        };
        
        this.init();
    }
    
    init() {
        this.setupFilterUI();
        this.bindEvents();
        this.loadUrlFilters();
        console.log('✅ Enhanced filtering system initialized');
    }
    
    setupFilterUI() {
        // Find existing filter containers and enhance them
        const filterContainers = document.querySelectorAll('.filter-container, .card-body form[method="GET"]');
        
        filterContainers.forEach(container => {
            this.enhanceFilterContainer(container);
        });
        
        // Setup quick filter buttons if they don't exist
        this.setupQuickFilters();
        
        // Setup date range picker
        this.setupDateRangePicker();
        
        // Setup filter presets
        this.setupFilterPresets();
    }
    
    enhanceFilterContainer(container) {
        // Add filter counter
        if (!container.querySelector('.filter-counter')) {
            const counter = document.createElement('span');
            counter.className = 'filter-counter badge bg-primary ms-2';
            counter.style.display = 'none';
            
            const header = container.closest('.card')?.querySelector('.card-header h6');
            if (header) {
                header.appendChild(counter);
            }
        }
        
        // Add clear all filters button
        if (!container.querySelector('.clear-filters-btn')) {
            const clearBtn = document.createElement('button');
            clearBtn.type = 'button';
            clearBtn.className = 'btn btn-outline-secondary btn-sm clear-filters-btn ms-2';
            clearBtn.innerHTML = '<i class="fas fa-times"></i> Clear All';
            clearBtn.style.display = 'none';
            
            const submitBtn = container.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.parentNode.insertBefore(clearBtn, submitBtn.nextSibling);
            } else {
                container.appendChild(clearBtn);
            }
        }
        
        // Add collapsible functionality
        this.makeFilterCollapsible(container);
    }
    
    makeFilterCollapsible(container) {
        const card = container.closest('.card');
        if (!card) return;
        
        const header = card.querySelector('.card-header');
        const body = card.querySelector('.card-body');
        
        if (header && body) {
            header.style.cursor = 'pointer';
            header.setAttribute('data-bs-toggle', 'collapse');
            header.setAttribute('data-bs-target', '#' + (body.id || 'filterBody'));
            
            if (!body.id) {
                body.id = 'filterBody';
            }
            
            body.classList.add('collapse', 'show');
            
            // Add chevron icon
            if (!header.querySelector('.filter-toggle-icon')) {
                const icon = document.createElement('i');
                icon.className = 'fas fa-chevron-up filter-toggle-icon float-end';
                header.appendChild(icon);
            }
        }
    }
    
    setupQuickFilters() {
        // Status quick filters
        const statusSelects = document.querySelectorAll('select[name="status"]');
        statusSelects.forEach(select => {
            this.addQuickStatusButtons(select);
        });
        
        // Priority quick filters for relevant pages
        this.addPriorityFilters();
    }
    
    addQuickStatusButtons(statusSelect) {
        const container = statusSelect.closest('.col-md-2, .col-lg-2, .col');
        if (!container) return;
        
        const quickButtons = document.createElement('div');
        quickButtons.className = 'quick-status-filters mt-2';
        quickButtons.innerHTML = `
            <div class="btn-group-vertical w-100" role="group">
                <button type="button" class="btn btn-outline-primary btn-sm quick-filter-btn" data-status="">
                    <i class="fas fa-list"></i> All
                </button>
                <button type="button" class="btn btn-outline-warning btn-sm quick-filter-btn" data-status="pending">
                    <i class="fas fa-clock"></i> Pending
                </button>
                <button type="button" class="btn btn-outline-info btn-sm quick-filter-btn" data-status="in_progress">
                    <i class="fas fa-play"></i> In Progress
                </button>
                <button type="button" class="btn btn-outline-success btn-sm quick-filter-btn" data-status="completed">
                    <i class="fas fa-check"></i> Completed
                </button>
            </div>
        `;
        
        container.appendChild(quickButtons);
    }
    
    addPriorityFilters() {
        const forms = document.querySelectorAll('form[method="GET"]');
        forms.forEach(form => {
            if (form.querySelector('.priority-filters')) return;
            
            const priorityContainer = document.createElement('div');
            priorityContainer.className = 'col-md-2 priority-filters';
            priorityContainer.innerHTML = `
                <label class="form-label">Priority</label>
                <div class="btn-group-vertical w-100" role="group">
                    <button type="button" class="btn btn-outline-danger btn-sm priority-filter-btn" data-priority="high">
                        <i class="fas fa-exclamation-triangle"></i> High
                    </button>
                    <button type="button" class="btn btn-outline-warning btn-sm priority-filter-btn" data-priority="medium">
                        <i class="fas fa-minus"></i> Medium
                    </button>
                    <button type="button" class="btn btn-outline-success btn-sm priority-filter-btn" data-priority="low">
                        <i class="fas fa-check"></i> Low
                    </button>
                </div>
            `;
            
            const row = form.querySelector('.row');
            if (row) {
                row.appendChild(priorityContainer);
            }
        });
    }
    
    setupDateRangePicker() {
        const dateInputs = document.querySelectorAll('input[type="date"]');
        
        dateInputs.forEach(input => {
            this.enhanceDateInput(input);
        });
        
        // Add date range presets if date inputs exist
        if (dateInputs.length > 0) {
            this.addDatePresets();
        }
    }
    
    enhanceDateInput(input) {
        const container = input.closest('.col-md-2, .col-lg-2, .col');
        if (!container) return;
        
        // Add quick date buttons
        const quickDates = document.createElement('div');
        quickDates.className = 'quick-dates mt-1';
        quickDates.innerHTML = `
            <div class="btn-group-vertical w-100" role="group">
                <button type="button" class="btn btn-outline-secondary btn-sm quick-date-btn" data-date="today">
                    Today
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm quick-date-btn" data-date="yesterday">
                    Yesterday
                </button>
                <button type="button" class="btn btn-outline-secondary btn-sm quick-date-btn" data-date="week_start">
                    Week Start
                </button>
            </div>
        `;
        
        container.appendChild(quickDates);
    }
    
    addDatePresets() {
        const forms = document.querySelectorAll('form[method="GET"]');
        
        forms.forEach(form => {
            if (form.querySelector('.date-presets')) return;
            
            const presetsContainer = document.createElement('div');
            presetsContainer.className = 'col-md-3 date-presets';
            presetsContainer.innerHTML = `
                <label class="form-label">Quick Date Range</label>
                <select class="form-select date-preset-select">
                    <option value="">Custom Range</option>
                    ${Object.entries(this.datePresets).map(([key, preset]) => 
                        `<option value="${key}">${preset.label}</option>`
                    ).join('')}
                </select>
                <div class="mt-2">
                    <button type="button" class="btn btn-outline-info btn-sm w-100 save-filter-preset">
                        <i class="fas fa-save"></i> Save as Preset
                    </button>
                </div>
            `;
            
            const row = form.querySelector('.row');
            if (row) {
                row.appendChild(presetsContainer);
            }
        });
    }
    
    setupFilterPresets() {
        // Add saved filter presets
        if (Object.keys(this.savedFilters).length > 0) {
            this.addSavedFilterPresets();
        }
    }
    
    addSavedFilterPresets() {
        const forms = document.querySelectorAll('form[method="GET"]');
        
        forms.forEach(form => {
            if (form.querySelector('.saved-presets')) return;
            
            const presetsContainer = document.createElement('div');
            presetsContainer.className = 'col-md-3 saved-presets';
            presetsContainer.innerHTML = `
                <label class="form-label">Saved Filters</label>
                <select class="form-select saved-filter-select">
                    <option value="">Select Saved Filter</option>
                    ${Object.entries(this.savedFilters).map(([name, filters]) => 
                        `<option value="${name}">${name}</option>`
                    ).join('')}
                </select>
                <div class="mt-2">
                    <button type="button" class="btn btn-outline-danger btn-sm w-100 delete-filter-preset">
                        <i class="fas fa-trash"></i> Delete Selected
                    </button>
                </div>
            `;
            
            const row = form.querySelector('.row');
            if (row) {
                row.appendChild(presetsContainer);
            }
        });
    }
    
    bindEvents() {
        // Quick filter buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('.quick-filter-btn')) {
                this.handleQuickFilter(e.target);
            }
            
            if (e.target.matches('.priority-filter-btn')) {
                this.handlePriorityFilter(e.target);
            }
            
            if (e.target.matches('.quick-date-btn')) {
                this.handleQuickDate(e.target);
            }
            
            if (e.target.matches('.clear-filters-btn')) {
                this.clearAllFilters();
            }
            
            if (e.target.matches('.save-filter-preset')) {
                this.saveFilterPreset();
            }
            
            if (e.target.matches('.delete-filter-preset')) {
                this.deleteFilterPreset();
            }
        });
        
        // Date preset changes
        document.addEventListener('change', (e) => {
            if (e.target.matches('.date-preset-select')) {
                this.applyDatePreset(e.target.value);
            }
            
            if (e.target.matches('.saved-filter-select')) {
                this.applySavedFilter(e.target.value);
            }
        });
        
        // Filter form changes
        document.addEventListener('change', (e) => {
            if (e.target.closest('form[method="GET"]')) {
                this.updateFilterCounter();
            }
        });
        
        // Collapsible filter headers
        document.addEventListener('click', (e) => {
            if (e.target.closest('[data-bs-toggle="collapse"]')) {
                const icon = e.target.closest('.card-header').querySelector('.filter-toggle-icon');
                if (icon) {
                    setTimeout(() => {
                        const isCollapsed = e.target.getAttribute('aria-expanded') === 'false';
                        icon.className = isCollapsed ? 
                            'fas fa-chevron-down filter-toggle-icon float-end' : 
                            'fas fa-chevron-up filter-toggle-icon float-end';
                    }, 200);
                }
            }
        });
    }
    
    handleQuickFilter(button) {
        const status = button.dataset.status;
        const statusSelect = button.closest('.col-md-2, .col-lg-2, .col').querySelector('select[name="status"]');
        
        if (statusSelect) {
            statusSelect.value = status;
            this.updateActiveButton(button, '.quick-filter-btn');
            this.applyFilters();
        }
    }
    
    handlePriorityFilter(button) {
        const priority = button.dataset.priority;
        this.updateActiveButton(button, '.priority-filter-btn');
        
        // Set hidden priority input or add to form
        let priorityInput = button.closest('form').querySelector('input[name="priority"]');
        if (!priorityInput) {
            priorityInput = document.createElement('input');
            priorityInput.type = 'hidden';
            priorityInput.name = 'priority';
            button.closest('form').appendChild(priorityInput);
        }
        priorityInput.value = priority;
        
        this.applyFilters();
    }
    
    handleQuickDate(button) {
        const dateType = button.dataset.date;
        const input = button.closest('.col-md-2, .col-lg-2, .col').querySelector('input[type="date"]');
        
        if (input) {
            let date = new Date();
            
            switch (dateType) {
                case 'today':
                    break;
                case 'yesterday':
                    date.setDate(date.getDate() - 1);
                    break;
                case 'week_start':
                    const day = date.getDay();
                    const diff = date.getDate() - day + (day === 0 ? -6 : 1);
                    date.setDate(diff);
                    break;
            }
            
            input.value = date.toISOString().split('T')[0];
            this.updateActiveButton(button, '.quick-date-btn');
            this.applyFilters();
        }
    }
    
    applyDatePreset(presetKey) {
        if (!presetKey || !this.datePresets[presetKey]) return;
        
        const preset = this.datePresets[presetKey];
        const startDate = preset.start();
        const endDate = preset.end();
        
        const dateFromInput = document.querySelector('input[name="date_from"], input[name="start_date"]');
        const dateToInput = document.querySelector('input[name="date_to"], input[name="end_date"]');
        
        if (dateFromInput) {
            dateFromInput.value = startDate.toISOString().split('T')[0];
        }
        if (dateToInput) {
            dateToInput.value = endDate.toISOString().split('T')[0];
        }
        
        this.applyFilters();
    }
    
    updateActiveButton(button, selector) {
        const container = button.closest('.btn-group-vertical, .btn-group');
        if (container) {
            container.querySelectorAll(selector).forEach(btn => {
                btn.classList.remove('active');
            });
            button.classList.add('active');
        }
    }
    
    clearAllFilters() {
        const form = document.querySelector('form[method="GET"]');
        if (!form) return;
        
        // Clear all form inputs
        form.querySelectorAll('select, input[type="date"], input[type="text"]').forEach(input => {
            if (input.type === 'hidden') return;
            input.value = '';
        });
        
        // Clear active buttons
        form.querySelectorAll('.active').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Reset URL
        window.location.href = window.location.pathname;
    }
    
    applyFilters() {
        const form = document.querySelector('form[method="GET"]');
        if (form) {
            form.submit();
        }
    }
    
    updateFilterCounter() {
        const counter = document.querySelector('.filter-counter');
        const clearBtn = document.querySelector('.clear-filters-btn');
        
        if (!counter) return;
        
        const form = document.querySelector('form[method="GET"]');
        let activeCount = 0;
        
        if (form) {
            form.querySelectorAll('select, input[type="date"], input[type="text"]').forEach(input => {
                if (input.type === 'hidden') return;
                if (input.value && input.value.trim() !== '') {
                    activeCount++;
                }
            });
        }
        
        if (activeCount > 0) {
            counter.textContent = activeCount;
            counter.style.display = 'inline';
            if (clearBtn) clearBtn.style.display = 'inline-block';
        } else {
            counter.style.display = 'none';
            if (clearBtn) clearBtn.style.display = 'none';
        }
    }
    
    saveFilterPreset() {
        const name = prompt('Enter a name for this filter preset:');
        if (!name) return;
        
        const form = document.querySelector('form[method="GET"]');
        const filters = {};
        
        if (form) {
            form.querySelectorAll('select, input[type="date"], input[type="text"]').forEach(input => {
                if (input.type === 'hidden') return;
                if (input.value && input.value.trim() !== '') {
                    filters[input.name] = input.value;
                }
            });
        }
        
        this.savedFilters[name] = filters;
        this.saveSavedFilters();
        
        // Refresh saved filter dropdown
        this.refreshSavedFilterDropdown();
        
        this.showToast('Filter preset saved successfully!', 'success');
    }
    
    deleteFilterPreset() {
        const select = document.querySelector('.saved-filter-select');
        const name = select?.value;
        
        if (!name) {
            this.showToast('Please select a filter preset to delete', 'warning');
            return;
        }
        
        if (confirm(`Are you sure you want to delete the filter preset "${name}"?`)) {
            delete this.savedFilters[name];
            this.saveSavedFilters();
            this.refreshSavedFilterDropdown();
            this.showToast('Filter preset deleted successfully!', 'success');
        }
    }
    
    applySavedFilter(presetName) {
        if (!presetName || !this.savedFilters[presetName]) return;
        
        const filters = this.savedFilters[presetName];
        const form = document.querySelector('form[method="GET"]');
        
        if (form) {
            Object.entries(filters).forEach(([name, value]) => {
                const input = form.querySelector(`[name="${name}"]`);
                if (input) {
                    input.value = value;
                }
            });
            
            this.applyFilters();
        }
    }
    
    refreshSavedFilterDropdown() {
        const select = document.querySelector('.saved-filter-select');
        if (!select) return;
        
        select.innerHTML = `
            <option value="">Select Saved Filter</option>
            ${Object.keys(this.savedFilters).map(name => 
                `<option value="${name}">${name}</option>`
            ).join('')}
        `;
    }
    
    loadUrlFilters() {
        // Update filter counter based on URL parameters
        setTimeout(() => {
            this.updateFilterCounter();
        }, 100);
    }
    
    loadSavedFilters() {
        try {
            const saved = localStorage.getItem('enhancedFilters');
            return saved ? JSON.parse(saved) : {};
        } catch (e) {
            return {};
        }
    }
    
    saveSavedFilters() {
        try {
            localStorage.setItem('enhancedFilters', JSON.stringify(this.savedFilters));
        } catch (e) {
            console.warn('Could not save filter presets');
        }
    }
    
    showToast(message, type = 'info') {
        // Use existing toast system if available
        if (window.showToast) {
            window.showToast(message, type);
        } else if (window.mobileEnhancements) {
            window.mobileEnhancements.showInfoToast(message);
        } else {
            alert(message);
        }
    }
}

// Initialize enhanced filters when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.enhancedFilters = new EnhancedFilters();
});

// Export for external use
window.EnhancedFilters = EnhancedFilters;