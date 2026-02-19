#!/usr/bin/env bash
set -euo pipefail

# validate-github-credentials.sh
# Purpose: Verify GitHub App credentials work in cluster context
# Execution: Validation phase (after bootstrap)
# Context: Receives context via $ZTC_CONTEXT_FILE, secrets via environment variables

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   GitHub Credentials Validation                             ║${NC}"
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
if ! command -v jq &> /dev/null; then
    echo -e "${RED}✗ Error: jq not found (required for JSON parsing)${NC}" >&2
    exit 1
fi

TENANT_ORG=$(jq -r '.tenant_org' "$ZTC_CONTEXT_FILE")
TENANT_REPO=$(jq -r '.tenant_repo' "$ZTC_CONTEXT_FILE")

# Verify required context data
if [[ -z "$TENANT_ORG" || "$TENANT_ORG" == "null" ]]; then
    echo -e "${RED}✗ Error: tenant_org not found in context${NC}" >&2
    exit 1
fi

if [[ -z "$TENANT_REPO" || "$TENANT_REPO" == "null" ]]; then
    echo -e "${RED}✗ Error: tenant_repo not found in context${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ Context data loaded${NC}"
echo -e "${BLUE}  Organization: $TENANT_ORG${NC}"
echo -e "${BLUE}  Repository: $TENANT_REPO${NC}"
echo ""

# Check kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}✗ Error: kubectl not found${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ kubectl found${NC}"
echo ""

# Verify ArgoCD namespace exists
echo -e "${BLUE}Checking ArgoCD namespace...${NC}"
if ! kubectl get namespace argocd &> /dev/null; then
    echo -e "${RED}✗ Error: argocd namespace not found${NC}" >&2
    echo -e "${YELLOW}Run bootstrap scripts first${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ ArgoCD namespace exists${NC}"
echo ""

# Verify GitHub App credentials secret exists
echo -e "${BLUE}Checking GitHub App credentials secret...${NC}"
if ! kubectl get secret argocd-github-app-creds -n argocd &> /dev/null; then
    echo -e "${RED}✗ Error: argocd-github-app-creds secret not found${NC}" >&2
    echo -e "${YELLOW}Run bootstrap scripts first (00-inject-identities.sh)${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ GitHub App credentials secret exists${NC}"
echo ""

# Verify secret contains required keys
echo -e "${BLUE}Validating secret contents...${NC}"
SECRET_KEYS=$(kubectl get secret argocd-github-app-creds -n argocd -o jsonpath='{.data}' | jq -r 'keys[]')

REQUIRED_KEYS=("githubAppID" "githubAppInstallationID" "githubAppPrivateKey")
MISSING_KEYS=()

for key in "${REQUIRED_KEYS[@]}"; do
    if ! echo "$SECRET_KEYS" | grep -q "^${key}$"; then
        MISSING_KEYS+=("$key")
    fi
done

if [ ${#MISSING_KEYS[@]} -gt 0 ]; then
    echo -e "${RED}✗ Error: Secret missing required keys: ${MISSING_KEYS[*]}${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ Secret contains all required keys${NC}"
echo ""

# Extract and validate App ID
echo -e "${BLUE}Validating GitHub App ID...${NC}"
APP_ID=$(kubectl get secret argocd-github-app-creds -n argocd -o jsonpath='{.data.githubAppID}' | base64 -d)

if [[ ! "$APP_ID" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}✗ Error: Invalid GitHub App ID format (must be numeric)${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ GitHub App ID is valid: $APP_ID${NC}"
echo ""

# Extract and validate Installation ID
echo -e "${BLUE}Validating GitHub App Installation ID...${NC}"
INSTALLATION_ID=$(kubectl get secret argocd-github-app-creds -n argocd -o jsonpath='{.data.githubAppInstallationID}' | base64 -d)

if [[ ! "$INSTALLATION_ID" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}✗ Error: Invalid Installation ID format (must be numeric)${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ Installation ID is valid: $INSTALLATION_ID${NC}"
echo ""

# Validate private key format
echo -e "${BLUE}Validating private key format...${NC}"
PRIVATE_KEY=$(kubectl get secret argocd-github-app-creds -n argocd -o jsonpath='{.data.githubAppPrivateKey}' | base64 -d)

if [[ ! "$PRIVATE_KEY" =~ ^-----BEGIN\ RSA\ PRIVATE\ KEY----- ]]; then
    echo -e "${RED}✗ Error: Invalid private key format (must be RSA private key)${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ Private key format is valid${NC}"
echo ""

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Validation Summary                                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ ArgoCD namespace exists${NC}"
echo -e "${GREEN}✓ GitHub App credentials secret exists${NC}"
echo -e "${GREEN}✓ Secret contains all required keys${NC}"
echo -e "${GREEN}✓ GitHub App ID is valid${NC}"
echo -e "${GREEN}✓ Installation ID is valid${NC}"
echo -e "${GREEN}✓ Private key format is valid${NC}"
echo ""
echo -e "${YELLOW}Note: This validates secret structure only${NC}"
echo -e "${YELLOW}API connectivity is validated during init phase${NC}"
echo ""

exit 0
