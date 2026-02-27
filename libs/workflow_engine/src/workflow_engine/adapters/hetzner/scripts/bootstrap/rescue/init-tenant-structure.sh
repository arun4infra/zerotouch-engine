#!/usr/bin/env bash
# Initialize tenant repository structure if missing
# Creates environments/{env}/talos-values.yaml from Jinja2 template

set -eo pipefail

TENANT_CACHE_DIR="$1"
ENV="$2"
RESCUE_PASSWORD="$3"
CLUSTER_NAME="$4"
CONTROLPLANE_NAME="$5"
CONTROLPLANE_IP="$6"
TALOS_VERSION="$7"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="$SCRIPT_DIR/talos-values.yaml.j2"
TARGET_DIR="$TENANT_CACHE_DIR/environments/$ENV"
TARGET_FILE="$TARGET_DIR/talos-values.yaml"

# Check if file already exists
if [[ -f "$TARGET_FILE" ]]; then
    echo "Tenant config already exists: $TARGET_FILE"
    exit 0
fi

echo "Initializing tenant repository structure for environment: $ENV"

# Create directory structure
mkdir -p "$TARGET_DIR"

# Render Jinja2 template using Python
python3 << PYTHON_SCRIPT
from jinja2 import Template
from pathlib import Path

template_content = Path('$TEMPLATE_FILE').read_text()
template = Template(template_content)

rendered = template.render(
    env='$ENV',
    controlplane_name='$CONTROLPLANE_NAME',
    controlplane_ip='$CONTROLPLANE_IP',
    rescue_password='$RESCUE_PASSWORD',
    cluster_name='$CLUSTER_NAME',
    talos_version='$TALOS_VERSION'
)

Path('$TARGET_FILE').write_text(rendered)
print(f'✓ Created $TARGET_FILE')
PYTHON_SCRIPT

# Commit to git if in a git repo
if [[ -d "$TENANT_CACHE_DIR/.git" ]]; then
    cd "$TENANT_CACHE_DIR"
    git add "environments/$ENV/talos-values.yaml"
    git commit -m "Initialize $ENV environment with rescue password" || true
    echo "✓ Committed to tenant repository"
    
    # Push to remote
    if git remote get-url origin &>/dev/null; then
        git push origin main --quiet 2>&1 || echo "Warning: Failed to push to remote" >&2
        echo "✓ Pushed to remote repository"
    fi
fi
