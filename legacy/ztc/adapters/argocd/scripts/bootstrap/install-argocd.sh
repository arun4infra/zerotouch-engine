#!/usr/bin/env bash
set -euo pipefail

# ArgoCD Installation Script
# Installs ArgoCD into Kubernetes cluster using Kustomize

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
MODE=$(jq -r '.mode' "$ZTC_CONTEXT_FILE")
MANIFESTS_PATH=$(jq -r '.manifests_path' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo "ERROR: namespace is required in context" >&2
    exit 1
fi

if [[ -z "$MODE" || "$MODE" == "null" ]]; then
    echo "ERROR: mode is required in context" >&2
    exit 1
fi

if [[ -z "$MANIFESTS_PATH" || "$MANIFESTS_PATH" == "null" ]]; then
    echo "ERROR: manifests_path is required in context" >&2
    exit 1
fi

# Check prerequisites
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl is not installed" >&2
    exit 1
fi

if ! kubectl cluster-info &>/dev/null; then
    echo "ERROR: Cannot connect to Kubernetes cluster" >&2
    exit 1
fi

echo "Installing ArgoCD to cluster..."
echo "  Namespace: $NAMESPACE"
echo "  Mode: $MODE"
echo "  Manifests: $MANIFESTS_PATH"

# Create namespace if not exists
if kubectl get namespace "$NAMESPACE" &>/dev/null; then
    echo "✓ Namespace $NAMESPACE already exists"
else
    echo "Creating namespace $NAMESPACE..."
    if ! kubectl create namespace "$NAMESPACE"; then
        echo "ERROR: Failed to create namespace $NAMESPACE" >&2
        exit 1
    fi
    echo "✓ Namespace created"
fi

# Apply Kustomize manifests
echo "Applying ArgoCD manifests from $MANIFESTS_PATH..."

if [[ ! -d "$MANIFESTS_PATH" ]]; then
    echo "ERROR: Manifests directory not found: $MANIFESTS_PATH" >&2
    exit 1
fi

if ! kubectl apply -k "$MANIFESTS_PATH"; then
    echo "ERROR: Failed to apply ArgoCD manifests" >&2
    echo "Troubleshooting:" >&2
    echo "  - Check manifests exist: ls -la $MANIFESTS_PATH" >&2
    echo "  - Validate kustomization: kubectl kustomize $MANIFESTS_PATH" >&2
    exit 1
fi

echo "✓ ArgoCD manifests applied successfully"
echo "✓ ArgoCD installation complete"
