#!/usr/bin/env bash
# Secret Injection Validation
#
# META_REQUIRE: None

set -euo pipefail

if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

echo "CHECKPOINT 2: Secret Injection Validation"
echo "=========================================="
echo ""

PASSED=0
FAILED=0

validate() {
    local test_name=$1
    local test_command=$2
    
    echo "Testing: $test_name"
    if eval "$test_command"; then
        echo "✓ PASSED: $test_name"
        PASSED=$((PASSED + 1))
    else
        echo "✗ FAILED: $test_name"
        FAILED=$((FAILED + 1))
    fi
    echo ""
}

# Validation 1: sops-age secret exists
validate "sops-age secret exists" \
    "kubectl get secret sops-age -n argocd &>/dev/null"

# Validation 2: Age key format
validate "Age key correctly formatted" \
    "kubectl get secret sops-age -n argocd -o jsonpath='{.data.keys\.txt}' | base64 -d | grep -q '^AGE-SECRET-KEY-1'"

# Validation 3: GitHub App secret exists
validate "argocd-github-app-creds exists" \
    "kubectl get secret argocd-github-app-creds -n argocd &>/dev/null"

# Validation 4: GitHub App secret fields
validate "GitHub App secret has required fields" \
    "kubectl get secret argocd-github-app-creds -n argocd -o jsonpath='{.data.githubAppID}' | base64 -d | grep -q '.'"

echo "Summary: Passed $PASSED, Failed $FAILED"

if [ $FAILED -eq 0 ]; then
    echo "✓ CHECKPOINT 2 PASSED"
    exit 0
else
    echo "✗ CHECKPOINT 2 FAILED"
    exit 1
fi
