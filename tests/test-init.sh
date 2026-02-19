#!/usr/bin/env bash
# Automated init test using non-interactive mode
# Usage: ./test-init.sh

set -e

# Clean previous state
rm -rf platform/platform.yaml ~/.ztp/secrets .ztc/session.json 2>/dev/null || true

# Load and export all values from .env.dev
set -a
source .env.dev
set +a

# Enable non-interactive mode
export ZTC_NON_INTERACTIVE=1

# Run init
./ztc-new.py init

echo "✓ Init test completed"
