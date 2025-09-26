/**
 * Enhanced UI/UX System for Mercedes W222 OBD Scanner
 * Implements guided workflows, progressive disclosure, and contextual help
 */

class EnhancedUI {
    constructor() {
        this.currentWorkflow = null;
        this.userExperience = 'beginner'; // beginner, intermediate, expert
        this.contextualHelp = new ContextualHelp();
        this.progressiveDisclosure = new ProgressiveDisclosure();
        this.guidedWorkflows = new GuidedWorkflows();
        this.notifications = new NotificationSystem();
        
        this.init();
    }
    
    init() {
        this.detectUserExperience();
        this.setupEventListeners();
        this.initializeComponents();
        this.loadUserPreferences();
        
        console.log('🎨 Enhanced UI System initialized');
    }
    
    detectUserExperience() {
        // Detect user experience level based on usage patterns
        const usage = localStorage.getItem('usage_stats');
        if (usage) {
            const stats = JSON.parse(usage);
            if (stats.sessions > 50 && stats.advanced_features_used > 10) {
                this.userExperience = 'expert';
            } else if (stats.sessions > 10) {
                this.userExperience = 'intermediate';
            }
        }
        
        // Adjust UI complexity based on experience
        this.adjustUIComplexity();
    }
    
    adjustUIComplexity() {
        const body = document.body;
        body.classList.remove('ui-beginner', 'ui-intermediate', 'ui-expert');
        body.classList.add(`ui-${this.userExperience}`);
        
        // Show/hide features based on experience level
        if (this.userExperience === 'beginner') {
            this.hideAdvancedFeatures();
            this.enableGuidedMode();
        } else if (this.userExperience === 'expert') {
            this.showAllFeatures();
            this.enableCompactMode();
        }
    }
    
    hideAdvancedFeatures() {
        document.querySelectorAll('.advanced-feature').forEach(el => {
            el.style.display = 'none';
        });
    }
    
    showAllFeatures() {
        document.querySelectorAll('.advanced-feature').forEach(el => {
            el.style.display = 'block';
        });
    }
    
    enableGuidedMode() {
        // Show guided workflow buttons
        const guidedPanel = document.createElement('div');
        guidedPanel.className = 'guided-panel';
        guidedPanel.innerHTML = `
            <h3>🚗 Quick Start</h3>
            <button class="btn-guided" data-workflow="first-scan">
                <i class="icon-scan"></i>
                Perform First Scan
            </button>
            <button class="btn-guided" data-workflow="check-health">
                <i class="icon-health"></i>
                Check Vehicle Health
            </button>
            <button class="btn-guided" data-workflow="analyze-trip">
                <i class="icon-trip"></i>
                Analyze Recent Trip
            </button>
        `;
        
        const dashboard = document.querySelector('.dashboard-main');
        if (dashboard) {
            dashboard.insertBefore(guidedPanel, dashboard.firstChild);
        }
    }
    
    enableCompactMode() {
        document.body.classList.add('compact-mode');
        
        // Add expert shortcuts
        const shortcuts = document.createElement('div');
        shortcuts.className = 'expert-shortcuts';
        shortcuts.innerHTML = `
            <div class="shortcut-bar">
                <button title="Quick Scan (Ctrl+S)" data-shortcut="scan">⚡</button>
                <button title="Live Data (Ctrl+L)" data-shortcut="live">📊</button>
                <button title="Clear Codes (Ctrl+C)" data-shortcut="clear">🗑️</button>
                <button title="Export Data (Ctrl+E)" data-shortcut="export">💾</button>
            </div>
        `;
        
        document.querySelector('.header').appendChild(shortcuts);
    }
    
    setupEventListeners() {
        // Guided workflow buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-workflow]')) {
                const workflow = e.target.dataset.workflow;
                this.startGuidedWorkflow(workflow);
            }
            
            if (e.target.matches('[data-shortcut]')) {
                const shortcut = e.target.dataset.shortcut;
                this.executeShortcut(shortcut);
            }
            
            if (e.target.matches('.help-trigger')) {
                this.contextualHelp.show(e.target);
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey) {
                switch(e.key) {
                    case 's':
                        e.preventDefault();
                        this.executeShortcut('scan');
                        break;
                    case 'l':
                        e.preventDefault();
                        this.executeShortcut('live');
                        break;
                    case 'c':
                        e.preventDefault();
                        this.executeShortcut('clear');
                        break;
                    case 'e':
                        e.preventDefault();
                        this.executeShortcut('export');
                        break;
                }
            }
        });
        
        // Progressive disclosure triggers
        document.addEventListener('click', (e) => {
            if (e.target.matches('.disclosure-trigger')) {
                this.progressiveDisclosure.toggle(e.target);
            }
        });
    }
    
    startGuidedWorkflow(workflowType) {
        this.currentWorkflow = this.guidedWorkflows.start(workflowType);
        this.notifications.show(`Starting ${workflowType} workflow`, 'info');
    }
    
    executeShortcut(shortcut) {
        const actions = {
            'scan': () => this.triggerScan(),
            'live': () => this.showLiveData(),
            'clear': () => this.clearCodes(),
            'export': () => this.exportData()
        };
        
        if (actions[shortcut]) {
            actions[shortcut]();
        }
    }
    
    triggerScan() {
        // Trigger OBD scan
        if (window.obdController) {
            window.obdController.startScan();
            this.notifications.show('OBD scan started', 'success');
        }
    }
    
    showLiveData() {
        // Show live data panel
        const livePanel = document.querySelector('.live-data-panel');
        if (livePanel) {
            livePanel.classList.add('active');
        }
    }
    
    clearCodes() {
        // Clear diagnostic codes
        if (confirm('Clear all diagnostic trouble codes?')) {
            if (window.obdController) {
                window.obdController.clearCodes();
                this.notifications.show('Diagnostic codes cleared', 'warning');
            }
        }
    }
    
    exportData() {
        // Export current data
        if (window.dataExporter) {
            window.dataExporter.exportAll();
            this.notifications.show('Data export started', 'info');
        }
    }
    
    initializeComponents() {
        this.initializeDataVisualization();
        this.initializeResponsiveDesign();
        this.initializeAccessibility();
    }
    
    initializeDataVisualization() {
        // Enhanced data visualization with Chart.js
        const chartContainers = document.querySelectorAll('.chart-container');
        chartContainers.forEach(container => {
            const chartType = container.dataset.chartType;
            this.createChart(container, chartType);
        });
    }
    
    createChart(container, type) {
        const canvas = document.createElement('canvas');
        container.appendChild(canvas);
        
        const ctx = canvas.getContext('2d');
        
        // Chart configurations based on type
        const configs = {
            'engine-performance': {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Engine RPM',
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        data: []
                    }, {
                        label: 'Engine Load',
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        data: []
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top'
                        }
                    }
                }
            },
            'fuel-efficiency': {
                type: 'doughnut',
                data: {
                    labels: ['City', 'Highway', 'Combined'],
                    datasets: [{
                        data: [18, 25, 21],
                        backgroundColor: ['#3498db', '#2ecc71', '#f39c12']
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            }
        };
        
        if (configs[type]) {
            new Chart(ctx, configs[type]);
        }
    }
    
    initializeResponsiveDesign() {
        // Mobile-first responsive design
        const mobileBreakpoint = 768;
        
        const handleResize = () => {
            const isMobile = window.innerWidth < mobileBreakpoint;
            document.body.classList.toggle('mobile-layout', isMobile);
            
            if (isMobile) {
                this.enableMobileOptimizations();
            } else {
                this.enableDesktopOptimizations();
            }
        };
        
        window.addEventListener('resize', handleResize);
        handleResize(); // Initial call
    }
    
    enableMobileOptimizations() {
        // Touch-friendly interface
        document.querySelectorAll('.btn').forEach(btn => {
            btn.style.minHeight = '44px'; // iOS recommended touch target
            btn.style.minWidth = '44px';
        });
        
        // Swipe gestures for navigation
        this.enableSwipeGestures();
        
        // Collapsible panels
        document.querySelectorAll('.panel').forEach(panel => {
            panel.classList.add('collapsible');
        });
    }
    
    enableDesktopOptimizations() {
        // Hover effects
        document.querySelectorAll('.card').forEach(card => {
            card.addEventListener('mouseenter', () => {
                card.style.transform = 'translateY(-2px)';
                card.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
            });
            
            card.addEventListener('mouseleave', () => {
                card.style.transform = 'translateY(0)';
                card.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
            });
        });
    }
    
    enableSwipeGestures() {
        let startX, startY, endX, endY;
        
        document.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        });
        
        document.addEventListener('touchend', (e) => {
            endX = e.changedTouches[0].clientX;
            endY = e.changedTouches[0].clientY;
            
            const deltaX = endX - startX;
            const deltaY = endY - startY;
            
            // Horizontal swipe
            if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
                if (deltaX > 0) {
                    this.handleSwipeRight();
                } else {
                    this.handleSwipeLeft();
                }
            }
        });
    }
    
    handleSwipeRight() {
        // Navigate to previous panel
        const activePanel = document.querySelector('.panel.active');
        if (activePanel && activePanel.previousElementSibling) {
            activePanel.classList.remove('active');
            activePanel.previousElementSibling.classList.add('active');
        }
    }
    
    handleSwipeLeft() {
        // Navigate to next panel
        const activePanel = document.querySelector('.panel.active');
        if (activePanel && activePanel.nextElementSibling) {
            activePanel.classList.remove('active');
            activePanel.nextElementSibling.classList.add('active');
        }
    }
    
    initializeAccessibility() {
        // ARIA labels and roles
        document.querySelectorAll('.btn').forEach(btn => {
            if (!btn.getAttribute('aria-label') && btn.title) {
                btn.setAttribute('aria-label', btn.title);
            }
        });
        
        // Keyboard navigation
        document.querySelectorAll('.focusable').forEach(el => {
            el.setAttribute('tabindex', '0');
        });
        
        // Screen reader announcements
        this.setupScreenReaderAnnouncements();
    }
    
    setupScreenReaderAnnouncements() {
        const announcer = document.createElement('div');
        announcer.setAttribute('aria-live', 'polite');
        announcer.setAttribute('aria-atomic', 'true');
        announcer.className = 'sr-only';
        document.body.appendChild(announcer);
        
        this.announcer = announcer;
    }
    
    announce(message) {
        if (this.announcer) {
            this.announcer.textContent = message;
        }
    }
    
    loadUserPreferences() {
        const prefs = localStorage.getItem('ui_preferences');
        if (prefs) {
            const preferences = JSON.parse(prefs);
            this.applyPreferences(preferences);
        }
    }
    
    applyPreferences(preferences) {
        if (preferences.theme) {
            document.body.className = document.body.className.replace(/theme-\\w+/, '');
            document.body.classList.add(`theme-${preferences.theme}`);
        }
        
        if (preferences.compactMode) {
            document.body.classList.add('compact-mode');
        }
        
        if (preferences.highContrast) {
            document.body.classList.add('high-contrast');
        }
    }
    
    savePreferences() {
        const preferences = {
            theme: this.getCurrentTheme(),
            compactMode: document.body.classList.contains('compact-mode'),
            highContrast: document.body.classList.contains('high-contrast'),
            userExperience: this.userExperience
        };
        
        localStorage.setItem('ui_preferences', JSON.stringify(preferences));
    }
    
    getCurrentTheme() {
        const classList = document.body.classList;
        for (let className of classList) {
            if (className.startsWith('theme-')) {
                return className.replace('theme-', '');
            }
        }
        return 'default';
    }
}

class ContextualHelp {
    constructor() {
        this.helpData = {};
        this.loadHelpData();
    }
    
    loadHelpData() {
        this.helpData = {
            'obd-scan': {
                title: 'OBD Scan',
                content: 'Performs a comprehensive scan of your Mercedes W222 diagnostic systems. This will read all diagnostic trouble codes and current vehicle status.',
                tips: ['Ensure engine is running for live data', 'Turn off engine to clear codes safely']
            },
            'live-data': {
                title: 'Live Data Monitoring',
                content: 'Real-time monitoring of engine parameters including RPM, temperature, load, and fuel system status.',
                tips: ['Monitor while driving for accurate readings', 'Watch for unusual patterns or spikes']
            },
            'trip-analysis': {
                title: 'Trip Analysis',
                content: 'AI-powered analysis of your driving patterns, fuel efficiency, and vehicle performance during trips.',
                tips: ['Longer trips provide more accurate analysis', 'Compare different driving conditions']
            }
        };
    }
    
    show(trigger) {
        const helpKey = trigger.dataset.help;
        if (!helpKey || !this.helpData[helpKey]) return;
        
        const helpData = this.helpData[helpKey];
        
        // Create help popup
        const popup = document.createElement('div');
        popup.className = 'help-popup';
        popup.innerHTML = `
            <div class="help-content">
                <h4>${helpData.title}</h4>
                <p>${helpData.content}</p>
                ${helpData.tips ? `
                    <div class="help-tips">
                        <strong>Tips:</strong>
                        <ul>
                            ${helpData.tips.map(tip => `<li>${tip}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                <button class="help-close">×</button>
            </div>
        `;
        
        // Position popup
        const rect = trigger.getBoundingClientRect();
        popup.style.position = 'absolute';
        popup.style.top = `${rect.bottom + 10}px`;
        popup.style.left = `${rect.left}px`;
        
        document.body.appendChild(popup);
        
        // Close handler
        popup.querySelector('.help-close').addEventListener('click', () => {
            popup.remove();
        });
        
        // Auto-close after 10 seconds
        setTimeout(() => {
            if (popup.parentNode) {
                popup.remove();
            }
        }, 10000);
    }
}

class ProgressiveDisclosure {
    toggle(trigger) {
        const targetId = trigger.dataset.target;
        const target = document.getElementById(targetId);
        
        if (!target) return;
        
        const isExpanded = target.classList.contains('expanded');
        
        if (isExpanded) {
            target.classList.remove('expanded');
            trigger.textContent = trigger.textContent.replace('Hide', 'Show');
            trigger.setAttribute('aria-expanded', 'false');
        } else {
            target.classList.add('expanded');
            trigger.textContent = trigger.textContent.replace('Show', 'Hide');
            trigger.setAttribute('aria-expanded', 'true');
        }
    }
}

class GuidedWorkflows {
    constructor() {
        this.workflows = {
            'first-scan': new FirstScanWorkflow(),
            'check-health': new HealthCheckWorkflow(),
            'analyze-trip': new TripAnalysisWorkflow()
        };
    }
    
    start(workflowType) {
        if (this.workflows[workflowType]) {
            return this.workflows[workflowType].start();
        }
        return null;
    }
}

class FirstScanWorkflow {
    start() {
        const steps = [
            {
                title: 'Connect to Vehicle',
                content: 'Ensure your OBD adapter is connected to the vehicle diagnostic port.',
                action: 'checkConnection'
            },
            {
                title: 'Start Engine',
                content: 'Start your Mercedes W222 engine and let it idle for 30 seconds.',
                action: 'waitForEngine'
            },
            {
                title: 'Begin Scan',
                content: 'Click the scan button to read diagnostic codes and system status.',
                action: 'startScan'
            },
            {
                title: 'Review Results',
                content: 'Review the scan results and any diagnostic trouble codes found.',
                action: 'showResults'
            }
        ];
        
        return new WorkflowRunner(steps);
    }
}

class HealthCheckWorkflow {
    start() {
        const steps = [
            {
                title: 'System Overview',
                content: 'Get an overview of all vehicle systems and their current status.',
                action: 'systemOverview'
            },
            {
                title: 'Engine Health',
                content: 'Check engine parameters and performance indicators.',
                action: 'engineHealth'
            },
            {
                title: 'Emissions Check',
                content: 'Verify emissions system readiness and catalyst efficiency.',
                action: 'emissionsCheck'
            },
            {
                title: 'Generate Report',
                content: 'Generate a comprehensive health report for your vehicle.',
                action: 'generateReport'
            }
        ];
        
        return new WorkflowRunner(steps);
    }
}

class TripAnalysisWorkflow {
    start() {
        const steps = [
            {
                title: 'Select Trip',
                content: 'Choose a recent trip from your trip history for analysis.',
                action: 'selectTrip'
            },
            {
                title: 'AI Analysis',
                content: 'Our AI will analyze your driving patterns and vehicle performance.',
                action: 'runAnalysis'
            },
            {
                title: 'Review Insights',
                content: 'Review AI-generated insights about your driving efficiency.',
                action: 'showInsights'
            },
            {
                title: 'Get Recommendations',
                content: 'Receive personalized recommendations for improvement.',
                action: 'showRecommendations'
            }
        ];
        
        return new WorkflowRunner(steps);
    }
}

class WorkflowRunner {
    constructor(steps) {
        this.steps = steps;
        this.currentStep = 0;
        this.createWorkflowUI();
    }
    
    createWorkflowUI() {
        const overlay = document.createElement('div');
        overlay.className = 'workflow-overlay';
        
        const modal = document.createElement('div');
        modal.className = 'workflow-modal';
        modal.innerHTML = `
            <div class="workflow-header">
                <h3>Guided Workflow</h3>
                <button class="workflow-close">×</button>
            </div>
            <div class="workflow-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 0%"></div>
                </div>
                <span class="progress-text">Step 1 of ${this.steps.length}</span>
            </div>
            <div class="workflow-content">
                <h4 class="step-title"></h4>
                <p class="step-content"></p>
            </div>
            <div class="workflow-actions">
                <button class="btn-secondary workflow-prev" disabled>Previous</button>
                <button class="btn-primary workflow-next">Next</button>
            </div>
        `;
        
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
        
        this.overlay = overlay;
        this.modal = modal;
        
        this.setupEventListeners();
        this.showCurrentStep();
    }
    
    setupEventListeners() {
        this.modal.querySelector('.workflow-close').addEventListener('click', () => {
            this.close();
        });
        
        this.modal.querySelector('.workflow-prev').addEventListener('click', () => {
            this.previousStep();
        });
        
        this.modal.querySelector('.workflow-next').addEventListener('click', () => {
            this.nextStep();
        });
    }
    
    showCurrentStep() {
        const step = this.steps[this.currentStep];
        
        this.modal.querySelector('.step-title').textContent = step.title;
        this.modal.querySelector('.step-content').textContent = step.content;
        
        // Update progress
        const progress = ((this.currentStep + 1) / this.steps.length) * 100;
        this.modal.querySelector('.progress-fill').style.width = `${progress}%`;
        this.modal.querySelector('.progress-text').textContent = `Step ${this.currentStep + 1} of ${this.steps.length}`;
        
        // Update buttons
        this.modal.querySelector('.workflow-prev').disabled = this.currentStep === 0;
        this.modal.querySelector('.workflow-next').textContent = 
            this.currentStep === this.steps.length - 1 ? 'Finish' : 'Next';
        
        // Execute step action
        if (step.action && this[step.action]) {
            this[step.action]();
        }
    }
    
    nextStep() {
        if (this.currentStep < this.steps.length - 1) {
            this.currentStep++;
            this.showCurrentStep();
        } else {
            this.finish();
        }
    }
    
    previousStep() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this.showCurrentStep();
        }
    }
    
    finish() {
        this.close();
        // Show completion message
        if (window.enhancedUI) {
            window.enhancedUI.notifications.show('Workflow completed successfully!', 'success');
        }
    }
    
    close() {
        if (this.overlay && this.overlay.parentNode) {
            this.overlay.remove();
        }
    }
    
    // Workflow action methods
    checkConnection() {
        // Simulate connection check
        setTimeout(() => {
            this.modal.querySelector('.step-content').innerHTML += 
                '<br><span class="status-success">✓ Connection verified</span>';
        }, 1000);
    }
    
    waitForEngine() {
        // Simulate engine check
        setTimeout(() => {
            this.modal.querySelector('.step-content').innerHTML += 
                '<br><span class="status-success">✓ Engine running detected</span>';
        }, 2000);
    }
    
    startScan() {
        // Trigger actual scan
        if (window.obdController) {
            window.obdController.startScan();
        }
    }
    
    showResults() {
        // Show scan results
        this.modal.querySelector('.step-content').innerHTML += 
            '<br><span class="status-info">📊 Scan completed - 2 codes found</span>';
    }
}

class NotificationSystem {
    constructor() {
        this.container = this.createContainer();
    }
    
    createContainer() {
        const container = document.createElement('div');
        container.className = 'notification-container';
        document.body.appendChild(container);
        return container;
    }
    
    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        
        const icons = {
            'success': '✓',
            'error': '✗',
            'warning': '⚠',
            'info': 'ℹ'
        };
        
        notification.innerHTML = `
            <span class="notification-icon">${icons[type] || icons.info}</span>
            <span class="notification-message">${message}</span>
            <button class="notification-close">×</button>
        `;
        
        this.container.appendChild(notification);
        
        // Auto-remove
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, duration);
        
        // Manual close
        notification.querySelector('.notification-close').addEventListener('click', () => {
            notification.remove();
        });
        
        // Animate in
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
    }
}

// Initialize Enhanced UI when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.enhancedUI = new EnhancedUI();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { EnhancedUI, ContextualHelp, ProgressiveDisclosure, GuidedWorkflows, NotificationSystem };
}
