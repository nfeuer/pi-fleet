#!/bin/bash
#
# SSH Key Management Tool
#
# Manage SSH keys across the fleet of Raspberry Pi devices.
# Supports key generation, distribution, and rotation.
#
# Usage:
#   ./manage-keys.sh [command] [options]
#
# Commands:
#   generate      Generate new SSH key pair
#   distribute    Distribute public key to devices
#   rotate        Rotate SSH keys across fleet
#   audit         Audit SSH key deployment status
#   remove        Remove SSH key from devices

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_DIR="${SCRIPT_DIR}/../../.ssh-keys"
DEFAULT_KEY_NAME="pi-fleet-key"

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

# Command: Generate SSH key pair
generate_key() {
    local key_name="${1:-$DEFAULT_KEY_NAME}"
    local key_path="${KEYS_DIR}/${key_name}"

    log_info "Generating SSH key pair: $key_name"

    # Create keys directory if it doesn't exist
    mkdir -p "$KEYS_DIR"
    chmod 700 "$KEYS_DIR"

    # Check if key already exists
    if [[ -f "$key_path" ]]; then
        read -p "Key already exists. Overwrite? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Key generation cancelled"
            return 0
        fi
    fi

    # Generate key
    ssh-keygen -t ed25519 -f "$key_path" -C "pi-fleet-manager" -N ""

    if [[ $? -eq 0 ]]; then
        log_success "SSH key pair generated:"
        log_info "  Private key: $key_path"
        log_info "  Public key: ${key_path}.pub"
        echo ""
        log_info "Public key content:"
        cat "${key_path}.pub"
        echo ""
        log_warning "Keep the private key secure!"
    else
        log_error "Failed to generate SSH key"
        return 1
    fi
}

# Command: Distribute public key to devices
distribute_key() {
    local key_name="${1:-$DEFAULT_KEY_NAME}"
    local device_filter="${2:-}"
    local key_path="${KEYS_DIR}/${key_name}.pub"

    if [[ ! -f "$key_path" ]]; then
        log_error "Public key not found: $key_path"
        log_info "Run './manage-keys.sh generate' first"
        return 1
    fi

    local pubkey
    pubkey=$(cat "$key_path")

    log_info "Distributing SSH public key to devices..."
    echo ""

    # Read devices list (you would typically get this from your inventory)
    local devices_file="${SCRIPT_DIR}/../../config/devices.txt"

    if [[ ! -f "$devices_file" ]]; then
        log_warning "Devices file not found: $devices_file"
        log_info "Expected format: username@hostname (one per line)"
        log_info "Example:"
        log_info "  pi@raspberrypi-1.local"
        log_info "  pi@192.168.1.100"
        return 1
    fi

    local count=0
    local success=0

    while IFS= read -r device; do
        # Skip empty lines and comments
        [[ -z "$device" || "$device" =~ ^# ]] && continue

        # Apply filter if specified
        if [[ -n "$device_filter" && ! "$device" =~ $device_filter ]]; then
            continue
        fi

        count=$((count + 1))

        log_info "Deploying to: $device"

        # Add public key to authorized_keys
        if ssh "$device" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '$pubkey' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"; then
            log_success "✓ Key deployed to $device"
            success=$((success + 1))
        else
            log_error "✗ Failed to deploy to $device"
        fi
    done < "$devices_file"

    echo ""
    log_info "Deployment complete: $success/$count successful"
}

# Command: Audit SSH key deployment
audit_keys() {
    local key_name="${1:-$DEFAULT_KEY_NAME}"
    local key_path="${KEYS_DIR}/${key_name}.pub"

    if [[ ! -f "$key_path" ]]; then
        log_error "Public key not found: $key_path"
        return 1
    fi

    local key_fingerprint
    key_fingerprint=$(ssh-keygen -lf "$key_path" | awk '{print $2}')

    log_info "Auditing SSH key deployment..."
    log_info "Key fingerprint: $key_fingerprint"
    echo ""

    local devices_file="${SCRIPT_DIR}/../../config/devices.txt"

    if [[ ! -f "$devices_file" ]]; then
        log_error "Devices file not found: $devices_file"
        return 1
    fi

    echo "Device | Status | Keys Count"
    echo "-------|--------|------------"

    while IFS= read -r device; do
        [[ -z "$device" || "$device" =~ ^# ]] && continue

        if ssh -o ConnectTimeout=5 "$device" "cat ~/.ssh/authorized_keys 2>/dev/null" > /dev/null 2>&1; then
            local keys_count
            keys_count=$(ssh "$device" "grep -c '^ssh-' ~/.ssh/authorized_keys 2>/dev/null" || echo "0")
            echo "$device | ✓ Connected | $keys_count"
        else
            echo "$device | ✗ Failed | -"
        fi
    done < "$devices_file"
}

# Command: Remove SSH key from devices
remove_key() {
    local key_name="${1:-$DEFAULT_KEY_NAME}"
    local key_path="${KEYS_DIR}/${key_name}.pub"

    if [[ ! -f "$key_path" ]]; then
        log_error "Public key not found: $key_path"
        return 1
    fi

    local pubkey_content
    pubkey_content=$(cat "$key_path" | awk '{print $1" "$2}')

    log_warning "This will remove the key from all devices!"
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Operation cancelled"
        return 0
    fi

    local devices_file="${SCRIPT_DIR}/../../config/devices.txt"

    if [[ ! -f "$devices_file" ]]; then
        log_error "Devices file not found: $devices_file"
        return 1
    fi

    local count=0
    local success=0

    while IFS= read -r device; do
        [[ -z "$device" || "$device" =~ ^# ]] && continue

        count=$((count + 1))
        log_info "Removing key from: $device"

        # Remove matching keys from authorized_keys
        if ssh "$device" "sed -i.bak '/${pubkey_content//\//\\/}/d' ~/.ssh/authorized_keys"; then
            log_success "✓ Key removed from $device"
            success=$((success + 1))
        else
            log_error "✗ Failed to remove from $device"
        fi
    done < "$devices_file"

    echo ""
    log_info "Removal complete: $success/$count successful"
}

# Command: Rotate SSH keys
rotate_keys() {
    log_info "Starting SSH key rotation..."
    echo ""

    # Generate new key with timestamp
    local new_key_name="pi-fleet-key-$(date +%Y%m%d-%H%M%S)"

    log_info "Step 1: Generating new key pair..."
    generate_key "$new_key_name"

    echo ""
    log_info "Step 2: Distributing new key..."
    distribute_key "$new_key_name"

    echo ""
    log_info "Key rotation complete!"
    log_warning "Old keys are still active. Test the new key before removing old ones."
    log_info "To remove old keys, run: ./manage-keys.sh remove <old-key-name>"
}

# Show help
show_help() {
    cat << EOF
SSH Key Management Tool for Pi Fleet

Usage:
    ./manage-keys.sh [command] [options]

Commands:
    generate [name]           Generate new SSH key pair
                              Default name: $DEFAULT_KEY_NAME

    distribute [name] [filter] Distribute public key to devices
                              filter: optional hostname pattern

    audit [name]              Audit SSH key deployment status

    remove [name]             Remove SSH key from all devices

    rotate                    Generate new key and distribute
                              (keeps old keys for safety)

    help                      Show this help message

Examples:
    # Generate new key pair
    ./manage-keys.sh generate

    # Distribute to all devices
    ./manage-keys.sh distribute

    # Distribute to specific devices
    ./manage-keys.sh distribute pi-fleet-key "192.168.1"

    # Audit key deployment
    ./manage-keys.sh audit

    # Rotate keys
    ./manage-keys.sh rotate

Setup:
    1. Create config/devices.txt with one device per line:
       pi@raspberrypi-1.local
       pi@192.168.1.100

    2. Generate SSH key pair:
       ./manage-keys.sh generate

    3. Distribute to devices:
       ./manage-keys.sh distribute

Keys are stored in: $KEYS_DIR
EOF
}

# Main function
main() {
    local command="${1:-help}"

    case "$command" in
        generate)
            generate_key "${2:-$DEFAULT_KEY_NAME}"
            ;;
        distribute)
            distribute_key "${2:-$DEFAULT_KEY_NAME}" "${3:-}"
            ;;
        audit)
            audit_keys "${2:-$DEFAULT_KEY_NAME}"
            ;;
        remove)
            remove_key "${2:-$DEFAULT_KEY_NAME}"
            ;;
        rotate)
            rotate_keys
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
