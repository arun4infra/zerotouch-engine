#!/usr/bin/env bash
set -euo pipefail

# sync-platform-repo.sh
# Purpose: Sync platform manifests to control plane repo and create PR
# Execution: Between render and bootstrap
# Context: Receives context via $ZTC_CONTEXT_FILE, secrets via environment variables

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Platform Manifest Sync                                     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Read context data
if [[ -z "${ZTC_CONTEXT_FILE:-}" ]]; then
    echo -e "${RED}✗ Error: ZTC_CONTEXT_FILE not set${NC}" >&2
    exit 1
fi

CONTROL_PLANE_URL=$(jq -r '.control_plane_repo_url' "$ZTC_CONTEXT_FILE")
BRANCH=$(jq -r '.platform_repo_branch' "$ZTC_CONTEXT_FILE")
ORG=$(jq -r '.tenant_org_name' "$ZTC_CONTEXT_FILE")
REPO=$(jq -r '.control_plane_repo_name' "$ZTC_CONTEXT_FILE")

if [[ -z "$CONTROL_PLANE_URL" || "$CONTROL_PLANE_URL" == "null" ]]; then
    echo -e "${RED}✗ Error: control_plane_repo_url not found${NC}" >&2
    exit 1
fi

if [[ -z "$BRANCH" || "$BRANCH" == "null" ]]; then
    BRANCH="main"
fi

echo -e "${GREEN}✓ Control plane repo: $CONTROL_PLANE_URL${NC}"
echo -e "${GREEN}✓ Branch: $BRANCH${NC}"
echo ""

# Clean cache directory before sync
CACHE_DIR=".zerotouch-cache/platform-repo"
echo -e "${BLUE}Cleaning cache directory...${NC}"
rm -rf "$CACHE_DIR"
echo -e "${GREEN}✓ Cache cleaned${NC}"

# Export GitHub App credentials for helper
export GIT_APP_ID=$(jq -r '.github_app_id' "$ZTC_CONTEXT_FILE")
export GIT_APP_INSTALLATION_ID=$(jq -r '.github_app_installation_id' "$ZTC_CONTEXT_FILE")
export GIT_APP_PRIVATE_KEY="${GIT_APP_PRIVATE_KEY:-}"

# Debug: Show what we got
echo -e "${BLUE}Debug - Credentials check:${NC}"
echo -e "  GIT_APP_ID: ${GIT_APP_ID:-<not set>}"
echo -e "  GIT_APP_INSTALLATION_ID: ${GIT_APP_INSTALLATION_ID:-<not set>}"
echo -e "  GIT_APP_PRIVATE_KEY length: ${#GIT_APP_PRIVATE_KEY}"
echo -e "  GIT_APP_PRIVATE_KEY set: $([[ -n "$GIT_APP_PRIVATE_KEY" ]] && echo 'yes' || echo 'no')"
echo ""

if [[ -z "$GIT_APP_ID" || "$GIT_APP_ID" == "null" ]]; then
    echo -e "${RED}✗ Error: github_app_id not found in context${NC}" >&2
    echo -e "${YELLOW}Context file: $ZTC_CONTEXT_FILE${NC}" >&2
    echo -e "${YELLOW}Available keys:${NC}" >&2
    jq 'keys' "$ZTC_CONTEXT_FILE" >&2
    exit 1
fi

if [[ -z "$GIT_APP_PRIVATE_KEY" ]]; then
    echo -e "${RED}✗ Error: GIT_APP_PRIVATE_KEY environment variable not set${NC}" >&2
    echo -e "${YELLOW}This should be passed as secret_env_vars${NC}" >&2
    exit 1
fi

# Source helper to fetch/update repo with GitHub App authentication
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers/update-platform-repo.sh" "$CONTROL_PLANE_URL" "$CACHE_DIR" "$BRANCH"

# Copy platform directory contents (not the directory itself)
echo -e "${BLUE}Copying platform manifests...${NC}"
cd "$CACHE_DIR"

# Delete all files except .git directory
echo -e "${BLUE}Cleaning repo (keeping .git)...${NC}"
find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
echo -e "${GREEN}✓ Repo cleaned${NC}"

# Copy platform contents to repo root
cp -r ../../platform/* .
echo -e "${GREEN}✓ Platform contents copied to repo root${NC}"

echo -e "${BLUE}Files after copy:${NC}"
ls -la | head -10

# Check for changes
echo -e "${BLUE}Checking for git changes...${NC}"
git status --short | head -20 || true

if [[ -z "$(git status --porcelain)" ]]; then
    echo ""
    echo -e "${GREEN}✓ No changes to sync${NC}"
    echo -e "${YELLOW}All manifests are up to date${NC}"
    exit 0
fi

# Commit and push changes
echo -e "${BLUE}Committing changes...${NC}"
git add -A
git commit -m "chore: update platform manifests" --quiet
echo -e "${GREEN}✓ Changes committed${NC}"

echo -e "${BLUE}Pushing to remote...${NC}"
git push origin "$BRANCH" --force --quiet 2>&1 || {
    echo -e "${RED}✗ Failed to push branch${NC}" >&2
    exit 1
}
echo -e "${GREEN}✓ Branch pushed${NC}"

# Create PR
echo -e "${BLUE}Creating pull request...${NC}"

if ! command -v gh &>/dev/null; then
    echo -e "${RED}✗ gh CLI not installed${NC}" >&2
    echo -e "${YELLOW}Install: brew install gh${NC}" >&2
    echo -e "${YELLOW}Or visit: https://github.com/$ORG/$REPO/compare/main...$BRANCH${NC}" >&2
    exit 1
fi

# Export GitHub App token for gh CLI
export GH_TOKEN="$GITHUB_TOKEN"

# Check if PR already exists
EXISTING_PR=$(gh pr list --repo "$ORG/$REPO" --head "$BRANCH" --json url -q '.[0].url' 2>/dev/null || echo "")

if [[ -n "$EXISTING_PR" ]]; then
    PR_URL="$EXISTING_PR"
    echo -e "${GREEN}✓ PR already exists${NC}"
else
    # Create new PR
    NEW_PR=$(gh pr create \
        --repo "$ORG/$REPO" \
        --base main \
        --head "$BRANCH" \
        --title "Platform manifests update" \
        --body "Automated sync of platform manifests from ztc render" \
        2>&1)
    
    if [[ "$NEW_PR" == https* ]]; then
        PR_URL="$NEW_PR"
        echo -e "${GREEN}✓ Pull request created${NC}"
    else
        echo -e "${RED}✗ Failed to create PR${NC}" >&2
        echo -e "${YELLOW}Error: $NEW_PR${NC}" >&2
        echo -e "${YELLOW}Manual URL: https://github.com/$ORG/$REPO/compare/main...$BRANCH${NC}" >&2
        exit 1
    fi
fi
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Action Required                                            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}PR URL: ${GREEN}$PR_URL${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Review and approve the PR"
echo -e "  2. Merge the PR"
echo -e "  3. Run: ${GREEN}ztc bootstrap${NC}"
echo ""

exit 0
