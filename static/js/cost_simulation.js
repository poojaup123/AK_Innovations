/**
 * Cost Simulation Engine
 * Phase 3: "What-if" scenarios for different material costs
 */

class CostSimulation {
    constructor(container, itemId) {
        this.container = container;
        this.itemId = itemId;
        this.baseScenario = null;
        this.scenarios = [];
        this.currentScenario = null;
        this.settings = null;
        this.init();
    }

    async init() {
        try {
            // Check if feature is enabled
            const settingsResponse = await fetch('/cost-settings/api/get');
            const settingsData = await settingsResponse.json();
            
            if (!settingsData.success || !settingsData.settings.phase3.cost_simulation) {
                this.showDisabledMessage();
                return;
            }
            
            this.settings = settingsData.settings;
            await this.loadBaseScenario();
            this.render();
            this.bindEvents();
        } catch (error) {
            console.error('Error initializing simulation:', error);
            this.showFallbackInterface();
        }
    }

    async loadBaseScenario() {
        try {
            const response = await fetch(`/cost-calculation/api/calculate/${this.itemId}?quantity=1`);
            const data = await response.json();
            
            if (data.success) {
                this.baseScenario = {
                    id: 'base',
                    name: 'Current Costs',
                    description: 'Based on current material and process costs',
                    data: data,
                    modifications: {},
                    isBase: true
                };
                this.currentScenario = this.baseScenario;
            } else {
                this.baseScenario = this.getFallbackScenario();
                this.currentScenario = this.baseScenario;
            }
        } catch (error) {
            console.error('Error loading base scenario:', error);
            this.baseScenario = this.getFallbackScenario();
            this.currentScenario = this.baseScenario;
        }
    }

    getFallbackScenario() {
        return {
            id: 'base',
            name: 'Demo Scenario',
            description: 'Sample cost simulation scenario',
            data: {
                success: true,
                item_name: 'Sample Item',
                manual_cost: 100.00,
                bom_cost: 95.50,
                cost_difference: 4.50
            },
            modifications: {},
            isBase: true
        };
    }

    render() {
        const html = `
            <div class="cost-simulation">
                <div class="simulation-header">
                    <h5><i class="fas fa-flask me-2"></i>Cost Simulation</h5>
                    <div class="simulation-controls">
                        <button class="btn btn-success btn-sm me-2" onclick="simulation.createNewScenario()">
                            <i class="fas fa-plus me-1"></i>New Scenario
                        </button>
                        <button class="btn btn-outline-secondary btn-sm" onclick="simulation.compareScenarios()">
                            <i class="fas fa-balance-scale me-1"></i>Compare
                        </button>
                    </div>
                </div>

                <div class="scenario-tabs mb-3">
                    ${this.renderScenarioTabs()}
                </div>

                <div class="scenario-content">
                    ${this.renderCurrentScenario()}
                </div>

                <div class="simulation-results mt-4">
                    ${this.renderSimulationResults()}
                </div>
            </div>
        `;
        
        this.container.innerHTML = html;
    }

    renderScenarioTabs() {
        const allScenarios = [this.baseScenario, ...this.scenarios];
        
        let html = '<ul class="nav nav-pills">';
        
        allScenarios.forEach(scenario => {
            const isActive = scenario.id === this.currentScenario.id;
            const badgeClass = scenario.isBase ? 'bg-primary' : 'bg-secondary';
            
            html += `
                <li class="nav-item">
                    <a class="nav-link ${isActive ? 'active' : ''}" 
                       href="#" onclick="simulation.switchScenario('${scenario.id}')">
                        ${scenario.name}
                        <span class="badge ${badgeClass} ms-1">${scenario.isBase ? 'Base' : 'Test'}</span>
                        ${!scenario.isBase ? `<button class="btn btn-sm ms-1" onclick="simulation.deleteScenario('${scenario.id}')"><i class="fas fa-times"></i></button>` : ''}
                    </a>
                </li>
            `;
        });
        
        html += '</ul>';
        return html;
    }

    renderCurrentScenario() {
        if (!this.currentScenario) return '';

        let html = `
            <div class="current-scenario">
                <div class="scenario-info mb-3">
                    <h6>${this.currentScenario.name}</h6>
                    <p class="text-muted mb-2">${this.currentScenario.description}</p>
                </div>
        `;

        if (!this.currentScenario.isBase) {
            html += `
                <div class="scenario-modifications mb-3">
                    <h6><i class="fas fa-edit me-2"></i>Modifications</h6>
                    ${this.renderModificationControls()}
                </div>
            `;
        }

        html += `
                <div class="scenario-breakdown">
                    ${this.renderScenarioBreakdown()}
                </div>
            </div>
        `;

        return html;
    }

    renderModificationControls() {
        if (!this.currentScenario.data.material_costs || !this.currentScenario.data.material_costs.details) {
            return '<p class="text-muted">No materials to modify</p>';
        }

        let html = '<div class="modification-controls">';
        
        this.currentScenario.data.material_costs.details.forEach((material, index) => {
            const currentModification = this.currentScenario.modifications[`material_${index}`] || {};
            const currentAdjustment = currentModification.adjustment || 0;
            
            html += `
                <div class="modification-item row mb-2">
                    <div class="col-6">
                        <label class="form-label">${material.item_name}</label>
                        <small class="text-muted d-block">Current: ₹${material.unit_cost.toFixed(2)}</small>
                    </div>
                    <div class="col-3">
                        <input type="number" class="form-control form-control-sm" 
                               placeholder="% change" value="${currentAdjustment}"
                               onchange="simulation.updateMaterialCost(${index}, this.value)">
                    </div>
                    <div class="col-3">
                        <div class="btn-group btn-group-sm" role="group">
                            <button class="btn btn-outline-danger" onclick="simulation.updateMaterialCost(${index}, -10)">-10%</button>
                            <button class="btn btn-outline-success" onclick="simulation.updateMaterialCost(${index}, 10)">+10%</button>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        return html;
    }

    renderScenarioBreakdown() {
        const data = this.currentScenario.data;
        const materialTotal = data.material_costs?.total || 0;
        const processTotal = data.process_costs?.total || 0;
        const totalCost = data.total_cost_per_unit;

        // Calculate variance from base scenario
        let variance = 0;
        let varianceClass = 'text-muted';
        if (!this.currentScenario.isBase && this.baseScenario) {
            variance = totalCost - this.baseScenario.data.total_cost_per_unit;
            varianceClass = variance > 0 ? 'text-danger' : 'text-success';
        }

        return `
            <div class="scenario-breakdown-box bg-light p-3 rounded">
                <div class="row">
                    <div class="col-md-6">
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
                    </div>
                    <div class="col-md-6">
                        ${!this.currentScenario.isBase ? `
                            <div class="variance-info">
                                <h6>Variance from Base</h6>
                                <div class="d-flex justify-content-between">
                                    <span>Cost Change:</span>
                                    <span class="fw-bold ${varianceClass}">
                                        ${variance >= 0 ? '+' : ''}₹${variance.toFixed(2)}
                                    </span>
                                </div>
                                <div class="d-flex justify-content-between">
                                    <span>Percentage:</span>
                                    <span class="fw-bold ${varianceClass}">
                                        ${variance >= 0 ? '+' : ''}${((variance / this.baseScenario.data.total_cost_per_unit) * 100).toFixed(1)}%
                                    </span>
                                </div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    renderSimulationResults() {
        if (this.scenarios.length === 0) {
            return '<div class="text-muted text-center">Create scenarios to see comparative analysis</div>';
        }

        const allScenarios = [this.baseScenario, ...this.scenarios];
        const minCost = Math.min(...allScenarios.map(s => s.data.total_cost_per_unit));
        const maxCost = Math.max(...allScenarios.map(s => s.data.total_cost_per_unit));

        let html = `
            <div class="simulation-results-container">
                <h6><i class="fas fa-chart-bar me-2"></i>Scenario Comparison</h6>
                <div class="scenario-comparison">
        `;

        allScenarios.forEach(scenario => {
            const cost = scenario.data.total_cost_per_unit;
            const isLowest = cost === minCost;
            const isHighest = cost === maxCost;
            const barWidth = ((cost - minCost) / (maxCost - minCost)) * 100 || 0;

            html += `
                <div class="scenario-bar mb-2">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <span class="fw-bold">${scenario.name}</span>
                        <span class="badge ${isLowest ? 'bg-success' : isHighest ? 'bg-danger' : 'bg-secondary'}">
                            ₹${cost.toFixed(2)}
                        </span>
                    </div>
                    <div class="progress" style="height: 8px;">
                        <div class="progress-bar ${isLowest ? 'bg-success' : isHighest ? 'bg-danger' : 'bg-primary'}" 
                             style="width: ${Math.max(barWidth, 5)}%"></div>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
                <div class="simulation-insights mt-3">
                    <div class="row">
                        <div class="col-6">
                            <div class="insight-card bg-success text-white p-2 rounded text-center">
                                <small>Lowest Cost</small>
                                <div class="fw-bold">₹${minCost.toFixed(2)}</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="insight-card bg-danger text-white p-2 rounded text-center">
                                <small>Highest Cost</small>
                                <div class="fw-bold">₹${maxCost.toFixed(2)}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        return html;
    }

    createNewScenario() {
        const scenarioName = prompt('Enter scenario name:');
        if (!scenarioName) return;

        const scenarioDescription = prompt('Enter scenario description (optional):') || 'Custom cost scenario';

        const newScenario = {
            id: `scenario_${Date.now()}`,
            name: scenarioName,
            description: scenarioDescription,
            data: JSON.parse(JSON.stringify(this.baseScenario.data)), // Deep copy
            modifications: {},
            isBase: false
        };

        this.scenarios.push(newScenario);
        this.currentScenario = newScenario;
        this.render();
    }

    switchScenario(scenarioId) {
        if (scenarioId === 'base') {
            this.currentScenario = this.baseScenario;
        } else {
            this.currentScenario = this.scenarios.find(s => s.id === scenarioId);
        }
        this.render();
    }

    deleteScenario(scenarioId) {
        if (confirm('Delete this scenario?')) {
            this.scenarios = this.scenarios.filter(s => s.id !== scenarioId);
            if (this.currentScenario.id === scenarioId) {
                this.currentScenario = this.baseScenario;
            }
            this.render();
        }
    }

    updateMaterialCost(materialIndex, adjustmentPercent) {
        if (this.currentScenario.isBase) return;

        const adjustment = parseFloat(adjustmentPercent) || 0;
        const materialKey = `material_${materialIndex}`;
        
        this.currentScenario.modifications[materialKey] = {
            adjustment: adjustment
        };

        // Recalculate costs
        this.recalculateScenarioCosts();
        this.render();
    }

    recalculateScenarioCosts() {
        if (this.currentScenario.isBase) return;

        const data = this.currentScenario.data;
        let newMaterialTotal = 0;

        // Apply modifications to material costs
        if (data.material_costs && data.material_costs.details) {
            data.material_costs.details.forEach((material, index) => {
                const modification = this.currentScenario.modifications[`material_${index}`];
                if (modification) {
                    const adjustmentFactor = 1 + (modification.adjustment / 100);
                    material.adjusted_unit_cost = material.unit_cost * adjustmentFactor;
                    material.adjusted_total_cost = material.adjusted_unit_cost * material.quantity;
                    newMaterialTotal += material.adjusted_total_cost;
                } else {
                    material.adjusted_unit_cost = material.unit_cost;
                    material.adjusted_total_cost = material.total_cost;
                    newMaterialTotal += material.total_cost;
                }
            });
            
            data.material_costs.total = newMaterialTotal;
        }

        // Recalculate total cost
        const processTotal = data.process_costs?.total || 0;
        data.total_cost_per_unit = newMaterialTotal + processTotal;
    }

    compareScenarios() {
        // Create comparison modal or navigate to comparison page
        const allScenarios = [this.baseScenario, ...this.scenarios];
        
        // For now, just show an alert with comparison
        let comparisonText = 'Scenario Comparison:\n\n';
        allScenarios.forEach(scenario => {
            comparisonText += `${scenario.name}: ₹${scenario.data.total_cost_per_unit.toFixed(2)}\n`;
        });
        
        alert(comparisonText);
    }

    showDisabledMessage() {
        this.container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                Cost simulation is currently disabled. 
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
                Cost Simulation ready for "what-if" scenarios and cost analysis
            </div>
            <div class="cost-simulation mt-3">
                <div class="simulation-header">
                    <h6><i class="fas fa-flask me-2"></i>Cost Simulation</h6>
                    <div class="simulation-actions">
                        <button class="btn btn-sm btn-success" disabled>
                            <i class="fas fa-plus me-1"></i>New Scenario
                        </button>
                        <button class="btn btn-sm btn-outline-secondary" disabled>
                            <i class="fas fa-chart-line me-1"></i>Compare
                        </button>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-header bg-primary text-white">
                                <h6 class="mb-0">Base Scenario</h6>
                            </div>
                            <div class="card-body">
                                <div class="scenario-item">
                                    <div class="d-flex justify-content-between mb-2">
                                        <span>Material Cost:</span>
                                        <span class="fw-bold">₹100.00</span>
                                    </div>
                                    <div class="d-flex justify-content-between mb-2">
                                        <span>Labor Cost:</span>
                                        <span class="fw-bold">₹25.00</span>
                                    </div>
                                    <hr>
                                    <div class="d-flex justify-content-between">
                                        <span class="fw-bold">Total:</span>
                                        <span class="fw-bold text-success">₹125.00</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-header bg-warning text-dark">
                                <h6 class="mb-0">Scenario Adjustments</h6>
                            </div>
                            <div class="card-body">
                                <div class="form-group mb-3">
                                    <label class="form-label">Material Cost Change (%)</label>
                                    <input type="range" class="form-range" min="-50" max="50" value="0" disabled>
                                    <small class="text-muted">0% change</small>
                                </div>
                                
                                <div class="form-group mb-3">
                                    <label class="form-label">Labor Cost Change (%)</label>
                                    <input type="range" class="form-range" min="-50" max="50" value="0" disabled>
                                    <small class="text-muted">0% change</small>
                                </div>
                                
                                <button class="btn btn-primary btn-sm w-100" disabled>
                                    <i class="fas fa-calculator me-1"></i>Calculate Impact
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-header bg-success text-white">
                                <h6 class="mb-0">Scenario Results</h6>
                            </div>
                            <div class="card-body">
                                <div class="text-center">
                                    <h5 class="text-success mb-2">₹125.00</h5>
                                    <p class="text-muted mb-2">New Total Cost</p>
                                    <div class="badge bg-light text-dark">
                                        <i class="fas fa-equals me-1"></i>No Change
                                    </div>
                                </div>
                                
                                <hr>
                                
                                <div class="d-flex justify-content-between text-sm">
                                    <span>Cost Difference:</span>
                                    <span class="fw-bold">₹0.00</span>
                                </div>
                                <div class="d-flex justify-content-between text-sm">
                                    <span>Percentage Change:</span>
                                    <span class="fw-bold">0.0%</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-3">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0">Scenario Comparison Chart</h6>
                            </div>
                            <div class="card-body text-center py-4">
                                <i class="fas fa-chart-bar fa-2x text-muted mb-2"></i>
                                <p class="text-muted">Cost comparison visualization would appear here</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
}

// Global simulation instance
let simulation = null;

// Initialize simulation when page loads
document.addEventListener('DOMContentLoaded', function() {
    const simulationContainer = document.getElementById('cost-simulation-container');
    if (simulationContainer) {
        const itemId = simulationContainer.dataset.itemId;
        simulation = new CostSimulation(simulationContainer, itemId);
    }
});