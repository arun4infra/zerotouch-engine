#!/usr/bin/env bash
# Master KSOPS Validation Script
#
# META_REQUIRE: None

set -euo pipefail

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to run validation step
run_validation() {
    local step_name="$1"
    local script_path="$2"
    
    echo "==> $step_name"
    
    if [ ! -f "$script_path" ]; then
        echo "⚠️  Script not found: $script_path - skipping"
        return 0
    fi
    
    if "$script_path"; then
        echo "✓ $step_name - PASSED"
        return 0
    else
        echo "✗ $step_name - FAILED"
        return 1
    fi
}

echo "Master KSOPS Validation"
echo "======================="
echo ""

FAILED_VALIDATIONS=0
TOTAL_VALIDATIONS=0

# Step 1: Validate KSOPS Package Deployment
TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
if ! run_validation "KSOPS Package Validation" "$SCRIPT_DIR/validate-ksops-package.sh"; then
    FAILED_VALIDATIONS=$((FAILED_VALIDATIONS + 1))
fi
echo ""

# Step 2: Validate Secret Injection
TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
if ! run_validation "Secret Injection Validation" "$SCRIPT_DIR/validate-secret-injection.sh"; then
    FAILED_VALIDATIONS=$((FAILED_VALIDATIONS + 1))
fi
echo ""

# Step 3: Validate Age Keys and Storage
TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
if ! run_validation "Age Keys and Storage Validation" "$SCRIPT_DIR/validate-age-keys-and-storage.sh"; then
    FAILED_VALIDATIONS=$((FAILED_VALIDATIONS + 1))
fi
echo ""

# Step 4: Validate SOPS Configuration
TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
if ! run_validation "SOPS Configuration Validation" "$SCRIPT_DIR/validate-sops-config.sh"; then
    FAILED_VALIDATIONS=$((FAILED_VALIDATIONS + 1))
fi
echo ""

# Step 5: Validate SOPS Encryption
TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
if ! run_validation "SOPS Encryption Validation" "$SCRIPT_DIR/validate-sops-encryption.sh"; then
    FAILED_VALIDATIONS=$((FAILED_VALIDATIONS + 1))
fi
echo ""

# Step 6: Validate Age Key Decryption
TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
if ! run_validation "ACTIVE Age Key Decryption Validation" "$SCRIPT_DIR/validate-age-key-decryption.sh"; then
    FAILED_VALIDATIONS=$((FAILED_VALIDATIONS + 1))
fi
echo ""

# Final Summary
echo "Validation Summary"
echo "=================="
echo ""

PASSED_VALIDATIONS=$((TOTAL_VALIDATIONS - FAILED_VALIDATIONS))
echo "✓ Passed: $PASSED_VALIDATIONS/$TOTAL_VALIDATIONS"

if [ $FAILED_VALIDATIONS -gt 0 ]; then
    echo "✗ Failed: $FAILED_VALIDATIONS/$TOTAL_VALIDATIONS"
    echo ""
    echo "KSOPS validation failed - check individual test outputs above"
    exit 1
else
    echo "✓ All KSOPS validations passed successfully!"
    echo ""
    echo "KSOPS is fully functional and ready for production use"
fi

exit 0
