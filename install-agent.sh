#!/bin/bash
#
# Pi Fleet Agent Installation Script
#
# Quick installation script for setting up the Pi Fleet agent on a Raspberry Pi
#
# Usage:
#   curl -sSL <url-to-this-script> | bash -s -- <server-url>
#   OR
#   ./install-agent.sh <server-url>

set -euo pipefail

# Configuration
SERVER_URL="${1:-}"
INSTALL_DIR="/opt/pi-fleet"
SERVICE_NAME="pi-fleet-agent"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check if running on Raspberry Pi
check_platform() {
    if [[ ! -f /proc/device-tree/model ]]; then
        log_warning "This doesn't appear to be a Raspberry Pi"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        local model
        model=$(cat /proc/device-tree/model)
        log_info "Detected: $model"
    fi
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."

    sudo apt-get update -qq
    sudo apt-get install -y -qq python3 python3-pip

    log_success "Dependencies installed"
}

# Install Python packages
install_python_packages() {
    log_info "Installing Python packages..."

    sudo pip3 install -q psutil requests

    log_success "Python packages installed"
}

# Create installation directory
create_install_dir() {
    log_info "Creating installation directory: $INSTALL_DIR"

    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$USER:$USER" "$INSTALL_DIR"

    log_success "Installation directory created"
}

# Download or copy agent files
install_agent() {
    log_info "Installing Pi Fleet agent..."

    # If script is in the repo, copy from there
    if [[ -f "$(dirname "$0")/pi-agent.py" ]]; then
        sudo cp "$(dirname "$0")/pi-agent.py" "$INSTALL_DIR/"
    else
        log_error "pi-agent.py not found"
        log_info "Please download pi-agent.py and requirements.txt to this directory"
        exit 1
    fi

    sudo chmod +x "$INSTALL_DIR/pi-agent.py"

    log_success "Agent installed"
}

# Create systemd service
create_service() {
    log_info "Creating systemd service..."

    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Pi Fleet Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 $INSTALL_DIR/pi-agent.py --server $SERVER_URL --name $(hostname)
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload

    log_success "Systemd service created"
}

# Start and enable service
start_service() {
    log_info "Starting Pi Fleet agent service..."

    sudo systemctl enable ${SERVICE_NAME}
    sudo systemctl start ${SERVICE_NAME}

    sleep 2

    if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
        log_success "Service started successfully"
    else
        log_error "Service failed to start"
        log_info "Check logs with: sudo journalctl -u ${SERVICE_NAME} -f"
        exit 1
    fi
}

# Show status
show_status() {
    echo ""
    log_success "Pi Fleet Agent Installation Complete!"
    echo ""
    log_info "Service Status:"
    sudo systemctl status ${SERVICE_NAME} --no-pager -l
    echo ""
    log_info "Useful commands:"
    echo "  View logs:    sudo journalctl -u ${SERVICE_NAME} -f"
    echo "  Stop service: sudo systemctl stop ${SERVICE_NAME}"
    echo "  Restart:      sudo systemctl restart ${SERVICE_NAME}"
    echo "  Disable:      sudo systemctl disable ${SERVICE_NAME}"
    echo ""
}

# Main installation
main() {
    echo ""
    log_info "Pi Fleet Agent Installation"
    echo ""

    # Check arguments
    if [[ -z "$SERVER_URL" ]]; then
        log_error "Server URL is required"
        echo ""
        echo "Usage: $0 <server-url>"
        echo "Example: $0 http://192.168.1.100:5000"
        exit 1
    fi

    log_info "Server URL: $SERVER_URL"
    echo ""

    # Confirm installation
    read -p "Continue with installation? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installation cancelled"
        exit 0
    fi

    check_platform
    install_dependencies
    install_python_packages
    create_install_dir
    install_agent
    create_service
    start_service
    show_status
}

# Run main
main
