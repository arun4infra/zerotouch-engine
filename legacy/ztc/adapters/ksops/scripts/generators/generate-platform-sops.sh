#!/bin/bash
# META_REQUIRE: sops, jq
# INCLUDE: shared/env-helpers.sh

# Master script to generate all platform secrets
# Orchestrates generation of environment, tenant, and core secrets

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Generate Platform Secrets (KSOPS)                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Read context
if [ -z "$ZTC_CONTEXT_FILE" ]; then
    echo -e "${RED}✗ ZTC_CONTEXT_FILE not set${NC}"
    exit 1
fi

REPO_ROOT=$(jq -r '.repo_root' "$ZTC_CONTEXT_FILE")
ENV_PREFIX=$(jq -r '.env_prefix' "$ZTC_CONTEXT_FILE")
SECRETS_DIR=$(jq -r '.secrets_dir' "$ZTC_CONTEXT_FILE")
SOPS_CONFIG=$(jq -r '.sops_config_path' "$ZTC_CONTEXT_FILE")
SCRIPT_DIR=$(jq -r '.script_dir' "$ZTC_CONTEXT_FILE")

echo -e "${GREEN}✓ Environment prefix: $ENV_PREFIX${NC}"
echo -e "${GREEN}✓ Repository: $REPO_ROOT${NC}"
echo -e "${GREEN}✓ SOPS config: $SOPS_CONFIG${NC}"
echo -e "${GREEN}✓ Output: $SECRETS_DIR${NC}"
echo ""

if ! command -v sops &> /dev/null; then
    echo -e "${RED}✗ Error: sops not found${NC}"
    exit 1
fi

# Verify .sops.yaml exists
if [ ! -f "$SOPS_CONFIG" ]; then
    echo -e "${RED}✗ Error: .sops.yaml not found at $SOPS_CONFIG${NC}"
    exit 1
fi

# Clean up old secrets
if [ -d "$SECRETS_DIR" ]; then
    echo -e "${YELLOW}Cleaning up old secrets...${NC}"
    rm -f "$SECRETS_DIR"/*.secret.yaml
    echo -e "${GREEN}✓ Old secrets removed${NC}"
    echo ""
fi

# Export SOPS config for sub-scripts
export SOPS_CONFIG

# Run generator scripts
"$SCRIPT_DIR/generate-env-secrets.sh"
"$SCRIPT_DIR/generate-tenant-registry-secrets.sh"
"$SCRIPT_DIR/generate-core-secrets.sh"

echo -e "${GREEN}✅ Platform secrets generated for $ENV_PREFIX${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Review: ${GREEN}ls -la $SECRETS_DIR${NC}"
echo -e "  2. Commit secrets to repository"
echo ""

exit 0
