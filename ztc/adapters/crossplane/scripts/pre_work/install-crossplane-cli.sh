#!/usr/bin/env bash
set -euo pipefail

# Source: (new) - Install kubectl-crossplane plugin
# Crossplane CLI Installation Script
# Installs kubectl-crossplane plugin from GitHub releases

# Validate context file exists
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE environment variable not set" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo "ERROR: Context file not found: $ZTC_CONTEXT_FILE" >&2
    exit 1
fi

# Parse context with jq
VERSION=$(jq -r '.version' "$ZTC_CONTEXT_FILE")
INSTALL_PATH=$(jq -r '.install_path // "/usr/local/bin/kubectl-crossplane"' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$VERSION" || "$VERSION" == "null" ]]; then
    echo "ERROR: version is required in context" >&2
    exit 1
fi

# Check if kubectl-crossplane already installed
if command -v kubectl-crossplane &> /dev/null; then
    INSTALLED_VERSION=$(kubectl-crossplane --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "unknown")
    echo "kubectl-crossplane already installed: $INSTALLED_VERSION"
    
    if [[ "$INSTALLED_VERSION" == "$VERSION" ]]; then
        echo "✓ Correct version already installed"
        exit 0
    else
        echo "Upgrading from $INSTALLED_VERSION to $VERSION..."
    fi
fi

# Download kubectl-crossplane plugin
echo "Downloading kubectl-crossplane plugin v$VERSION..."

TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

# Detect OS and architecture
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$ARCH" in
    x86_64)
        ARCH="amd64"
        ;;
    aarch64|arm64)
        ARCH="arm64"
        ;;
    *)
        echo "ERROR: Unsupported architecture: $ARCH" >&2
        exit 1
        ;;
esac

DOWNLOAD_URL="https://releases.crossplane.io/stable/v${VERSION}/bin/${OS}_${ARCH}/crank"

if ! curl -sSL -o "$TEMP_FILE" "$DOWNLOAD_URL"; then
    echo "ERROR: Failed to download kubectl-crossplane from $DOWNLOAD_URL" >&2
    exit 1
fi

# Make executable
chmod +x "$TEMP_FILE"

# Move to install path
INSTALL_DIR=$(dirname "$INSTALL_PATH")
if [[ ! -d "$INSTALL_DIR" ]]; then
    echo "Creating install directory: $INSTALL_DIR"
    sudo mkdir -p "$INSTALL_DIR"
fi

if ! sudo mv "$TEMP_FILE" "$INSTALL_PATH"; then
    echo "ERROR: Failed to install kubectl-crossplane to $INSTALL_PATH" >&2
    exit 1
fi

# Verify installation
if ! command -v kubectl-crossplane &> /dev/null; then
    echo "ERROR: kubectl-crossplane not found in PATH after installation" >&2
    exit 1
fi

INSTALLED_VERSION=$(kubectl-crossplane --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "unknown")
echo "✓ kubectl-crossplane installed successfully: $INSTALLED_VERSION"

