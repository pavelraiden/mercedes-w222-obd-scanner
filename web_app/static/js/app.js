// Mercedes W222 OBD Scanner Web Interface JavaScript

class OBDScannerApp {
    constructor() {
        this.websocket = null;
        this.chart = null;
        this.chartData = {
            labels: [],
            datasets: [
                {
                    label: 'Температура ОЖ (°C)',
                    data: [],
                    borderColor: '#ff6384',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    tension: 0.4
                },
                {
                    label: 'Давление масла (бар)',
                    data: [],
                    borderColor: '#36a2eb',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    tension: 0.4
                },
                {
                    label: 'Обороты (/100)',
                    data: [],
                    borderColor: '#4bc0c0',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.4
                }
            ]
        };
        this.maxDataPoints = 50;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupTabs();
        this.setupChart();
        this.connectWebSocket();
        this.loadAvailablePorts();
        this.loadTripHistory();
    }

    setupEventListeners() {
        // Connection controls
        document.getElementById('connect-btn').addEventListener('click', () => this.connect());
        document.getElementById('disconnect-btn').addEventListener('click', () => this.disconnect());
        document.getElementById('refresh-ports').addEventListener('click', () => this.loadAvailablePorts());
    }

    setupTabs() {
        const tabButtons = document.querySelectorAll('.tab-button');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.getAttribute('data-tab');
                
                // Remove active class from all tabs and contents
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));
                
                // Add active class to clicked tab and corresponding content
                button.classList.add('active');
                document.getElementById(`${targetTab}-tab`).classList.add('active');
            });
        });
    }

    setupChart() {
        const ctx = document.getElementById('parameters-chart').getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'line',
            data: this.chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        display: false
                    },
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                animation: {
                    duration: 0
                }
            }
        });
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
        };
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            // Attempt to reconnect after 3 seconds
            setTimeout(() => this.connectWebSocket(), 3000);
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'data_update':
                this.updateParameter(data);
                this.updateChart(data);
                break;
            case 'status_update':
                this.updateStatus(data.status, data.message);
                break;
            case 'prediction_update':
                this.updateDiagnostics(data.predictions);
                break;
            case 'anomaly_detected':
                this.showAnomalyAlert(data);
                break;
        }
    }

    updateParameter(data) {
        const elementMap = {
            'coolant_temperature': 'coolant-temp',
            'oil_pressure': 'oil-pressure',
            'engine_rpm': 'engine-rpm',
            'transmission_fluid_temperature': 'trans-temp',
            'current_gear': 'current-gear',
            'air_strut_pressure_fl': 'air-pressure-fl',
            'air_strut_pressure_fr': 'air-pressure-fr'
        };

        const elementId = elementMap[data.name];
        if (elementId) {
            const element = document.getElementById(elementId);
            if (element) {
                element.textContent = `${data.value}${data.unit}`;
            }
        }
    }

    updateChart(data) {
        const now = new Date().toLocaleTimeString();
        
        // Add new data point
        this.chartData.labels.push(now);
        
        // Update datasets based on parameter name
        switch (data.name) {
            case 'coolant_temperature':
                this.chartData.datasets[0].data.push(data.value);
                break;
            case 'oil_pressure':
                this.chartData.datasets[1].data.push(data.value);
                break;
            case 'engine_rpm':
                this.chartData.datasets[2].data.push(data.value / 100); // Scale down RPM
                break;
        }

        // Limit data points
        if (this.chartData.labels.length > this.maxDataPoints) {
            this.chartData.labels.shift();
            this.chartData.datasets.forEach(dataset => {
                if (dataset.data.length > this.maxDataPoints) {
                    dataset.data.shift();
                }
            });
        }

        this.chart.update('none');
    }

    updateStatus(status, message) {
        const statusIndicator = document.querySelector('.status-dot');
        const statusText = document.getElementById('status-text');
        const connectBtn = document.getElementById('connect-btn');
        const disconnectBtn = document.getElementById('disconnect-btn');

        statusIndicator.className = `status-dot ${status}`;
        statusText.textContent = this.getStatusText(status);

        if (status === 'connected') {
            connectBtn.disabled = true;
            disconnectBtn.disabled = false;
        } else {
            connectBtn.disabled = false;
            disconnectBtn.disabled = true;
        }
    }

    getStatusText(status) {
        const statusMap = {
            'connected': 'Подключено',
            'disconnected': 'Отключено',
            'connecting': 'Подключение...',
            'error': 'Ошибка'
        };
        return statusMap[status] || status;
    }

    updateDiagnostics(predictions) {
        const diagnosticResults = document.getElementById('diagnostic-results');
        
        if (!predictions || predictions.length === 0) {
            diagnosticResults.innerHTML = '<p>Все системы работают нормально.</p>';
            return;
        }

        let html = '';
        predictions.forEach(prediction => {
            const severityClass = prediction.severity.toLowerCase();
            html += `
                <div class="diagnostic-item ${severityClass}">
                    <h4>${prediction.component}</h4>
                    <p><strong>Проблема:</strong> ${prediction.issue}</p>
                    <p><strong>Уровень:</strong> ${prediction.severity}</p>
                    <p><strong>Рекомендация:</strong> ${prediction.action}</p>
                    ${prediction.wear_index ? `<p><strong>Индекс износа:</strong> ${(prediction.wear_index * 100).toFixed(1)}%</p>` : ''}
                </div>
            `;
        });
        
        diagnosticResults.innerHTML = html;
    }

    showAnomalyAlert(data) {
        const anomalyResults = document.getElementById('anomaly-results');
        
        const alertHtml = `
            <div class="anomaly-alert">
                <h4>🚨 Обнаружена аномалия!</h4>
                <p><strong>Оценка аномалии:</strong> ${data.score.toFixed(3)}</p>
                <p><strong>Время:</strong> ${new Date().toLocaleString()}</p>
                <p>Система машинного обучения обнаружила необычное поведение параметров. Рекомендуется дополнительная диагностика.</p>
            </div>
        `;
        
        anomalyResults.innerHTML = alertHtml + anomalyResults.innerHTML;
    }

    async loadAvailablePorts() {
        try {
            const response = await fetch('/api/ports');
            const data = await response.json();
            
            const portSelect = document.getElementById('port-select');
            portSelect.innerHTML = '<option value="DEMO">DEMO</option>';
            
            data.ports.forEach(port => {
                if (port !== 'DEMO') {
                    const option = document.createElement('option');
                    option.value = port;
                    option.textContent = port;
                    portSelect.appendChild(option);
                }
            });
        } catch (error) {
            console.error('Error loading ports:', error);
        }
    }

    async connect() {
        const protocol = document.getElementById('protocol-select').value;
        const port = document.getElementById('port-select').value;
        const vehicleId = document.getElementById('vehicle-id').value;

        try {
            const response = await fetch('/api/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    protocol,
                    port,
                    vehicle_id: vehicleId || null
                })
            });

            if (response.ok) {
                console.log('Connection request sent');
            }
        } catch (error) {
            console.error('Error connecting:', error);
        }
    }

    async disconnect() {
        try {
            const response = await fetch('/api/disconnect', {
                method: 'POST'
            });

            if (response.ok) {
                console.log('Disconnect request sent');
            }
        } catch (error) {
            console.error('Error disconnecting:', error);
        }
    }

    async loadTripHistory() {
        try {
            const response = await fetch('/api/trip-history');
            const data = await response.json();
            
            const tripHistory = document.getElementById('trip-history');
            
            if (!data.trips || data.trips.length === 0) {
                tripHistory.innerHTML = '<p>История поездок пуста.</p>';
                return;
            }

            let html = '';
            data.trips.forEach(trip => {
                const startTime = new Date(trip.start_time).toLocaleString();
                const endTime = trip.end_time ? new Date(trip.end_time).toLocaleString() : 'В процессе';
                
                html += `
                    <div class="trip-item" onclick="this.loadTripDetails('${trip.session_id}')">
                        <h4>Поездка ${trip.session_id.substring(0, 8)}</h4>
                        <p><strong>Начало:</strong> ${startTime}</p>
                        <p><strong>Конец:</strong> ${endTime}</p>
                        <p><strong>Протокол:</strong> ${trip.protocol}</p>
                        ${trip.vehicle_id ? `<p><strong>VIN:</strong> ${trip.vehicle_id}</p>` : ''}
                    </div>
                `;
            });
            
            tripHistory.innerHTML = html;
        } catch (error) {
            console.error('Error loading trip history:', error);
        }
    }

    async loadTripDetails(sessionId) {
        try {
            const response = await fetch(`/api/trip-details/${sessionId}`);
            const data = await response.json();
            
            // Display trip details in a modal or expanded view
            console.log('Trip details:', data);
            // TODO: Implement trip details display
        } catch (error) {
            console.error('Error loading trip details:', error);
        }
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new OBDScannerApp();
});
