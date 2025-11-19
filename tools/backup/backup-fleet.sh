#!/bin/bash
#
# Fleet Backup Tool
#
# Backup configurations and data from all devices in the fleet.
#
# Usage:
#   ./backup-fleet.sh [options]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${SCRIPT_DIR}/../../backups}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DEVICES_FILE="${SCRIPT_DIR}/../../config/devices.txt"

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

# Default paths to backup
DEFAULT_BACKUP_PATHS=(
    "/etc/hostname"
    "/etc/hosts"
    "/etc/network/interfaces"
    "/etc/dhcpcd.conf"
    "/etc/wpa_supplicant/wpa_supplicant.conf"
    "/etc/fstab"
    "/etc/rc.local"
    "/etc/crontab"
    "/var/spool/cron/crontabs"
)

# Backup a single device
backup_device() {
    local device="$1"
    local device_name
    device_name=$(echo "$device" | sed 's/@/-/g' | sed 's/\./-/g')

    local backup_path="${BACKUP_DIR}/${TIMESTAMP}/${device_name}"

    log_info "Backing up: $device"

    # Create backup directory
    mkdir -p "$backup_path"

    # Backup system info
    log_info "  Collecting system information..."
    ssh "$device" "uname -a" > "${backup_path}/system-info.txt" 2>/dev/null || true
    ssh "$device" "cat /proc/cpuinfo" > "${backup_path}/cpuinfo.txt" 2>/dev/null || true
    ssh "$device" "df -h" > "${backup_path}/disk-usage.txt" 2>/dev/null || true
    ssh "$device" "dpkg -l" > "${backup_path}/packages.txt" 2>/dev/null || true
    ssh "$device" "systemctl list-units --type=service --state=running" > "${backup_path}/services.txt" 2>/dev/null || true

    # Backup configuration files
    log_info "  Backing up configuration files..."
    for path in "${DEFAULT_BACKUP_PATHS[@]}"; do
        local filename
        filename=$(echo "$path" | sed 's/\//-/g' | sed 's/^-//')

        if ssh "$device" "test -e $path" 2>/dev/null; then
            if ssh "$device" "test -f $path" 2>/dev/null; then
                scp -q "$device:$path" "${backup_path}/${filename}" 2>/dev/null || true
            elif ssh "$device" "test -d $path" 2>/dev/null; then
                scp -q -r "$device:$path" "${backup_path}/${filename}" 2>/dev/null || true
            fi
        fi
    done

    # Backup custom configurations if specified
    if [[ -f "${SCRIPT_DIR}/../../config/backup-paths.txt" ]]; then
        while IFS= read -r custom_path; do
            [[ -z "$custom_path" || "$custom_path" =~ ^# ]] && continue

            local filename
            filename=$(echo "$custom_path" | sed 's/\//-/g' | sed 's/^-//')

            if ssh "$device" "test -e $custom_path" 2>/dev/null; then
                scp -q -r "$device:$custom_path" "${backup_path}/${filename}" 2>/dev/null || true
            fi
        done < "${SCRIPT_DIR}/../../config/backup-paths.txt"
    fi

    # Create metadata
    cat > "${backup_path}/metadata.json" <<EOF
{
    "device": "$device",
    "timestamp": "$TIMESTAMP",
    "backup_date": "$(date -Iseconds)",
    "script_version": "1.0.0"
}
EOF

    log_success "✓ Backup complete: $device_name"
}

# Main backup function
main() {
    log_info "Pi Fleet Backup Tool"
    log_info "Backup directory: ${BACKUP_DIR}/${TIMESTAMP}"
    echo ""

    # Check devices file
    if [[ ! -f "$DEVICES_FILE" ]]; then
        log_error "Devices file not found: $DEVICES_FILE"
        log_info "Create config/devices.txt with one device per line"
        exit 1
    fi

    # Create backup directory
    mkdir -p "${BACKUP_DIR}/${TIMESTAMP}"

    # Backup each device
    local count=0
    local success=0

    while IFS= read -r device; do
        [[ -z "$device" || "$device" =~ ^# ]] && continue

        count=$((count + 1))

        if backup_device "$device"; then
            success=$((success + 1))
        else
            log_error "✗ Failed to backup: $device"
        fi

        echo ""
    done < "$DEVICES_FILE"

    # Create backup manifest
    cat > "${BACKUP_DIR}/${TIMESTAMP}/manifest.json" <<EOF
{
    "timestamp": "$TIMESTAMP",
    "backup_date": "$(date -Iseconds)",
    "total_devices": $count,
    "successful_backups": $success,
    "failed_backups": $((count - success))
}
EOF

    # Summary
    log_success "Backup complete!"
    log_info "Total devices: $count"
    log_info "Successful: $success"
    log_info "Failed: $((count - success))"
    log_info "Backup location: ${BACKUP_DIR}/${TIMESTAMP}"

    # Create symlink to latest backup
    ln -sfn "${TIMESTAMP}" "${BACKUP_DIR}/latest"
}

main "$@"
