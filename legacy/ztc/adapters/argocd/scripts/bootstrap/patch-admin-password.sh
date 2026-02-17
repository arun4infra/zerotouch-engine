#!/usr/bin/env bash
set -euo pipefail

# ArgoCD Admin Password Patch Script
# Patches argocd-secret with hashed admin password

# Validate context file exists
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE environment variable not set" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo "ERROR: Context file not found: $ZTC_CONTEXT_FILE" >&2
    exit 1
fi

# Parse context with jq
NAMESPACE=$(jq -r '.namespace' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo "ERROR: namespace is required in context" >&2
    exit 1
fi

# Admin password comes from secret environment variable
if [[ -z "${ADMIN_PASSWORD:-}" ]]; then
    echo "ERROR: ADMIN_PASSWORD environment variable not set" >&2
    exit 1
fi

# Check prerequisites
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl is not installed" >&2
    exit 1
fi

if ! command -v htpasswd &> /dev/null; then
    echo "ERROR: htpasswd is not installed (apache2-utils package)" >&2
    exit 1
fi

echo "Patching ArgoCD admin password..."

# Hash password using bcrypt
HASHED_PASSWORD=$(htpasswd -nbBC 10 admin "$ADMIN_PASSWORD" | cut -d: -f2)

if [[ -z "$HASHED_PASSWORD" ]]; then
    echo "ERROR: Failed to hash password" >&2
    exit 1
fi

# Patch argocd-secret
echo "Updating argocd-secret in namespace $NAMESPACE..."

if ! kubectl patch secret argocd-secret -n "$NAMESPACE" \
    --type='json' \
    -p="[{\"op\": \"replace\", \"path\": \"/data/admin.password\", \"value\": \"$(echo -n "$HASHED_PASSWORD" | base64 -w0)\"}]"; then
    echo "ERROR: Failed to patch argocd-secret" >&2
    echo "Troubleshooting:" >&2
    echo "  - Check secret exists: kubectl get secret argocd-secret -n $NAMESPACE" >&2
    exit 1
fi

echo "✓ Admin password updated successfully"
