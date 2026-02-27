#!/usr/bin/env bash
# Apply environment variable substitution to ArgoCD applications and secrets
#
# META_REQUIRE: tenant_org_name (context)
# META_REQUIRE: tenant_repo_name (context)

set -euo pipefail

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo "ERROR: Context file not found: $ZTC_CONTEXT_FILE" >&2
    exit 1
fi

echo "Apply Environment Variable Substitution"
echo "========================================"
echo ""

# Read configuration from context
ORG_NAME=$(jq -r '.tenant_org_name' "$ZTC_CONTEXT_FILE")
TENANTS_REPO_NAME=$(jq -r '.tenant_repo_name' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$ORG_NAME" || "$ORG_NAME" == "null" ]]; then
    echo "ERROR: tenant_org_name required in context" >&2
    exit 1
fi

if [[ -z "$TENANTS_REPO_NAME" || "$TENANTS_REPO_NAME" == "null" ]]; then
    echo "ERROR: tenant_repo_name required in context" >&2
    exit 1
fi

# Build TENANTS_REPO_URL from components
TENANTS_REPO_URL="https://github.com/${ORG_NAME}/${TENANTS_REPO_NAME}.git"
export TENANTS_REPO_URL

echo "✓ Built TENANTS_REPO_URL: $TENANTS_REPO_URL"
echo ""

# Get repository root
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

echo "Applying substitutions to ArgoCD applications..."

# Function to replace tenant repo URL in files
replace_tenant_url() {
    local file="$1"
    if [ -f "$file" ]; then
        # Replace any github.com/*/zerotouch-tenants.git with the correct URL
        sed -i.bak "s|repoURL: https://github.com/.*/zerotouch-tenants\.git|repoURL: ${TENANTS_REPO_URL}|g" "$file"
        rm -f "${file}.bak"
        echo "  ✓ $(basename $file)"
    else
        echo "  ⚠️  $(basename $file) not found"
    fi
}

# Process all files with tenant repo URLs
replace_tenant_url "$REPO_ROOT/platform/generated/argocd/k8/core/argocd-repo-configs.yaml"
replace_tenant_url "$REPO_ROOT/platform/generated/argocd/k8/core/tenant-infrastructure.yaml"
replace_tenant_url "$REPO_ROOT/platform/generated/argocd/k8/overlays/dev/99-tenants.yaml"
replace_tenant_url "$REPO_ROOT/platform/generated/argocd/k8/overlays/staging/99-tenants.yaml"
replace_tenant_url "$REPO_ROOT/platform/generated/argocd/k8/overlays/prod/99-tenants.yaml"

echo ""
echo "✅ Environment substitution complete"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff"
echo "  2. Commit: git add bootstrap/ && git commit -m 'chore: apply env substitution'"
echo "  3. Push: git push"
