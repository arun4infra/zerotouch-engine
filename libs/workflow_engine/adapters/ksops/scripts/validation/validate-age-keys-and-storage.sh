#!/usr/bin/env bash
# Age Key Infrastructure and Storage Validation
#
# META_REQUIRE: s3_endpoint (context)
# META_REQUIRE: s3_region (context)
# META_REQUIRE: s3_bucket_name (context)
# META_REQUIRE: S3_ACCESS_KEY (env)
# META_REQUIRE: S3_SECRET_KEY (env)
#
# INCLUDE: shared/s3-helpers.sh

set -euo pipefail

if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

echo "Age Key Infrastructure and Storage Validation"
echo "=============================================="
echo ""

PASSED=0
FAILED=0

validate() {
    local test_name=$1
    local test_command=$2
    
    echo "Testing: $test_name"
    if eval "$test_command"; then
        echo "✓ PASSED"
        PASSED=$((PASSED + 1))
    else
        echo "✗ FAILED"
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

# Validation 3: Backup secrets exist
validate "age-backup-encrypted exists" \
    "kubectl get secret age-backup-encrypted -n argocd &>/dev/null"

validate "recovery-master-key exists" \
    "kubectl get secret recovery-master-key -n argocd &>/dev/null"

# Validation 4: S3 buckets (if credentials available)
if [ -n "${S3_ACCESS_KEY:-}" ] && [ -n "${S3_SECRET_KEY:-}" ]; then
    configure_s3_credentials
    
    validate "S3 bucket accessible" \
        "aws s3 ls s3://$S3_BUCKET --endpoint-url $S3_ENDPOINT &>/dev/null"
else
    echo "⚠️  Skipping S3 validation (credentials not set)"
fi

# Validation 5: hetzner-s3-credentials secret
validate "hetzner-s3-credentials exists" \
    "kubectl get secret hetzner-s3-credentials -n default &>/dev/null"

echo "Summary: Passed $PASSED, Failed $FAILED"

if [ $FAILED -eq 0 ]; then
    echo "✓ Validation PASSED"
    exit 0
else
    echo "✗ Validation FAILED"
    exit 1
fi
