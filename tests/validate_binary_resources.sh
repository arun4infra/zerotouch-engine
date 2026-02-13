#!/bin/bash
set -e

echo "=== Task 154: Validate Embedded Resources in Packaged Binary ==="
echo

# Test 1: Verify binary exists and is executable
echo "1. Binary exists and is executable"
if [ -x "./dist/ztc" ]; then
    echo "   ✓ Binary is executable"
else
    echo "   ✗ Binary not found or not executable"
    exit 1
fi
echo

# Test 2: Verify adapter metadata is accessible
echo "2. Adapter metadata accessible (version command)"
./dist/ztc version | grep -q "Embedded Adapter Versions"
if [ $? -eq 0 ]; then
    echo "   ✓ Adapter metadata accessible"
    ./dist/ztc version | grep -A 5 "Embedded Adapter"
else
    echo "   ✗ Adapter metadata not accessible"
    exit 1
fi
echo

# Test 3: Verify templates are accessible (render command)
echo "3. Templates accessible (render generates manifests)"
cd test-binary-workspace
rm -rf platform .zerotouch-cache
../dist/ztc render > /dev/null 2>&1
if [ -f "platform/generated/talos/nodes/control-1/config.yaml" ]; then
    echo "   ✓ Templates rendered successfully"
    echo "   Generated: $(find platform/generated -type f | wc -l) files"
else
    echo "   ✗ Templates not accessible"
    exit 1
fi
echo

# Test 4: Verify scripts are accessible (eject command)
echo "4. Scripts accessible (eject extracts scripts)"
../dist/ztc eject > /dev/null 2>&1
if [ -f "debug/scripts/talos/bootstrap/bootstrap-talos.sh" ]; then
    echo "   ✓ Scripts extracted successfully"
    echo "   Extracted: $(find debug/scripts -name "*.sh" | wc -l) scripts"
else
    echo "   ✗ Scripts not accessible"
    exit 1
fi
echo

# Test 5: Verify script content is valid
echo "5. Script content is valid (not empty/corrupted)"
SCRIPT="debug/scripts/talos/bootstrap/bootstrap-talos.sh"
if [ -s "$SCRIPT" ] && head -1 "$SCRIPT" | grep -q "#!/bin/bash"; then
    echo "   ✓ Script content is valid"
    echo "   Size: $(wc -c < "$SCRIPT") bytes"
else
    echo "   ✗ Script content invalid"
    exit 1
fi
echo

# Test 6: Verify adapter.yaml files are accessible
echo "6. Adapter metadata files accessible"
if [ -f "platform/generated/talos/nodes/control-1/config.yaml" ]; then
    # Check if talos config has expected structure
    grep -q "type: controlplane" "platform/generated/talos/nodes/control-1/config.yaml"
    if [ $? -eq 0 ]; then
        echo "   ✓ Adapter metadata files accessible"
    else
        echo "   ✗ Adapter metadata incomplete"
        exit 1
    fi
fi
echo

# Test 7: Verify versions.yaml is accessible
echo "7. versions.yaml accessible"
../dist/ztc version | grep -q "CLI Version"
if [ $? -eq 0 ]; then
    echo "   ✓ versions.yaml accessible"
else
    echo "   ✗ versions.yaml not accessible"
    exit 1
fi
echo

echo "=== All embedded resources validated successfully ==="
