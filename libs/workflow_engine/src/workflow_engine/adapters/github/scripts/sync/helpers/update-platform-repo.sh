#!/bin/bash
# Update platform repository with GitHub App authentication
# Usage: source update-platform-repo.sh <REPO_URL> <CACHE_DIR> <BRANCH>

set -e

REPO_URL="$1"
CACHE_DIR="$2"
BRANCH="${3:-main}"

if [[ -z "$REPO_URL" || -z "$CACHE_DIR" ]]; then
    echo "Error: Missing required parameters" >&2
    echo "Usage: source update-platform-repo.sh <REPO_URL> <CACHE_DIR> <BRANCH>" >&2
    exit 1
fi

# Generate GitHub App token
if [[ -n "$GIT_APP_ID" && -n "$GIT_APP_INSTALLATION_ID" && -n "$GIT_APP_PRIVATE_KEY" ]]; then
    echo "✓ Generating GitHub App token..." >&2
    
    # Generate JWT
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
    
    if [[ -z "$GITHUB_TOKEN" ]]; then
        echo "Error: Failed to generate GitHub App token" >&2
        echo "API Response: $TOKEN_RESPONSE" >&2
        echo "App ID: $GIT_APP_ID" >&2
        echo "Installation ID: $GIT_APP_INSTALLATION_ID" >&2
        exit 1
    fi
    
    REPO_AUTH_URL=$(echo "$REPO_URL" | sed "s|https://|https://x-access-token:${GITHUB_TOKEN}@|")
    echo "✓ GitHub App authentication configured" >&2
else
    echo "Error: GitHub App credentials not available" >&2
    echo "Set: GIT_APP_ID, GIT_APP_INSTALLATION_ID, GIT_APP_PRIVATE_KEY" >&2
    exit 1
fi

# Clone or update repository
if [[ -d "$CACHE_DIR/.git" ]]; then
    echo "Updating repository cache..." >&2
    cd "$CACHE_DIR"
    git remote set-url origin "$REPO_AUTH_URL"
    git fetch origin "$BRANCH" --quiet 2>/dev/null || {
        echo "Error: Failed to fetch from repository" >&2
        exit 1
    }
    git checkout "$BRANCH" --quiet 2>/dev/null || git checkout -b "$BRANCH" --quiet
    git reset --hard "origin/$BRANCH" --quiet 2>/dev/null || true
    cd - > /dev/null
else
    echo "Cloning repository..." >&2
    rm -rf "$CACHE_DIR"
    mkdir -p "$(dirname "$CACHE_DIR")"
    
    if git clone --branch "$BRANCH" "$REPO_AUTH_URL" "$CACHE_DIR" 2>&1; then
        echo "✓ Repository cloned successfully" >&2
    else
        # Branch might not exist, clone default and create branch
        echo "Branch $BRANCH not found, cloning default branch..." >&2
        if git clone "$REPO_AUTH_URL" "$CACHE_DIR" 2>&1; then
            cd "$CACHE_DIR"
            git checkout -b "$BRANCH" --quiet
            cd - > /dev/null
            echo "✓ Repository cloned and branch created" >&2
        else
            echo "Error: Failed to clone repository" >&2
            echo "URL: $REPO_URL" >&2
            exit 1
        fi
    fi
fi

# Verify we're in the repo
if [[ ! -d "$CACHE_DIR/.git" ]]; then
    echo "Error: Repository not properly cloned" >&2
    echo "Cache dir: $CACHE_DIR" >&2
    ls -la "$CACHE_DIR" >&2 || true
    exit 1
fi

echo "✓ Repository ready: $BRANCH" >&2
