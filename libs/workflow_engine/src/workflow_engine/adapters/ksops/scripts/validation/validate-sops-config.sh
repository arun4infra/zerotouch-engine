#!/usr/bin/env bash
# SOPS Configuration Validation
#
# META_REQUIRE: None

set -euo pipefail

if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo "ERROR: ZTC_CONTEXT_FILE not set" >&2
    exit 1
fi

echo "SOPS Configuration Validation"
echo "=============================="
echo ""

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Find .sops.yaml files
SOPS_FILES=$(find "$REPO_ROOT" -name ".sops.yaml" 2>/dev/null || echo "")

if [[ -z "$SOPS_FILES" ]]; then
    echo "ERROR: No .sops.yaml files found" >&2
    exit 1
fi

echo "Found .sops.yaml files:"
echo "$SOPS_FILES"
echo ""

# Validate each .sops.yaml
for SOPS_YAML in $SOPS_FILES; do
    echo "Validating: $SOPS_YAML"
    
    # Check YAML format
    if ! python3 -c "import yaml; yaml.safe_load(open('$SOPS_YAML'))" 2>/dev/null; then
        echo "✗ Invalid YAML format"
        exit 1
    fi
    
    echo "✓ Valid YAML format"
done

echo ""
echo "✓ SOPS configuration validation complete"
exit 0
