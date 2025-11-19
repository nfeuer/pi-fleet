#!/bin/bash
#
# Device Restore Tool
#
# Restore configuration from backup to a device.
#
# Usage:
#   ./restore-device.sh <backup-timestamp> <device>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${SCRIPT_DIR}/../../backups}"

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

show_help() {
    cat << EOF
Device Restore Tool

Usage:
    ./restore-device.sh <backup-timestamp> <device> [options]

Arguments:
    backup-timestamp    Backup timestamp (e.g., 20240101-120000) or 'latest'
    device              Target device (e.g., pi@192.168.1.100)

Options:
    --dry-run          Show what would be restored without executing
    --help             Show this help message

Examples:
    # Restore from latest backup
    ./restore-device.sh latest pi@raspberrypi.local

    # Restore from specific backup
    ./restore-device.sh 20240101-120000 pi@192.168.1.100

    # Dry run
    ./restore-device.sh latest pi@raspberrypi.local --dry-run
EOF
}

# Find backup directory for device
find_device_backup() {
    local timestamp="$1"
    local device="$2"

    # Handle 'latest'
    if [[ "$timestamp" == "latest" ]]; then
        if [[ -L "${BACKUP_DIR}/latest" ]]; then
            timestamp=$(readlink "${BACKUP_DIR}/latest")
        else
            log_error "No latest backup found"
            return 1
        fi
    fi

    local backup_path="${BACKUP_DIR}/${timestamp}"

    if [[ ! -d "$backup_path" ]]; then
        log_error "Backup not found: $backup_path"
        return 1
    fi

    # Find device backup directory
    local device_name
    device_name=$(echo "$device" | sed 's/@/-/g' | sed 's/\./-/g')

    local device_backup="${backup_path}/${device_name}"

    # Try exact match first
    if [[ -d "$device_backup" ]]; then
        echo "$device_backup"
        return 0
    fi

    # Try to find similar backup
    local found
    found=$(find "$backup_path" -maxdepth 1 -type d -name "*${device_name}*" | head -1)

    if [[ -n "$found" ]]; then
        log_warning "Using closest match: $(basename "$found")"
        echo "$found"
        return 0
    fi

    log_error "No backup found for device: $device"
    return 1
}

# Restore device from backup
restore_device() {
    local backup_path="$1"
    local device="$2"
    local dry_run="${3:-false}"

    log_info "Restoring device: $device"
    log_info "From backup: $backup_path"
    echo ""

    # Check metadata
    if [[ -f "${backup_path}/metadata.json" ]]; then
        log_info "Backup information:"
        cat "${backup_path}/metadata.json"
        echo ""
    fi

    if [[ "$dry_run" == "true" ]]; then
        log_warning "DRY RUN MODE - No changes will be made"
        echo ""
    fi

    # Confirm restore
    if [[ "$dry_run" == "false" ]]; then
        log_warning "This will overwrite configurations on $device"
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Restore cancelled"
            return 0
        fi
    fi

    # Restore configuration files
    log_info "Restoring configuration files..."

    local restored=0
    local failed=0

    for backup_file in "$backup_path"/*; do
        [[ ! -f "$backup_file" ]] && continue

        local filename
        filename=$(basename "$backup_file")

        # Skip metadata and info files
        [[ "$filename" =~ \.(json|txt)$ ]] && continue

        # Convert filename back to path
        local target_path
        target_path=$(echo "$filename" | sed 's/^-/\//' | sed 's/-/\//g')

        # Skip if not a system path
        [[ ! "$target_path" =~ ^/etc ]] && continue

        log_info "  Restoring: $target_path"

        if [[ "$dry_run" == "true" ]]; then
            log_info "    [DRY RUN] Would restore: $backup_file -> $device:$target_path"
            restored=$((restored + 1))
            continue
        fi

        # Create parent directory on device
        local parent_dir
        parent_dir=$(dirname "$target_path")

        if ssh "$device" "sudo mkdir -p '$parent_dir'" 2>/dev/null; then
            if scp -q "$backup_file" "$device:/tmp/restore-$$-$filename" 2>/dev/null; then
                if ssh "$device" "sudo mv '/tmp/restore-$$-$filename' '$target_path'" 2>/dev/null; then
                    log_success "    ✓ Restored: $target_path"
                    restored=$((restored + 1))
                else
                    log_error "    ✗ Failed to move: $target_path"
                    failed=$((failed + 1))
                fi
            else
                log_error "    ✗ Failed to copy: $backup_file"
                failed=$((failed + 1))
            fi
        else
            log_error "    ✗ Failed to create directory: $parent_dir"
            failed=$((failed + 1))
        fi
    done

    echo ""
    log_info "Restore summary:"
    log_info "  Restored: $restored"
    log_info "  Failed: $failed"

    if [[ "$dry_run" == "false" && $restored -gt 0 ]]; then
        echo ""
        log_warning "Some services may need to be restarted for changes to take effect"
        log_info "Consider rebooting the device: ssh $device 'sudo reboot'"
    fi
}

# Main function
main() {
    if [[ $# -lt 2 ]]; then
        show_help
        exit 1
    fi

    local timestamp="$1"
    local device="$2"
    local dry_run=false

    shift 2

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                dry_run=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Find device backup
    local backup_path
    backup_path=$(find_device_backup "$timestamp" "$device")

    if [[ -z "$backup_path" ]]; then
        exit 1
    fi

    # Restore device
    restore_device "$backup_path" "$device" "$dry_run"
}

main "$@"
