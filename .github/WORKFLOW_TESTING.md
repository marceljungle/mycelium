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
6. Choose version type (`patch`, `minor`, or `major`)
7. Check **"Upload to Test PyPI instead of PyPI"** ✅
8. Click **"Run workflow"**

This will test the complete build process without affecting your production PyPI package.

### 2. Test Merge-Based Trigger

The primary workflow trigger is merging PRs to main with appropriate labels:

#### Test Minor Version Release
```bash
# 1. Create a feature branch
git checkout -b feature/test-release

# 2. Make a small change (e.g., update README)
echo "Test change" >> README.md
git add README.md
git commit -m "Test: minor release test"

# 3. Push and create PR
git push origin feature/test-release

# 4. Create PR with "minor" label to main branch
# 5. Merge the PR → triggers workflow → creates new minor version
```

#### Test Hotfix Release
```bash
# 1. Create a hotfix branch from main
git checkout main
git checkout -b hotfix/test-fix

# 2. Make a fix (e.g., update version comment)
# 3. Push and create PR with "hotfix" label to main
# 4. Merge → triggers workflow → creates new patch version
```

### 3. Production Release

For actual releases, follow the normal PR workflow:

- **Feature releases**: Create PR from `develop` to `main` with `minor` or `major` label
- **Hotfixes**: Create PR from hotfix branch to `main` with `hotfix` label

The workflow will automatically:
1. Detect the label from the merged PR
2. Calculate the new version number
3. Update `pyproject.toml`
4. Create and push a git tag
5. Build and publish to PyPI

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