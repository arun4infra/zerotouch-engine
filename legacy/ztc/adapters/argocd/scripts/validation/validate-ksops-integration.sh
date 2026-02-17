#!/usr/bin/env bash
set -euo pipefail

# Validate KSOPS Integration
# Verifies KSOPS init container and volumes are properly configured in repo-server

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

echo "Validating KSOPS integration..."
echo "  Namespace: $NAMESPACE"
echo ""

VALIDATION_FAILED=0

# Get repo-server deployment
if ! kubectl get deployment argocd-repo-server -n "$NAMESPACE" &>/dev/null; then
    echo "✗ ArgoCD repo-server deployment not found" >&2
    exit 1
fi

# Check KSOPS init container is present
echo "Checking KSOPS init container..."
INIT_CONTAINER=$(kubectl get deployment argocd-repo-server -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.initContainers[?(@.name=="install-ksops")].name}' 2>/dev/null || echo "")

if [[ "$INIT_CONTAINER" == "install-ksops" ]]; then
    echo "✓ KSOPS init container present"
else
    echo "✗ KSOPS init container not found" >&2
    VALIDATION_FAILED=1
fi

# Check custom-tools volume is mounted
echo ""
echo "Checking volumes..."
CUSTOM_TOOLS_VOLUME=$(kubectl get deployment argocd-repo-server -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.volumes[?(@.name=="custom-tools")].name}' 2>/dev/null || echo "")

if [[ "$CUSTOM_TOOLS_VOLUME" == "custom-tools" ]]; then
    echo "✓ custom-tools volume present"
else
    echo "✗ custom-tools volume not found" >&2
    VALIDATION_FAILED=1
fi

# Check sops-age-key volume is mounted
SOPS_AGE_VOLUME=$(kubectl get deployment argocd-repo-server -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.volumes[?(@.name=="sops-age-key")].name}' 2>/dev/null || echo "")

if [[ "$SOPS_AGE_VOLUME" == "sops-age-key" ]]; then
    echo "✓ sops-age-key volume present"
else
    echo "✗ sops-age-key volume not found" >&2
    VALIDATION_FAILED=1
fi

# Check environment variables are set
echo ""
echo "Checking environment variables..."
XDG_CONFIG_HOME=$(kubectl get deployment argocd-repo-server -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="XDG_CONFIG_HOME")].value}' 2>/dev/null || echo "")

if [[ "$XDG_CONFIG_HOME" == "/.config" ]]; then
    echo "✓ XDG_CONFIG_HOME environment variable set"
else
    echo "✗ XDG_CONFIG_HOME environment variable not set" >&2
    VALIDATION_FAILED=1
fi

SOPS_AGE_KEY_FILE=$(kubectl get deployment argocd-repo-server -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="SOPS_AGE_KEY_FILE")].value}' 2>/dev/null || echo "")

if [[ "$SOPS_AGE_KEY_FILE" == "/.config/sops/age/keys.txt" ]]; then
    echo "✓ SOPS_AGE_KEY_FILE environment variable set"
else
    echo "✗ SOPS_AGE_KEY_FILE environment variable not set" >&2
    VALIDATION_FAILED=1
fi

# Check PATH includes /custom-tools
PATH_VAR=$(kubectl get deployment argocd-repo-server -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="PATH")].value}' 2>/dev/null || echo "")

if [[ "$PATH_VAR" == *"/custom-tools"* ]]; then
    echo "✓ PATH includes /custom-tools"
else
    echo "✗ PATH does not include /custom-tools" >&2
    VALIDATION_FAILED=1
fi

# Verify KSOPS is actually installed in running pod
echo ""
echo "Verifying KSOPS installation in running pod..."
REPO_POD=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=argocd-repo-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [[ -n "$REPO_POD" ]]; then
    if kubectl exec -n "$NAMESPACE" "$REPO_POD" -- test -f /custom-tools/ksops 2>/dev/null; then
        echo "✓ KSOPS binary present in pod"
    else
        echo "✗ KSOPS binary not found in pod" >&2
        VALIDATION_FAILED=1
    fi
    
    if kubectl exec -n "$NAMESPACE" "$REPO_POD" -- test -f /custom-tools/kustomize 2>/dev/null; then
        echo "✓ Kustomize binary present in pod"
    else
        echo "✗ Kustomize binary not found in pod" >&2
        VALIDATION_FAILED=1
    fi
else
    echo "⚠️  Could not find repo-server pod to verify binaries"
fi

echo ""
if [[ $VALIDATION_FAILED -eq 0 ]]; then
    echo "✓ KSOPS integration validation passed"
    exit 0
else
    echo "✗ KSOPS integration validation failed" >&2
    echo ""
    echo "Troubleshooting:" >&2
    echo "  kubectl describe deployment argocd-repo-server -n $NAMESPACE" >&2
    echo "  kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=argocd-repo-server" >&2
    exit 1
fi
