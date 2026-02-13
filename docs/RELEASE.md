# Release Workflow

## Prerequisites

- Poetry installed
- PyInstaller installed (`poetry add --group dev pyinstaller`)
- Git repository with clean working tree

## Release Steps

### 1. Update Version

```bash
# Update version in pyproject.toml
poetry version patch  # or minor, major
```

### 2. Build Distribution Packages

```bash
# Build wheel and sdist
poetry build

# Verify build artifacts
ls -lh dist/
```

### 3. Build Standalone Binary

```bash
# Build binary with PyInstaller
poetry run pyinstaller ztc.spec --clean

# Verify binary
./dist/ztc version
```

### 4. Test Binary

```bash
# Run validation tests
./tests/validate_binary_resources.sh
```

### 5. Create Git Tag

```bash
# Get version from pyproject.toml
VERSION=$(poetry version -s)

# Create and push tag
git tag -a "v${VERSION}" -m "Release v${VERSION}"
git push origin "v${VERSION}"
```

## Distribution

### PyPI (Python Package)

```bash
# Publish to PyPI
poetry publish

# Install from PyPI
pip install ztc
```

### Binary Distribution

```bash
# Package binary for distribution
tar -czf "ztc-${VERSION}-$(uname -s)-$(uname -m).tar.gz" -C dist ztc

# Distribute via GitHub Releases or artifact repository
```

## Verification

```bash
# Test installed package
pip install ztc
ztc version

# Test binary
./dist/ztc version
./dist/ztc render --help
```
