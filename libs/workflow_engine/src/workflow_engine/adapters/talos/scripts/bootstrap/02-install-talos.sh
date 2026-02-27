#!/bin/bash
# Install Talos OS on bare-metal server
# Adapted from zerotouch-platform/scripts/bootstrap/install/03-install-talos.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Read context data from ZTC
if [ -z "${ZTC_CONTEXT_FILE:-}" ]; then
    log_error "ZTC_CONTEXT_FILE not set"
    exit 1
fi

NODES=$(jq -c '.nodes[]' "$ZTC_CONTEXT_FILE")
FACTORY_IMAGE_ID=$(jq -r '.factory_image_id' "$ZTC_CONTEXT_FILE")
DISK_DEVICE=$(jq -r '.disk_device // "/dev/sda"' "$ZTC_CONTEXT_FILE")
TALOS_VERSION=$(jq -r '.nodes[0].talos_version // "v1.11.5"' "$ZTC_CONTEXT_FILE")

# Check dependencies
if ! command -v sshpass &> /dev/null; then
    log_error "sshpass not installed"
    echo "  macOS: brew install sshpass"
    echo "  Linux: sudo apt-get install sshpass"
    exit 1
fi

TALOS_IMAGE_URL="https://factory.talos.dev/image/${FACTORY_IMAGE_ID}/${TALOS_VERSION}/metal-amd64.raw.xz"

log_info "Starting Talos installation on rescue machine(s)"
log_info "Factory Image: $FACTORY_IMAGE_ID"
log_info "Disk Device: $DISK_DEVICE"
log_info "Talos Version: $TALOS_VERSION"

# SSH command wrapper
ssh_exec() {
    local node_ip="$1"
    local cmd="$2"
    sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$node_ip" "$cmd"
}

# Process each node
echo "$NODES" | while IFS= read -r node; do
    NODE_NAME=$(echo "$node" | jq -r '.name')
    NODE_IP=$(echo "$node" | jq -r '.ip')
    NODE_ROLE=$(echo "$node" | jq -r '.role')
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Installing Talos on: $NODE_NAME ($NODE_IP) - $NODE_ROLE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Get SSH credentials from environment
    SSH_USER="${SSH_USER:-root}"
    SSH_PASSWORD="${SSH_PASSWORD:-}"
    
    if [ -z "$SSH_PASSWORD" ]; then
        log_error "SSH_PASSWORD environment variable not set"
        exit 1
    fi
    
    # Step 1: Test connectivity
    log_info "Step 1: Testing SSH connectivity..."
    if ! ssh_exec "$NODE_IP" "echo 'Connected'" 2>/dev/null; then
        log_error "Cannot connect to $NODE_IP. Is rescue mode enabled?"
        exit 1
    fi
    log_info "✓ SSH connection successful"
    
    # Step 2: Detect disk device
    log_info "Step 2: Detecting disk devices..."
    ssh_exec "$NODE_IP" "lsblk"
    log_warn "Using disk device: $DISK_DEVICE"
    log_warn "⚠️  ALL DATA ON $DISK_DEVICE WILL BE ERASED!"
    
    # Step 3: Download Talos image
    log_info "Step 3: Downloading Talos ${TALOS_VERSION} image..."
    ssh_exec "$NODE_IP" "curl -L -o /tmp/talos.raw.xz '$TALOS_IMAGE_URL'"
    
    # Step 4: Verify download
    log_info "Step 4: Verifying download..."
    ssh_exec "$NODE_IP" "ls -lh /tmp/talos.raw.xz"
    
    # Step 5: Flash to disk
    log_info "Step 5: Flashing Talos to $DISK_DEVICE (this may take 5-10 minutes)..."
    log_warn "⚠️  DESTRUCTIVE OPERATION - Wiping $DISK_DEVICE now!"
    ssh_exec "$NODE_IP" "xz -d -c /tmp/talos.raw.xz | dd of=$DISK_DEVICE bs=4M status=progress && sync"
    
    log_info "✓ Talos image written successfully"
    
    # Step 6: Reboot
    log_info "Step 6: Rebooting server into Talos..."
    ssh_exec "$NODE_IP" "reboot" || true  # SSH will disconnect, so ignore error
    log_info "✓ Reboot initiated"
    
    log_info "✓ $NODE_NAME installation complete"
done

echo ""
cat << EOF

${GREEN}════════════════════════════════════════════════════════${NC}
${GREEN}✓ Talos installation completed on all nodes!${NC}
${GREEN}════════════════════════════════════════════════════════${NC}

${YELLOW}Wait 2-3 minutes for nodes to boot into Talos${NC}

EOF
