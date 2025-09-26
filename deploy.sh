#!/bin/bash

# Mercedes W222 OBD Scanner Deployment Script
# This script automates the deployment process on a server

set -e

echo "🚗 Mercedes W222 OBD Scanner Deployment Script"
echo "=============================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker installed successfully"
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose installed successfully"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p data
mkdir -p ssl

# Set up environment variables
if [ ! -f .env ]; then
    echo "📝 Creating environment file..."
    cat > .env << EOF
# AI API Keys (optional)
OPENAI_API_KEY=your_openai_api_key_here
GROK_API_KEY=your_grok_api_key_here

# Application settings
PYTHONPATH=/app
PYTHONUNBUFFERED=1
EOF
    echo "✅ Environment file created. Please edit .env with your API keys if needed."
fi

# Build and start the application
echo "🔨 Building and starting the application..."
docker-compose build
docker-compose up -d

# Wait for the application to start
echo "⏳ Waiting for application to start..."
sleep 10

# Check if the application is running
if curl -f http://localhost:8000 > /dev/null 2>&1; then
    echo "✅ Application is running successfully!"
    echo ""
    echo "🌐 Access the application at:"
    echo "   Local: http://localhost:8000"
    echo "   Network: http://$(hostname -I | awk '{print $1}'):8000"
    echo ""
    echo "📊 To view logs: docker-compose logs -f"
    echo "🛑 To stop: docker-compose down"
    echo "🔄 To restart: docker-compose restart"
else
    echo "❌ Application failed to start. Check logs with: docker-compose logs"
    exit 1
fi

# Display additional information
echo ""
echo "📋 Additional Information:"
echo "========================="
echo "• Data is stored in: ./data/"
echo "• Configuration files are in the project directory"
echo "• For production deployment, use: docker-compose --profile production up -d"
echo "• Make sure to configure SSL certificates in ./ssl/ for HTTPS"
echo ""
echo "🔧 Troubleshooting:"
echo "• If you can't access serial ports, make sure the user is in the dialout group"
echo "• For USB OBD adapters, they should appear as /dev/ttyUSB* or /dev/ttyACM*"
echo "• Check firewall settings if accessing from remote machines"
echo ""
echo "🎉 Deployment completed successfully!"
