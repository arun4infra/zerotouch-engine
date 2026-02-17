#!/usr/bin/env bash
# KSOPS Tools Installation Script
# Installs SOPS and Age binaries only
#
# META_REQUIRE: None

set -euo pipefail

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

# Configuration
SOPS_VERSION="v3.8.1"
AGE_VERSION="v1.1.1"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo "KSOPS Tools Installation"
echo "========================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command_exists kubectl; then
    echo "ERROR: kubectl is not installed" >&2
    exit 1
fi

echo "✓ Prerequisites satisfied"
echo ""

# Install SOPS
if ! command_exists sops; then
    echo "Installing SOPS $SOPS_VERSION..."
    local OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    curl -LO "https://github.com/getsops/sops/releases/download/$SOPS_VERSION/sops-$SOPS_VERSION.${OS}.amd64"
    chmod +x "sops-$SOPS_VERSION.${OS}.amd64"
    sudo mv "sops-$SOPS_VERSION.${OS}.amd64" /usr/local/bin/sops
    echo "✓ SOPS installed successfully"
else
    echo "✓ SOPS already available: $(sops --version)"
fi

# Install Age
if ! command_exists age || ! command_exists age-keygen; then
    echo "Installing Age $AGE_VERSION..."
    local OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    curl -LO "https://github.com/FiloSottile/age/releases/download/$AGE_VERSION/age-$AGE_VERSION-${OS}-amd64.tar.gz"
    tar xzf "age-$AGE_VERSION-${OS}-amd64.tar.gz"
    sudo mv age/age /usr/local/bin/
    sudo mv age/age-keygen /usr/local/bin/
    rm -rf age "age-$AGE_VERSION-${OS}-amd64.tar.gz"
    echo "✓ Age installed successfully"
else
    echo "✓ Age already available: $(age --version)"
fi

# Install KSOPS kustomize plugin
local PLUGIN_DIR="$HOME/.config/kustomize/plugin/viaduct.ai/v1/ksops"

if [ -f "$PLUGIN_DIR/ksops" ]; then
    echo "✓ KSOPS plugin already installed"
else
    echo "Installing KSOPS kustomize plugin..."
    
    # Create plugin directory
    mkdir -p "$PLUGIN_DIR"
    
    # Detect OS and architecture
    local OS=$(uname -s)
    local ARCH=$(uname -m)
    
    case "$OS" in
        Darwin)
            OS="Darwin"
            ;;
        Linux)
            OS="Linux"
            ;;
        *)
            echo "ERROR: Unsupported OS: $OS" >&2
            exit 1
            ;;
    esac
    
    case "$ARCH" in
        x86_64)
            ARCH="x86_64"
            ;;
        arm64|aarch64)
            ARCH="arm64"
            ;;
        *)
            echo "ERROR: Unsupported architecture: $ARCH" >&2
            exit 1
            ;;
    esac
    
    # Download and extract KSOPS archive with retry
    local TEMP_DIR=$(mktemp -d)
    local DOWNLOAD_URL="https://github.com/viaduct-ai/kustomize-sops/releases/latest/download/ksops_latest_${OS}_${ARCH}.tar.gz"
    local MAX_RETRIES=3
    local RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        echo "Downloading KSOPS (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)..."
        if curl -Lo "$TEMP_DIR/ksops.tar.gz" "$DOWNLOAD_URL"; then
            if tar -tzf "$TEMP_DIR/ksops.tar.gz" >/dev/null 2>&1; then
                echo "✓ Download successful"
                break
            else
                echo "ERROR: Downloaded file is corrupted" >&2
                rm -f "$TEMP_DIR/ksops.tar.gz"
            fi
        fi
        RETRY_COUNT=$((RETRY_COUNT + 1))
        [ $RETRY_COUNT -lt $MAX_RETRIES ] && sleep 2
    done
    
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo "ERROR: Failed to download KSOPS after $MAX_RETRIES attempts" >&2
        rm -rf "$TEMP_DIR"
        exit 1
    fi
    
    tar -xzf "$TEMP_DIR/ksops.tar.gz" -C "$TEMP_DIR"
    mv "$TEMP_DIR/ksops" "$PLUGIN_DIR/ksops"
    chmod +x "$PLUGIN_DIR/ksops"
    rm -rf "$TEMP_DIR"
    
    echo "✓ KSOPS plugin installed successfully"
fi

echo ""
echo "✅ KSOPS tools installation complete"
