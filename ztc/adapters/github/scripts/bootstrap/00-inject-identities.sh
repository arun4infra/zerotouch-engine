#!/usr/bin/env bash
set -euo pipefail

# 00-inject-identities.sh
# Purpose: Inject GitHub App credentials into ArgoCD namespace
# Execution: Bootstrap phase (after cluster creation)
# Context: Receives context via $ZTC_CONTEXT_FILE, secrets via environment variables

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   GitHub App Authentication - Identity Injection            ║${NC}"
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
GIT_APP_ID=$(jq -r '.github_app_id' "$ZTC_CONTEXT_FILE")
INSTALLATION_ID=$(jq -r '.github_app_installation_id' "$ZTC_CONTEXT_FILE")

# Verify required context data
if [[ -z "$GIT_APP_ID" || "$GIT_APP_ID" == "null" ]]; then
    echo -e "${RED}✗ Error: github_app_id not found in context${NC}" >&2
    exit 1
fi

if [[ -z "$INSTALLATION_ID" || "$INSTALLATION_ID" == "null" ]]; then
    echo -e "${RED}✗ Error: github_app_installation_id not found in context${NC}" >&2
    exit 1
fi

# Verify secret environment variable
if [[ -z "${GITHUB_APP_PRIVATE_KEY:-}" ]]; then
    echo -e "${RED}✗ Error: GITHUB_APP_PRIVATE_KEY environment variable not set${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ GitHub App ID: $GIT_APP_ID${NC}"
echo -e "${GREEN}✓ Installation ID: $INSTALLATION_ID${NC}"
echo -e "${GREEN}✓ Private key loaded from environment${NC}"
echo ""

# Check kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}✗ Error: kubectl not found${NC}" >&2
    echo -e "${YELLOW}Install kubectl: https://kubernetes.io/docs/tasks/tools/${NC}" >&2
    exit 1
fi

# Ensure ArgoCD namespace exists
echo -e "${BLUE}Ensuring ArgoCD namespace exists...${NC}"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1
echo -e "${GREEN}✓ ArgoCD namespace ready${NC}"
echo ""

# Create or update the secret
echo -e "${BLUE}Creating GitHub App credentials secret...${NC}"

kubectl create secret generic argocd-github-app-creds \
    --namespace=argocd \
    --from-literal=githubAppID="$GIT_APP_ID" \
    --from-literal=githubAppInstallationID="$INSTALLATION_ID" \
    --from-literal=githubAppPrivateKey="$GITHUB_APP_PRIVATE_KEY" \
    --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ Secret argocd-github-app-creds created/updated successfully${NC}"
else
    echo -e "${RED}✗ Failed to create secret${NC}" >&2
    exit 1
fi

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Summary                                                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ GitHub App authentication credentials injected${NC}"
echo -e "${GREEN}✓ Secret: argocd-github-app-creds${NC}"
echo -e "${GREEN}✓ Namespace: argocd${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Deploy ArgoCD with GitHub App authentication"
echo -e "  2. Configure ArgoCD to use the GitHub App credentials"
echo -e "  3. Verify: ${GREEN}kubectl get secret -n argocd argocd-github-app-creds${NC}"
echo ""

exit 0
