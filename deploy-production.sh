#!/bin/bash

# Mercedes W222 OBD Scanner - Production Deployment Script
# This script handles the complete production deployment with monitoring and security

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="mercedes-obd-scanner"
BACKUP_DIR="./backups"
LOG_FILE="./logs/deployment.log"

# Functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

# Check requirements
check_requirements() {
    log "Checking system requirements..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
    fi
    
    # Check available disk space (minimum 5GB)
    available_space=$(df . | tail -1 | awk '{print $4}')
    if [ "$available_space" -lt 5242880 ]; then
        warning "Available disk space is less than 5GB. Consider freeing up space."
    fi
    
    # Check available memory (minimum 2GB)
    available_memory=$(free -m | awk 'NR==2{printf "%.0f", $7}')
    if [ "$available_memory" -lt 2048 ]; then
        warning "Available memory is less than 2GB. Performance may be affected."
    fi
    
    success "System requirements check completed"
}

# Create necessary directories
create_directories() {
    log "Creating necessary directories..."
    
    mkdir -p data logs ml/models backups ssl docker/grafana/{provisioning,dashboards}
    
    # Set proper permissions
    chmod 755 data logs ml/models backups
    
    success "Directories created successfully"
}

# Generate environment file
generate_env_file() {
    log "Generating environment configuration..."
    
    if [ ! -f .env ]; then
        cat > .env << EOF
# Mercedes W222 OBD Scanner - Production Environment

# API Keys (REQUIRED - Set your actual keys)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Database
POSTGRES_PASSWORD=$(openssl rand -base64 32)
DATABASE_URL=postgresql://mercedes:\${POSTGRES_PASSWORD}@postgres:5432/mercedes_obd

# Security
SECRET_KEY=$(openssl rand -base64 32)
JWT_SECRET_KEY=$(openssl rand -base64 32)

# Monitoring
GRAFANA_PASSWORD=$(openssl rand -base64 16)

# Application
ENVIRONMENT=production
DEBUG=false
WORKERS=4
LOG_LEVEL=info

# Redis
REDIS_URL=redis://redis:6379/0

# Backup
BACKUP_RETENTION_DAYS=30
EOF
        
        warning "Environment file created. Please edit .env and set your API keys!"
        warning "ANTHROPIC_API_KEY and OPENAI_API_KEY are required for AI features."
    else
        log "Environment file already exists"
    fi
}

# Setup monitoring configuration
setup_monitoring() {
    log "Setting up monitoring configuration..."
    
    # Prometheus configuration
    cat > docker/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'mercedes-obd-scanner'
    static_configs:
      - targets: ['mercedes-obd-scanner:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
EOF

    # Grafana provisioning
    mkdir -p docker/grafana/provisioning/{datasources,dashboards}
    
    cat > docker/grafana/provisioning/datasources/prometheus.yml << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF

    cat > docker/grafana/provisioning/dashboards/dashboard.yml << EOF
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
EOF

    success "Monitoring configuration completed"
}

# Build and deploy
deploy() {
    log "Starting deployment..."
    
    # Pull latest changes (if in git repository)
    if [ -d .git ]; then
        log "Pulling latest changes from git..."
        git pull origin main || warning "Failed to pull latest changes"
    fi
    
    # Build and start services
    log "Building Docker images..."
    docker-compose -f docker-compose.production.yml build --no-cache
    
    log "Starting services..."
    docker-compose -f docker-compose.production.yml up -d
    
    # Wait for services to be ready
    log "Waiting for services to be ready..."
    sleep 30
    
    # Health check
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        success "Application is running and healthy!"
    else
        error "Application health check failed"
    fi
    
    success "Deployment completed successfully!"
}

# Backup existing data
backup_data() {
    if [ -d data ] && [ "$(ls -A data)" ]; then
        log "Creating backup of existing data..."
        
        backup_filename="mercedes-obd-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
        tar -czf "$BACKUP_DIR/$backup_filename" data/ logs/ 2>/dev/null || true
        
        success "Backup created: $backup_filename"
    fi
}

# Setup SSL certificates (optional)
setup_ssl() {
    if [ "$1" = "--ssl" ]; then
        log "Setting up SSL certificates..."
        
        if [ ! -f ssl/cert.pem ] || [ ! -f ssl/key.pem ]; then
            log "Generating self-signed SSL certificate..."
            mkdir -p ssl
            openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes \
                -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
            
            warning "Self-signed certificate generated. Replace with proper certificates for production."
        fi
        
        # Enable SSL profile
        export COMPOSE_PROFILES=ssl
    fi
}

# Show deployment information
show_info() {
    log "Deployment Information:"
    echo ""
    echo "🚗 Mercedes W222 OBD Scanner - Production Deployment"
    echo ""
    echo "📊 Services:"
    echo "  • Main Application: http://localhost"
    echo "  • API Endpoint: http://localhost:8000"
    echo "  • Grafana Dashboard: http://localhost:3000"
    echo "  • Prometheus Metrics: http://localhost:9090"
    echo ""
    echo "📁 Important Directories:"
    echo "  • Data: ./data/"
    echo "  • Logs: ./logs/"
    echo "  • Models: ./ml/models/"
    echo "  • Backups: ./backups/"
    echo ""
    echo "🔧 Management Commands:"
    echo "  • View logs: docker-compose -f docker-compose.production.yml logs -f"
    echo "  • Stop services: docker-compose -f docker-compose.production.yml down"
    echo "  • Restart services: docker-compose -f docker-compose.production.yml restart"
    echo "  • Update: ./deploy-production.sh --update"
    echo ""
    echo "⚠️  Important Notes:"
    echo "  • Edit .env file and set your API keys"
    echo "  • Default Grafana login: admin/admin (change on first login)"
    echo "  • Monitor logs for any issues"
    echo "  • Set up regular backups for production use"
    echo ""
}

# Update deployment
update_deployment() {
    log "Updating deployment..."
    
    # Backup before update
    backup_data
    
    # Pull latest changes
    if [ -d .git ]; then
        git pull origin main
    fi
    
    # Rebuild and restart
    docker-compose -f docker-compose.production.yml down
    docker-compose -f docker-compose.production.yml build --no-cache
    docker-compose -f docker-compose.production.yml up -d
    
    success "Deployment updated successfully!"
}

# Cleanup old backups
cleanup_backups() {
    log "Cleaning up old backups..."
    
    find "$BACKUP_DIR" -name "mercedes-obd-backup-*.tar.gz" -mtime +30 -delete 2>/dev/null || true
    
    success "Old backups cleaned up"
}

# Main execution
main() {
    log "Starting Mercedes W222 OBD Scanner production deployment..."
    
    # Parse arguments
    case "${1:-}" in
        --update)
            update_deployment
            exit 0
            ;;
        --backup)
            backup_data
            exit 0
            ;;
        --cleanup)
            cleanup_backups
            exit 0
            ;;
        --ssl)
            setup_ssl --ssl
            ;;
        --help)
            echo "Usage: $0 [--update|--backup|--cleanup|--ssl|--help]"
            echo ""
            echo "Options:"
            echo "  --update    Update existing deployment"
            echo "  --backup    Create backup of current data"
            echo "  --cleanup   Remove old backups"
            echo "  --ssl       Deploy with SSL support"
            echo "  --help      Show this help message"
            exit 0
            ;;
    esac
    
    # Run deployment steps
    check_requirements
    create_directories
    generate_env_file
    setup_monitoring
    backup_data
    deploy
    cleanup_backups
    show_info
    
    success "Mercedes W222 OBD Scanner deployed successfully!"
    warning "Don't forget to configure your API keys in the .env file!"
}

# Run main function
main "$@"
