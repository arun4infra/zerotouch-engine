#!/usr/bin/env bash
# Source: zerotouch-platform/scripts/bootstrap/wait/wait-for-gateway.sh
# Migration: Converted CLI args to JSON context
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
GATEWAY_NAMESPACE=$(jq -r '.namespace' "$ZTC_CONTEXT_FILE")
TIMEOUT=$(jq -r '.timeout_seconds // 300' "$ZTC_CONTEXT_FILE")

# Validate required fields
if [[ -z "$GATEWAY_NAME" || "$GATEWAY_NAME" == "null" ]]; then
    echo "ERROR: gateway_name is required in context" >&2
    exit 1
fi

if [[ -z "$GATEWAY_NAMESPACE" || "$GATEWAY_NAMESPACE" == "null" ]]; then
    echo "ERROR: namespace is required in context" >&2
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

POLL_INTERVAL=10

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Waiting for Gateway Infrastructure                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Gateway: ${GATEWAY_NAME}${NC}"
echo -e "${BLUE}Namespace: ${GATEWAY_NAMESPACE}${NC}"
echo -e "${BLUE}Timeout: ${TIMEOUT}s${NC}"
echo ""

# Function to check Gateway status
check_gateway_status() {
    local gateway_json
    gateway_json=$(kubectl get gateway "$GATEWAY_NAME" -n "$GATEWAY_NAMESPACE" -o json 2>/dev/null || echo "{}")
    
    if [ "$gateway_json" = "{}" ]; then
        echo "not_found"
        return
    fi
    
    local accepted_status programmed_status loadbalancer_ip
    accepted_status=$(echo "$gateway_json" | jq -r '.status.conditions[] | select(.type == "Accepted") | .status' 2>/dev/null || echo "Unknown")
    programmed_status=$(echo "$gateway_json" | jq -r '.status.conditions[] | select(.type == "Programmed") | .status' 2>/dev/null || echo "Unknown")
    loadbalancer_ip=$(echo "$gateway_json" | jq -r '.status.addresses[]? | select(.type == "IPAddress") | .value' 2>/dev/null || echo "")
    
    echo "${accepted_status}|${programmed_status}|${loadbalancer_ip}"
}

# Function to get Gateway condition messages
get_gateway_messages() {
    local gateway_json
    gateway_json=$(kubectl get gateway "$GATEWAY_NAME" -n "$GATEWAY_NAMESPACE" -o json 2>/dev/null || echo "{}")
    
    if [ "$gateway_json" != "{}" ]; then
        local accepted_msg programmed_msg
        accepted_msg=$(echo "$gateway_json" | jq -r '.status.conditions[] | select(.type == "Accepted") | .message' 2>/dev/null || echo "")
        programmed_msg=$(echo "$gateway_json" | jq -r '.status.conditions[] | select(.type == "Programmed") | .message' 2>/dev/null || echo "")
        
        [ -n "$accepted_msg" ] && echo "  Accepted: $accepted_msg"
        [ -n "$programmed_msg" ] && echo "  Programmed: $programmed_msg"
    fi
}

# Function to test LoadBalancer connectivity
test_connectivity() {
    local ip="$1"
    if command -v curl >/dev/null 2>&1; then
        if curl -s --connect-timeout 5 --max-time 10 "http://$ip" >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

ELAPSED=0
LAST_STATUS=""

while [ $ELAPSED -lt $TIMEOUT ]; do
    STATUS=$(check_gateway_status)
    
    echo -e "${BLUE}=== Checking Gateway status (${ELAPSED}s / ${TIMEOUT}s) ===${NC}"
    
    case "$STATUS" in
        "not_found")
            echo -e "${YELLOW}⏳ Waiting for Gateway resource to be created...${NC}"
            LAST_STATUS="not_found"
            ;;
        "Unknown|Unknown|")
            echo -e "${YELLOW}⏳ Gateway created, waiting for controller to process...${NC}"
            if [ "$LAST_STATUS" != "waiting_controller" ]; then
                get_gateway_messages
                LAST_STATUS="waiting_controller"
            fi
            ;;
        "True|Unknown|"|"True|False|")
            echo -e "${GREEN}✓ Gateway accepted by controller${NC}"
            echo -e "${YELLOW}⏳ Waiting for LoadBalancer provisioning...${NC}"
            if [ "$LAST_STATUS" != "accepted" ]; then
                get_gateway_messages
                LAST_STATUS="accepted"
            fi
            ;;
        "True|True|")
            echo -e "${GREEN}✓ Gateway programmed${NC}"
            echo -e "${YELLOW}⏳ Waiting for LoadBalancer IP assignment...${NC}"
            LAST_STATUS="programmed_no_ip"
            ;;
        "True|True|"*)
            IFS='|' read -r accepted programmed ip <<< "$STATUS"
            if [ -n "$ip" ]; then
                echo -e "${GREEN}✓ Gateway ready with LoadBalancer IP: ${ip}${NC}"
                
                echo -e "${BLUE}🔍 Testing LoadBalancer connectivity...${NC}"
                if test_connectivity "$ip"; then
                    echo -e "${GREEN}✓ LoadBalancer responds to HTTP requests${NC}"
                else
                    echo -e "${YELLOW}⚠️  LoadBalancer reachable but no routes configured (expected)${NC}"
                fi
                
                echo ""
                echo -e "${GREEN}✓ Gateway Infrastructure Ready${NC}"
                echo -e "${BLUE}ℹ  LoadBalancer IP: ${ip}${NC}"
                echo -e "${BLUE}ℹ  Gateway can now accept HTTPRoute configurations${NC}"
                echo ""
                exit 0
            fi
            ;;
        *)
            IFS='|' read -r accepted programmed ip <<< "$STATUS"
            echo -e "${RED}⚠️  Gateway in unexpected state:${NC}"
            echo -e "   Accepted: $accepted"
            echo -e "   Programmed: $programmed"
            echo -e "   IP: ${ip:-none}"
            if [ "$LAST_STATUS" != "error_state" ]; then
                get_gateway_messages
                LAST_STATUS="error_state"
            fi
            ;;
    esac
    
    echo -e "${BLUE}Current Gateway status:${NC}"
    if kubectl get gateway "$GATEWAY_NAME" -n "$GATEWAY_NAMESPACE" >/dev/null 2>&1; then
        kubectl get gateway "$GATEWAY_NAME" -n "$GATEWAY_NAMESPACE" -o custom-columns="NAME:.metadata.name,CLASS:.spec.gatewayClassName,ADDRESS:.status.addresses[0].value,ACCEPTED:.status.conditions[?(@.type=='Accepted')].status,PROGRAMMED:.status.conditions[?(@.type=='Programmed')].status" --no-headers 2>/dev/null || \
        kubectl get gateway "$GATEWAY_NAME" -n "$GATEWAY_NAMESPACE" --no-headers 2>/dev/null
        
        LB_SERVICE=$(kubectl get svc -n "$GATEWAY_NAMESPACE" -l "gateway.networking.k8s.io/gateway-name=$GATEWAY_NAME" -o name 2>/dev/null | head -1)
        if [ -n "$LB_SERVICE" ]; then
            echo -e "${BLUE}LoadBalancer service:${NC}"
            kubectl get "$LB_SERVICE" -n "$GATEWAY_NAMESPACE" --no-headers 2>/dev/null || echo "   Service details unavailable"
        fi
    else
        echo -e "   ${YELLOW}Gateway resource not found${NC}"
    fi
    
    echo ""
    sleep $POLL_INTERVAL
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

# Timeout reached
echo ""
echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║   TIMEOUT: Gateway not ready after ${TIMEOUT}s                   ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}Manual debug commands:${NC}"
echo "  kubectl describe gateway ${GATEWAY_NAME} -n ${GATEWAY_NAMESPACE}"
echo "  kubectl describe gatewayclass cilium"
echo "  kubectl logs -n kube-system deployment/cilium-operator --tail=50"
echo ""

exit 1
