#!/usr/bin/env bash
# Convert ~/.ztc/secrets to .env format
# Reads INI format from ~/.ztc/secrets and outputs .env format

set -euo pipefail

SECRETS_FILE="${HOME}/.ztc/secrets"

if [ ! -f "$SECRETS_FILE" ]; then
    echo "Error: ~/.ztc/secrets not found" >&2
    exit 1
fi

# Parse INI format and convert to .env
while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    
    # Skip section headers
    [[ "$line" =~ ^\[.*\]$ ]] && continue
    
    # Parse key = value
    if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        
        # Trim whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        
        # Decode base64-encoded values
        if [[ "$value" =~ ^base64:(.+)$ ]]; then
            value=$(echo "${BASH_REMATCH[1]}" | base64 -d)
        fi
        
        # Map secrets to environment variable names
        case "$key" in
            hcloud_api_token)
                echo "HCLOUD_TOKEN=${value}"
                ;;
            hetzner_dns_token)
                echo "HETZNER_DNS_TOKEN=${value}"
                ;;
            github_app_id)
                echo "GIT_APP_ID=${value}"
                ;;
            github_app_installation_id)
                echo "GIT_APP_INSTALLATION_ID=${value}"
                ;;
            github_app_private_key)
                echo "GIT_APP_PRIVATE_KEY=${value}"
                ;;
            tenant_repo_url)
                # Extract org and repo from URL
                if [[ "$value" =~ https://github\.com/([^/]+)/([^/]+) ]]; then
                    echo "ORG_NAME=${BASH_REMATCH[1]}"
                    echo "TENANTS_REPO_NAME=${BASH_REMATCH[2]}"
                fi
                ;;
            s3_access_key)
                echo "S3_ACCESS_KEY=${value}"
                ;;
            s3_secret_key)
                echo "S3_SECRET_KEY=${value}"
                ;;
        esac
    fi
done < "$SECRETS_FILE"
