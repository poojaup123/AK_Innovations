/**
 * Searchable Dropdown Component for Factory Management System
 * Provides advanced search and filtering capabilities for both forms and tables
 */

class SearchableDropdown {
    constructor(element, options = {}) {
        this.element = element;
        this.options = {
            placeholder: options.placeholder || 'Search...',
            apiUrl: options.apiUrl || null,
            data: options.data || [],
            multiSelect: options.multiSelect || false,
            allowEmpty: options.allowEmpty !== false,
            minSearchLength: options.minSearchLength || 0,
            maxResults: options.maxResults || 100,
            showRecent: options.showRecent !== false,
            enableFavorites: options.enableFavorites !== false,
            clearOnSelect: options.clearOnSelect || false,
            onSelect: options.onSelect || null,
            onClear: options.onClear || null,
            searchKeys: options.searchKeys || ['text', 'name', 'title'],
            groupBy: options.groupBy || null,
            templateItem: options.templateItem || null,
            templateGroup: options.templateGroup || null,
            noResultsText: options.noResultsText || 'No results found',
            loadingText: options.loadingText || 'Loading...',
            recentItemsKey: options.recentItemsKey || 'searchable-dropdown-recent'
        };
        
        this.isOpen = false;
        this.selectedItems = [];
        this.data = [];
        this.filteredData = [];
        this.searchTerm = '';
        this.loading = false;
        this.recentItems = this.loadRecentItems();
        this.favorites = this.loadFavorites();
        
        this.init();
    }

    init() {
        this.createDOM();
        this.bindEvents();
        this.loadData();
        
        // Hide original select if it exists
        if (this.element.tagName === 'SELECT') {
            this.element.style.display = 'none';
            this.originalSelect = this.element;
        }
    }

    createDOM() {
        // Create wrapper
        this.wrapper = document.createElement('div');
        this.wrapper.className = 'searchable-dropdown';
        
        // Create main input/button
        this.trigger = document.createElement('div');
        this.trigger.className = 'searchable-dropdown-trigger';
        this.trigger.innerHTML = `
            <input type="text" class="form-control searchable-dropdown-input" 
                   placeholder="${this.options.placeholder}" autocomplete="off">
            <button type="button" class="searchable-dropdown-btn">
                <i class="fas fa-chevron-down"></i>
            </button>
        `;
        
        // Create dropdown menu
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'searchable-dropdown-menu';
        this.dropdown.innerHTML = `
            <div class="searchable-dropdown-content">
                <div class="searchable-dropdown-loading" style="display: none;">
                    <div class="text-center py-3">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">${this.options.loadingText}</span>
                        </div>
                        <div class="mt-2 small text-muted">${this.options.loadingText}</div>
                    </div>
                </div>
                <div class="searchable-dropdown-no-results" style="display: none;">
                    <div class="text-center py-3 text-muted">
                        <i class="fas fa-search mb-2"></i>
                        <div>${this.options.noResultsText}</div>
                    </div>
                </div>
                <div class="searchable-dropdown-items"></div>
            </div>
        `;
        
        // Create selected items display (for multi-select)
        if (this.options.multiSelect) {
            this.selectedDisplay = document.createElement('div');
            this.selectedDisplay.className = 'searchable-dropdown-selected';
        }
        
        this.wrapper.appendChild(this.trigger);
        this.wrapper.appendChild(this.dropdown);
        if (this.selectedDisplay) {
            this.wrapper.appendChild(this.selectedDisplay);
        }
        
        // Insert after original element
        this.element.parentNode.insertBefore(this.wrapper, this.element.nextSibling);
        
        // Get references to elements
        this.input = this.trigger.querySelector('.searchable-dropdown-input');
        this.button = this.trigger.querySelector('.searchable-dropdown-btn');
        this.itemsContainer = this.dropdown.querySelector('.searchable-dropdown-items');
        this.loadingEl = this.dropdown.querySelector('.searchable-dropdown-loading');
        this.noResultsEl = this.dropdown.querySelector('.searchable-dropdown-no-results');
    }

    bindEvents() {
        // Input events with null checks
        if (this.input) {
            this.input.addEventListener('input', (e) => this.handleSearch(e.target.value));
            this.input.addEventListener('focus', () => this.open());
            this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        }
        
        // Button events with null checks
        if (this.button) {
            this.button.addEventListener('click', () => this.toggle());
        }
        
        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.wrapper.contains(e.target)) {
                this.close();
            }
        });
        
        // Prevent form submission on Enter when dropdown is open
        if (this.input) {
            this.input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && this.isOpen) {
                    e.preventDefault();
                }
            });
        }
    }

    async loadData() {
        if (this.options.apiUrl) {
            this.setLoading(true);
            try {
                const response = await fetch(this.options.apiUrl);
                this.data = await response.json();
                this.filterItems();
            } catch (error) {
                console.error('Error loading data:', error);
                this.data = [];
            }
            this.setLoading(false);
        } else {
            this.data = this.options.data;
            this.filterItems();
        }
    }

    handleSearch(term) {
        this.searchTerm = term.toLowerCase();
        if (this.searchTerm.length >= this.options.minSearchLength) {
            this.filterItems();
            if (!this.isOpen) this.open();
        } else {
            this.filteredData = this.data.slice(0, this.options.maxResults);
            this.renderItems();
        }
    }

    filterItems() {
        if (!this.searchTerm) {
            this.filteredData = this.data.slice(0, this.options.maxResults);
        } else {
            this.filteredData = this.data.filter(item => {
                return this.options.searchKeys.some(key => {
                    const value = this.getNestedValue(item, key);
                    return value && value.toString().toLowerCase().includes(this.searchTerm);
                });
            }).slice(0, this.options.maxResults);
        }
        this.renderItems();
    }

    getNestedValue(obj, key) {
        return key.split('.').reduce((o, k) => (o || {})[k], obj);
    }

    renderItems() {
        this.itemsContainer.innerHTML = '';
        
        // Show recent items if no search term and recent items exist
        if (!this.searchTerm && this.options.showRecent && this.recentItems.length > 0) {
            this.renderSection('Recently Used', this.recentItems.slice(0, 5));
        }
        
        // Show favorites if enabled and no search term
        if (!this.searchTerm && this.options.enableFavorites && this.favorites.length > 0) {
            this.renderSection('Favorites', this.favorites);
        }
        
        // Group items if groupBy option is set
        if (this.options.groupBy) {
            this.renderGroupedItems();
        } else {
            this.renderFlatItems();
        }
        
        // Show no results message
        if (this.filteredData.length === 0 && this.searchTerm) {
            this.noResultsEl.style.display = 'block';
        } else {
            this.noResultsEl.style.display = 'none';
        }
    }

    renderSection(title, items) {
        if (items.length === 0) return;
        
        const section = document.createElement('div');
        section.className = 'searchable-dropdown-section';
        section.innerHTML = `
            <div class="searchable-dropdown-section-title">${title}</div>
            <div class="searchable-dropdown-section-items"></div>
        `;
        
        const itemsContainer = section.querySelector('.searchable-dropdown-section-items');
        items.forEach(item => {
            const itemEl = this.createItemElement(item);
            itemsContainer.appendChild(itemEl);
        });
        
        this.itemsContainer.appendChild(section);
    }

    renderGroupedItems() {
        const groups = {};
        this.filteredData.forEach(item => {
            const groupKey = this.getNestedValue(item, this.options.groupBy) || 'Other';
            if (!groups[groupKey]) groups[groupKey] = [];
            groups[groupKey].push(item);
        });
        
        Object.keys(groups).sort().forEach(groupKey => {
            this.renderSection(groupKey, groups[groupKey]);
        });
    }

    renderFlatItems() {
        this.filteredData.forEach(item => {
            const itemEl = this.createItemElement(item);
            this.itemsContainer.appendChild(itemEl);
        });
    }

    createItemElement(item) {
        const itemEl = document.createElement('div');
        itemEl.className = 'searchable-dropdown-item';
        itemEl.dataset.value = item.value || item.id;
        
        // Use custom template if provided
        if (this.options.templateItem) {
            itemEl.innerHTML = this.options.templateItem(item);
        } else {
            const text = item.text || item.name || item.title || item.label;
            const subtitle = item.subtitle || item.description || '';
            
            itemEl.innerHTML = `
                <div class="item-content">
                    <div class="item-text">${text}</div>
                    ${subtitle ? `<div class="item-subtitle">${subtitle}</div>` : ''}
                </div>
                ${this.options.enableFavorites ? `
                    <button type="button" class="item-favorite ${this.isFavorite(item) ? 'active' : ''}" 
                            data-action="favorite" title="Add to favorites">
                        <i class="fas fa-star"></i>
                    </button>
                ` : ''}
            `;
        }
        
        // Bind click events
        itemEl.addEventListener('click', (e) => {
            if (e.target.dataset.action === 'favorite') {
                this.toggleFavorite(item);
                e.stopPropagation();
            } else {
                this.selectItem(item);
            }
        });
        
        return itemEl;
    }

    selectItem(item) {
        if (this.options.multiSelect) {
            this.addSelectedItem(item);
        } else {
            this.selectedItems = [item];
            const text = item.text || item.name || item.title || item.label;
            this.input.value = this.options.clearOnSelect ? '' : text;
            this.close();
            
            // Update original select if exists
            if (this.originalSelect) {
                this.originalSelect.value = item.value || item.id;
                this.originalSelect.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        
        // Add to recent items
        this.addToRecent(item);
        
        // Trigger callback
        if (this.options.onSelect) {
            this.options.onSelect(item, this.selectedItems);
        }
    }

    addSelectedItem(item) {
        const exists = this.selectedItems.find(selected => 
            (selected.value || selected.id) === (item.value || item.id)
        );
        
        if (!exists) {
            this.selectedItems.push(item);
            this.updateSelectedDisplay();
        }
    }

    removeSelectedItem(item) {
        this.selectedItems = this.selectedItems.filter(selected => 
            (selected.value || selected.id) !== (item.value || item.id)
        );
        this.updateSelectedDisplay();
    }

    updateSelectedDisplay() {
        if (!this.selectedDisplay) return;
        
        this.selectedDisplay.innerHTML = '';
        this.selectedItems.forEach(item => {
            const tag = document.createElement('span');
            tag.className = 'selected-item-tag';
            tag.innerHTML = `
                ${item.text || item.name || item.title}
                <button type="button" class="remove-item" data-value="${item.value || item.id}">×</button>
            `;
            
            tag.querySelector('.remove-item').addEventListener('click', () => {
                this.removeSelectedItem(item);
            });
            
            this.selectedDisplay.appendChild(tag);
        });
    }

    addToRecent(item) {
        // Remove if already exists
        this.recentItems = this.recentItems.filter(recent => 
            (recent.value || recent.id) !== (item.value || item.id)
        );
        
        // Add to beginning
        this.recentItems.unshift(item);
        
        // Keep only last 10
        this.recentItems = this.recentItems.slice(0, 10);
        
        // Save to localStorage
        this.saveRecentItems();
    }

    toggleFavorite(item) {
        const index = this.favorites.findIndex(fav => 
            (fav.value || fav.id) === (item.value || item.id)
        );
        
        if (index >= 0) {
            this.favorites.splice(index, 1);
        } else {
            this.favorites.push(item);
        }
        
        this.saveFavorites();
        this.renderItems(); // Re-render to update star icon
    }

    isFavorite(item) {
        return this.favorites.some(fav => 
            (fav.value || fav.id) === (item.value || item.id)
        );
    }

    loadRecentItems() {
        try {
            const stored = localStorage.getItem(this.options.recentItemsKey);
            return stored ? JSON.parse(stored) : [];
        } catch {
            return [];
        }
    }

    saveRecentItems() {
        try {
            localStorage.setItem(this.options.recentItemsKey, JSON.stringify(this.recentItems));
        } catch {}
    }

    loadFavorites() {
        try {
            const stored = localStorage.getItem(this.options.recentItemsKey + '-favorites');
            return stored ? JSON.parse(stored) : [];
        } catch {
            return [];
        }
    }

    saveFavorites() {
        try {
            localStorage.setItem(this.options.recentItemsKey + '-favorites', JSON.stringify(this.favorites));
        } catch {}
    }

    handleKeydown(e) {
        const items = this.itemsContainer.querySelectorAll('.searchable-dropdown-item');
        const currentFocus = this.itemsContainer.querySelector('.searchable-dropdown-item.focused');
        let currentIndex = Array.from(items).indexOf(currentFocus);
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                currentIndex = Math.min(currentIndex + 1, items.length - 1);
                this.focusItem(items[currentIndex]);
                break;
            case 'ArrowUp':
                e.preventDefault();
                currentIndex = Math.max(currentIndex - 1, 0);
                this.focusItem(items[currentIndex]);
                break;
            case 'Enter':
                if (currentFocus && this.isOpen) {
                    e.preventDefault();
                    currentFocus.click();
                }
                break;
            case 'Escape':
                this.close();
                break;
        }
    }

    focusItem(item) {
        // Remove previous focus
        this.itemsContainer.querySelectorAll('.focused').forEach(el => {
            el.classList.remove('focused');
        });
        
        // Add focus to current item
        if (item) {
            item.classList.add('focused');
            item.scrollIntoView({ block: 'nearest' });
        }
    }

    setLoading(loading) {
        this.loading = loading;
        if (loading) {
            this.loadingEl.style.display = 'block';
            this.itemsContainer.style.display = 'none';
        } else {
            this.loadingEl.style.display = 'none';
            this.itemsContainer.style.display = 'block';
        }
    }

    open() {
        if (this.isOpen) return;
        this.isOpen = true;
        this.wrapper.classList.add('open');
        this.dropdown.style.display = 'block';
        
        // Position dropdown
        this.positionDropdown();
    }

    close() {
        if (!this.isOpen) return;
        this.isOpen = false;
        this.wrapper.classList.remove('open');
        this.dropdown.style.display = 'none';
        
        // Remove focus from items
        this.itemsContainer.querySelectorAll('.focused').forEach(el => {
            el.classList.remove('focused');
        });
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    positionDropdown() {
        const rect = this.trigger.getBoundingClientRect();
        const spaceBelow = window.innerHeight - rect.bottom;
        const spaceAbove = rect.top;
        
        if (spaceBelow < 200 && spaceAbove > spaceBelow) {
            // Show above
            this.dropdown.classList.add('dropdown-up');
        } else {
            // Show below
            this.dropdown.classList.remove('dropdown-up');
        }
    }

    // Public API methods
    getValue() {
        if (this.options.multiSelect) {
            return this.selectedItems.map(item => item.value || item.id);
        } else {
            return this.selectedItems.length > 0 ? (this.selectedItems[0].value || this.selectedItems[0].id) : null;
        }
    }

    setValue(value) {
        if (this.options.multiSelect) {
            this.selectedItems = Array.isArray(value) ? 
                this.data.filter(item => value.includes(item.value || item.id)) : [];
            this.updateSelectedDisplay();
        } else {
            const item = this.data.find(item => (item.value || item.id) === value);
            if (item) {
                this.selectedItems = [item];
                this.input.value = item.text || item.name || item.title || item.label;
            }
        }
    }

    clear() {
        this.selectedItems = [];
        this.input.value = '';
        if (this.selectedDisplay) {
            this.selectedDisplay.innerHTML = '';
        }
        if (this.originalSelect) {
            this.originalSelect.value = '';
        }
        if (this.options.onClear) {
            this.options.onClear();
        }
    }

    refresh() {
        this.loadData();
    }

    destroy() {
        this.wrapper.remove();
        if (this.originalSelect) {
            this.originalSelect.style.display = '';
        }
    }
}

// Table Filter Dropdown Component
class TableFilterDropdown {
    constructor(table, columnIndex, options = {}) {
        this.table = table;
        this.columnIndex = columnIndex;
        this.options = {
            placeholder: options.placeholder || 'Filter...',
            showSelectAll: options.showSelectAll !== false,
            maxItems: options.maxItems || 1000,
            ...options
        };
        
        this.selectedValues = new Set();
        this.allValues = new Set();
        this.isOpen = false;
        
        this.init();
    }

    init() {
        this.extractValues();
        this.createFilterButton();
        this.bindEvents();
    }

    extractValues() {
        const rows = this.table.querySelectorAll('tbody tr');
        this.allValues.clear();
        
        rows.forEach(row => {
            const cell = row.cells[this.columnIndex];
            if (cell) {
                const value = cell.textContent.trim();
                if (value) {
                    this.allValues.add(value);
                }
            }
        });
    }

    createFilterButton() {
        const header = this.table.querySelectorAll('th')[this.columnIndex];
        if (!header) return;
        
        const filterBtn = document.createElement('div');
        filterBtn.className = 'table-filter-btn';
        filterBtn.innerHTML = `
            <button type="button" class="btn btn-sm btn-outline-secondary filter-toggle" title="Filter column">
                <i class="fas fa-filter"></i>
            </button>
        `;
        
        const dropdown = document.createElement('div');
        dropdown.className = 'table-filter-dropdown';
        dropdown.innerHTML = `
            <div class="filter-search-container">
                <input type="text" class="form-control form-control-sm filter-search" 
                       placeholder="${this.options.placeholder}">
            </div>
            <div class="filter-options">
                ${this.options.showSelectAll ? `
                    <div class="filter-option select-all">
                        <label class="form-check-label">
                            <input type="checkbox" class="form-check-input select-all-checkbox"> Select All
                        </label>
                    </div>
                ` : ''}
                <div class="filter-values"></div>
            </div>
            <div class="filter-actions">
                <button type="button" class="btn btn-primary btn-sm apply-filter">Apply</button>
                <button type="button" class="btn btn-secondary btn-sm clear-filter">Clear</button>
            </div>
        `;
        
        header.style.position = 'relative';
        header.appendChild(filterBtn);
        header.appendChild(dropdown);
        
        this.filterBtn = filterBtn;
        this.dropdown = dropdown;
        this.searchInput = dropdown.querySelector('.filter-search');
        this.valuesContainer = dropdown.querySelector('.filter-values');
        this.selectAllCheckbox = dropdown.querySelector('.select-all-checkbox');
        
        this.renderValues();
    }

    renderValues() {
        const searchTerm = this.searchInput ? this.searchInput.value.toLowerCase() : '';
        const values = Array.from(this.allValues)
            .filter(value => value.toLowerCase().includes(searchTerm))
            .sort()
            .slice(0, this.options.maxItems);
        
        this.valuesContainer.innerHTML = '';
        
        values.forEach(value => {
            const option = document.createElement('div');
            option.className = 'filter-option';
            option.innerHTML = `
                <label class="form-check-label">
                    <input type="checkbox" class="form-check-input" value="${value}"> ${value}
                </label>
            `;
            
            const checkbox = option.querySelector('input');
            if (this.selectedValues.has(value)) {
                checkbox.checked = true;
            }
            
            this.valuesContainer.appendChild(option);
        });
        
        // Update select all checkbox
        if (this.selectAllCheckbox) {
            const visibleCheckboxes = this.valuesContainer.querySelectorAll('input[type="checkbox"]');
            const checkedBoxes = this.valuesContainer.querySelectorAll('input[type="checkbox"]:checked');
            this.selectAllCheckbox.indeterminate = checkedBoxes.length > 0 && checkedBoxes.length < visibleCheckboxes.length;
            this.selectAllCheckbox.checked = visibleCheckboxes.length > 0 && checkedBoxes.length === visibleCheckboxes.length;
        }
    }

    bindEvents() {
        // Toggle dropdown
        this.filterBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggle();
        });
        
        // Search functionality
        if (this.searchInput) {
            this.searchInput.addEventListener('input', () => this.renderValues());
        }
        
        // Select all functionality
        if (this.selectAllCheckbox) {
            this.selectAllCheckbox.addEventListener('change', (e) => {
                const checkboxes = this.valuesContainer.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(cb => cb.checked = e.target.checked);
            });
        }
        
        // Apply filter
        this.dropdown.querySelector('.apply-filter').addEventListener('click', () => {
            this.applyFilter();
        });
        
        // Clear filter
        this.dropdown.querySelector('.clear-filter').addEventListener('click', () => {
            this.clearFilter();
        });
        
        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!this.dropdown.contains(e.target) && !this.filterBtn.contains(e.target)) {
                this.close();
            }
        });
    }

    applyFilter() {
        const checkboxes = this.valuesContainer.querySelectorAll('input[type="checkbox"]:checked');
        this.selectedValues.clear();
        
        checkboxes.forEach(cb => {
            this.selectedValues.add(cb.value);
        });
        
        this.filterTable();
        this.updateFilterButton();
        this.close();
    }

    clearFilter() {
        this.selectedValues.clear();
        this.filterTable();
        this.updateFilterButton();
        this.renderValues();
    }

    filterTable() {
        const rows = this.table.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            const cell = row.cells[this.columnIndex];
            if (!cell) return;
            
            const value = cell.textContent.trim();
            
            if (this.selectedValues.size === 0 || this.selectedValues.has(value)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    updateFilterButton() {
        const button = this.filterBtn.querySelector('button');
        const icon = button.querySelector('i');
        
        if (this.selectedValues.size > 0) {
            button.classList.remove('btn-outline-secondary');
            button.classList.add('btn-primary');
            icon.className = 'fas fa-filter-circle-xmark';
            button.title = `Filtered (${this.selectedValues.size} selected)`;
        } else {
            button.classList.remove('btn-primary');
            button.classList.add('btn-outline-secondary');
            icon.className = 'fas fa-filter';
            button.title = 'Filter column';
        }
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    open() {
        this.isOpen = true;
        this.dropdown.style.display = 'block';
        if (this.searchInput) {
            this.searchInput.focus();
        }
    }

    close() {
        this.isOpen = false;
        this.dropdown.style.display = 'none';
    }
}

// Initialize searchable dropdowns
window.SearchableDropdown = SearchableDropdown;
window.TableFilterDropdown = TableFilterDropdown;

// Auto-initialize dropdowns with data attributes
document.addEventListener('DOMContentLoaded', function() {
    // Initialize form dropdowns
    document.querySelectorAll('[data-searchable-dropdown]').forEach(element => {
        const options = JSON.parse(element.dataset.searchableDropdown || '{}');
        new SearchableDropdown(element, options);
    });
    
    // Initialize table filters
    document.querySelectorAll('table[data-enable-filters]').forEach(table => {
        const headers = table.querySelectorAll('th');
        headers.forEach((header, index) => {
            if (header.dataset.filterable !== 'false') {
                new TableFilterDropdown(table, index);
            }
        });
    });
});