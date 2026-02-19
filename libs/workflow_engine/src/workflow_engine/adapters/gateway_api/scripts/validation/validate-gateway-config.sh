#!/usr/bin/env bash
# Source: zerotouch-platform/scripts/bootstrap/validation/agent-gateway/03-validate-gateway-config.py
# Migration: Converted to bash wrapper with context JSON input
set -euo pipefail

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
GATEWAY_NAME=$(jq -r '.gateway_name' "$ZTC_CONTEXT_FILE")
GATEWAY_NAMESPACE=$(jq -r '.gateway_namespace' "$ZTC_CONTEXT_FILE")
GATEWAYCLASS_NAME=$(jq -r '.gatewayclass_name' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$GATEWAY_NAME" || "$GATEWAY_NAME" == "null" ]]; then
    echo "ERROR: gateway_name is required in context" >&2
    exit 1
fi

if [[ -z "$GATEWAY_NAMESPACE" || "$GATEWAY_NAMESPACE" == "null" ]]; then
    echo "ERROR: gateway_namespace is required in context" >&2
    exit 1
fi

if [[ -z "$GATEWAYCLASS_NAME" || "$GATEWAYCLASS_NAME" == "null" ]]; then
    echo "ERROR: gatewayclass_name is required in context" >&2
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Validating Gateway API Configuration                       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check Gateway resource exists and is Programmed
echo -e "${BLUE}⏳ Checking Gateway resource...${NC}"
if ! kubectl get gateway "$GATEWAY_NAME" -n "$GATEWAY_NAMESPACE" &>/dev/null; then
    echo -e "${RED}✗ Gateway ${GATEWAY_NAME} not found in namespace ${GATEWAY_NAMESPACE}${NC}"
    exit 1
fi

PROGRAMMED=$(kubectl get gateway "$GATEWAY_NAME" -n "$GATEWAY_NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}' 2>/dev/null)
if [ "$PROGRAMMED" != "True" ]; then
    echo -e "${RED}✗ Gateway is not Programmed${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ Gateway exists and is Programmed${NC}"

# Check GatewayClass resource exists and is Accepted
echo -e "${BLUE}⏳ Checking GatewayClass resource...${NC}"
if ! kubectl get gatewayclass "$GATEWAYCLASS_NAME" &>/dev/null; then
    echo -e "${RED}✗ GatewayClass ${GATEWAYCLASS_NAME} not found${NC}"
    exit 1
fi

ACCEPTED=$(kubectl get gatewayclass "$GATEWAYCLASS_NAME" -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}' 2>/dev/null)
if [ "$ACCEPTED" != "True" ]; then
    echo -e "${RED}✗ GatewayClass is not Accepted${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ GatewayClass exists and is Accepted${NC}"

# Check Certificate resource exists and is Ready
echo -e "${BLUE}⏳ Checking Certificate resource...${NC}"
CERT_NAME=$(kubectl get gateway "$GATEWAY_NAME" -n "$GATEWAY_NAMESPACE" -o jsonpath='{.spec.listeners[?(@.protocol=="HTTPS")].tls.certificateRefs[0].name}' 2>/dev/null)

if [[ -z "$CERT_NAME" || "$CERT_NAME" == "null" ]]; then
    echo -e "${YELLOW}  ⚠ No certificate configured for HTTPS listener${NC}"
else
    if ! kubectl get certificate "$CERT_NAME" -n "$GATEWAY_NAMESPACE" &>/dev/null; then
        echo -e "${RED}✗ Certificate ${CERT_NAME} not found${NC}"
        exit 1
    fi
    
    CERT_READY=$(kubectl get certificate "$CERT_NAME" -n "$GATEWAY_NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    if [ "$CERT_READY" != "True" ]; then
        echo -e "${YELLOW}  ⚠ Certificate is not Ready yet${NC}"
    else
        echo -e "${GREEN}  ✓ Certificate exists and is Ready${NC}"
    fi
fi

# Verify Cilium gateway service has LoadBalancer IP
echo -e "${BLUE}⏳ Checking LoadBalancer IP...${NC}"
LB_IP=$(kubectl get gateway "$GATEWAY_NAME" -n "$GATEWAY_NAMESPACE" -o jsonpath='{.status.addresses[?(@.type=="IPAddress")].value}' 2>/dev/null)

if [[ -z "$LB_IP" || "$LB_IP" == "null" ]]; then
    echo -e "${RED}✗ No LoadBalancer IP assigned${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ LoadBalancer IP assigned: ${LB_IP}${NC}"

echo ""
echo -e "${GREEN}✓ Gateway API configuration validated successfully${NC}"
echo ""
