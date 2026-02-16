#!/bin/bash
set -euo pipefail

# Backup Age Private Key to Hetzner Object Storage
# Reads context from $ZTC_CONTEXT_FILE and secrets from environment variables
# Requires AGE_PRIVATE_KEY environment variable (from 08b-generate-age-keys.sh)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPERS_DIR="$SCRIPT_DIR/../shared"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Backup Age Key to Hetzner Object Storage                  ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Validate AGE_PRIVATE_KEY
if [ -z "${AGE_PRIVATE_KEY:-}" ]; then
    echo -e "${RED}✗ AGE_PRIVATE_KEY not set${NC}"
    echo -e "${YELLOW}Run 08b-generate-age-keys.sh first${NC}"
    exit 1
fi

# Source helper libraries
if [ ! -f "$HELPERS_DIR/s3-helpers.sh" ]; then
    echo -e "${RED}✗ Error: s3-helpers.sh not found${NC}"
    exit 1
fi

if [ ! -f "$HELPERS_DIR/age-helpers.sh" ]; then
    echo -e "${RED}✗ Error: age-helpers.sh not found${NC}"
    exit 1
fi

source "$HELPERS_DIR/s3-helpers.sh"
source "$HELPERS_DIR/age-helpers.sh"

# Configure S3 credentials
echo -e "${BLUE}Configuring S3 credentials...${NC}"
if ! configure_s3_credentials; then
    echo -e "${RED}✗ Error: Failed to configure S3 credentials${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites validated${NC}"
echo ""

# Generate recovery master key
echo -e "${BLUE}Generating recovery master key...${NC}"
if ! generate_recovery_keypair; then
    echo -e "${RED}✗ Error: Failed to generate recovery keypair${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Recovery master key generated${NC}"
echo -e "${BLUE}Recovery public key: $RECOVERY_PUBLIC${NC}"
echo ""

# Use centralized S3 backup function
echo -e "${BLUE}Backing up Age key to S3...${NC}"
if ! s3_backup_age_key "$AGE_PRIVATE_KEY" "$RECOVERY_PRIVATE" "$RECOVERY_PUBLIC"; then
    echo -e "${RED}✗ Failed to backup Age key to S3${NC}"
    exit 1
fi

# Export recovery key for in-cluster backup
export RECOVERY_PRIVATE_KEY="$RECOVERY_PRIVATE"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Backup Summary                                             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ Age key backed up to Hetzner Object Storage${NC}"
echo -e "${GREEN}✓ Location: s3://$S3_BUCKET/age-keys/ACTIVE-*${NC}"
echo ""
echo -e "${YELLOW}CRITICAL: Store recovery key securely offline${NC}"
echo -e "${YELLOW}Recovery public key: $RECOVERY_PUBLIC${NC}"
echo ""
echo -e "${BLUE}To recover Age key (using active markers):${NC}"
echo -e "  1. Download: ${GREEN}aws s3 cp s3://$S3_BUCKET/age-keys/ACTIVE-recovery-key.txt recovery.key --endpoint-url $S3_ENDPOINT${NC}"
echo -e "  2. Download: ${GREEN}aws s3 cp s3://$S3_BUCKET/age-keys/ACTIVE-age-key-encrypted.txt encrypted.txt --endpoint-url $S3_ENDPOINT${NC}"
echo -e "  3. Decrypt: ${GREEN}age -d -i recovery.key encrypted.txt${NC}"
echo ""
