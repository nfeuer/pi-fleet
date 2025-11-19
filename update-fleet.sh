#!/bin/bash
#
# Pi Fleet Update Orchestration Script
#
# This script orchestrates updates across the entire fleet of Raspberry Pi devices.
# It can perform OS updates, package updates, and coordinate rolling updates with
# configurable batch sizes and delays.
#
# Usage:
#   ./update-fleet.sh [options]
#
# Options:
#   --server URL      Fleet manager server URL (default: http://localhost:5000)
#   --type TYPE       Update type: packages, os, all (default: packages)
#   --batch SIZE      Number of devices to update simultaneously (default: 5)
#   --delay SECONDS   Delay between batches (default: 60)
#   --filter PATTERN  Only update devices matching pattern (default: all)
#   --dry-run         Show what would be updated without executing
#   --help            Show this help message

set -euo pipefail

# Configuration
SERVER_URL="${SERVER_URL:-http://localhost:5000}"
UPDATE_TYPE="packages"
BATCH_SIZE=5
BATCH_DELAY=60
DEVICE_FILTER=""
DRY_RUN=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --server)
                SERVER_URL="$2"
                shift 2
                ;;
            --type)
                UPDATE_TYPE="$2"
                shift 2
                ;;
            --batch)
                BATCH_SIZE="$2"
                shift 2
                ;;
            --delay)
                BATCH_DELAY="$2"
                shift 2
                ;;
            --filter)
                DEVICE_FILTER="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
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
}

show_help() {
    cat << EOF
Pi Fleet Update Orchestration Script

Usage:
    ./update-fleet.sh [options]

Options:
    --server URL      Fleet manager server URL (default: http://localhost:5000)
    --type TYPE       Update type: packages, os, all (default: packages)
    --batch SIZE      Number of devices to update simultaneously (default: 5)
    --delay SECONDS   Delay between batches (default: 60)
    --filter PATTERN  Only update devices matching pattern (default: all)
    --dry-run         Show what would be updated without executing
    --help            Show this help message

Examples:
    # Update all devices with default settings
    ./update-fleet.sh --server http://192.168.1.100:5000

    # Update only devices matching "livingroom"
    ./update-fleet.sh --filter "livingroom"

    # Update in batches of 3 with 120 second delay
    ./update-fleet.sh --batch 3 --delay 120

    # Dry run to see what would be updated
    ./update-fleet.sh --dry-run
EOF
}

# API call helper
api_call() {
    local endpoint="$1"
    local method="${2:-GET}"
    local data="${3:-}"

    local curl_args=(-s -X "$method" "${SERVER_URL}${endpoint}")

    if [[ -n "$data" ]]; then
        curl_args+=(-H "Content-Type: application/json" -d "$data")
    fi

    if ! curl "${curl_args[@]}"; then
        log_error "API call failed: $endpoint"
        return 1
    fi
}

# Get list of devices
get_devices() {
    local response
    response=$(api_call "/api/devices")

    if [[ -z "$response" ]]; then
        log_error "Failed to get device list"
        return 1
    fi

    echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
devices = data.get('devices', [])

filter_pattern = '$DEVICE_FILTER'
if filter_pattern:
    devices = [d for d in devices if filter_pattern.lower() in d['device_name'].lower()]

# Only include online devices
devices = [d for d in devices if d['status'] == 'online']

for device in devices:
    print(f\"{device['device_id']}|{device['device_name']}\")
"
}

# Send update command to a device
send_update_command() {
    local device_id="$1"
    local device_name="$2"

    log_info "Sending update command to: $device_name"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would update: $device_name ($device_id)"
        return 0
    fi

    local payload
    payload=$(cat <<EOF
{
    "type": "update",
    "payload": {
        "update_type": "$UPDATE_TYPE"
    }
}
EOF
)

    if api_call "/api/devices/${device_id}/commands" "POST" "$payload" > /dev/null; then
        log_success "Update command sent to: $device_name"
        return 0
    else
        log_error "Failed to send update command to: $device_name"
        return 1
    fi
}

# Check command status
check_command_status() {
    local device_id="$1"
    local max_wait="${2:-600}" # 10 minutes default
    local wait_interval=10
    local elapsed=0

    while [[ $elapsed -lt $max_wait ]]; do
        local response
        response=$(api_call "/api/devices/${device_id}/commands/history?limit=1")

        local status
        status=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('commands'):
    print(data['commands'][0]['status'])
else:
    print('pending')
" 2>/dev/null || echo "unknown")

        if [[ "$status" == "completed" ]]; then
            return 0
        elif [[ "$status" == "error" ]]; then
            return 1
        fi

        sleep $wait_interval
        elapsed=$((elapsed + wait_interval))
    done

    log_warning "Timeout waiting for command completion"
    return 1
}

# Process devices in batches
process_batches() {
    local devices=("$@")
    local total=${#devices[@]}
    local processed=0
    local batch=()
    local batch_num=1

    log_info "Processing $total devices in batches of $BATCH_SIZE"

    for device_info in "${devices[@]}"; do
        batch+=("$device_info")

        if [[ ${#batch[@]} -ge $BATCH_SIZE ]] || [[ $((processed + ${#batch[@]})) -eq $total ]]; then
            log_info "Processing batch $batch_num (${#batch[@]} devices)"

            # Send update commands to batch
            local pids=()
            for info in "${batch[@]}"; do
                IFS='|' read -r device_id device_name <<< "$info"
                send_update_command "$device_id" "$device_name" &
                pids+=($!)
            done

            # Wait for all commands to be sent
            for pid in "${pids[@]}"; do
                wait "$pid"
            done

            processed=$((processed + ${#batch[@]}))
            log_success "Batch $batch_num sent ($processed/$total devices)"

            # Wait between batches (except for last batch)
            if [[ $processed -lt $total ]]; then
                log_info "Waiting $BATCH_DELAY seconds before next batch..."
                sleep "$BATCH_DELAY"
            fi

            batch=()
            batch_num=$((batch_num + 1))
        fi
    done

    log_success "All update commands sent to $total devices"
}

# Generate update report
generate_report() {
    local devices=("$@")

    log_info "Generating update report..."

    echo ""
    echo "======================================"
    echo "Fleet Update Report"
    echo "======================================"
    echo "Server: $SERVER_URL"
    echo "Update Type: $UPDATE_TYPE"
    echo "Total Devices: ${#devices[@]}"
    echo "Batch Size: $BATCH_SIZE"
    echo "Batch Delay: ${BATCH_DELAY}s"
    echo "======================================"
    echo ""

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "DRY RUN - No updates were executed"
        echo ""
    fi

    echo "Devices to update:"
    for device_info in "${devices[@]}"; do
        IFS='|' read -r device_id device_name <<< "$device_info"
        echo "  - $device_name ($device_id)"
    done
    echo ""
}

# Check if server is reachable
check_server() {
    log_info "Checking server connectivity: $SERVER_URL"

    if ! api_call "/api/status" > /dev/null 2>&1; then
        log_error "Cannot connect to fleet manager server: $SERVER_URL"
        log_error "Please check that the server is running and the URL is correct"
        exit 1
    fi

    log_success "Server is reachable"
}

# Main function
main() {
    parse_args "$@"

    echo ""
    log_info "Pi Fleet Update Orchestration"
    echo ""

    # Check server
    check_server

    # Get devices
    log_info "Fetching device list..."
    mapfile -t devices < <(get_devices)

    if [[ ${#devices[@]} -eq 0 ]]; then
        log_warning "No devices found matching criteria"
        if [[ -n "$DEVICE_FILTER" ]]; then
            log_info "Filter: $DEVICE_FILTER"
        fi
        exit 0
    fi

    # Generate and show report
    generate_report "${devices[@]}"

    # Confirm unless dry run
    if [[ "$DRY_RUN" == "false" ]]; then
        read -p "Proceed with fleet update? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Update cancelled"
            exit 0
        fi
    fi

    # Process updates
    process_batches "${devices[@]}"

    if [[ "$DRY_RUN" == "false" ]]; then
        log_success "Fleet update orchestration complete!"
        log_info "Monitor device status in the dashboard or check command history"
    fi
}

# Run main function
main "$@"
