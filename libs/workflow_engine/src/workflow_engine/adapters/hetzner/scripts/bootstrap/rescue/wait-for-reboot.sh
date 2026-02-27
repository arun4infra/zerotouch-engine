#!/usr/bin/env bash
# Wait for server to reboot into rescue mode
# Hetzner servers typically take 60-90 seconds to reboot

set -eo pipefail

echo "Waiting 120 seconds for server to reboot into rescue mode..."
sleep 120
echo "✓ Wait complete - server should be in rescue mode"
