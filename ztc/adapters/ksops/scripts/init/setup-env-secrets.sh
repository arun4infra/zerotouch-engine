#!/usr/bin/env bash
# E2E script to setup environment-specific secrets
# Reads context from $ZTC_CONTEXT_FILE and secrets from environment variables
#
# This script orchestrates:
# 1. Generate Age keypair (or retrieve from S3)
# 2. Backup Age key to S3
# 3. Export keys for subsequent use

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   E2E Environment Secrets Setup                              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo "ERROR: Context file not found: $ZTC_CONTEXT_FILE" >&2
    exit 1
fi

echo -e "${GREEN}✓ Context file validated${NC}"
echo ""

# Step 1: Generate Age keypair
echo -e "${BLUE}[1/2] Generating Age keypair...${NC}"
source "$SCRIPT_DIR/08b-generate-age-keys.sh"

if [ -z "${AGE_PRIVATE_KEY:-}" ]; then
    echo -e "${RED}✗ Failed to generate/retrieve Age key${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Age keypair ready${NC}"
echo ""

# Step 2: Backup to S3
echo -e "${BLUE}[2/2] Backing up Age key to S3...${NC}"
"$SCRIPT_DIR/08b-backup-age-to-s3.sh"

echo -e "${GREEN}✓ Age key backed up to S3${NC}"
echo ""

# Summary
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Setup Complete                                             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✅ Environment secrets setup complete${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Add Age private key to GitHub org secrets"
echo -e "  2. Commit encrypted secrets"
echo -e "  3. Deploy to cluster"
echo ""
