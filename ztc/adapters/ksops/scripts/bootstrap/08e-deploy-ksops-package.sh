#!/usr/bin/env bash
# Deploy KSOPS Package to ArgoCD
#
# META_REQUIRE: None

set -euo pipefail

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

echo "KSOPS Package Deployment to ArgoCD"
echo "==================================="
echo ""

# Check ArgoCD is running
echo "Checking ArgoCD status..."
if ! kubectl get deployment argocd-repo-server -n argocd &>/dev/null; then
    echo "ERROR: ArgoCD repo-server deployment not found" >&2
    exit 1
fi
echo "✓ ArgoCD repo-server found"
echo ""

# NOTE: KSOPS init container patch is already applied during ArgoCD installation
# via bootstrap/argocd/install/kustomization.yaml (JSON patches)
# No need to patch again here
echo "Skipping KSOPS patch (already applied at install time)..."
echo ""

# Get repository root
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Apply KSOPS package (includes Age Key Guardian CronJob)
echo "Applying KSOPS package resources..."
if [ -d "$REPO_ROOT/platform/secrets/ksops/" ]; then
    kubectl apply -k "$REPO_ROOT/platform/secrets/ksops/"
    echo "✓ KSOPS package resources applied"
else
    echo "WARNING: KSOPS package directory not found at $REPO_ROOT/platform/secrets/ksops/" >&2
    echo "Skipping package application" >&2
fi
echo ""

# No rollout needed - deployment not changed
echo "✓ ArgoCD repo-server already configured with KSOPS"
echo ""

echo "✅ KSOPS package deployment complete"
