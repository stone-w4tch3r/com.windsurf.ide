"""Update Windsurf binary information in the Flatpak manifest."""

import logging
import re
from typing import Optional
import yaml

from .version_fetcher import VersionFetcher
from .github_client import GitHubClient
from .types import WindsurfVersionInfo
from .exceptions import ValidationError, ManifestTransformError


logger = logging.getLogger(__name__)


class WindsurfUpdater:
    """Updates Windsurf binary information in Flatpak manifest."""
    
    def __init__(self, github_client: GitHubClient):
        """Initialize the updater.
        
        Args:
            github_client: GitHub API client
        """
        self.github = github_client
        self.version_fetcher = VersionFetcher()
    
    def check_and_update(self) -> Optional[str]:
        """Check for Windsurf updates and create PR if needed.
        
        Returns:
            PR URL if update was created, None if no update needed
            
        Raises:
            ValidationError: If validation fails
            ManifestTransformError: If manifest transformation fails
        """
        try:
            # Fetch latest Windsurf version
            logger.info("Checking for Windsurf updates")
            windsurf_info = self.version_fetcher.fetch_windsurf_version()
            
            # Get current manifest
            current_manifest = self.github.get_file_content("com.windsurf.ide.yaml")
            if not current_manifest:
                raise ValidationError("Current manifest not found")
            
            # Parse current manifest
            manifest_data = yaml.safe_load(current_manifest)
            current_version = self._extract_current_version(manifest_data)
            
            logger.info(f"Current version: {current_version}, Latest version: {windsurf_info.version}")
            
            # Check if update is needed
            if current_version == windsurf_info.version:
                logger.info("Windsurf is already up to date")
                return None
            
            # Update manifest
            updated_manifest = self._update_manifest(manifest_data, windsurf_info)
            
            # Create branch and PR
            branch_name = f"update-windsurf-{windsurf_info.version}"
            commit_message = f"Update Windsurf to version {windsurf_info.version}"
            
            # Create branch
            self.github.create_branch(branch_name)
            
            # Get current file SHA
            manifest_sha = self.github.get_file_sha("com.windsurf.ide.yaml")
            
            # Update manifest file
            self.github.create_or_update_file(
                path="com.windsurf.ide.yaml",
                content=updated_manifest,
                message=commit_message,
                branch=branch_name,
                sha=manifest_sha
            )
            
            # Create PR
            pr_title = f"Update Windsurf to {windsurf_info.version}"
            pr_body = self._generate_pr_body(current_version, windsurf_info)
            
            pr = self.github.create_pull_request(
                title=pr_title,
                head=branch_name,
                body=pr_body,
                labels=["windsurf-update", "automated"]
            )
            
            # Enable auto-merge
            self.github.enable_auto_merge(pr["number"])
            
            logger.info(f"Created PR for Windsurf update: {pr['html_url']}")
            return pr["html_url"]
            
        except Exception as e:
            logger.error(f"Failed to update Windsurf: {e}")
            raise
    
    def _extract_current_version(self, manifest_data: dict) -> str:
        """Extract current Windsurf version from manifest.
        
        Args:
            manifest_data: Parsed manifest YAML
            
        Returns:
            Current version string
            
        Raises:
            ValidationError: If version cannot be extracted
        """
        try:
            # Look for windsurf module
            modules = manifest_data.get("modules", [])
            windsurf_module = None
            
            for module in modules:
                if module.get("name") == "windsurf":
                    windsurf_module = module
                    break
            
            if not windsurf_module:
                raise ValidationError("Windsurf module not found in manifest")
            
            # Find extra-data source
            sources = windsurf_module.get("sources", [])
            for source in sources:
                if source.get("type") == "extra-data":
                    url = source.get("url", "")
                    
                    # Extract version from URL
                    version_match = re.search(r"Windsurf-linux-x64-([0-9.]+)\.tar\.gz", url)
                    if version_match:
                        return version_match.group(1)
            
            raise ValidationError("Could not extract version from manifest")
            
        except (KeyError, TypeError) as e:
            raise ValidationError(f"Invalid manifest structure: {e}") from e
    
    def _update_manifest(self, manifest_data: dict, windsurf_info: WindsurfVersionInfo) -> str:
        """Update manifest with new Windsurf version.
        
        Args:
            manifest_data: Parsed manifest YAML
            windsurf_info: New Windsurf version information
            
        Returns:
            Updated manifest as YAML string
            
        Raises:
            ManifestTransformError: If update fails
        """
        try:
            # Find windsurf module
            modules = manifest_data.get("modules", [])
            windsurf_module = None
            
            for module in modules:
                if module.get("name") == "windsurf":
                    windsurf_module = module
                    break
            
            if not windsurf_module:
                raise ManifestTransformError("Windsurf module not found in manifest")
            
            # Update extra-data source
            sources = windsurf_module.get("sources", [])
            for source in sources:
                if source.get("type") == "extra-data":
                    source["url"] = windsurf_info.url
                    source["sha256"] = windsurf_info.sha256
                    source["size"] = windsurf_info.size
                    break
            else:
                raise ManifestTransformError("Extra-data source not found in windsurf module")
            
            # Convert back to YAML with proper formatting
            yaml_content = yaml.dump(
                manifest_data,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=100,
                indent=2
            )
            
            return yaml_content
            
        except Exception as e:
            raise ManifestTransformError(f"Failed to update manifest: {e}") from e
    
    def _generate_pr_body(self, current_version: str, windsurf_info: WindsurfVersionInfo) -> str:
        """Generate PR description.
        
        Args:
            current_version: Current version
            windsurf_info: New version information
            
        Returns:
            PR body markdown
        """
        return f"""## Windsurf Version Update

**Current Version:** `{current_version}`
**New Version:** `{windsurf_info.version}`

### Changes
- Updated Windsurf binary URL to: `{windsurf_info.url}`
- Updated SHA256: `{windsurf_info.sha256}`
- Updated file size: `{windsurf_info.size:,} bytes`

### Automation
This PR was created automatically by the Windsurf update bot.
- ✅ Auto-merge enabled on build success
- 🏗️ Flatpak build will be tested automatically
- 🔄 Will merge automatically if all checks pass

---
*Generated by Windsurf Flatpak automation*"""
