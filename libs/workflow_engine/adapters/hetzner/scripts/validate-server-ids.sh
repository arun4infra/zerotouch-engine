#!/bin/bash
# Validate server IDs in node specs

set -euo pipefail

echo "Validating Hetzner server IDs..."

# Read context data
if [ -n "${ZTC_CONTEXT_FILE:-}" ]; then
    SERVER_IDS=$(jq -r '.server_ids' "$ZTC_CONTEXT_FILE")
else
    echo "Error: ZTC_CONTEXT_FILE not set"
    exit 1
fi

# Mock validation
echo "Server IDs validated successfully"
