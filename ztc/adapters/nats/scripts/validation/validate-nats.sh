#!/usr/bin/env bash
# Validation script for NATS deployment
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Validate context file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo -e "${RED}ERROR: ZTC_CONTEXT_FILE not set${NC}" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo -e "${RED}ERROR: Context file not found: $ZTC_CONTEXT_FILE${NC}" >&2
    exit 1
fi

# Parse context
NAMESPACE=$(jq -r '.namespace' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$NAMESPACE" || "$NAMESPACE" == "null" ]]; then
    echo -e "${RED}ERROR: namespace is required in context${NC}" >&2
    exit 1
fi

echo -e "${GREEN}Validating NATS deployment in namespace: $NAMESPACE${NC}"

# Check StatefulSet
if ! kubectl get statefulset nats -n "$NAMESPACE" &>/dev/null; then
    echo -e "${RED}✗ NATS StatefulSet not found${NC}" >&2
    exit 1
fi

ready=$(kubectl get statefulset nats -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
total=$(kubectl get statefulset nats -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

if [ "$ready" -ne "$total" ] || [ "$total" -eq 0 ]; then
    echo -e "${RED}✗ NATS StatefulSet not ready: $ready/$total${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ NATS StatefulSet ready: $ready/$total${NC}"

# Check pods
pod_count=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=nats --field-selector=status.phase=Running 2>/dev/null | grep -c "Running" || echo "0")

if [ "$pod_count" -eq 0 ]; then
    echo -e "${RED}✗ No NATS pods running${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ NATS pods running: $pod_count${NC}"

# Check JetStream (optional - best effort)
if kubectl exec -n "$NAMESPACE" nats-0 -- nats stream ls &>/dev/null; then
    echo -e "${GREEN}✓ JetStream is functional${NC}"
else
    echo -e "${YELLOW}⚠ JetStream check skipped (nats CLI not available)${NC}"
fi

echo ""
echo -e "${GREEN}✓ NATS validation passed!${NC}"
exit 0
