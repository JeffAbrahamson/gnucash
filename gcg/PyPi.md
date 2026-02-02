# PyPI Publishing Guide for gcg

This document explains how to publish gcg to PyPI.

## Prerequisites

1. **PyPI Account**: Create accounts on both [PyPI](https://pypi.org) and [TestPyPI](https://test.pypi.org)

2. **API Tokens**: Generate API tokens for authentication:
   - Go to Account Settings > API tokens
   - Create a token scoped to the `gcg` project (or all projects for first upload)

3. **Install build tools**:
   ```bash
   pip install build twine
   ```

## Configuration

### Option 1: .pypirc file (traditional)

Create `~/.pypirc`:
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-your-api-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-api-token-here
```

**Security**: Set permissions: `chmod 600 ~/.pypirc`

### Option 2: Environment variables (CI-friendly)

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-your-api-token-here
```

## Version Bump

Before releasing, update the version in two places:

1. `gcg/__init__.py`:
   ```python
   __version__ = "0.2.0"
   ```

2. `pyproject.toml`:
   ```toml
   version = "0.2.0"
   ```

Follow [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes (backward compatible)

## Building

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info gcg/*.egg-info

# Build source distribution and wheel
python -m build
```

This creates:
- `dist/gcg-X.Y.Z.tar.gz` (source distribution)
- `dist/gcg-X.Y.Z-py3-none-any.whl` (wheel)

## Testing with TestPyPI

Always test on TestPyPI first:

```bash
# Upload to TestPyPI
python -m twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ gcg
```

Note: `--extra-index-url` is needed because dependencies (piecash, tabulate) are on regular PyPI.

## Publishing to PyPI

Once tested:

```bash
# Upload to PyPI
python -m twine upload dist/*
```

## Verifying the Release

```bash
# Install from PyPI
pip install gcg

# Or upgrade
pip install --upgrade gcg

# Verify version
gcg --version
```

## Common Tasks

### Check package before uploading

```bash
python -m twine check dist/*
```

### View package metadata

```bash
# From built wheel
unzip -p dist/gcg-*.whl gcg-*/METADATA | head -50
```

### Yanking a release

If you publish a broken version, you can yank it (discourages installation but doesn't delete):

1. Go to https://pypi.org/manage/project/gcg/releases/
2. Find the version
3. Click "Options" > "Yank"

### Deleting a release

PyPI does not allow deleting releases. If critical, contact PyPI support.

## CI/CD Integration

### GitHub Actions example

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install build tools
        run: pip install build twine

      - name: Build package
        run: python -m build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: python -m twine upload dist/*
```

Add `PYPI_API_TOKEN` to repository secrets in GitHub.

## Checklist for Releases

1. [ ] Update version in `gcg/__init__.py` and `pyproject.toml`
2. [ ] Update CHANGELOG (if you have one)
3. [ ] Ensure tests pass: `pytest`
4. [ ] Ensure linting passes: `black --check` and `flake8`
5. [ ] Clean and build: `rm -rf dist/ && python -m build`
6. [ ] Check package: `twine check dist/*`
7. [ ] Test on TestPyPI first
8. [ ] Upload to PyPI: `twine upload dist/*`
9. [ ] Create GitHub release/tag
10. [ ] Verify installation: `pip install --upgrade gcg`

## Troubleshooting

### "File already exists"
You cannot re-upload the same version. Bump the version number.

### "Invalid credentials"
- Verify your API token is correct
- Ensure username is `__token__` (literal string)
- Check token scope (project-specific vs all projects)

### "Package name already taken"
Someone else owns that name. Choose a different name or contact the owner.

### Build fails with encoding errors
Ensure all source files are UTF-8 encoded.
