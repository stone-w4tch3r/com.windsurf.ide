# Windsurf Flatpak Automation

This repository contains automation scripts to maintain the Windsurf Flatpak based on VSCodium's Flatpak, with minimal manual intervention.

## 🎯 Overview

The automation follows a **static files + PR-based updates** approach:

- **Flatpak manifest and files**: Static files in the repository root
- **Windsurf version updates**: Automated PRs that auto-merge on build success
- **VSCodium Flatpak updates**: Manual-review PRs for base dependency changes

## 📁 Structure

```
.
├── com.windsurf.ide.yaml              # Main Flatpak manifest (static)
├── assets/                            # Static assets directory
│   ├── com.windsurf.ide.desktop           # Desktop file
│   ├── com.windsurf.ide.metainfo.xml      # AppStream metadata
│   ├── com.windsurf.ide-url-handler.desktop # URL handler desktop file
│   ├── com.windsurf.ide-workspace.xml     # Workspace file associations
│   └── icons/                             # Application icons
│       ├── windsurf_64.png
│       ├── windsurf_128.png
│       ├── windsurf_256.png
│       └── windsurf_512.png
├── scripts/                           # Automation scripts
│   ├── main.py                        # CLI entry point
│   ├── windsurf_updater.py           # Windsurf version updates
│   ├── vscodium_updater.py           # VSCodium base updates
│   ├── github_client.py              # GitHub API integration
│   ├── version_fetcher.py             # Version fetching utilities
│   ├── manifest_fetcher.py            # Manifest fetching utilities
│   ├── validator.py                  # Manifest validation
│   ├── types.py                      # Type definitions
│   ├── exceptions.py                 # Custom exceptions
│   └── requirements.txt              # Python dependencies
├── shared-modules/                    # Git submodule for shared dependencies
└── .github/workflows/                 # GitHub Actions workflows
    ├── windsurf-update.yml           # Windsurf version checks
    ├── vscodium-update.yml           # VSCodium base checks
    ├── build-test.yml                # Build and test PRs
    └── external-trigger.yml          # External webhook triggers
```

## 🔄 Automation Workflows

### 1. Windsurf Version Updates (Auto-merge)

**Trigger**: Every 6 hours / Manual / Webhook
**Action**: 
- Ensures repository auto-merge is enabled automatically
- Checks Windsurf API for new versions
- Updates binary URL, SHA256, and size in manifest using surgical text replacement
- Preserves original YAML formatting (only 3 lines changed)
- Creates PR with auto-merge enabled via GitHub GraphQL API
- Auto-merges on successful build + tests

**Workflow**: `windsurf-update.yml`

### 2. VSCodium Flatpak Updates (Manual review)

**Trigger**: Daily / Manual / Webhook
**Action**:
- Fetches latest VSCodium Flatpak manifest
- Compares base dependencies (runtime, SDK, modules)
- Creates PR with proposed changes for manual review
- Requires manual merge after review

**Workflow**: `vscodium-update.yml`

### 3. Build & Test (All PRs)

**Trigger**: All PRs affecting Flatpak files
**Action**:
- Validates manifest syntax and structure
- Builds Flatpak in container environment  
- Tests basic functionality and installation
- Auto-merges Windsurf update PRs on success
- Preserves KDE Wayland desktop integration fixes

**Workflow**: `build-test.yml`

**Note**: Security scanning has been removed to prevent auto-merge failures due to false positives.

## 🛠️ Setup

### 1. Environment Variables

Set these in your GitHub repository settings:

```bash
GITHUB_TOKEN    # GitHub Personal Access Token with repo/PR permissions
```

### 2. Repository Settings

Enable the following in your repository:
- Actions (for workflows)
- **Auto-merge is enabled automatically** by the automation scripts
- No branch protection rules required (auto-merge works without them)

### 3. Local Development

```bash
# Install dependencies
pip install -r scripts/requirements.txt

# Check for Windsurf updates
python -m scripts.main check-windsurf

# Check for VSCodium updates  
python -m scripts.main check-vscodium

# Validate manifest
python -m scripts.main validate com.windsurf.ide.yaml --windsurf

# Test updater locally (creates test files)
python3 test_updater.py                    # Basic functionality test
python3 test_real_update.py               # Test with real version data
```

## 📋 Commands

### CLI Commands

```bash
# Check for updates
python -m scripts.main check-windsurf       # Check Windsurf versions
python -m scripts.main check-vscodium       # Check VSCodium base

# Validation
python -m scripts.main validate <manifest>  # Validate manifest
python -m scripts.main validate <manifest> --windsurf  # Windsurf-specific validation
```

### Manual Triggers

```bash
# Trigger via GitHub CLI
gh workflow run windsurf-update.yml
gh workflow run vscodium-update.yml

# Trigger via API webhook
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/OWNER/REPO/dispatches \
  -d '{"event_type":"windsurf-update"}'
```

## 🔍 Validation

The automation includes comprehensive validation:

### Manifest Validation
- ✅ YAML syntax and structure
- ✅ Required fields and types
- ✅ App ID format (`com.windsurf.ide`)
- ✅ Source definitions and URLs
- ✅ SHA256 hash formats
- ✅ Windsurf-specific requirements

### Update Validation
- ✅ Version progression (newer versions only)
- ✅ **Surgical formatting preservation** (only URL, SHA256, size changed)
- ✅ Build testing in container environment with KDE desktop integration
- ✅ Auto-merge enablement validation

## 🚨 Error Handling

The automation is designed to **fail fast** and **fail safe**:

- **Network errors**: Retry with exponential backoff
- **Validation errors**: Stop and report detailed issues  
- **Build failures**: Block auto-merge, require manual intervention
- **API rate limits**: Respect GitHub API limits with proper headers
- **Auto-merge issues**: Automatically enable repository auto-merge if disabled

## 🔗 Integration Points

### Windsurf API
- **Endpoint**: `https://windsurf-stable.codeium.com/api/update/linux-x64/stable/latest`
- **Data**: Version, download URL, metadata
- **Rate limit**: Reasonable usage (every 6 hours)

### VSCodium Flatpak
- **Source**: `https://github.com/flathub/com.vscodium.codium`
- **Files**: `com.vscodium.codium.yaml`, metainfo, patches
- **Comparison**: Runtime versions, shared modules, permissions

### GitHub API
- **Operations**: File CRUD, branch/PR management, auto-merge
- **Permissions**: `contents:write`, `pull-requests:write`
- **Rate limits**: Handled with proper headers and retries

## 📊 Monitoring

Monitor automation health via:

- **GitHub Actions**: Workflow run history and logs
- **PR labels**: `windsurf-update`, `vscodium-update`, `automated`
- **Build status**: Success/failure of Flatpak builds
- **Auto-merge status**: Successful auto-merges for Windsurf updates

## 🔧 Troubleshooting

### Common Issues

1. **Build failures**: Check container environment and dependency versions
2. **API failures**: Verify network connectivity and API endpoints  
3. **Auto-merge not working**: Repository auto-merge is enabled automatically by scripts
4. **Version extraction fails**: URL format may have changed
5. **Formatting corruption**: Use surgical text replacement, not YAML dumping

### Debug Mode

```bash
python -m scripts.main --debug check-windsurf
```

### Testing Locally

```bash
# Test the updater with mock data
python3 test_updater.py

# Test with real Windsurf version data
python3 test_real_update.py

# Clean up test files
rm test_*_manifest.yaml
```

### Manual Recovery

If automation fails, you can always:
1. Manually update the manifest files
2. Create PRs manually
3. Disable workflows temporarily
4. Roll back to previous versions

---

## 📝 License

Same as the main Windsurf Flatpak project.
