#!/usr/bin/env python3
"""Generate GitHub Pages content for pre-signed Flatpak repository."""

import os
import sys
import shutil
import subprocess
import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SimpleFlatpakPagesPublisher:
    """Handles GitHub Pages content generation for pre-signed Flatpak repository."""
    
    def __init__(self, repo_path: str = "repo", output_path: str = "gh-pages-content"):
        """Initialize the publisher.
        
        Args:
            repo_path: Path to the pre-signed Flatpak repository
            output_path: Path where GitHub Pages content will be generated
        """
        self.repo_path = Path(repo_path)
        self.output_path = Path(output_path)
        self.gpg_public_key = os.getenv("FLATPAK_GPG_PUBLIC_KEY", "")
        
    def validate_repository(self) -> bool:
        """Validate that the repository exists and is properly structured.
        
        Returns:
            True if repository is valid, False otherwise
        """
        if not self.repo_path.exists():
            logger.error(f"Repository path {self.repo_path} does not exist")
            return False
            
        # Check if it's a valid OSTree repo
        config_path = self.repo_path / "config"
        if not config_path.exists():
            logger.error(f"No OSTree config found at {config_path}")
            return False
            
        # Check refs directory
        refs_path = self.repo_path / "refs"
        if not refs_path.exists():
            logger.error(f"No refs directory found at {refs_path}")
            return False
            
        # Check if we have refs
        try:
            result = subprocess.run(
                ["ostree", "refs", "--repo", str(self.repo_path)],
                capture_output=True, text=True, check=True
            )
            refs = result.stdout.strip()
            if not refs:
                logger.error("No refs found in repository")
                return False
            logger.info(f"Available refs: {refs}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list refs: {e.stderr}")
            return False
        
        return True
    
    def get_app_info(self) -> dict:
        """Extract application information from the repository.
        
        Returns:
            Dictionary with app name, version, and other metadata
        """
        try:
            # Get repository summary
            process = subprocess.run([
                "ostree", "summary", "--view",
                "--repo", str(self.repo_path)
            ], capture_output=True, text=True, check=True)
            
            summary_output = process.stdout
            
            # Extract app info from summary
            app_info = {
                "name": "com.windsurf.ide",
                "title": "Windsurf IDE", 
                "version": "latest",
                "runtime": "org.freedesktop.Sdk/x86_64/24.08"
            }
            
            # Try to extract version from extra data if available
            if "Windsurf-linux-x64-" in summary_output:
                import re
                version_match = re.search(r"Windsurf-linux-x64-([0-9.]+)\.tar\.gz", summary_output)
                if version_match:
                    app_info["version"] = version_match.group(1)
            
            return app_info
            
        except Exception as e:
            logger.warning(f"Failed to extract app info: {e}")
            return {
                "name": "com.windsurf.ide",
                "title": "Windsurf IDE",
                "version": "latest", 
                "runtime": "org.freedesktop.Sdk/x86_64/24.08"
            }
    
    def generate_flatpakref(self, base_url: str) -> str:
        """Generate .flatpakref file content.
        
        Args:
            base_url: Base URL for the GitHub Pages site
            
        Returns:
            .flatpakref file content as string
        """
        app_info = self.get_app_info()
        
        # Encode public key to base64 for embedding
        public_key_b64 = base64.b64encode(self.gpg_public_key.encode()).decode()
        
        flatpakref_content = f"""[Flatpak Ref]
Title={app_info['title']}
Name={app_info['name']}
Url={base_url}/repo/
RuntimeRepo=https://flathub.org/repo/flathub.flatpakrepo
SuggestRemoteName=windsurf-origin
GPGKey={public_key_b64}
IsRuntime=false
"""
        return flatpakref_content
    
    def generate_index_html(self, base_url: str) -> str:
        """Generate index.html with installation instructions.
        
        Args:
            base_url: Base URL for the GitHub Pages site
            
        Returns:
            HTML content as string
        """
        app_info = self.get_app_info()
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{app_info['title']} - Flatpak Repository</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
        .header {{ text-align: center; margin-bottom: 40px; }}
        .install-button {{ display: inline-block; background: #4CAF50; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 10px 0; }}
        .install-button:hover {{ background: #45a049; }}
        .code {{ background: #f4f4f4; padding: 15px; border-radius: 5px; font-family: monospace; margin: 10px 0; overflow-x: auto; }}
        .warning {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .info {{ background: #d1ecf1; border: 1px solid #bee5eb; padding: 15px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{app_info['title']}</h1>
        <p>Unofficial Flatpak build - Version {app_info['version']}</p>
    </div>

    <div class="warning">
        <strong>⚠️ Warning:</strong> This is an unofficial Flatpak build of Windsurf, automatically generated from official packages. Use at your own risk.
    </div>

    <h2>🚀 Quick Install</h2>
    <p>Install with a single command:</p>
    <div class="code">flatpak install --from {base_url}/{app_info['name']}.flatpakref</div>
    
    <a href="{app_info['name']}.flatpakref" class="install-button">📦 Install {app_info['title']}</a>

    <h2>📋 Manual Installation</h2>
    <p>If the one-click install doesn't work, you can manually add the repository:</p>
    <div class="code">
# Add the repository<br>
flatpak remote-add --if-not-exists windsurf-repo {base_url}/repo/<br><br>
# Install the application<br>
flatpak install windsurf-repo {app_info['name']}
    </div>

    <h2>🔧 Running</h2>
    <p>After installation, run {app_info['title']} with:</p>
    <div class="code">flatpak run {app_info['name']}</div>

    <h2>📝 About</h2>
    <p>This is an automatically updated Flatpak build of {app_info['title']}, packaged from the official releases. 
    The repository is signed with GPG for security.</p>
    
    <div class="info">
        <strong>Source:</strong> <a href="https://windsurf.codeium.com">Official Windsurf Website</a><br>
        <strong>Repository:</strong> <a href="https://github.com/stone-w4tch3r/com.windsurf.ide">GitHub</a><br>
        <strong>Runtime:</strong> {app_info['runtime']}
    </div>

    <p><small>Generated automatically by GitHub Actions</small></p>
</body>
</html>"""
        return html_content
    
    def generate_pages_content(self, base_url: str) -> bool:
        """Generate GitHub Pages content.
        
        Args:
            base_url: Base URL for the GitHub Pages site
            
        Returns:
            True if generation successful, False otherwise
        """
        try:
            # Create output directory
            self.output_path.mkdir(parents=True, exist_ok=True)
            
            # Copy the pre-signed repository
            repo_dest = self.output_path / "repo"
            if repo_dest.exists():
                shutil.rmtree(repo_dest)
            shutil.copytree(self.repo_path, repo_dest)
            
            # Generate .flatpakref file
            app_info = self.get_app_info()
            flatpakref_content = self.generate_flatpakref(base_url)
            flatpakref_path = self.output_path / f"{app_info['name']}.flatpakref"
            flatpakref_path.write_text(flatpakref_content)
            
            # Save GPG public key if available
            if self.gpg_public_key:
                gpg_key_path = self.output_path / "windsurf-gpg-key.asc"
                gpg_key_path.write_text(self.gpg_public_key)
            
            # Generate index.html
            html_content = self.generate_index_html(base_url)
            index_path = self.output_path / "index.html"
            index_path.write_text(html_content)
            
            # Create .nojekyll to disable Jekyll processing
            nojekyll_path = self.output_path / ".nojekyll"
            nojekyll_path.touch()
            
            logger.info(f"GitHub Pages content generated in {self.output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate Pages content: {e}")
            return False
    
    def publish(self, base_url: str) -> bool:
        """Complete publishing workflow: validate repository and generate Pages content.
        
        Args:
            base_url: Base URL for the GitHub Pages site
            
        Returns:
            True if publishing successful, False otherwise
        """
        logger.info("Starting Flatpak repository publishing...")
        
        # Validate repository
        if not self.validate_repository():
            return False
        
        # Generate Pages content
        if not self.generate_pages_content(base_url):
            return False
            
        logger.info("Publishing completed successfully!")
        return True


def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Get base URL from environment or use default
    base_url = os.getenv("GITHUB_PAGES_URL", "https://stone-w4tch3r.github.io/com.windsurf.ide")
    
    # Initialize publisher
    publisher = SimpleFlatpakPagesPublisher()
    
    # Run publishing workflow
    success = publisher.publish(base_url)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()