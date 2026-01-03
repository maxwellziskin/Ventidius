#!/bin/bash
# Ziskin Field Systems - Edge Device Installation Script
#
# This script installs and configures the ZFS edge device software
# on Ubuntu Server 22.04 LTS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo_error "This script must be run as root"
    exit 1
fi

echo_info "Starting Ziskin Field Systems Edge Device Installation"
echo ""

# Install system dependencies
echo_info "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    ffmpeg \
    wireguard \
    apcupsd \
    git \
    curl \
    jq

# Install MediaMTX
echo_info "Installing MediaMTX..."
MEDIAMTX_VERSION="1.4.2"
MEDIAMTX_URL="https://github.com/bluenviron/mediamtx/releases/download/v${MEDIAMTX_VERSION}/mediamtx_v${MEDIAMTX_VERSION}_linux_amd64.tar.gz"

if [ ! -f /usr/local/bin/mediamtx ]; then
    curl -L "$MEDIAMTX_URL" -o /tmp/mediamtx.tar.gz
    tar -xzf /tmp/mediamtx.tar.gz -C /usr/local/bin mediamtx
    chmod +x /usr/local/bin/mediamtx
    rm /tmp/mediamtx.tar.gz
    echo_info "MediaMTX installed successfully"
else
    echo_info "MediaMTX already installed"
fi

# Create zfs user and group
echo_info "Creating zfs user..."
if ! id -u zfs &>/dev/null; then
    useradd -r -s /bin/false -d /opt/ziskin zfs
fi

# Create directory structure
echo_info "Creating directory structure..."
mkdir -p /opt/ziskin
mkdir -p /opt/ziskin/orchestrator
mkdir -p /opt/ziskin/logs
mkdir -p /mnt/recordings
mkdir -p /var/log/ziskin

# Copy application files
echo_info "Copying application files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "$SCRIPT_DIR/orchestrator/"* /opt/ziskin/orchestrator/

# Create Python virtual environment
echo_info "Setting up Python virtual environment..."
python3.11 -m venv /opt/ziskin/venv
/opt/ziskin/venv/bin/pip install --upgrade pip
/opt/ziskin/venv/bin/pip install -r "$SCRIPT_DIR/requirements.txt"

# Copy example config if no config exists
if [ ! -f /opt/ziskin/config.yaml ]; then
    echo_info "Copying example configuration..."
    cp "$SCRIPT_DIR/config.example.yaml" /opt/ziskin/config.yaml
    echo_warn "Please edit /opt/ziskin/config.yaml with your site configuration"
fi

# Create UPS monitor script
echo_info "Creating UPS monitor script..."
cat > /opt/ziskin/ups-monitor.sh << 'EOFUPS'
#!/bin/bash
# UPS Monitor Script for Ziskin Field Systems
# Monitors APC UPS via apcupsd and triggers graceful shutdown

SHUTDOWN_THRESHOLD=20  # Shutdown when battery drops below this percentage
CHECK_INTERVAL=30      # Check interval in seconds

while true; do
    # Get UPS status
    STATUS=$(apcaccess 2>/dev/null)

    if [ -z "$STATUS" ]; then
        echo "Unable to get UPS status"
        sleep $CHECK_INTERVAL
        continue
    fi

    # Extract battery level and status
    BATTERY=$(echo "$STATUS" | grep "BCHARGE" | awk '{print $3}' | cut -d. -f1)
    LINE_STATUS=$(echo "$STATUS" | grep "STATUS" | awk '{print $3}')

    echo "UPS Status: $LINE_STATUS, Battery: ${BATTERY}%"

    # Check if on battery and below threshold
    if [ "$LINE_STATUS" = "ONBATT" ] && [ -n "$BATTERY" ] && [ "$BATTERY" -lt "$SHUTDOWN_THRESHOLD" ]; then
        echo "Battery critical (${BATTERY}%), initiating graceful shutdown..."

        # Stop orchestrator gracefully
        systemctl stop zfs-orchestrator

        # Wait for graceful shutdown
        sleep 10

        # Initiate system shutdown
        shutdown -h now "UPS battery critical - emergency shutdown"
    fi

    sleep $CHECK_INTERVAL
done
EOFUPS
chmod +x /opt/ziskin/ups-monitor.sh

# Install systemd services
echo_info "Installing systemd services..."
cp "$SCRIPT_DIR/systemd/zfs-orchestrator.service" /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/zfs-ups-monitor.service" /etc/systemd/system/

# Set permissions
echo_info "Setting permissions..."
chown -R zfs:zfs /opt/ziskin
chown -R zfs:zfs /mnt/recordings
chown -R zfs:zfs /var/log/ziskin
chmod 750 /opt/ziskin
chmod 640 /opt/ziskin/config.yaml

# Reload systemd
systemctl daemon-reload

# Enable services
echo_info "Enabling services..."
systemctl enable zfs-orchestrator
systemctl enable zfs-ups-monitor

echo ""
echo_info "Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Edit /opt/ziskin/config.yaml with your site configuration"
echo "  2. Configure WireGuard tunnel to cloud server"
echo "  3. Set up recording storage mount at /mnt/recordings"
echo "  4. Configure apcupsd for your UPS model"
echo "  5. Start the service: systemctl start zfs-orchestrator"
echo ""
echo_info "For WireGuard setup, run: zfs-wireguard-setup"
