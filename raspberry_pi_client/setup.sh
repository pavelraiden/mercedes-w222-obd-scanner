#!/bin/bash

# Automated setup script for the Mercedes W222 OBD Scanner Raspberry Pi Client

set -e

echo "Mercedes W222 OBD Scanner - Raspberry Pi Client Setup"
echo "======================================================"

# Check for root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root. Please use sudo." >&2
    exit 1
fi

# --- Create Virtual Environment ---
echo "[1/5] Creating Python virtual environment..."
python3 -m venv /opt/obd_client_venv
source /opt/obd_client_venv/bin/activate

# --- Install Python Dependencies ---
echo "[2/5] Installing Python dependencies..."
pip install -r requirements.txt

# --- Configure Client ---
echo "[3/5] Configuring client..."

read -p "Enter your username: " username
read -s -p "Enter your password: " password
echo
read -p "Enter your device ID: " device_id

CONFIG_FILE="/etc/obd_client.conf"

echo "[auth]" > $CONFIG_FILE
echo "username = $username" >> $CONFIG_FILE
echo "password = $password" >> $CONFIG_FILE
echo "device_id = $device_id" >> $CONFIG_FILE

echo "[obd]" >> $CONFIG_FILE
echo "port = /dev/rfcomm0" >> $CONFIG_FILE
echo "baudrate = 9600" >> $CONFIG_FILE

chmod 600 $CONFIG_FILE

echo "Configuration saved to $CONFIG_FILE"

# --- Set up Systemd Service ---
echo "[4/5] Setting up systemd service..."

SERVICE_FILE="/etc/systemd/system/obd-client.service"

cat > $SERVICE_FILE << EOL
[Unit]
Description=Mercedes W222 OBD Scanner Client
After=network.target

[Service]
User=pi
Group=pi
WorkingDirectory=$(pwd)/raspberry_pi_client
ExecStart=/opt/obd_client_venv/bin/python obd_client.py --config $CONFIG_FILE
Restart=always

[Install]
WantedBy=multi-user.target
EOL

systemctl daemon-reload
systemctl enable obd-client.service

# --- Final Steps ---
echo "[5/5] Setup complete!"

echo "The OBD client will start automatically on boot."
echo "To start it now, run: sudo systemctl start obd-client.service"
echo "To check its status, run: sudo systemctl status obd-client.service"

exit 0

