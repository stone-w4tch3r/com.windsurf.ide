# Windsurf Flatpak Automation

This repository contains automation scripts to maintain the Windsurf Flatpak based on VSCodium's Flatpak, with minimal manual intervention.

## 🎯 Overview

The automation follows a **static files + PR-based updates** approach:

- **Flatpak manifest and files**: Static files in the repository root
- **Windsurf version updates**: Automated PRs that auto-merge on build success
- **VSCodium Flatpak updates**: Manual-review PRs for base dependency changes
- **Signed repo + Pages publish**: After a successful build, a signed OSTree repo is published to GitHub Pages

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
│   ├── version_fetcher.py            # Version fetching utilities
│   ├── manifest_fetcher.py           # Manifest fetching utilities
│   ├── validator.py                  # Manifest validation
│   ├── windsurf_types.py             # Type definitions
│   ├── exceptions.py                 # Custom exceptions
│   ├── pages_publisher_simple.py     # Publish signed repo to GitHub Pages
│   └── requirements.txt              # Python dependencies
├── shared-modules/                    # Git submodule for shared dependencies
└── .github/workflows/                 # GitHub Actions workflows
    ├── windsurf-update.yml           # Windsurf version checks
    ├── vscodium-update.yml           # VSCodium base checks
    ├── build-test.yml                # Build and test PRs
    └── deploy-pages.yml              # Sign repo and publish to GitHub Pages
```

## 🔄 Automation Workflows

### 1. Windsurf Version Updates (Auto-merge)

**Trigger**: Every 6 hours / Manual / Webhook
**Action**:
- Ensures repository auto-merge is enabled automatically
- Checks Windsurf API for new versions
- Updates binary URL, SHA256, and size in manifest using surgical text replacement
- Preserves original YAML formatting (only 3 lines changed)
- Creates PR with auto-merge enabled via GitHub's native auto-merge API
- Auto-merges when required status checks (`validate` and `build`) pass

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

**Trigger**: All PRs affecting Flatpak files (`com.windsurf.ide.yaml`, `com.windsurf.ide.metainfo.xml`, assets, scripts)
**Action**:
- Validates manifest syntax and structure (`validate` job)
- Builds Flatpak in container environment (`build` job)
- Tests basic functionality and installation
- Reports status to GitHub's status check API
- Enables GitHub's native auto-merge for qualified PRs

**Workflow**: `build-test.yml`

### 4. Sign and Publish OSTree Repo to GitHub Pages

**Trigger**: On successful completion of "Build and Test Flatpak" (or manual)
**Action**:
- Downloads the built `repo/` artifact
- Ensures correct OSTree structure and signs it
- Generates static content and publishes to GitHub Pages

**Workflow**: `deploy-pages.yml`

> Requires GPG keys in repository secrets (see Setup → Secrets).

## 🛠️ Setup

### 1. Prerequisites

For auto-merge to work properly, you **must** configure:

#### Required Repository Settings:
1. **Enable Auto-merge**: Settings → General → Pull Requests → ☑️ "Allow auto-merge"
2. **Configure Branch Protection**: Settings → Branches → Add rule for `master`:
   - ☑️ "Require status checks to pass before merging"
   - ☑️ "Require branches to be up to date before merging"
   - Add required status checks: `validate` and `build`

#### Important Notes:
- Status checks (`validate`, `build`) must run at least once before they appear in the branch protection settings
- You can search for these job names when configuring required status checks
- Without branch protection, GitHub's native auto-merge will not work

### 2. Environment Variables

Set these in your GitHub repository settings:

Set for local runs (workflows set these automatically):

```bash
GITHUB_TOKEN    # GitHub token with repo/PR permissions
GITHUB_OWNER    # e.g. your-username or org name
GITHUB_REPO     # repository name
```

### 3. Additional Repository Settings

Ensure these are also enabled:
- Actions (for workflows)
- GitHub Pages (for publishing signed Flatpak repository)

#### Secrets
- **`PAT_TOKEN`** (Personal Access Token) - **REQUIRED** for PR workflows to trigger
  - Must have `repo` scope (full control of private repositories)
  - Optional: `workflow` scope (if workflows need to be modified)
  - **Critical**: Without this, PRs created by automation won't trigger build workflows
- `FLATPAK_GPG_PRIVATE_KEY` and `FLATPAK_GPG_PASSPHRASE` (used for signing in build on push and during Pages publish)
- `FLATPAK_GPG_PUBLIC_KEY` (used during Pages publish)

### 4. Setting Up Auto-merge (Step-by-step)

If you're setting up a new repository, follow these steps **in order**:

1. **Create Personal Access Token**:
   - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate token with `repo` scope (and optionally `workflow` scope)
   - Copy the token value

2. **Add PAT as repository secret**:
   - Go to repository Settings → Secrets and variables → Actions
   - Add new secret: Name=`PAT_TOKEN`, Value=[your token]
   - **Critical**: Without this, PRs won't trigger build workflows due to GitHub's GITHUB_TOKEN limitation

3. **Enable repository auto-merge**:
   ```bash
   # This can be done via API (requires admin permissions):
   gh api repos/OWNER/REPO --method PATCH --field allow_auto_merge=true

   # Or manually: Settings → General → Pull Requests → ☑️ "Allow auto-merge"
   ```

4. **Run workflows at least once** to register status checks:
   ```bash
   # Trigger a build to register the validate/build jobs
   gh workflow run build-test.yml
   ```

5. **Configure branch protection** (after status checks are registered):
   ```bash
   # Via API:
   gh api repos/OWNER/REPO/branches/master/protection --method PUT --input - <<'EOF'
   {
     "required_status_checks": {
       "strict": true,
       "contexts": ["validate", "build"]
     },
     "enforce_admins": false,
     "required_pull_request_reviews": null,
     "restrictions": null
   }
   EOF

   # Or manually: Settings → Branches → Add rule → Configure as described above
   ```

6. **Test the setup**:
   ```bash
   # Trigger a Windsurf update to test auto-merge
   gh workflow run windsurf-update.yml
   ```

### 5. Local Development

```bash
# Install dependencies
pip install -r scripts/requirements.txt

# Check for Windsurf updates
python -m scripts.main check-windsurf

# Check for VSCodium updates  
python -m scripts.main check-vscodium

# Validate manifest
python -m scripts.main validate com.windsurf.ide.yaml --windsurf
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
gh workflow run deploy-pages.yml

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
 - ✅ Signed repo generation and Pages publishing on successful builds

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

Note: The Flatpak manifest downloads the tarball from the `codeiumdata.com` host; the version metadata API is served from `codeium.com`.

### VSCodium Flatpak
- **Source**: `https://github.com/flathub/com.vscodium.codium`
- **Files**: `com.vscodium.codium.yaml`, metainfo, patches
- **Comparison**: Runtime versions, shared modules, permissions
- **Tracking**: Local `vscodium-manifest.yaml` tracks upstream details for change detection

### GitHub API
- **Operations**: File CRUD, branch/PR management, auto-merge
- **Permissions**: `contents:write`, `pull-requests:write`
- **Rate limits**: Handled with proper headers and retries

## 📊 Monitoring

Monitor automation health via:

- **GitHub Actions**: Workflow run history and logs
- **PR labels**: `windsurf-update`, `vscodium-update`, `automated`, `manual-review`
- **Build status**: Success/failure of Flatpak builds
- **Auto-merge status**: Successful auto-merges for Windsurf updates
- **Pages deployment**: Environments → GitHub Pages for latest published repo

## 🔧 Troubleshooting

### Common Issues

1. **Build failures**: Check container environment and dependency versions
2. **API failures**: Verify network connectivity and API endpoints
3. **Auto-merge not working**:
   - Verify repository auto-merge is enabled (Settings → General → Allow auto-merge)
   - Ensure branch protection rules are configured with required status checks
   - Check that `validate` and `build` jobs completed successfully
   - Confirm the PR has auto-merge enabled (should show "Will auto-merge" label)
4. **Status checks not appearing**: Jobs must run at least once before appearing in branch protection settings
5. **PRs created by automation don't trigger workflows**:
   - **Root cause**: GitHub's GITHUB_TOKEN limitation - bot-created PRs don't trigger pull_request workflows
   - **Solution**: Must use Personal Access Token (PAT_TOKEN) instead of GITHUB_TOKEN
   - **Symptoms**: PR shows "auto-merge enabled" but no status checks appear
6. **Version extraction fails**: URL format may have changed
7. **Formatting corruption**: Use surgical text replacement, not YAML dumping
8. **Pages publish issues**: Verify Pages is enabled, and GPG secrets are correctly configured

### Debug Mode

```bash
python -m scripts.main --debug check-windsurf
```

### Testing Locally

```bash
# Run validators and dry-runs
python -m scripts.main validate com.windsurf.ide.yaml --windsurf
# Optionally run with debug logging
python -m scripts.main --debug check-windsurf
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
