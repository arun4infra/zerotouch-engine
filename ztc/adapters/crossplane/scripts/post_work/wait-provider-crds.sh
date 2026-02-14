#!/usr/bin/env bash
set -euo pipefail

# Source: zerotouch-platform/scripts/bootstrap/wait/13-wait-service-dependencies.sh
# Migration: Extracted CRD establishment checks, converted CLI args to JSON context

# Wait for Provider CRDs to be Established
# Waits for Crossplane provider CRDs to be established before XRD installation

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
TIMEOUT=$(jq -r '.timeout_seconds // 180' "$ZTC_CONTEXT_FILE")
CHECK_INTERVAL=$(jq -r '.check_interval // 3' "$ZTC_CONTEXT_FILE")
REQUIRED_CRDS=$(jq -r '.required_crds[]' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo "ERROR: namespace is required in context" >&2
    exit 1
fi

if [[ -z "$REQUIRED_CRDS" ]]; then
    echo "ERROR: required_crds is required in context" >&2
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Waiting for provider CRDs to be established..."
echo "  Required CRDs:"
echo "$REQUIRED_CRDS" | while read crd; do echo "    - $crd"; done
echo "  Timeout: ${TIMEOUT}s"
echo ""

ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    echo -e "${YELLOW}⏳ Checking CRDs (${ELAPSED}s / ${TIMEOUT}s)...${NC}"
    
    all_established=true
    
    while IFS= read -r crd_name; do
        if ! kubectl get crd "$crd_name" >/dev/null 2>&1; then
            echo "  ✗ $crd_name: Not found"
            all_established=false
            continue
        fi
        
        # Check if CRD is established
        ESTABLISHED=$(kubectl get crd "$crd_name" -o jsonpath='{.status.conditions[?(@.type=="Established")].status}' 2>/dev/null || echo "False")
        
        if [[ "$ESTABLISHED" == "True" ]]; then
            echo "  ✓ $crd_name: Established"
        else
            echo "  ✗ $crd_name: Not established"
            all_established=false
        fi
    done <<< "$REQUIRED_CRDS"
    
    if [[ "$all_established" == "true" ]]; then
        echo ""
        echo -e "${GREEN}✓ All provider CRDs are established!${NC}"
        echo ""
        exit 0
    fi
    
    echo ""
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED + CHECK_INTERVAL))
done

# Timeout reached
echo ""
echo -e "${RED}ERROR: Timeout waiting for provider CRDs to be established${NC}" >&2
echo ""
echo "CRD status:" >&2
while IFS= read -r crd_name; do
    if kubectl get crd "$crd_name" >/dev/null 2>&1; then
        kubectl get crd "$crd_name" -o jsonpath='{.metadata.name}: {.status.conditions[?(@.type=="Established")].status}{"\n"}' 2>&1 || echo "$crd_name: Failed to get status" >&2
    else
        echo "$crd_name: Not found" >&2
    fi
done <<< "$REQUIRED_CRDS"

echo ""
echo "Troubleshooting commands:" >&2
echo "  kubectl get crds | grep crossplane" >&2
echo "  kubectl describe crd providers.pkg.crossplane.io" >&2
echo "  kubectl get pods -n $NAMESPACE" >&2
echo ""

exit 1

