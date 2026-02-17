#!/usr/bin/env bash
set -euo pipefail

# Validate Provider Installations
# Checks that all configured providers are installed and healthy

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
EXPECTED_PROVIDERS=$(jq -r '.expected_providers[]' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo "ERROR: namespace is required in context" >&2
    exit 1
fi

if [[ -z "$EXPECTED_PROVIDERS" ]]; then
    echo "ERROR: expected_providers is required in context" >&2
    exit 1
fi

echo "Validating provider installations..."
echo "  Expected providers:"
echo "$EXPECTED_PROVIDERS" | while read provider; do echo "    - $provider"; done
echo ""

EXIT_CODE=0

while IFS= read -r provider; do
    PROVIDER_NAME="provider-${provider}"
    
    # Check if Provider resource exists
    if ! kubectl get provider "$PROVIDER_NAME" >/dev/null 2>&1; then
        echo "✗ Provider $PROVIDER_NAME not found"
        EXIT_CODE=1
        continue
    fi
    
    # Check provider health
    HEALTHY=$(kubectl get provider "$PROVIDER_NAME" -o jsonpath='{.status.conditions[?(@.type=="Healthy")].status}' 2>/dev/null || echo "False")
    INSTALLED=$(kubectl get provider "$PROVIDER_NAME" -o jsonpath='{.status.conditions[?(@.type=="Installed")].status}' 2>/dev/null || echo "False")
    
    if [[ "$HEALTHY" == "True" ]] && [[ "$INSTALLED" == "True" ]]; then
        echo "✓ Provider $PROVIDER_NAME is healthy and installed"
    else
        echo "✗ Provider $PROVIDER_NAME is not healthy (Healthy: $HEALTHY, Installed: $INSTALLED)"
        EXIT_CODE=1
    fi
    
    # Check if ProviderConfig exists
    if kubectl get providerconfig -A 2>/dev/null | grep -q "$provider"; then
        echo "  ✓ ProviderConfig found"
    else
        echo "  ✗ ProviderConfig not found"
        EXIT_CODE=1
    fi
    
    # Check provider package installation
    PACKAGE=$(kubectl get provider "$PROVIDER_NAME" -o jsonpath='{.spec.package}' 2>/dev/null || echo "")
    if [[ -n "$PACKAGE" ]]; then
        echo "  ✓ Package: $PACKAGE"
    else
        echo "  ✗ Package not specified"
        EXIT_CODE=1
    fi
    
    echo ""
done <<< "$EXPECTED_PROVIDERS"

if [[ $EXIT_CODE -eq 0 ]]; then
    echo "✓ All providers are healthy"
else
    echo "✗ Provider validation failed"
    echo ""
    echo "Check: kubectl get providers"
    echo "Check: kubectl get providerconfigs -A"
    echo "Check: kubectl describe provider <provider-name>"
fi

exit $EXIT_CODE

