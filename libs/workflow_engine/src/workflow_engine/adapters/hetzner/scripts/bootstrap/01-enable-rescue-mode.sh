#!/usr/bin/env bash
# Enable rescue mode for Hetzner servers and persist to tenant repo
# Adapted from zerotouch-platform/scripts/bootstrap/00-enable-rescue-mode.sh

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPERS_DIR="$SCRIPT_DIR/helpers"

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
HETZNER_API_TOKEN="${HETZNER_API_TOKEN:-}"  # Read from environment (injected by bootstrap executor)
TENANT_REPO_URL=$(jq -r '.tenant_repo_url // empty' "$ZTC_CONTEXT_FILE")
ENV=$(jq -r '.env // "dev"' "$ZTC_CONTEXT_FILE")

if [[ -z "$SERVER_IP" || "$SERVER_IP" == "null" ]]; then
    echo "ERROR: server_ip not provided in context" >&2
    exit 1
fi

if [[ -z "$HETZNER_API_TOKEN" ]]; then
    echo "ERROR: HETZNER_API_TOKEN not set in environment" >&2
    exit 1
fi

# Source Hetzner API helper
source "$HELPERS_DIR/hetzner-api.sh"

# Fetch tenant config if repo URL provided
if [[ -n "$TENANT_REPO_URL" && "$TENANT_REPO_URL" != "null" ]]; then
    echo "Fetching tenant configuration from $TENANT_REPO_URL..."
    source "$HELPERS_DIR/fetch-tenant-config.sh" "$ENV" || {
        echo "WARNING: Failed to fetch tenant config, will use local cache only"
        VALUES_FILE=""
        TENANT_CACHE_DIR=""
    }
    VALUES_FILE="${TENANT_CONFIG_FILE:-}"
    TENANT_CACHE_DIR="${TENANT_CACHE_DIR:-}"
else
    echo "No tenant repo URL provided, using local cache only"
    VALUES_FILE=""
    TENANT_CACHE_DIR=""
fi

# Enable rescue mode
echo "Enabling rescue mode for server ($SERVER_IP)..."

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

# Save password using Python provider
# PROJECT_ROOT is provided by bootstrap executor
SCRIPT_DIR="$PROJECT_ROOT/libs/workflow_engine/src/workflow_engine/adapters/hetzner/scripts/bootstrap"
RESCUE_DIR="$SCRIPT_DIR/rescue"
HELPERS_DIR="$SCRIPT_DIR/helpers"

python3 << PYTHON_SCRIPT
import sys
from pathlib import Path

# Add rescue module to path
rescue_dir = Path('$RESCUE_DIR')
sys.path.insert(0, str(rescue_dir))

from rescue_password_provider import RescuePasswordProvider

password = """$ROOT_PASSWORD"""
project_root = Path('$PROJECT_ROOT')
provider = RescuePasswordProvider(cache_dir=project_root / ".zerotouch-cache")

# Save to local cache
provider.save_to_cache(password)
print(f"Password saved to {provider.password_file}")

# Save to tenant repo if available
tenant_cache_dir = """${TENANT_CACHE_DIR:-}"""
helpers_dir = Path('$HELPERS_DIR')
env = """$ENV"""
cluster_name = """$(jq -r '.cluster_name' "$ZTC_CONTEXT_FILE")"""
controlplane_name = """$(jq -r '.nodes[] | select(.role == "controlplane") | .name' "$ZTC_CONTEXT_FILE" | head -1)"""
controlplane_ip = """$SERVER_IP"""
talos_version = """$(jq -r '.nodes[0].talos_version // "v1.11.5"' "$ZTC_CONTEXT_FILE")"""

if tenant_cache_dir and Path(tenant_cache_dir).exists():
    print("Updating tenant repository...")
    success = provider.save_to_tenant_repo(
        password,
        Path(tenant_cache_dir),
        helpers_dir,
        env,
        cluster_name,
        controlplane_name,
        controlplane_ip,
        talos_version
    )
    if not success:
        print("ERROR: Tenant repo update failed", file=sys.stderr)
        sys.exit(1)
else:
    print("No tenant cache available, password saved to local cache only")
PYTHON_SCRIPT

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
