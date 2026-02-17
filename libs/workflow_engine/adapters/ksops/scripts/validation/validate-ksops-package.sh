#!/usr/bin/env bash
# KSOPS Package Deployment Validation
#
# META_REQUIRE: None

set -euo pipefail

if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

echo "=== CHECKPOINT 1: KSOPS Package Deployment Validation ==="
echo ""

VALIDATION_FAILED=0

log_check() {
    local status=$1
    local message=$2
    if [[ "$status" == "PASS" ]]; then
        echo "✅ PASS: $message"
    else
        echo "❌ FAIL: $message"
        VALIDATION_FAILED=1
    fi
}

# 1. Verify KSOPS init container completed
echo "1. Checking KSOPS init container..."
POD_NAME=$(kubectl get pod -n argocd -l app.kubernetes.io/name=argocd-repo-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [[ -n "$POD_NAME" ]]; then
    INIT_STATUS=$(kubectl get pod -n argocd "$POD_NAME" -o jsonpath='{.status.initContainerStatuses[?(@.name=="install-ksops")].state.terminated.reason}' 2>/dev/null || echo "")
    if [[ "$INIT_STATUS" == "Completed" ]]; then
        if kubectl exec -n argocd "$POD_NAME" -c argocd-repo-server -- which ksops 2>/dev/null | grep -q ksops; then
            log_check "PASS" "KSOPS init container completed and tools installed"
        else
            log_check "FAIL" "Init container completed but KSOPS binary not found"
        fi
    else
        log_check "FAIL" "KSOPS init container not completed (status: $INIT_STATUS)"
    fi
else
    log_check "FAIL" "argocd-repo-server pod not found"
fi

# 2. Verify kustomize available
echo "2. Checking kustomize..."
if [[ -n "$POD_NAME" ]]; then
    if kubectl exec -n argocd "$POD_NAME" -c argocd-repo-server -- test -f /usr/local/bin/kustomize 2>/dev/null; then
        log_check "PASS" "Kustomize binary available"
    else
        log_check "FAIL" "Kustomize binary not found"
    fi
fi

# 3. Verify environment variables
echo "3. Checking environment variables..."
if [[ -n "$POD_NAME" ]]; then
    SOPS_KEY=$(kubectl exec -n argocd "$POD_NAME" -c argocd-repo-server -- env 2>/dev/null | grep SOPS_AGE_KEY_FILE || echo "")
    if [[ -n "$SOPS_KEY" ]]; then
        log_check "PASS" "Environment variables configured"
    else
        log_check "FAIL" "SOPS_AGE_KEY_FILE not set"
    fi
fi

# 4. Verify Age key mount
echo "4. Checking Age key mount..."
if [[ -n "$POD_NAME" ]]; then
    if kubectl exec -n argocd "$POD_NAME" -c argocd-repo-server -- test -f /.config/sops/age/keys.txt 2>/dev/null; then
        log_check "PASS" "Age key file mounted"
    else
        log_check "FAIL" "Age key file not found"
    fi
fi

echo ""
if [[ $VALIDATION_FAILED -eq 0 ]]; then
    echo "✅ CHECKPOINT 1 PASSED"
    exit 0
else
    echo "❌ CHECKPOINT 1 FAILED"
    exit 1
fi
