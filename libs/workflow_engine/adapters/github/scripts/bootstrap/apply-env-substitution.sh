#!/usr/bin/env bash
set -euo pipefail

# apply-env-substitution.sh
# Purpose: Update tenant repository URLs in ArgoCD Application manifests
# Execution: Bootstrap phase (after cluster creation)
# Context: Receives context via $ZTC_CONTEXT_FILE

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Apply Environment Variable Substitution                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Read context data from JSON file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo -e "${RED}✗ Error: ZTC_CONTEXT_FILE environment variable not set${NC}" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo -e "${RED}✗ Error: Context file not found: $ZTC_CONTEXT_FILE${NC}" >&2
    exit 1
fi

# Extract context data using jq
TENANT_ORG_NAME=$(jq -r '.tenant_org_name' "$ZTC_CONTEXT_FILE")
TENANT_REPO_NAME=$(jq -r '.tenant_repo_name' "$ZTC_CONTEXT_FILE")

# Verify required context data
if [[ -z "$TENANT_ORG_NAME" || "$TENANT_ORG_NAME" == "null" ]]; then
    echo -e "${RED}✗ Error: tenant_org_name not found in context${NC}" >&2
    exit 1
fi

if [[ -z "$TENANT_REPO_NAME" || "$TENANT_REPO_NAME" == "null" ]]; then
    echo -e "${RED}✗ Error: tenant_repo_name not found in context${NC}" >&2
    exit 1
fi

# Build TENANTS_REPO_URL from components
TENANTS_REPO_URL="https://github.com/${TENANT_ORG_NAME}/${TENANT_REPO_NAME}-tenants.git"

echo -e "${GREEN}✓ Organization: $TENANT_ORG_NAME${NC}"
echo -e "${GREEN}✓ Repository: $TENANT_REPO_NAME-tenants${NC}"
echo -e "${GREEN}✓ Tenant repo URL: $TENANTS_REPO_URL${NC}"
echo ""

# Determine repository root
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

echo -e "${BLUE}Applying substitutions to ArgoCD applications...${NC}"

# Function to replace tenant repo URL in files
replace_tenant_url() {
    local file="$1"
    if [[ -f "$file" ]]; then
        # Replace any github.com/*/zerotouch-tenants.git or *-tenants.git with the correct URL
        sed -i.bak "s|repoURL: https://github.com/.*/.*-tenants\.git|repoURL: ${TENANTS_REPO_URL}|g" "$file"
        rm -f "${file}.bak"
        echo -e "${GREEN}  ✓ $(basename "$file")${NC}"
    else
        echo -e "${YELLOW}  ⚠️  $(basename "$file") not found (skipping)${NC}"
    fi
}

# Process all files with tenant repo URLs
replace_tenant_url "$REPO_ROOT/bootstrap/argocd/overlays/main/core/argocd-repo-configs.yaml"
replace_tenant_url "$REPO_ROOT/bootstrap/argocd/overlays/main/core/tenant-infrastructure.yaml"
replace_tenant_url "$REPO_ROOT/bootstrap/argocd/overlays/main/dev/99-tenants.yaml"
replace_tenant_url "$REPO_ROOT/bootstrap/argocd/overlays/main/staging/99-tenants.yaml"
replace_tenant_url "$REPO_ROOT/bootstrap/argocd/overlays/main/prod/99-tenants.yaml"

echo ""
echo -e "${GREEN}✅ Environment substitution complete${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Review changes: ${GREEN}git diff${NC}"
echo -e "  2. Commit: ${GREEN}git add bootstrap/ && git commit -m 'chore: apply env substitution'${NC}"
echo -e "  3. Push: ${GREEN}git push${NC}"
echo ""

exit 0
