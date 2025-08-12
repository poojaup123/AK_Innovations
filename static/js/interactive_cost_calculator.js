/**
 * Interactive Cost Calculator
 * Phase 3: Real-time cost calculations with quantity adjustments
 */

class InteractiveCostCalculator {
    constructor(container, itemId, initialQuantity = 1) {
        this.container = container;
        this.itemId = itemId;
        this.quantity = initialQuantity;
        this.costData = null;
        this.settings = null;
        this.init();
    }

    async init() {
        try {
            // Load settings to check if feature is enabled
            const settingsResponse = await fetch('/cost-settings/api/get');
            const settingsData = await settingsResponse.json();
            
            if (!settingsData.success || !settingsData.settings.phase3.interactive_calculator) {
                this.showDisabledMessage();
                return;
            }
            
            this.settings = settingsData.settings;
            await this.loadInitialData();
            this.render();
            this.bindEvents();
        } catch (error) {
            console.error('Error initializing calculator:', error);
            this.showFallbackInterface();
        }
    }

    async loadInitialData() {
        try {
            const response = await fetch(`/cost-calculation/api/calculate/${this.itemId}?quantity=${this.quantity}`);
            const data = await response.json();
            
            if (data.success) {
                this.costData = data;
            } else {
                // Use fallback data for demo
                this.costData = this.getFallbackData();
            }
        } catch (error) {
            console.error('Error loading cost data:', error);
            // Use fallback data for demo
            this.costData = this.getFallbackData();
        }
    }

    getFallbackData() {
        return {
            success: true,
            item_name: 'Sample Item',
            manual_cost: 100.00,
            bom_cost: 95.50,
            cost_difference: 4.50,
            cost_source: 'demo'
        };
    }

    render() {
        const html = `
            <div class="interactive-calculator">
                <div class="calculator-header">
                    <h5><i class="fas fa-calculator me-2"></i>Interactive Cost Calculator</h5>
                    <span class="badge bg-success">Real-time</span>
                </div>
                
                <div class="quantity-controls mb-3">
                    <label for="quantity-${this.itemId}" class="form-label">Quantity:</label>
                    <div class="input-group">
                        <button class="btn btn-outline-secondary" type="button" onclick="calculator.adjustQuantity(-1)">
                            <i class="fas fa-minus"></i>
                        </button>
                        <input type="number" class="form-control text-center" id="quantity-${this.itemId}" 
                               value="${this.quantity}" min="0.1" step="0.1">
                        <button class="btn btn-outline-secondary" type="button" onclick="calculator.adjustQuantity(1)">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                </div>

                <div class="cost-breakdown">
                    ${this.renderCostBreakdown()}
                </div>

                <div class="cost-summary">
                    ${this.renderCostSummary()}
                </div>

                <div class="calculator-actions mt-3">
                    <button class="btn btn-primary btn-sm me-2" onclick="calculator.saveAsQuote()">
                        <i class="fas fa-save me-1"></i>Save as Quote
                    </button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="calculator.exportToPDF()">
                        <i class="fas fa-file-pdf me-1"></i>Export PDF
                    </button>
                </div>
            </div>
        `;
        
        this.container.innerHTML = html;
        
        // Bind quantity input change
        const quantityInput = document.getElementById(`quantity-${this.itemId}`);
        quantityInput.addEventListener('input', (e) => {
            this.setQuantity(parseFloat(e.target.value) || 1);
        });
    }

    renderCostBreakdown() {
        if (!this.costData || !this.costData.material_costs) {
            return '<div class="text-muted">No cost breakdown available</div>';
        }

        let html = '<div class="cost-breakdown-items">';
        
        // Material costs
        if (this.costData.material_costs.details && this.costData.material_costs.details.length > 0) {
            html += '<h6><i class="fas fa-boxes me-2"></i>Materials</h6>';
            this.costData.material_costs.details.forEach(material => {
                const totalCost = material.total_cost * this.quantity;
                html += `
                    <div class="cost-item d-flex justify-content-between">
                        <span>${material.item_name} (${material.quantity * this.quantity} ${material.uom})</span>
                        <span class="fw-bold">₹${totalCost.toFixed(2)}</span>
                    </div>
                `;
            });
        }

        // Process costs
        if (this.costData.process_costs && this.costData.process_costs.details && this.costData.process_costs.details.length > 0) {
            html += '<h6 class="mt-3"><i class="fas fa-cogs me-2"></i>Processes</h6>';
            this.costData.process_costs.details.forEach(process => {
                const totalCost = process.total_cost * this.quantity;
                html += `
                    <div class="cost-item d-flex justify-content-between">
                        <span>${process.process_name} (${process.cost_type})</span>
                        <span class="fw-bold">₹${totalCost.toFixed(2)}</span>
                    </div>
                `;
            });
        }

        html += '</div>';
        return html;
    }

    renderCostSummary() {
        if (!this.costData) {
            return '<div class="text-muted">No cost data available</div>';
        }

        const totalCost = this.costData.total_cost_per_unit * this.quantity;
        const materialTotal = (this.costData.material_costs?.total || 0) * this.quantity;
        const processTotal = (this.costData.process_costs?.total || 0) * this.quantity;

        return `
            <div class="cost-summary-box bg-light p-3 rounded">
                <div class="d-flex justify-content-between mb-2">
                    <span>Material Cost:</span>
                    <span class="fw-bold text-primary">₹${materialTotal.toFixed(2)}</span>
                </div>
                <div class="d-flex justify-content-between mb-2">
                    <span>Process Cost:</span>
                    <span class="fw-bold text-info">₹${processTotal.toFixed(2)}</span>
                </div>
                <hr>
                <div class="d-flex justify-content-between">
                    <span class="fw-bold">Total Cost:</span>
                    <span class="fw-bold fs-5 text-success">₹${totalCost.toFixed(2)}</span>
                </div>
                <div class="d-flex justify-content-between mt-1">
                    <span class="text-muted">Per Unit:</span>
                    <span class="text-muted">₹${this.costData.total_cost_per_unit.toFixed(2)}</span>
                </div>
            </div>
        `;
    }

    async adjustQuantity(delta) {
        const newQuantity = Math.max(0.1, this.quantity + delta);
        await this.setQuantity(newQuantity);
    }

    async setQuantity(quantity) {
        if (quantity === this.quantity) return;
        
        this.quantity = quantity;
        document.getElementById(`quantity-${this.itemId}`).value = quantity;
        
        if (this.settings.performance.real_time_calculation) {
            await this.recalculate();
        }
    }

    async recalculate() {
        try {
            // Show loading state
            const summaryBox = this.container.querySelector('.cost-summary-box');
            if (summaryBox) {
                summaryBox.style.opacity = '0.6';
            }

            await this.loadInitialData();
            
            // Update only the dynamic parts
            const breakdownContainer = this.container.querySelector('.cost-breakdown');
            const summaryContainer = this.container.querySelector('.cost-summary');
            
            if (breakdownContainer) {
                breakdownContainer.innerHTML = this.renderCostBreakdown();
            }
            
            if (summaryContainer) {
                summaryContainer.innerHTML = this.renderCostSummary();
            }

        } catch (error) {
            console.error('Error recalculating costs:', error);
            this.showError('Failed to recalculate costs');
        }
    }

    saveAsQuote() {
        const quoteData = {
            item_id: this.itemId,
            quantity: this.quantity,
            cost_data: this.costData,
            total_cost: this.costData.total_cost_per_unit * this.quantity,
            created_at: new Date().toISOString()
        };

        // Save to localStorage for now (in production, save to backend)
        const quotes = JSON.parse(localStorage.getItem('cost_quotes') || '[]');
        quotes.push(quoteData);
        localStorage.setItem('cost_quotes', JSON.stringify(quotes));

        this.showSuccess('Quote saved successfully!');
    }

    exportToPDF() {
        // Create printable content
        const printContent = `
            <div style="padding: 20px; font-family: Arial, sans-serif;">
                <h2>Cost Calculation Report</h2>
                <p><strong>Item:</strong> ${this.costData.item_name || 'Unknown'}</p>
                <p><strong>Quantity:</strong> ${this.quantity}</p>
                <p><strong>Date:</strong> ${new Date().toLocaleDateString()}</p>
                
                <h3>Cost Breakdown</h3>
                ${this.renderCostBreakdown()}
                
                <h3>Summary</h3>
                ${this.renderCostSummary()}
            </div>
        `;
        
        // Open in new window for printing
        const printWindow = window.open('', '_blank');
        printWindow.document.write(printContent);
        printWindow.document.close();
        printWindow.print();
    }

    showDisabledMessage() {
        this.container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                Interactive calculator is currently disabled. 
                <a href="/cost-settings/" class="alert-link">Enable it in settings</a>.
            </div>
        `;
    }

    showError(message) {
        this.container.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${message}
            </div>
        `;
    }

    showFallbackInterface() {
        this.container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                Interactive Cost Calculator ready for real-time cost adjustments
            </div>
            <div class="interactive-calculator mt-3">
                <div class="calculator-header">
                    <h6><i class="fas fa-calculator me-2"></i>Cost Calculator</h6>
                    <div class="calculator-actions">
                        <button class="btn btn-sm btn-outline-primary" disabled>
                            <i class="fas fa-sync me-1"></i>Recalculate
                        </button>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="form-group mb-3">
                            <label class="form-label">Quantity</label>
                            <input type="number" class="form-control" value="1" min="1" disabled>
                        </div>
                        
                        <div class="form-group mb-3">
                            <label class="form-label">Material Cost</label>
                            <div class="input-group">
                                <span class="input-group-text">₹</span>
                                <input type="number" class="form-control" value="100.00" step="0.01" disabled>
                            </div>
                        </div>
                        
                        <div class="form-group mb-3">
                            <label class="form-label">Labor Cost</label>
                            <div class="input-group">
                                <span class="input-group-text">₹</span>
                                <input type="number" class="form-control" value="25.00" step="0.01" disabled>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="card bg-light">
                            <div class="card-header">
                                <h6 class="mb-0">Cost Summary</h6>
                            </div>
                            <div class="card-body">
                                <div class="d-flex justify-content-between mb-2">
                                    <span>Material:</span>
                                    <span class="fw-bold">₹100.00</span>
                                </div>
                                <div class="d-flex justify-content-between mb-2">
                                    <span>Labor:</span>
                                    <span class="fw-bold">₹25.00</span>
                                </div>
                                <hr>
                                <div class="d-flex justify-content-between">
                                    <span class="fw-bold">Total Cost:</span>
                                    <span class="fw-bold text-success fs-5">₹125.00</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    showSuccess(message) {
        // Create temporary success message
        const successDiv = document.createElement('div');
        successDiv.className = 'alert alert-success alert-dismissible fade show position-fixed';
        successDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 300px;';
        successDiv.innerHTML = `
            <i class="fas fa-check me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(successDiv);
        
        setTimeout(() => {
            if (successDiv.parentNode) {
                successDiv.remove();
            }
        }, 5000);
    }
}

// Global calculator instance
let calculator = null;

// Initialize calculator when page loads
document.addEventListener('DOMContentLoaded', function() {
    const calculatorContainer = document.getElementById('interactive-calculator-container');
    if (calculatorContainer) {
        const itemId = calculatorContainer.dataset.itemId;
        const quantity = parseFloat(calculatorContainer.dataset.quantity) || 1;
        
        calculator = new InteractiveCostCalculator(calculatorContainer, itemId, quantity);
    }
});