/**
 * Drag & Drop BOM Builder
 * Phase 3: Visual BOM creation with instant cost calculation
 */

class DragDropBOMBuilder {
    constructor(container) {
        this.container = container;
        this.bomComponents = [];
        this.availableItems = [];
        this.currentCost = 0;
        this.settings = null;
        this.init();
    }

    async init() {
        try {
            // Check if feature is enabled
            const settingsResponse = await fetch('/cost-settings/api/get');
            const settingsData = await settingsResponse.json();
            
            if (!settingsData.success || !settingsData.settings.phase3.drag_drop_bom) {
                this.showDisabledMessage();
                return;
            }
            
            this.settings = settingsData.settings;
            await this.loadAvailableItems();
            this.render();
            this.bindEvents();
        } catch (error) {
            console.error('Error initializing BOM builder:', error);
            this.showError('Failed to initialize BOM builder');
        }
    }

    async loadAvailableItems() {
        try {
            const response = await fetch('/api/inventory/items');
            const data = await response.json();
            
            if (data.success) {
                this.availableItems = data.items.map(item => ({
                    id: item.id,
                    code: item.code,
                    name: item.name,
                    unit_price: item.unit_price || 0,
                    effective_cost: item.effective_cost || item.unit_price || 0,
                    uom: item.uom || 'PCS',
                    category: item.category || 'General'
                }));
            } else {
                throw new Error(data.error || 'Failed to load items');
            }
        } catch (error) {
            console.error('Error loading items:', error);
            // Use mock data for demo if API fails
            this.availableItems = [
                { id: 1, code: 'M001', name: 'Steel Plate', effective_cost: 150, uom: 'KG', category: 'Material' },
                { id: 2, code: 'F001', name: 'Bolt M6x20', effective_cost: 2.5, uom: 'PCS', category: 'Fastener' },
                { id: 3, code: 'F002', name: 'Washer M6', effective_cost: 0.5, uom: 'PCS', category: 'Fastener' }
            ];
        }
    }

    render() {
        const html = `
            <div class="drag-drop-bom-builder">
                <div class="builder-header mb-4">
                    <h5><i class="fas fa-magic me-2"></i>Drag & Drop BOM Builder</h5>
                    <div class="builder-actions">
                        <button class="btn btn-success btn-sm me-2" onclick="bomBuilder.saveBOM()">
                            <i class="fas fa-save me-1"></i>Save BOM
                        </button>
                        <button class="btn btn-outline-secondary btn-sm" onclick="bomBuilder.clearBOM()">
                            <i class="fas fa-trash me-1"></i>Clear All
                        </button>
                    </div>
                </div>

                <div class="row">
                    <!-- Available Items Panel -->
                    <div class="col-md-4">
                        <div class="card h-100">
                            <div class="card-header bg-primary text-white">
                                <h6 class="mb-0"><i class="fas fa-box me-2"></i>Available Items</h6>
                            </div>
                            <div class="card-body p-2">
                                <div class="search-box mb-3">
                                    <input type="text" class="form-control form-control-sm" 
                                           placeholder="Search items..." 
                                           onkeyup="bomBuilder.filterItems(this.value)">
                                </div>
                                <div id="items-list" class="items-list">
                                    ${this.renderAvailableItems()}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- BOM Building Area -->
                    <div class="col-md-5">
                        <div class="card h-100">
                            <div class="card-header bg-success text-white">
                                <h6 class="mb-0"><i class="fas fa-list me-2"></i>BOM Components</h6>
                            </div>
                            <div class="card-body">
                                <div id="bom-drop-zone" class="bom-drop-zone" 
                                     ondrop="bomBuilder.handleDrop(event)" 
                                     ondragover="bomBuilder.handleDragOver(event)">
                                    ${this.renderBOMComponents()}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Cost Summary Panel -->
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-header bg-warning text-dark">
                                <h6 class="mb-0"><i class="fas fa-calculator me-2"></i>Cost Summary</h6>
                            </div>
                            <div class="card-body">
                                ${this.renderCostSummary()}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        this.container.innerHTML = html;
    }

    renderAvailableItems() {
        if (this.availableItems.length === 0) {
            return '<div class="text-muted text-center py-3">No items available</div>';
        }

        let html = '';
        const categories = [...new Set(this.availableItems.map(item => item.category))];
        
        categories.forEach(category => {
            const categoryItems = this.availableItems.filter(item => item.category === category);
            
            html += `<div class="item-category mb-3">
                <h6 class="category-header text-muted">${category}</h6>
            `;
            
            categoryItems.forEach(item => {
                html += `
                    <div class="item-card" 
                         draggable="true" 
                         data-item-id="${item.id}"
                         ondragstart="bomBuilder.handleDragStart(event, ${item.id})">
                        <div class="item-info">
                            <div class="item-name fw-bold">${item.name}</div>
                            <div class="item-code text-muted small">${item.code}</div>
                            <div class="item-cost text-primary small">₹${item.effective_cost.toFixed(2)}/${item.uom}</div>
                        </div>
                        <div class="drag-handle">
                            <i class="fas fa-grip-vertical"></i>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
        });
        
        return html;
    }

    renderBOMComponents() {
        if (this.bomComponents.length === 0) {
            return `
                <div class="empty-bom text-center py-5">
                    <i class="fas fa-plus-circle fa-3x text-muted mb-3"></i>
                    <h5 class="text-muted">Drag items here to build your BOM</h5>
                    <p class="text-muted">Components will appear here with editable quantities</p>
                </div>
            `;
        }

        let html = '<div class="bom-components">';
        
        this.bomComponents.forEach((component, index) => {
            const totalCost = component.quantity * component.effective_cost;
            
            html += `
                <div class="bom-component-card mb-2" data-component-index="${index}">
                    <div class="component-header d-flex justify-content-between align-items-center">
                        <div class="component-info">
                            <strong>${component.name}</strong>
                            <small class="text-muted d-block">${component.code}</small>
                        </div>
                        <button class="btn btn-sm btn-outline-danger" 
                                onclick="bomBuilder.removeComponent(${index})">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="component-details mt-2">
                        <div class="row align-items-center">
                            <div class="col-6">
                                <label class="form-label small">Quantity</label>
                                <div class="input-group input-group-sm">
                                    <button class="btn btn-outline-secondary" type="button" 
                                            onclick="bomBuilder.adjustQuantity(${index}, -1)">-</button>
                                    <input type="number" class="form-control text-center" 
                                           value="${component.quantity}" 
                                           min="0.1" step="0.1"
                                           onchange="bomBuilder.updateQuantity(${index}, this.value)">
                                    <button class="btn btn-outline-secondary" type="button" 
                                            onclick="bomBuilder.adjustQuantity(${index}, 1)">+</button>
                                </div>
                            </div>
                            <div class="col-3">
                                <label class="form-label small">UOM</label>
                                <div class="small fw-bold">${component.uom}</div>
                            </div>
                            <div class="col-3">
                                <label class="form-label small">Total</label>
                                <div class="fw-bold text-success">₹${totalCost.toFixed(2)}</div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        return html;
    }

    renderCostSummary() {
        const totalCost = this.bomComponents.reduce((sum, comp) => 
            sum + (comp.quantity * comp.effective_cost), 0);
        
        const componentCount = this.bomComponents.length;
        const avgCostPerComponent = componentCount > 0 ? totalCost / componentCount : 0;

        return `
            <div class="cost-summary">
                <div class="cost-item d-flex justify-content-between mb-2">
                    <span>Components:</span>
                    <span class="fw-bold">${componentCount}</span>
                </div>
                <div class="cost-item d-flex justify-content-between mb-2">
                    <span>Material Cost:</span>
                    <span class="fw-bold text-primary">₹${totalCost.toFixed(2)}</span>
                </div>
                <div class="cost-item d-flex justify-content-between mb-3">
                    <span>Avg per Component:</span>
                    <span class="text-muted">₹${avgCostPerComponent.toFixed(2)}</span>
                </div>
                <hr>
                <div class="cost-total d-flex justify-content-between">
                    <span class="fw-bold">Total BOM Cost:</span>
                    <span class="fw-bold fs-5 text-success">₹${totalCost.toFixed(2)}</span>
                </div>
                
                ${this.renderCostBreakdown()}
            </div>
        `;
    }

    renderCostBreakdown() {
        if (this.bomComponents.length === 0) return '';

        const categories = {};
        this.bomComponents.forEach(comp => {
            const category = comp.category || 'General';
            if (!categories[category]) {
                categories[category] = 0;
            }
            categories[category] += comp.quantity * comp.effective_cost;
        });

        let html = '<div class="cost-breakdown mt-3"><h6 class="small">Cost by Category</h6>';
        
        Object.entries(categories).forEach(([category, cost]) => {
            html += `
                <div class="d-flex justify-content-between small mb-1">
                    <span>${category}:</span>
                    <span class="fw-bold">₹${cost.toFixed(2)}</span>
                </div>
            `;
        });
        
        html += '</div>';
        return html;
    }

    handleDragStart(event, itemId) {
        event.dataTransfer.setData('text/plain', itemId);
        event.dataTransfer.effectAllowed = 'copy';
    }

    handleDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'copy';
        
        // Add visual feedback
        const dropZone = document.getElementById('bom-drop-zone');
        dropZone.classList.add('drag-over');
    }

    handleDrop(event) {
        event.preventDefault();
        
        const dropZone = document.getElementById('bom-drop-zone');
        dropZone.classList.remove('drag-over');
        
        const itemId = parseInt(event.dataTransfer.getData('text/plain'));
        this.addComponent(itemId);
    }

    addComponent(itemId) {
        const item = this.availableItems.find(i => i.id === itemId);
        if (!item) return;

        // Check if component already exists
        const existingIndex = this.bomComponents.findIndex(comp => comp.id === itemId);
        
        if (existingIndex >= 0) {
            // Increase quantity if already exists
            this.bomComponents[existingIndex].quantity += 1;
        } else {
            // Add new component
            this.bomComponents.push({
                ...item,
                quantity: 1
            });
        }

        this.updateDisplay();
        this.showSuccess(`Added ${item.name} to BOM`);
    }

    removeComponent(index) {
        const component = this.bomComponents[index];
        this.bomComponents.splice(index, 1);
        this.updateDisplay();
        this.showSuccess(`Removed ${component.name} from BOM`);
    }

    updateQuantity(index, newQuantity) {
        const quantity = parseFloat(newQuantity) || 0.1;
        this.bomComponents[index].quantity = Math.max(0.1, quantity);
        this.updateDisplay();
    }

    adjustQuantity(index, delta) {
        const newQuantity = this.bomComponents[index].quantity + delta;
        this.updateQuantity(index, Math.max(0.1, newQuantity));
    }

    filterItems(searchText) {
        const itemCards = document.querySelectorAll('.item-card');
        const searchLower = searchText.toLowerCase();
        
        itemCards.forEach(card => {
            const itemName = card.querySelector('.item-name').textContent.toLowerCase();
            const itemCode = card.querySelector('.item-code').textContent.toLowerCase();
            
            if (itemName.includes(searchLower) || itemCode.includes(searchLower)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }

    updateDisplay() {
        // Update BOM components section
        const bomZone = document.getElementById('bom-drop-zone');
        bomZone.innerHTML = this.renderBOMComponents();
        
        // Update cost summary
        const costSummary = document.querySelector('.cost-summary');
        if (costSummary) {
            costSummary.innerHTML = this.renderCostSummary().replace('<div class="cost-summary">', '').replace('</div>', '');
        }
    }

    saveBOM() {
        if (this.bomComponents.length === 0) {
            this.showError('Cannot save empty BOM');
            return;
        }

        const bomName = prompt('Enter BOM name:');
        if (!bomName) return;

        const bomData = {
            name: bomName,
            components: this.bomComponents.map(comp => ({
                item_id: comp.id,
                quantity: comp.quantity,
                unit_cost: comp.effective_cost
            })),
            total_cost: this.bomComponents.reduce((sum, comp) => 
                sum + (comp.quantity * comp.effective_cost), 0),
            created_via: 'drag_drop_builder'
        };

        // Save to localStorage for now (in production, save to backend)
        const savedBOMs = JSON.parse(localStorage.getItem('saved_boms') || '[]');
        savedBOMs.push({
            ...bomData,
            id: Date.now(),
            created_at: new Date().toISOString()
        });
        localStorage.setItem('saved_boms', JSON.stringify(savedBOMs));

        this.showSuccess(`BOM "${bomName}" saved successfully!`);
    }

    clearBOM() {
        if (this.bomComponents.length === 0) return;
        
        if (confirm('Clear all components from BOM?')) {
            this.bomComponents = [];
            this.updateDisplay();
            this.showSuccess('BOM cleared');
        }
    }

    bindEvents() {
        // Add drag leave event to remove visual feedback
        const dropZone = document.getElementById('bom-drop-zone');
        dropZone.addEventListener('dragleave', (e) => {
            if (!dropZone.contains(e.relatedTarget)) {
                dropZone.classList.remove('drag-over');
            }
        });
    }

    showDisabledMessage() {
        this.container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                Drag & Drop BOM Builder is currently disabled. 
                <a href="/cost-settings/" class="alert-link">Enable it in settings</a>.
            </div>
        `;
    }

    showError(message) {
        this.showAlert(message, 'danger');
    }

    showSuccess(message) {
        this.showAlert(message, 'success');
    }

    showAlert(message, type) {
        // Create temporary alert
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 300px;';
        alertDiv.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check' : 'exclamation-triangle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 3000);
    }
}

// Global BOM builder instance
let bomBuilder = null;

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    const builderContainer = document.getElementById('drag-drop-bom-container');
    if (builderContainer) {
        bomBuilder = new DragDropBOMBuilder(builderContainer);
    }
});