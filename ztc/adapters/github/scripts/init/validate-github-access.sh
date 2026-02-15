#!/usr/bin/env bash
set -euo pipefail

# validate-github-access.sh
# Purpose: Validate GitHub API access and create tenant repository if needed
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
TENANT_ORG=$(jq -r '.tenant_org' "$ZTC_CONTEXT_FILE")
TENANT_REPO=$(jq -r '.tenant_repo' "$ZTC_CONTEXT_FILE")

# Verify required context data
if [[ -z "$GITHUB_APP_ID" || "$GITHUB_APP_ID" == "null" ]]; then
    echo -e "${RED}Error: github_app_id not found in context${NC}" >&2
    exit 1
fi

if [[ -z "$GITHUB_APP_INSTALLATION_ID" || "$GITHUB_APP_INSTALLATION_ID" == "null" ]]; then
    echo -e "${RED}Error: github_app_installation_id not found in context${NC}" >&2
    exit 1
fi

if [[ -z "$TENANT_ORG" || "$TENANT_ORG" == "null" ]]; then
    echo -e "${RED}Error: tenant_org not found in context${NC}" >&2
    exit 1
fi

if [[ -z "$TENANT_REPO" || "$TENANT_REPO" == "null" ]]; then
    echo -e "${RED}Error: tenant_repo not found in context${NC}" >&2
    exit 1
fi

# Verify secret environment variable
if [[ -z "${GITHUB_APP_PRIVATE_KEY:-}" ]]; then
    echo -e "${RED}Error: GITHUB_APP_PRIVATE_KEY environment variable not set${NC}" >&2
    exit 1
fi

echo "Validating GitHub API access..."
echo "  App ID: $GITHUB_APP_ID"
echo "  Installation ID: $GITHUB_APP_INSTALLATION_ID"
echo "  Repository: $TENANT_ORG/$TENANT_REPO"

# Step 1: Generate JWT from App ID and private key
echo -e "\n${YELLOW}Step 1: Generating JWT...${NC}"

# Create temporary file for private key
TEMP_KEY_FILE=$(mktemp)
trap "rm -f $TEMP_KEY_FILE" EXIT

# Write private key to temp file - use printf to preserve exact format
printf "%s" "$GITHUB_APP_PRIVATE_KEY" > "$TEMP_KEY_FILE"

# Verify private key format
if ! grep -q "BEGIN RSA PRIVATE KEY" "$TEMP_KEY_FILE"; then
    echo -e "${RED}Error: Invalid private key format${NC}" >&2
    echo -e "${YELLOW}Hint: Private key must start with '-----BEGIN RSA PRIVATE KEY-----'${NC}" >&2
    echo -e "${YELLOW}Debug: First line of key file:${NC}" >&2
    head -n1 "$TEMP_KEY_FILE" >&2
    exit 1
fi

# JWT header and payload
CURRENT_TIME=$(date +%s)
IAT_TIME=$((CURRENT_TIME - 60))  # 60 seconds in past for clock drift protection
EXPIRATION_TIME=$((CURRENT_TIME + 600)) # 10 minutes

# Create JWT components
JWT_HEADER='{"alg":"RS256","typ":"JWT"}'
JWT_PAYLOAD="{\"iat\":$IAT_TIME,\"exp\":$EXPIRATION_TIME,\"iss\":\"$GITHUB_APP_ID\"}"

# Base64url encode (no padding, URL-safe)
JWT_HEADER_B64=$(echo -n "$JWT_HEADER" | openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')
JWT_PAYLOAD_B64=$(echo -n "$JWT_PAYLOAD" | openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')

# Sign with private key
JWT_SIGNATURE=$(echo -n "${JWT_HEADER_B64}.${JWT_PAYLOAD_B64}" | \
    openssl dgst -sha256 -sign "$TEMP_KEY_FILE" | \
    openssl base64 -e | tr -d '=' | tr '/+' '_-' | tr -d '\n')

JWT="${JWT_HEADER_B64}.${JWT_PAYLOAD_B64}.${JWT_SIGNATURE}"

echo -e "${GREEN}✓ JWT generated${NC}"

# Step 2: Exchange JWT for installation access token
echo -e "\n${YELLOW}Step 2: Exchanging JWT for installation access token...${NC}"

TOKEN_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $JWT" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/app/installations/$GITHUB_APP_INSTALLATION_ID/access_tokens")

# Check for errors in token response
if echo "$TOKEN_RESPONSE" | jq -e '.message' > /dev/null 2>&1; then
    ERROR_MSG=$(echo "$TOKEN_RESPONSE" | jq -r '.message')
    echo -e "${RED}Error: Failed to get installation access token${NC}" >&2
    echo -e "${RED}GitHub API error: $ERROR_MSG${NC}" >&2
    echo -e "${YELLOW}Hint: Check that GIT_APP_PRIVATE_KEY in .env.global is valid${NC}" >&2
    exit 1
fi

INSTALLATION_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.token')

if [[ -z "$INSTALLATION_TOKEN" || "$INSTALLATION_TOKEN" == "null" ]]; then
    echo -e "${RED}Error: Failed to extract installation token from response${NC}" >&2
    exit 1
fi

echo -e "${GREEN}✓ Installation access token obtained${NC}"

# Step 3: Check if repository exists
echo -e "\n${YELLOW}Step 3: Checking if repository exists...${NC}"

REPO_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: token $INSTALLATION_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$TENANT_ORG/$TENANT_REPO")

HTTP_CODE=$(echo "$REPO_RESPONSE" | tail -n1)
REPO_DATA=$(echo "$REPO_RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" == "200" ]]; then
    REPO_NAME=$(echo "$REPO_DATA" | jq -r '.full_name')
    echo -e "${GREEN}✓ Repository exists: $REPO_NAME${NC}"
    echo -e "\n${GREEN}✓ GitHub API validation successful!${NC}"
    exit 0
elif [[ "$HTTP_CODE" == "404" ]]; then
    echo -e "${RED}Error: Repository not found: $TENANT_ORG/$TENANT_REPO${NC}" >&2
    echo -e "${YELLOW}Hint: Please create the repository manually at:${NC}" >&2
    echo -e "${YELLOW}      https://github.com/$TENANT_ORG/$TENANT_REPO${NC}" >&2
    exit 1
elif [[ "$HTTP_CODE" == "401" ]]; then
    echo -e "${RED}Error: GitHub API returned 401 Unauthorized${NC}" >&2
    echo -e "${YELLOW}Hint: Check that GIT_APP_PRIVATE_KEY in .env.global is valid${NC}" >&2
    exit 1
elif [[ "$HTTP_CODE" == "403" ]]; then
    echo -e "${RED}Error: GitHub API returned 403 Forbidden${NC}" >&2
    echo -e "${YELLOW}Hint: Check that the GitHub App has access to the repository${NC}" >&2
    exit 1
else
    echo -e "${RED}Error: GitHub API returned HTTP $HTTP_CODE${NC}" >&2
    echo -e "${RED}Response: $REPO_DATA${NC}" >&2
    exit 1
fi
