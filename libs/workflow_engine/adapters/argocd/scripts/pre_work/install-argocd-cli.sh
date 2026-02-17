#!/usr/bin/env bash
set -euo pipefail

# ArgoCD CLI Installation Script
# Installs ArgoCD CLI from GitHub releases

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
ARGOCD_VERSION=$(jq -r '.argocd_version' "$ZTC_CONTEXT_FILE")
INSTALL_PATH=$(jq -r '.install_path // "/usr/local/bin/argocd"' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$ARGOCD_VERSION" || "$ARGOCD_VERSION" == "null" ]]; then
    echo "ERROR: argocd_version is required in context" >&2
    exit 1
fi

# Check if ArgoCD CLI already installed
if command -v argocd &> /dev/null; then
    INSTALLED_VERSION=$(argocd version --client --short 2>/dev/null | grep -oP 'v\d+\.\d+\.\d+' || echo "unknown")
    echo "ArgoCD CLI already installed: $INSTALLED_VERSION"
    
    if [[ "$INSTALLED_VERSION" == "$ARGOCD_VERSION" ]]; then
        echo "✓ Correct version already installed"
        exit 0
    else
        echo "Upgrading from $INSTALLED_VERSION to $ARGOCD_VERSION..."
    fi
fi

# Download ArgoCD CLI
echo "Downloading ArgoCD CLI $ARGOCD_VERSION..."

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

DOWNLOAD_URL="https://github.com/argoproj/argo-cd/releases/download/${ARGOCD_VERSION}/argocd-${OS}-${ARCH}"

if ! curl -sSL -o "$TEMP_FILE" "$DOWNLOAD_URL"; then
    echo "ERROR: Failed to download ArgoCD CLI from $DOWNLOAD_URL" >&2
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
    echo "ERROR: Failed to install ArgoCD CLI to $INSTALL_PATH" >&2
    exit 1
fi

# Verify installation
if ! command -v argocd &> /dev/null; then
    echo "ERROR: ArgoCD CLI not found in PATH after installation" >&2
    exit 1
fi

INSTALLED_VERSION=$(argocd version --client --short 2>/dev/null | grep -oP 'v\d+\.\d+\.\d+' || echo "unknown")
echo "✓ ArgoCD CLI installed successfully: $INSTALLED_VERSION"
