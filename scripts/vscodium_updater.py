"""Update Windsurf Flatpak based on VSCodium Flatpak changes."""

import logging
import copy
import yaml
from typing import Optional, Dict, Any, List

from .manifest_fetcher import ManifestFetcher
from .github_client import GitHubClient
from .exceptions import ValidationError, ManifestTransformError
from .emergency_brake import EmergencyBrake


logger = logging.getLogger(__name__)


# Modules that MUST be preserved from Windsurf (never sync from VSCodium)
# These are Windsurf-specific and incompatible with VSCodium's approach
WINDSURF_ONLY_MODULES = {
    "windsurf",  # Windsurf main app module (uses .tar.gz, different from codium .deb)
    "host-spawn",  # Windsurf uses pre-built binaries, VSCodium builds from source
}

# Modules from VSCodium that MUST be excluded (never sync to Windsurf)
# These are VSCodium-specific and incompatible with Windsurf
VSCODIUM_EXCLUDED_MODULES = {
    "codium",  # VSCodium main app module (uses .deb, different from windsurf .tar.gz)
}


class VSCodiumUpdater:
    """Updates Windsurf Flatpak based on VSCodium Flatpak changes."""
    
    def __init__(self, github_client: GitHubClient):
        """Initialize the updater.

        Args:
            github_client: GitHub API client
        """
        self.github = github_client
        self.manifest_fetcher = ManifestFetcher()
        self.emergency_brake = EmergencyBrake(github_client)
    
    def check_and_update(self) -> Optional[str]:
        """Check for VSCodium Flatpak updates and create PR if needed.

        Returns:
            PR URL if update was created, None if no update needed

        Raises:
            ValidationError: If validation fails
            ManifestTransformError: If manifest transformation fails
        """
        try:
            # Run emergency brake pre-flight checks
            logger.info("Running emergency brake pre-flight checks")
            is_safe, reason = self.emergency_brake.check()
            if not is_safe:
                logger.warning(f"Emergency brake triggered: {reason}")
                return None

            # Check if another PR is already in progress (single PR enforcement)
            # NOTE: This check happens before branch creation. In the rare case of
            # concurrent workflow execution (e.g., manual trigger + scheduled trigger),
            # multiple PRs could still be created. This is an acceptable trade-off
            # given the low probability (scheduled runs are 6 hours apart).
            if self.github.has_open_prs():
                logger.info("Another PR is already in progress, skipping this run")
                return None

            # Fetch latest VSCodium manifest
            logger.info("Checking for VSCodium Flatpak updates")
            current_vscodium = self.manifest_fetcher.fetch_vscodium_manifest()
            
            # Get stored VSCodium manifest for comparison
            stored_vscodium_content = self.github.get_file_content("vscodium-manifest.yaml")
            if not stored_vscodium_content:
                raise ValidationError("Stored VSCodium manifest not found")

            stored_vscodium = yaml.safe_load(stored_vscodium_content)
            
            # Extract version info
            current_version = self._extract_vscodium_version(current_vscodium)
            stored_version = stored_vscodium.get("version")
            
            logger.info(f"Stored VSCodium version: {stored_version}, Current version: {current_version}")
            
            # Detect what changed
            changes = self._detect_changes(stored_vscodium, current_vscodium)
            
            if not changes:
                logger.info("No relevant changes detected in VSCodium Flatpak")
                return None
            
            # Get current Windsurf manifest
            windsurf_content = self.github.get_file_content("com.windsurf.ide.yaml")
            if not windsurf_content:
                raise ValidationError("Windsurf manifest not found")

            windsurf_data = yaml.safe_load(windsurf_content)

            # Apply changes to Windsurf manifest
            updated_windsurf = self._apply_changes(windsurf_data, current_vscodium, changes)
            updated_vscodium_tracking = self._update_tracking_manifest(stored_vscodium, current_vscodium)

            # Create branch and PR
            branch_name = f"vscodium-update-{current_version.replace('.', '-')}"

            # Create branch
            self.github.create_branch(branch_name)

            # Dump YAML with sensible formatting
            dump_params = {
                'default_flow_style': False,
                'sort_keys': False,
                'width': 100,
                'indent': 2
            }

            # Update Windsurf manifest
            windsurf_sha = self.github.get_file_sha("com.windsurf.ide.yaml")
            self.github.create_or_update_file(
                path="com.windsurf.ide.yaml",
                content=yaml.dump(updated_windsurf, **dump_params),
                message=f"Update Windsurf based on VSCodium {current_version}",
                branch=branch_name,
                sha=windsurf_sha
            )

            # Update tracking manifest
            tracking_sha = self.github.get_file_sha("vscodium-manifest.yaml")
            self.github.create_or_update_file(
                path="vscodium-manifest.yaml",
                content=yaml.dump(updated_vscodium_tracking, **dump_params),
                message=f"Update VSCodium tracking to {current_version}",
                branch=branch_name,
                sha=tracking_sha
            )
            
            # Create PR (no auto-merge for VSCodium updates)
            pr_title = f"Update from VSCodium Flatpak {current_version}"
            pr_body = self._generate_pr_body(changes, current_version, stored_version)
            
            pr = self.github.create_pull_request(
                title=pr_title,
                head=branch_name,
                body=pr_body,
                labels=["vscodium-update", "manual-review"]
            )
            
            logger.info(f"Created PR for VSCodium-based update: {pr['html_url']}")
            return pr["html_url"]
            
        except Exception as e:
            logger.error(f"Failed to update from VSCodium: {e}")
            raise
    
    def _extract_vscodium_version(self, manifest_data: dict) -> str:
        """Extract VSCodium version from manifest.
        
        Args:
            manifest_data: Parsed VSCodium manifest
            
        Returns:
            VSCodium version string
            
        Raises:
            ValidationError: If version cannot be extracted
        """
        try:
            # Look for codium module
            modules = manifest_data.get("modules", [])
            for module in modules:
                if isinstance(module, str):
                    continue
                if module.get("name") == "codium":
                    sources = module.get("sources", [])
                    for source in sources:
                        if source.get("dest-filename") == "codium.deb":
                            url = source.get("url", "")
                            import re
                            version_match = re.search(r"codium_([0-9.]+)_", url)
                            if version_match:
                                return version_match.group(1)
            
            raise ValidationError("Could not extract VSCodium version from manifest")
            
        except (KeyError, TypeError) as e:
            raise ValidationError(f"Invalid VSCodium manifest structure: {e}") from e
    
    def _detect_changes(self, stored_manifest: dict, current_manifest: dict) -> List[str]:
        """Detect relevant changes between stored and current VSCodium manifests.
        
        Uses "if anything changed except XYZ" logic instead of "if XYZ changed".
        
        Args:
            stored_manifest: Previously stored manifest state
            current_manifest: Current upstream manifest
            
        Returns:
            List of detected changes
        """
        changes = []
        
        # Fields we ignore (VSCodium-specific)
        ignored_fields = {
            "id",  # app ID
            "command",  # command name
            "persist",  # .vscode-oss vs .windsurf-ide
        }
        
        # Fields we ignore in modules
        ignored_module_names = {"codium"}  # VSCodium main module
        
        # Check runtime versions
        stored_runtime = stored_manifest.get("runtime_version")
        current_runtime = current_manifest.get("runtime-version")
        if stored_runtime != current_runtime:
            changes.append(f"Runtime version: {stored_runtime} → {current_runtime}")
        
        # Check base versions
        stored_base = stored_manifest.get("base_version")
        current_base = current_manifest.get("base-version")
        if stored_base != current_base:
            changes.append(f"Base version: {stored_base} → {current_base}")
        
        # Check finish-args
        stored_finish_args = set(stored_manifest.get("finish_args", []))
        current_finish_args = set(current_manifest.get("finish-args", []))
        
        # Filter out ignored args
        windsurf_specific_args = {
            "--persist=.windsurf-ide",
            "--env=NPM_CONFIG_GLOBALCONFIG=/app/etc/npmrc",
            "--env=LD_LIBRARY_PATH=/app/lib",
            "--talk-name=org.freedesktop.Notifications",
        }
        vscodium_specific_args = {
            "--persist=.vscode-oss",
        }
        
        # Compare relevant args only
        relevant_stored = stored_finish_args - windsurf_specific_args - vscodium_specific_args
        relevant_current = current_finish_args - windsurf_specific_args - vscodium_specific_args
        
        new_args = relevant_current - relevant_stored
        removed_args = relevant_stored - relevant_current
        
        if new_args:
            changes.append(f"New finish-args: {', '.join(sorted(new_args))}")
        if removed_args:
            changes.append(f"Removed finish-args: {', '.join(sorted(removed_args))}")
        
        # Check shared modules
        stored_modules = self._extract_shared_modules(stored_manifest)
        current_modules = self._extract_shared_modules_from_manifest(current_manifest)
        
        for module_name in ["libsecret", "wrapper-flatpak-wrapper"]:
            if module_name in stored_modules and module_name in current_modules:
                if self._modules_differ(stored_modules[module_name], current_modules[module_name]):
                    changes.append(f"Module '{module_name}' updated")
        
        return changes
    
    def _extract_shared_modules(self, stored_manifest: dict) -> Dict[str, dict]:
        """Extract shared modules from stored tracking manifest."""
        modules = {}
        shared_modules = stored_manifest.get("shared_modules", {})

        if "libsecret" in shared_modules:
            modules["libsecret"] = shared_modules["libsecret"]
        if "wrapper-flatpak-wrapper" in shared_modules:
            modules["wrapper-flatpak-wrapper"] = shared_modules["wrapper-flatpak-wrapper"]

        return modules
    
    def _extract_shared_modules_from_manifest(self, manifest_data: dict) -> Dict[str, dict]:
        """Extract shared modules from VSCodium manifest."""
        modules = {}

        for module in manifest_data.get("modules", []):
            if isinstance(module, str):
                continue

            name = module.get("name")
            if name in ["libsecret", "wrapper-flatpak-wrapper"]:
                modules[name] = module

        return modules
    
    def _modules_differ(self, stored_module: dict, current_module: dict) -> bool:
        """Check if two modules have meaningful differences."""
        # For tracking manifest modules, compare with current manifest modules
        if "url" in stored_module and "sha256" in stored_module:
            # libsecret format in tracking manifest
            sources = current_module.get("sources", [])
            for source in sources:
                if source.get("type") == "archive":
                    return (stored_module.get("url") != source.get("url") or
                           stored_module.get("sha256") != source.get("sha256"))

        elif "commit" in stored_module:
            # wrapper format in tracking manifest
            stored_commit = stored_module.get("commit")
            sources = current_module.get("sources", [])
            for source in sources:
                if source.get("type") == "git":
                    return stored_commit != source.get("commit")

        return False
    
    def _apply_changes(self, windsurf_data: dict, vscodium_manifest: dict, changes: List[str]) -> dict:
        """Apply detected changes to Windsurf manifest.

        Uses Windsurf's module list as the base and:
        1. Preserves Windsurf-only modules (windsurf, host-spawn)
        2. Updates shared modules from VSCodium (libsecret, wrapper-flatpak-wrapper)
        3. Auto-includes new modules from VSCodium (except excluded ones)
        4. Preserves Windsurf's original module order

        Args:
            windsurf_data: Current Windsurf manifest
            vscodium_manifest: Current VSCodium manifest
            changes: List of detected changes

        Returns:
            Updated Windsurf manifest
        """
        updated = copy.deepcopy(windsurf_data)

        # Update runtime/base versions
        updated["runtime-version"] = vscodium_manifest.get("runtime-version")
        updated["base-version"] = vscodium_manifest.get("base-version")

        # Get module names from both manifests
        windsurf_module_names = set()
        windsurf_modules_by_name = {}
        for i, module in enumerate(updated.get("modules", [])):
            if isinstance(module, dict):
                name = module.get("name")
                if name:
                    windsurf_module_names.add(name)
                    windsurf_modules_by_name[name] = module

        vscodium_modules_by_name = {}
        for module in vscodium_manifest.get("modules", []):
            if isinstance(module, dict):
                name = module.get("name")
                if name:
                    vscodium_modules_by_name[name] = module

        # Build new module list using Windsurf's order as base
        new_modules = []

        # First, add all Windsurf modules (preserves order)
        for module in updated.get("modules", []):
            if isinstance(module, str):
                # String references (like shared-modules/libusb/libusb.json) stay as-is
                new_modules.append(module)
            elif isinstance(module, dict):
                name = module.get("name")
                if not name:
                    # Module without name, keep as-is
                    new_modules.append(module)
                    continue

                # Windsurf-only modules: preserve exactly as-is
                if name in WINDSURF_ONLY_MODULES:
                    new_modules.append(module)
                    logger.debug(f"Preserving Windsurf-only module: {name}")
                    continue

                # VSCodium-excluded modules: skip (don't include)
                if name in VSCODIUM_EXCLUDED_MODULES:
                    logger.debug(f"Skipping VSCodium-excluded module: {name}")
                    continue

                # Shared modules: update from VSCodium if available
                if name in vscodium_modules_by_name:
                    new_modules.append(copy.deepcopy(vscodium_modules_by_name[name]))
                    logger.debug(f"Updating shared module from VSCodium: {name}")
                else:
                    # Module exists in Windsurf but not in VSCodium, keep as-is
                    new_modules.append(module)
                    logger.debug(f"Keeping Windsurf module (not in VSCodium): {name}")

        # Then, add any NEW modules from VSCodium (auto-include new dependencies)
        for name, vscodium_module in vscodium_modules_by_name.items():
            if name not in windsurf_module_names and name not in VSCODIUM_EXCLUDED_MODULES:
                new_modules.append(copy.deepcopy(vscodium_module))
                logger.info(f"Auto-including new module from VSCodium: {name}")

        updated["modules"] = new_modules

        # Update finish-args, preserving Windsurf-specific ones
        windsurf_specific_args = {
            "--persist=.windsurf-ide",
            "--env=NPM_CONFIG_GLOBALCONFIG=/app/etc/npmrc",
            "--env=LD_LIBRARY_PATH=/app/lib",
            "--talk-name=org.freedesktop.Notifications",
            "--require-version=0.10.3",  # If present
        }

        vscodium_args = set(vscodium_manifest.get("finish-args", []))
        vscodium_specific_args = {"--persist=.vscode-oss"}

        # Merge args: VSCodium args + Windsurf-specific args, minus VSCodium-specific
        merged_args = list((vscodium_args - vscodium_specific_args) | windsurf_specific_args)
        updated["finish-args"] = sorted(merged_args)

        return updated
    
    def _update_tracking_manifest(self, stored_manifest: dict, current_vscodium: dict) -> dict:
        """Update the VSCodium tracking manifest.
        
        Args:
            stored_manifest: Current tracking manifest
            current_vscodium: New VSCodium manifest
            
        Returns:
            Updated tracking manifest
        """
        updated = copy.deepcopy(stored_manifest)
        
        # Update version and metadata
        updated["version"] = self._extract_vscodium_version(current_vscodium)
        updated["last_updated"] = self._get_current_date()
        updated["runtime_version"] = current_vscodium.get("runtime-version")
        updated["base_version"] = current_vscodium.get("base-version")
        
        # Update finish_args
        updated["finish_args"] = current_vscodium.get("finish-args", [])
        
        # Update shared modules
        vscodium_modules = self._extract_shared_modules_from_manifest(current_vscodium)
        
        if "libsecret" in vscodium_modules:
            sources = vscodium_modules["libsecret"].get("sources", [])
            for source in sources:
                if source.get("type") == "archive":
                    updated["shared_modules"]["libsecret"] = {
                        "url": source.get("url"),
                        "sha256": source.get("sha256")
                    }

        if "wrapper-flatpak-wrapper" in vscodium_modules:
            sources = vscodium_modules["wrapper-flatpak-wrapper"].get("sources", [])
            for source in sources:
                if source.get("type") == "git":
                    updated["shared_modules"]["wrapper-flatpak-wrapper"] = {
                        "commit": source.get("commit")
                    }
        
        return updated
    
    def _get_current_date(self) -> str:
        """Get current date in YYYY-MM-DD format."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
    
    def _generate_pr_body(self, changes: List[str], current_version: str, stored_version: str) -> str:
        """Generate PR description for VSCodium-based updates."""
        changes_text = "\n".join(f"- {change}" for change in changes)
        
        return f"""## VSCodium Flatpak Update

This PR updates the Windsurf Flatpak based on changes in VSCodium Flatpak `{stored_version}` → `{current_version}`.

### Detected Changes
{changes_text}

### What's Updated
- ✅ Updated `com.windsurf.ide.yaml` with relevant changes from VSCodium
- ✅ Updated `vscodium-manifest.yaml` tracking file
- 🔍 Preserved Windsurf-specific configuration (persist path, environment variables, etc.)
- 🔍 Applied only relevant changes (ignored VSCodium-specific modules)

### Manual Review Required
⚠️ **This PR requires manual review** as it may affect:
- Runtime environment compatibility
- Permission model (finish-args)
- Shared dependencies (libsecret)
- Base application behavior

### Testing Checklist
- [ ] Flatpak builds successfully
- [ ] Windsurf launches without errors
- [ ] File operations work correctly
- [ ] Extensions can be installed and load properly
- [ ] Terminal integration functions
- [ ] No permission regressions
- [ ] Settings and configuration persist correctly

### References
- VSCodium Flatpak: https://github.com/flathub/com.vscodium.codium
- Windsurf releases: https://windsurf-stable.codeium.com/api/update/linux-x64/stable/latest

---
*Generated by VSCodium update automation - manual review required*"""