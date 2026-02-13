#!/bin/bash
# META_REQUIRE: sops, jq, curl, openssl
# INCLUDE: shared/env-helpers.sh

# Generate GHCR pull secret using GitHub App credentials
# Creates dockerconfigjson secret for GitHub Container Registry

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Read context
if [ -z "$ZTC_CONTEXT_FILE" ]; then
    echo -e "${RED}✗ ZTC_CONTEXT_FILE not set${NC}"
    exit 1
fi

OUTPUT_FILE=$(jq -r '.output_file' "$ZTC_CONTEXT_FILE")
NAMESPACE=$(jq -r '.namespace' "$ZTC_CONTEXT_FILE")
SOPS_CONFIG=$(jq -r '.sops_config_path' "$ZTC_CONTEXT_FILE")
TEMPLATE_DIR=$(jq -r '.template_dir' "$ZTC_CONTEXT_FILE")

DOCKERCONFIGJSON_TEMPLATE="$TEMPLATE_DIR/ghcr-pull-secret.yaml"

# Read GitHub App credentials from environment
if [ -z "$GIT_APP_ID" ] || [ -z "$GIT_APP_INSTALLATION_ID" ] || [ -z "$GIT_APP_PRIVATE_KEY" ]; then
    echo -e "${RED}Error: Missing GitHub App credentials${NC}"
    echo -e "${YELLOW}Required: GIT_APP_ID, GIT_APP_INSTALLATION_ID, GIT_APP_PRIVATE_KEY${NC}"
    exit 1
fi

# Generate JWT for GitHub App
NOW=$(date +%s)
IAT=$((NOW - 60))
EXP=$((NOW + 600))

HEADER='{"alg":"RS256","typ":"JWT"}'
PAYLOAD="{\"iat\":${IAT},\"exp\":${EXP},\"iss\":\"${GIT_APP_ID}\"}"

HEADER_B64=$(echo -n "$HEADER" | openssl base64 -e -A | tr '+/' '-_' | tr -d '=')
PAYLOAD_B64=$(echo -n "$PAYLOAD" | openssl base64 -e -A | tr '+/' '-_' | tr -d '=')

SIGNATURE=$(echo -n "${HEADER_B64}.${PAYLOAD_B64}" | openssl dgst -sha256 -sign <(echo "$GIT_APP_PRIVATE_KEY") | openssl base64 -e -A | tr '+/' '-_' | tr -d '=')
JWT="${HEADER_B64}.${PAYLOAD_B64}.${SIGNATURE}"

# Get installation access token
TOKEN_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $JWT" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/app/installations/${GIT_APP_INSTALLATION_ID}/access_tokens")

GITHUB_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.token // empty')

if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}Error: Failed to generate GitHub App token${NC}"
    echo -e "${RED}API Response: $TOKEN_RESPONSE${NC}"
    exit 1
fi

# Create dockerconfigjson auth string
AUTH_STRING=$(echo -n "x-access-token:${GITHUB_TOKEN}" | base64)

# Create dockerconfigjson
DOCKER_CONFIG_JSON="{\"auths\":{\"ghcr.io\":{\"auth\":\"${AUTH_STRING}\"}}}"
DOCKER_CONFIG_JSON_BASE64=$(echo -n "$DOCKER_CONFIG_JSON" | base64)

# Create secret YAML from template
sed -e "s/SECRET_NAME_PLACEHOLDER/ghcr-pull-secret/g" \
    -e "s/NAMESPACE_PLACEHOLDER/${NAMESPACE}/g" \
    -e "s/ANNOTATIONS_PLACEHOLDER/argocd.argoproj.io\/sync-wave: \\\"0\\\"/g" \
    -e "s|DOCKER_CONFIG_JSON_BASE64_PLACEHOLDER|${DOCKER_CONFIG_JSON_BASE64}|g" \
    "$DOCKERCONFIGJSON_TEMPLATE" > "$OUTPUT_FILE"

# Encrypt with SOPS
if [ -n "$SOPS_CONFIG" ] && [ -f "$SOPS_CONFIG" ]; then
    sops --config "$SOPS_CONFIG" -e -i "$OUTPUT_FILE"
else
    sops -e -i "$OUTPUT_FILE"
fi

echo -e "${GREEN}✓ Created: $OUTPUT_FILE${NC}"
