#!/usr/bin/env bash
# Inject GitHub App authentication credentials into ArgoCD
#
# META_REQUIRE: github_app_id (context)
# META_REQUIRE: github_app_installation_id (context)
# META_REQUIRE: GITHUB_APP_PRIVATE_KEY (env)

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

echo "GitHub App Authentication - Identity Injection"
echo "==============================================="
echo ""

# Read configuration from context
GIT_APP_ID=$(jq -r '.github_app_id' "$ZTC_CONTEXT_FILE")
INSTALLATION_ID=$(jq -r '.github_app_installation_id' "$ZTC_CONTEXT_FILE")

# Read private key from environment
PRIVATE_KEY_CONTENT="${GITHUB_APP_PRIVATE_KEY:?GITHUB_APP_PRIVATE_KEY not set}"

# Validate inputs
if [[ -z "$GIT_APP_ID" || "$GIT_APP_ID" == "null" ]]; then
    echo "ERROR: github_app_id required in context" >&2
    exit 1
fi

if [[ -z "$INSTALLATION_ID" || "$INSTALLATION_ID" == "null" ]]; then
    echo "ERROR: github_app_installation_id required in context" >&2
    exit 1
fi

echo "✓ GitHub App ID: $GIT_APP_ID"
echo "✓ Installation ID: $INSTALLATION_ID"
echo ""

# Check kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not found" >&2
    echo "Install kubectl: https://kubernetes.io/docs/tasks/tools/" >&2
    exit 1
fi

# Ensure ArgoCD namespace exists
echo "Ensuring ArgoCD namespace exists..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1
echo "✓ ArgoCD namespace ready"
echo ""

# Create or update the secret
echo "Creating GitHub App credentials secret..."

kubectl create secret generic argocd-github-app-creds \
    --namespace=argocd \
    --from-literal=githubAppID="$GIT_APP_ID" \
    --from-literal=githubAppInstallationID="$INSTALLATION_ID" \
    --from-literal=githubAppPrivateKey="$PRIVATE_KEY_CONTENT" \
    --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Secret argocd-github-app-creds created/updated successfully"
else
    echo "ERROR: Failed to create secret" >&2
    exit 1
fi

echo ""
echo "Summary"
echo "======="
echo ""
echo "✓ GitHub App authentication credentials injected"
echo "✓ Secret: argocd-github-app-creds"
echo "✓ Namespace: argocd"
echo ""
echo "Next steps:"
echo "  1. Deploy ArgoCD with GitHub App authentication"
echo "  2. Configure ArgoCD to use the GitHub App credentials"
echo "  3. Verify: kubectl get secret -n argocd argocd-github-app-creds"
echo ""

exit 0
