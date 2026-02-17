#!/usr/bin/env bash
# Inject Age private key into ArgoCD namespace
#
# META_REQUIRE: AGE_PRIVATE_KEY (env)

set -euo pipefail

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

echo "Age Key Injection - SOPS Decryption Setup"
echo "=========================================="
echo ""

# Check kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl not found" >&2
    echo "Install kubectl: https://kubernetes.io/docs/tasks/tools/" >&2
    exit 1
fi

# Check if AGE_PRIVATE_KEY environment variable is set
if [ -z "${AGE_PRIVATE_KEY:-}" ]; then
    echo "ERROR: AGE_PRIVATE_KEY environment variable not set" >&2
    echo "Run generate-age-keys.sh first" >&2
    exit 1
fi

# Validate Age private key format
if [[ ! "$AGE_PRIVATE_KEY" =~ ^AGE-SECRET-KEY-1 ]]; then
    echo "ERROR: Invalid Age private key format" >&2
    echo "Expected format: AGE-SECRET-KEY-1..." >&2
    exit 1
fi

echo "✓ Age private key found in environment"
echo ""

# Wait for ArgoCD namespace to exist (up to 300 seconds)
echo "Waiting for ArgoCD namespace to exist..."
TIMEOUT=300
ELAPSED=0
INTERVAL=5

while [ $ELAPSED -lt $TIMEOUT ]; do
    if kubectl get namespace argocd &> /dev/null; then
        echo "✓ ArgoCD namespace exists"
        break
    fi
    
    echo "⏳ Waiting for ArgoCD namespace... (${ELAPSED}s/${TIMEOUT}s)"
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "ERROR: ArgoCD namespace not found after ${TIMEOUT} seconds" >&2
    echo "Create the namespace manually:" >&2
    echo "  kubectl create namespace argocd" >&2
    exit 1
fi

echo ""

# Create or update the sops-age secret
echo "Creating sops-age secret..."

# Delete existing secret if it exists to ensure clean replacement
kubectl delete secret sops-age -n argocd --ignore-not-found=true > /dev/null 2>&1

# Create new secret
kubectl create secret generic sops-age \
    --namespace=argocd \
    --from-literal=keys.txt="$AGE_PRIVATE_KEY" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Secret sops-age created/updated successfully"
else
    echo "ERROR: Failed to create secret" >&2
    exit 1
fi

echo ""

# Verify secret was created successfully
echo "Verifying secret..."

if kubectl get secret sops-age -n argocd &> /dev/null; then
    echo "✓ Secret sops-age exists in argocd namespace"
    
    # Validate secret format
    SECRET_KEY=$(kubectl get secret sops-age -n argocd -o jsonpath='{.data.keys\.txt}' 2>/dev/null | base64 -d)
    
    if [[ "$SECRET_KEY" =~ ^AGE-SECRET-KEY-1 ]]; then
        echo "✓ Secret format validated (AGE-SECRET-KEY-1...)"
    else
        echo "ERROR: Secret format validation failed" >&2
        exit 1
    fi
else
    echo "ERROR: Failed to verify secret" >&2
    exit 1
fi

echo ""
echo "Summary"
echo "======="
echo ""
echo "✓ Age private key injected into cluster"
echo "✓ Secret: sops-age"
echo "✓ Namespace: argocd"
echo "✓ Data field: keys.txt"
echo ""
echo "Next steps:"
echo "  1. Deploy KSOPS package to ArgoCD"
echo "  2. KSOPS sidecar will mount this secret"
echo "  3. Verify: kubectl get secret -n argocd sops-age"
echo ""

exit 0
