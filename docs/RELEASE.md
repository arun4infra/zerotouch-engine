# Release Workflow

## Prerequisites

- Poetry installed
- Git repository with clean working tree

## Release Steps

### 1. Update Version

```bash
# Update version in libs/cli/pyproject.toml
cd libs/cli
poetry version patch  # or minor, major
```

### 2. Build Distribution Packages

```bash
# Build wheel and sdist
poetry build

# Verify build artifacts
ls -lh dist/
```

### 3. Test Installation

```bash
# Test local installation
pip install dist/ztc_cli-*.whl

# Verify
ztc-workflow --version
```

### 4. Create Git Tag

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
