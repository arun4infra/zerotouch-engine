#!/usr/bin/env bash
# Enable rescue mode for Hetzner servers
# Adapted from zerotouch-platform/scripts/bootstrap/00-enable-rescue-mode.sh
# Inlined Hetzner API functions for adapter independence

set -euo pipefail

# Read context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

# Parse context with jq
if ! command -v jq &> /dev/null; then
    echo "ERROR: jq is required but not installed" >&2
    exit 1
fi

SERVER_IP=$(jq -r '.server_ip' "$ZTC_CONTEXT_FILE")
HETZNER_API_TOKEN=$(jq -r '.hetzner_api_token' "$ZTC_CONTEXT_FILE")
SERVER_NAME=$(jq -r '.server_name // "server"' "$ZTC_CONTEXT_FILE")

if [[ -z "$SERVER_IP" || "$SERVER_IP" == "null" ]]; then
    echo "ERROR: server_ip not provided in context" >&2
    exit 1
fi

if [[ -z "$HETZNER_API_TOKEN" || "$HETZNER_API_TOKEN" == "null" ]]; then
    echo "ERROR: hetzner_api_token not provided in context" >&2
    exit 1
fi

HETZNER_API_URL="https://api.hetzner.cloud/v1"

# Inline Hetzner API function (copied from helpers/hetzner-api.sh)
hetzner_api() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    
    if [[ -n "$data" ]]; then
        curl -s -X "$method" \
            -H "Authorization: Bearer $HETZNER_API_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$HETZNER_API_URL$endpoint"
    else
        curl -s -X "$method" \
            -H "Authorization: Bearer $HETZNER_API_TOKEN" \
            "$HETZNER_API_URL$endpoint"
    fi
}

# Inline get_server_id_by_ip (copied from helpers/hetzner-api.sh)
get_server_id_by_ip() {
    local ip="$1"
    local servers=$(hetzner_api "GET" "/servers" "")
    local server_id=$(echo "$servers" | jq -r ".servers[] | select(.public_net.ipv4.ip == \"$ip\") | .id")
    
    if [[ -z "$server_id" || "$server_id" == "null" ]]; then
        echo "ERROR: Could not find server with IP: $ip" >&2
        return 1
    fi
    
    echo "$server_id"
}

# Core rescue mode logic
echo "Enabling rescue mode for $SERVER_NAME ($SERVER_IP)..."

# Get server ID
SERVER_ID=$(get_server_id_by_ip "$SERVER_IP")
if [[ $? -ne 0 ]]; then
    exit 1
fi

echo "Server ID: $SERVER_ID"

# Enable rescue mode
RESPONSE=$(hetzner_api "POST" "/servers/$SERVER_ID/actions/enable_rescue" '{"type":"linux64"}')

# Check for errors
ERROR_MSG=$(echo "$RESPONSE" | jq -r '.error.message // empty')
if [[ -n "$ERROR_MSG" ]]; then
    echo "ERROR: Failed to enable rescue mode: $ERROR_MSG" >&2
    echo "$RESPONSE" | jq '.' >&2
    exit 1
fi

# Extract root password
ROOT_PASSWORD=$(echo "$RESPONSE" | jq -r '.root_password')

if [[ -z "$ROOT_PASSWORD" || "$ROOT_PASSWORD" == "null" ]]; then
    echo "ERROR: Failed to get root password from API response" >&2
    echo "$RESPONSE" | jq '.' >&2
    exit 1
fi

echo "Rescue mode enabled successfully"
echo "Root password: $ROOT_PASSWORD"

# Reboot server
echo "Rebooting server..."
REBOOT_RESPONSE=$(hetzner_api "POST" "/servers/$SERVER_ID/actions/reboot" '{}')

ERROR_MSG=$(echo "$REBOOT_RESPONSE" | jq -r '.error.message // empty')
if [[ -n "$ERROR_MSG" ]]; then
    echo "ERROR: Failed to reboot server: $ERROR_MSG" >&2
    echo "$REBOOT_RESPONSE" | jq '.' >&2
    exit 1
fi

ACTION_ID=$(echo "$REBOOT_RESPONSE" | jq -r '.action.id')
echo "Reboot initiated (action ID: $ACTION_ID)"
echo "Server will boot into rescue mode in ~60-90 seconds"
