# Testing the GitHub Actions Workflow

This document provides instructions for testing the new PyPI build and publish workflow.

## Prerequisites

1. **Repository Secrets**: Configure the following secrets in your GitHub repository settings:
   - `PYPI_API_TOKEN`: Your PyPI API token (for production releases)
   - `TEST_PYPI_API_TOKEN`: Your Test PyPI API token (optional, for testing)

2. **PyPI Account**: Ensure you have accounts on:
   - [PyPI](https://pypi.org/) for production releases
   - [Test PyPI](https://test.pypi.org/) for testing (optional)

## Testing Workflow

### 1. Test Manual Trigger (Recommended First Test)

1. Go to your repository on GitHub
2. Navigate to **Actions** tab
3. Select **"Build and Publish to PyPI"** workflow
4. Click **"Run workflow"**
5. Select your branch (usually `main`)
6. Check **"Upload to Test PyPI instead of PyPI"** ✅
7. Click **"Run workflow"**

This will test the complete build process without affecting your production PyPI package.

### 2. Test Automatic Tag Trigger

Once manual testing succeeds:

```bash
# Create and push a test version tag
git tag v0.1.0-test
git push origin v0.1.0-test
```

This will automatically trigger the workflow and upload to production PyPI.

### 3. Production Release

For actual releases:

```bash
# Create and push a version tag (matches the version in pyproject.toml)
git tag v0.1.0
git push origin v0.1.0
```

## Workflow Verification

The workflow includes several verification steps:

1. ✅ **Frontend Build**: Confirms Next.js builds successfully
2. ✅ **Frontend Integration**: Verifies frontend files are copied to Python package
3. ✅ **Package Build**: Creates both wheel and source distributions
4. ✅ **Package Contents**: Confirms frontend assets are included in the final package
5. ✅ **PyPI Upload**: Publishes to the specified PyPI instance

## Troubleshooting

### Common Issues

**Frontend Build Fails**:
- Check Node.js version compatibility (workflow uses Node.js 20)
- Verify frontend dependencies are properly specified in `package-lock.json`

**Python Build Fails**:
- Check Python dependencies in `pyproject.toml`
- Verify build tools are properly installed

**Upload Fails**:
- Confirm API tokens are correctly configured in repository secrets
- Check that package version doesn't already exist on PyPI
- Verify PyPI account has upload permissions

### Build Output

The workflow provides detailed logging for each step. Check the GitHub Actions logs for:

```
✓ Frontend dist directory exists and is not empty
✓ Client frontend dist directory exists and is not empty
✓ Frontend files are included in the package
```

## Manual Local Testing

You can test the build process locally:

```bash
# Test frontend build
./build_frontend.sh

# Test Python package build
python -m build

# Verify contents
ls -la dist/
```

This allows you to debug issues before running the GitHub Action.