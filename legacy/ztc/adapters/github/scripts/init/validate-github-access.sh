#!/usr/bin/env bash
set -euo pipefail

# validate-github-access.sh
# Purpose: Validate GitHub API access to a single repository
# Execution: Init phase (before cluster exists)
# Context: Receives context via $ZTC_CONTEXT_FILE, secrets via environment variables

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Read context data from JSON file
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo -e "${RED}Error: ZTC_CONTEXT_FILE environment variable not set${NC}" >&2
    exit 1
fi

if [[ ! -f "$ZTC_CONTEXT_FILE" ]]; then
    echo -e "${RED}Error: Context file not found: $ZTC_CONTEXT_FILE${NC}" >&2
    exit 1
fi

# Extract context data using jq
GITHUB_APP_ID=$(jq -r '.github_app_id' "$ZTC_CONTEXT_FILE")
GITHUB_APP_INSTALLATION_ID=$(jq -r '.github_app_installation_id' "$ZTC_CONTEXT_FILE")
REPO_ORG=$(jq -r '.repo_org' "$ZTC_CONTEXT_FILE")
REPO_NAME=$(jq -r '.repo_name' "$ZTC_CONTEXT_FILE")
REPO_TYPE=$(jq -r '.repo_type' "$ZTC_CONTEXT_FILE")

# Verify required context data
if [[ -z "$GITHUB_APP_ID" || "$GITHUB_APP_ID" == "null" ]]; then
    echo -e "${RED}Error: github_app_id not found in context${NC}" >&2
    exit 1
fi

if [[ -z "$GITHUB_APP_INSTALLATION_ID" || "$GITHUB_APP_INSTALLATION_ID" == "null" ]]; then
    echo -e "${RED}Error: github_app_installation_id not found in context${NC}" >&2
    exit 1
fi

if [[ -z "$REPO_ORG" || "$REPO_ORG" == "null" ]]; then
    echo -e "${RED}Error: repo_org not found in context${NC}" >&2
    exit 1
fi

if [[ -z "$REPO_NAME" || "$REPO_NAME" == "null" ]]; then
    echo -e "${RED}Error: repo_name not found in context${NC}" >&2
    exit 1
fi

# Verify secret environment variable
if [[ -z "${GITHUB_APP_PRIVATE_KEY:-}" ]]; then
    echo -e "${RED}Error: GITHUB_APP_PRIVATE_KEY environment variable not set${NC}" >&2
    exit 1
fi

echo "Validating ${REPO_TYPE} repository access..."
echo "  Repository: $REPO_ORG/$REPO_NAME"

# Generate JWT
TEMP_KEY_FILE=$(mktemp)
trap "rm -f $TEMP_KEY_FILE" EXIT
printf "%s" "$GITHUB_APP_PRIVATE_KEY" > "$TEMP_KEY_FILE"

if ! grep -q "BEGIN RSA PRIVATE KEY" "$TEMP_KEY_FILE"; then
    echo -e "${RED}Error: Invalid private key format${NC}" >&2
    exit 1
fi

CURRENT_TIME=$(date +%s)
IAT_TIME=$((CURRENT_TIME - 60))
EXPIRATION_TIME=$((CURRENT_TIME + 600))

JWT_HEADER='{"alg":"RS256","typ":"JWT"}'
JWT_PAYLOAD="{\"iat\":$IAT_TIME,\"exp\":$EXPIRATION_TIME,\"iss\":\"$GITHUB_APP_ID\"}"

JWT_HEADER_B64=$(echo -n "$JWT_HEADER" | openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')
JWT_PAYLOAD_B64=$(echo -n "$JWT_PAYLOAD" | openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')

JWT_SIGNATURE=$(echo -n "${JWT_HEADER_B64}.${JWT_PAYLOAD_B64}" | \
    openssl dgst -sha256 -sign "$TEMP_KEY_FILE" | \
    openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')

JWT="${JWT_HEADER_B64}.${JWT_PAYLOAD_B64}.${JWT_SIGNATURE}"

# Exchange JWT for installation access token
TOKEN_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $JWT" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/app/installations/$GITHUB_APP_INSTALLATION_ID/access_tokens")

if echo "$TOKEN_RESPONSE" | jq -e '.message' > /dev/null 2>&1; then
    ERROR_MSG=$(echo "$TOKEN_RESPONSE" | jq -r '.message')
    echo -e "${RED}Error: Failed to get installation access token${NC}" >&2
    echo -e "${RED}GitHub API error: $ERROR_MSG${NC}" >&2
    exit 1
fi

INSTALLATION_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.token')

if [[ -z "$INSTALLATION_TOKEN" || "$INSTALLATION_TOKEN" == "null" ]]; then
    echo -e "${RED}Error: Failed to extract installation token${NC}" >&2
    exit 1
fi

# Validate repository access
REPO_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: token $INSTALLATION_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO_ORG/$REPO_NAME")

HTTP_CODE=$(echo "$REPO_RESPONSE" | tail -n1)

if [[ "$HTTP_CODE" == "200" ]]; then
    echo -e "${GREEN}✓ Repository accessible: $REPO_ORG/$REPO_NAME${NC}"
elif [[ "$HTTP_CODE" == "404" ]]; then
    echo -e "${RED}Error: Repository not found: $REPO_ORG/$REPO_NAME${NC}" >&2
    exit 1
else
    echo -e "${RED}Error: Validation failed (HTTP $HTTP_CODE)${NC}" >&2
    exit 1
fi
