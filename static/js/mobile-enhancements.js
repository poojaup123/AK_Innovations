/**
 * Mobile Enhancement JavaScript for Factory Management System
 * Provides touch-friendly interactions and mobile-specific functionality
 */

class MobileEnhancements {
    constructor() {
        this.isMobile = window.innerWidth <= 768;
        this.isTouchDevice = 'ontouchstart' in window;
        this.fabMenuOpen = false;
        
        this.init();
    }
    
    init() {
        this.setupViewportHandler();
        this.setupTouchEnhancements();
        this.setupMobileTable();
        this.setupMobileSearchableDropdowns();
        this.setupMobileFAB();
        this.setupSwipeGestures();
        this.setupMobileToasts();
        this.preventZoomOnInput();
        
        console.log('Mobile enhancements initialized');
    }
    
    setupViewportHandler() {
        // Dynamically adjust viewport for better mobile experience
        const viewport = document.querySelector('meta[name="viewport"]');
        if (viewport && this.isMobile) {
            viewport.setAttribute('content', 
                'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no'
            );
        }
        
        // Handle orientation changes
        window.addEventListener('orientationchange', () => {
            setTimeout(() => {
                this.handleOrientationChange();
            }, 100);
        });
    }
    
    handleOrientationChange() {
        // Refresh mobile table layout
        this.setupMobileTable();
        
        // Adjust searchable dropdowns
        const openDropdowns = document.querySelectorAll('.searchable-dropdown-menu.show');
        openDropdowns.forEach(dropdown => {
            dropdown.style.maxHeight = `${window.innerHeight * 0.6}px`;
        });
    }
    
    setupTouchEnhancements() {
        // Add touch feedback to buttons
        document.addEventListener('touchstart', (e) => {
            if (e.target.closest('.btn, .card, .list-group-item')) {
                e.target.closest('.btn, .card, .list-group-item').classList.add('touched');
            }
        });
        
        document.addEventListener('touchend', (e) => {
            setTimeout(() => {
                document.querySelectorAll('.touched').forEach(el => {
                    el.classList.remove('touched');
                });
            }, 150);
        });
        
        // Add touch-friendly hover states
        const style = document.createElement('style');
        style.textContent = `
            .touched {
                transform: scale(0.98);
                opacity: 0.8;
                transition: all 0.1s ease;
            }
            
            @media (hover: hover) {
                .btn:hover,
                .card:hover,
                .list-group-item:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    setupMobileTable() {
        if (!this.isMobile) return;
        
        const tables = document.querySelectorAll('.table-responsive');
        
        tables.forEach(tableContainer => {
            const table = tableContainer.querySelector('table');
            if (!table) return;
            
            // Create mobile card view
            const mobileContainer = document.createElement('div');
            mobileContainer.className = 'mobile-table-card d-block d-sm-none';
            
            const rows = table.querySelectorAll('tbody tr');
            const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent.trim());
            
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                const mobileCard = this.createMobileCard(cells, headers);
                mobileContainer.appendChild(mobileCard);
            });
            
            // Insert mobile container after table
            tableContainer.appendChild(mobileContainer);
            
            // Hide table on mobile
            table.classList.add('d-none', 'd-sm-table');
        });
    }
    
    createMobileCard(cells, headers) {
        const card = document.createElement('div');
        card.className = 'mobile-item-card';
        
        const header = document.createElement('div');
        header.className = 'mobile-item-header';
        
        const title = document.createElement('div');
        title.className = 'mobile-item-title';
        title.textContent = cells[1]?.textContent.trim() || cells[0]?.textContent.trim();
        
        const code = document.createElement('div');
        code.className = 'mobile-item-code';
        code.textContent = cells[0]?.textContent.trim();
        
        header.appendChild(title);
        header.appendChild(code);
        
        const details = document.createElement('div');
        details.className = 'mobile-item-details';
        
        // Add key details (skip first two as they're in header)
        for (let i = 2; i < Math.min(cells.length - 1, 6); i++) {
            if (headers[i] && cells[i]) {
                const detail = document.createElement('div');
                detail.className = 'mobile-detail-item';
                
                const label = document.createElement('div');
                label.className = 'mobile-detail-label';
                label.textContent = headers[i];
                
                const value = document.createElement('div');
                value.className = 'mobile-detail-value';
                value.innerHTML = cells[i].innerHTML;
                
                detail.appendChild(label);
                detail.appendChild(value);
                details.appendChild(detail);
            }
        }
        
        const actions = document.createElement('div');
        actions.className = 'mobile-item-actions';
        
        // Copy action buttons from last cell
        const lastCell = cells[cells.length - 1];
        if (lastCell) {
            const buttons = lastCell.querySelectorAll('.btn');
            buttons.forEach(btn => {
                const newBtn = btn.cloneNode(true);
                newBtn.className = newBtn.className.replace('btn-sm', '');
                actions.appendChild(newBtn);
            });
        }
        
        card.appendChild(header);
        card.appendChild(details);
        card.appendChild(actions);
        
        return card;
    }
    
    setupMobileSearchableDropdowns() {
        if (!this.isMobile) return;
        
        // Override searchable dropdown positioning for mobile
        document.addEventListener('DOMContentLoaded', () => {
            const originalSearchableDropdown = window.SearchableDropdown;
            if (originalSearchableDropdown) {
                window.SearchableDropdown = class extends originalSearchableDropdown {
                    positionDropdown() {
                        if (window.innerWidth <= 576) {
                            // Full-screen positioning for mobile
                            this.dropdown.style.position = 'fixed';
                            this.dropdown.style.left = '0.5rem';
                            this.dropdown.style.right = '0.5rem';
                            this.dropdown.style.top = 'auto';
                            this.dropdown.style.bottom = '1rem';
                            this.dropdown.style.maxHeight = '60vh';
                            this.dropdown.style.zIndex = '1060';
                        } else {
                            super.positionDropdown();
                        }
                    }
                    
                    handleInputFocus() {
                        super.handleInputFocus();
                        
                        if (window.innerWidth <= 576) {
                            // Scroll to element on focus for mobile
                            setTimeout(() => {
                                this.input.scrollIntoView({ 
                                    behavior: 'smooth', 
                                    block: 'center' 
                                });
                            }, 100);
                        }
                    }
                };
            }
        });
    }
    
    setupMobileFAB() {
        if (!this.isMobile) return;
        
        // Create floating action button for quick actions
        const fabContainer = document.createElement('div');
        fabContainer.className = 'mobile-quick-actions';
        fabContainer.innerHTML = `
            <div class="mobile-fab-menu" id="mobileFabMenu">
                <a href="/inventory/add" class="mobile-fab-item">
                    <i class="fas fa-plus"></i>
                    Add Item
                </a>
                <a href="/purchase/add" class="mobile-fab-item">
                    <i class="fas fa-shopping-cart"></i>
                    New Purchase
                </a>
                <a href="/job-work/add" class="mobile-fab-item">
                    <i class="fas fa-tasks"></i>
                    Create Job
                </a>
                <a href="/inventory/dashboard" class="mobile-fab-item">
                    <i class="fas fa-chart-bar"></i>
                    Dashboard
                </a>
            </div>
            <button class="mobile-fab primary" id="mobileFabToggle">
                <i class="fas fa-plus"></i>
            </button>
        `;
        
        document.body.appendChild(fabContainer);
        
        // FAB toggle functionality with null checks
        const fabToggle = document.getElementById('mobileFabToggle');
        const fabMenu = document.getElementById('mobileFabMenu');
        
        if (fabToggle && fabMenu) {
            fabToggle.addEventListener('click', () => {
                this.fabMenuOpen = !this.fabMenuOpen;
                fabMenu.classList.toggle('show', this.fabMenuOpen);
                fabToggle.innerHTML = this.fabMenuOpen 
                    ? '<i class="fas fa-times"></i>' 
                    : '<i class="fas fa-plus"></i>';
            });
        }
        
        // Close FAB menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!fabContainer.contains(e.target) && this.fabMenuOpen) {
                this.fabMenuOpen = false;
                fabMenu.classList.remove('show');
                fabToggle.innerHTML = '<i class="fas fa-plus"></i>';
            }
        });
    }
    
    setupSwipeGestures() {
        if (!this.isTouchDevice) return;
        
        let startX, startY, startTime;
        
        document.addEventListener('touchstart', (e) => {
            const touch = e.touches[0];
            startX = touch.clientX;
            startY = touch.clientY;
            startTime = Date.now();
        });
        
        document.addEventListener('touchend', (e) => {
            if (!startX || !startY) return;
            
            const touch = e.changedTouches[0];
            const endX = touch.clientX;
            const endY = touch.clientY;
            const endTime = Date.now();
            
            const diffX = startX - endX;
            const diffY = startY - endY;
            const diffTime = endTime - startTime;
            
            // Only process fast swipes
            if (diffTime > 300) return;
            
            // Horizontal swipe
            if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 100) {
                if (diffX > 0) {
                    // Swipe left - next page or close sidebar
                    this.handleSwipeLeft(e.target);
                } else {
                    // Swipe right - previous page or open sidebar
                    this.handleSwipeRight(e.target);
                }
            }
            
            // Vertical swipe
            if (Math.abs(diffY) > Math.abs(diffX) && Math.abs(diffY) > 100) {
                if (diffY > 0) {
                    // Swipe up - scroll to top or show more
                    this.handleSwipeUp(e.target);
                } else {
                    // Swipe down - refresh or scroll to bottom
                    this.handleSwipeDown(e.target);
                }
            }
            
            startX = startY = null;
        });
    }
    
    handleSwipeLeft(target) {
        // Close any open dropdowns or menus
        const openDropdowns = document.querySelectorAll('.show');
        openDropdowns.forEach(dropdown => {
            if (dropdown.classList.contains('dropdown-menu') || 
                dropdown.classList.contains('offcanvas')) {
                dropdown.classList.remove('show');
            }
        });
    }
    
    handleSwipeRight(target) {
        // Open navigation if available
        const navToggle = document.querySelector('[data-bs-toggle="offcanvas"]');
        if (navToggle) {
            navToggle.click();
        }
    }
    
    handleSwipeUp(target) {
        // Scroll to top of current section
        const section = target.closest('.card, .container, .row');
        if (section) {
            section.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
    
    handleSwipeDown(target) {
        // Pull to refresh functionality for certain pages
        if (window.scrollY === 0 && target.closest('.table-responsive, .card-body')) {
            this.showPullToRefresh();
        }
    }
    
    showPullToRefresh() {
        const toast = this.createToast('Pull to refresh', 'Swipe down to refresh data', 'info');
        this.showToast(toast);
    }
    
    setupMobileToasts() {
        // Create toast container for mobile
        if (!document.getElementById('mobileToastContainer')) {
            const container = document.createElement('div');
            container.id = 'mobileToastContainer';
            container.className = 'toast-container position-fixed top-0 start-50 translate-middle-x p-3';
            container.style.zIndex = '1080';
            document.body.appendChild(container);
        }
    }
    
    createToast(title, message, type = 'info') {
        const toastId = 'toast_' + Date.now();
        const iconClass = {
            success: 'fas fa-check-circle text-success',
            error: 'fas fa-exclamation-circle text-danger',
            warning: 'fas fa-exclamation-triangle text-warning',
            info: 'fas fa-info-circle text-info'
        }[type] || 'fas fa-info-circle text-info';
        
        const toastHtml = `
            <div class="toast" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <i class="${iconClass} me-2"></i>
                    <strong class="me-auto">${title}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = toastHtml;
        return tempDiv.firstElementChild;
    }
    
    showToast(toastElement) {
        const container = document.getElementById('mobileToastContainer');
        if (container) {
            container.appendChild(toastElement);
            
            const toast = new bootstrap.Toast(toastElement);
            toast.show();
        }
        
        // Remove toast after it's hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
    
    preventZoomOnInput() {
        // Prevent zoom on input focus for iOS
        if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
            const inputs = document.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                if (input.style.fontSize !== '16px') {
                    input.style.fontSize = '16px';
                }
            });
        }
    }
    
    // Utility methods for external use
    showMobileLoading(message = 'Loading...') {
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'mobileLoading';
        loadingDiv.className = 'mobile-loading';
        loadingDiv.innerHTML = `
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <div class="mobile-loading-text">${message}</div>
        `;
        
        document.body.appendChild(loadingDiv);
        return loadingDiv;
    }
    
    hideMobileLoading() {
        const loading = document.getElementById('mobileLoading');
        if (loading) {
            loading.remove();
        }
    }
    
    vibrate(pattern = [200]) {
        if ('vibrate' in navigator && this.isTouchDevice) {
            navigator.vibrate(pattern);
        }
    }
    
    showSuccessToast(message) {
        const toast = this.createToast('Success', message, 'success');
        this.showToast(toast);
        this.vibrate([100]);
    }
    
    showErrorToast(message) {
        const toast = this.createToast('Error', message, 'error');
        this.showToast(toast);
        this.vibrate([300, 100, 300]);
    }
    
    showInfoToast(message) {
        const toast = this.createToast('Info', message, 'info');
        this.showToast(toast);
    }
}

// Initialize mobile enhancements when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.mobileEnhancements = new MobileEnhancements();
});

// Export for external use
window.MobileEnhancements = MobileEnhancements;