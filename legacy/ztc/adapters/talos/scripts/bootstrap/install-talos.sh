#!/bin/bash
# Install Talos OS on bare-metal server
# Adapted from zerotouch-platform/scripts/bootstrap/install/03-install-talos.sh

set -euo pipefail

# Read context data from ZTC
if [ -z "${ZTC_CONTEXT_FILE:-}" ]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set"
    exit 1
fi

NODES=$(jq -c '.nodes[]' "$ZTC_CONTEXT_FILE")
FACTORY_IMAGE_ID=$(jq -r '.factory_image_id' "$ZTC_CONTEXT_FILE")
DISK_DEVICE=$(jq -r '.disk_device' "$ZTC_CONTEXT_FILE")
TALOS_VERSION="${TALOS_VERSION:-v1.11.5}"

# Check dependencies
if ! command -v sshpass &> /dev/null; then
    echo "ERROR: sshpass not installed"
    echo "  macOS: brew install sshpass"
    echo "  Linux: sudo apt-get install sshpass"
    exit 1
fi

TALOS_IMAGE_URL="https://factory.talos.dev/image/${FACTORY_IMAGE_ID}/${TALOS_VERSION}/metal-amd64.raw.xz"

echo "Installing Talos ${TALOS_VERSION} on nodes..."
echo "Factory Image: $FACTORY_IMAGE_ID"
echo "Disk Device: $DISK_DEVICE"

# Process each node
echo "$NODES" | while IFS= read -r node; do
    NODE_NAME=$(echo "$node" | jq -r '.name')
    NODE_IP=$(echo "$node" | jq -r '.ip')
    NODE_ROLE=$(echo "$node" | jq -r '.role')
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Installing Talos on: $NODE_NAME ($NODE_IP) - $NODE_ROLE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Get SSH credentials from environment
    SSH_USER="${SSH_USER:-root}"
    SSH_PASSWORD="${SSH_PASSWORD:-}"
    
    if [ -z "$SSH_PASSWORD" ]; then
        echo "ERROR: SSH_PASSWORD environment variable not set"
        exit 1
    fi
    
    # Test connectivity
    echo "Testing SSH connectivity..."
    if ! sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$NODE_IP" "echo 'Connected'" 2>/dev/null; then
        echo "ERROR: Cannot connect to $NODE_IP. Is rescue mode enabled?"
        exit 1
    fi
    echo "✓ SSH connection successful"
    
    # Download Talos image
    echo "Downloading Talos image..."
    sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$NODE_IP" \
        "curl -L -o /tmp/talos.raw.xz '$TALOS_IMAGE_URL'"
    
    # Verify download
    echo "Verifying download..."
    sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$NODE_IP" \
        "ls -lh /tmp/talos.raw.xz"
    
    # Flash to disk
    echo "⚠️  Flashing Talos to $DISK_DEVICE (DESTRUCTIVE)..."
    sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$NODE_IP" \
        "xz -d -c /tmp/talos.raw.xz | dd of=$DISK_DEVICE bs=4M status=progress && sync"
    
    echo "✓ Talos flashed successfully"
    
    # Reboot
    echo "Rebooting into Talos..."
    sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$NODE_IP" \
        "reboot" || true
    
    echo "✓ $NODE_NAME installation complete"
done

echo ""
echo "✓ Talos installation complete on all nodes"
echo "Wait 2-3 minutes for nodes to boot into Talos"
