#!/bin/bash
# Deploy ArgoCD root application

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

# Read from context file
MODE=$(jq -r '.mode // "production"' "$ZTC_CONTEXT_FILE")
ENV=$(jq -r '.env // "dev"' "$ZTC_CONTEXT_FILE")
NAMESPACE=$(jq -r '.namespace // "argocd"' "$ZTC_CONTEXT_FILE")

# Determine root app overlay path based on environment
if [ "$MODE" = "preview" ]; then
    ROOT_APP_OVERLAY="platform/generated/argocd/kind"
else
    ROOT_APP_OVERLAY="platform/generated/argocd/k8/overlays/$ENV"
fi

echo "════════════════════════════════════════════════════════"
echo "ArgoCD Root Application Deployment"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Mode: $MODE"
echo "Environment: $ENV"
echo "Overlay: $ROOT_APP_OVERLAY"
echo ""

# Get admin password
echo "Retrieving ArgoCD credentials..."
ARGOCD_PASSWORD=$(kubectl -n "$NAMESPACE" get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" 2>/dev/null | base64 -d || echo "")

if [[ -n "$ARGOCD_PASSWORD" ]]; then
    echo "✓ ArgoCD credentials retrieved"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "ArgoCD Login Credentials:"
    echo "  Username: admin"
    if [[ -z "${CI:-}" ]]; then
        echo "  Password: $ARGOCD_PASSWORD"
    else
        echo "  Password: ***MASKED*** (CI mode)"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

# Deploy root application
echo "Deploying root application from: $ROOT_APP_OVERLAY"

if [[ ! -f "$ROOT_APP_OVERLAY/root.yaml" ]]; then
    echo "ERROR: Root application not found at: $ROOT_APP_OVERLAY/root.yaml" >&2
    exit 1
fi

echo "Applying root application..."
kubectl apply --server-side -f "$ROOT_APP_OVERLAY/root.yaml"

echo "✓ Root application deployed"
echo ""

# Wait for application to be detected
echo "Waiting for ArgoCD to detect application..."
sleep 5

echo "Checking ArgoCD applications..."
kubectl get applications -n "$NAMESPACE"

echo ""
echo "✓ GitOps deployment initiated!"
echo ""
echo "Monitor deployment:"
echo "  kubectl get applications -n $NAMESPACE -w"
echo ""
echo "Access ArgoCD UI:"
echo "  kubectl port-forward svc/argocd-server -n $NAMESPACE 8080:443"
echo "  https://localhost:8080"
echo ""
