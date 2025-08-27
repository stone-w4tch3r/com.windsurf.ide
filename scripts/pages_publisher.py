#!/usr/bin/env python3
"""Generate and sign GitHub Pages content for Flatpak repository."""

import os
import sys
import shutil
import subprocess
import tempfile
import base64
import logging
from pathlib import Path
from typing import Optional
import yaml

logger = logging.getLogger(__name__)


class FlatpakPagesPublisher:
    """Handles GPG signing and GitHub Pages content generation for Flatpak repository."""
    
    def __init__(self, repo_path: str = "repo", output_path: str = "gh-pages-content"):
        """Initialize the publisher.
        
        Args:
            repo_path: Path to the built Flatpak repository
            output_path: Path where GitHub Pages content will be generated
        """
        self.repo_path = Path(repo_path)
        self.output_path = Path(output_path)
        self.gpg_key_id = None
        self.gpg_public_key = None
        self.gpg_setup_done = False
        
    def setup_gpg(self) -> bool:
        """Set up GPG key from environment variables.
        
        Returns:
            True if GPG setup successful, False otherwise
        """
        try:
            # Get GPG configuration from environment
            private_key_b64 = os.getenv("FLATPAK_GPG_PRIVATE_KEY")
            passphrase = os.getenv("FLATPAK_GPG_PASSPHRASE")
            key_id = os.getenv("FLATPAK_GPG_KEY_ID")
            public_key = os.getenv("FLATPAK_GPG_PUBLIC_KEY")
            
            if not all([private_key_b64, passphrase, key_id, public_key]):
                logger.error("Missing required GPG environment variables")
                return False
                
            self.gpg_key_id = key_id
            self.gpg_public_key = public_key
            
            # Decode and import private key
            private_key = base64.b64decode(private_key_b64).decode('utf-8')
            
            # Create GPG config for batch operations
            gpg_conf = os.path.expanduser("~/.gnupg/gpg.conf")
            os.makedirs(os.path.dirname(gpg_conf), exist_ok=True)
            with open(gpg_conf, 'w') as f:
                f.write("batch\n")
                f.write("yes\n")
                f.write("pinentry-mode loopback\n")
                f.write(f"passphrase {passphrase}\n")
            
            # Set permissions
            os.chmod(gpg_conf, 0o600)
            os.chmod(os.path.dirname(gpg_conf), 0o700)
            
            # Import the private key
            process = subprocess.run(
                ["gpg", "--batch", "--import"],
                input=private_key,
                text=True,
                capture_output=True
            )
            
            if process.returncode != 0:
                logger.error(f"Failed to import GPG key: {process.stderr}")
                return False
                
            # Trust the key
            trust_input = f"{key_id}:6:\n"
            process = subprocess.run(
                ["gpg", "--batch", "--import-ownertrust"],
                input=trust_input,
                text=True,
                capture_output=True
            )
            
            if process.returncode != 0:
                logger.warning(f"Failed to set key trust: {process.stderr}")
            
            # Verify key is available
            process = subprocess.run(
                ["gpg", "--list-secret-keys", "--keyid-format", "LONG"],
                capture_output=True,
                text=True
            )
            
            if key_id not in process.stdout:
                logger.error(f"GPG key {key_id} not found after import")
                return False
                
            logger.info(f"GPG key {key_id} successfully imported and configured")
            self.gpg_setup_done = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup GPG: {e}")
            return False
    
    def sign_repository(self) -> bool:
        """Sign the Flatpak repository.
        
        Returns:
            True if signing successful, False otherwise
        """
        if not self.gpg_setup_done:
            logger.error("GPG not set up, cannot sign repository")
            return False
            
        if not self.repo_path.exists():
            logger.error(f"Repository path {self.repo_path} does not exist")
            return False
            
        try:
            # Debug repository structure before signing
            logger.info(f"Debugging repository structure at {self.repo_path}")
            
            # Check if it's a valid OSTree repo
            config_path = self.repo_path / "config"
            if not config_path.exists():
                logger.error(f"No OSTree config found at {config_path}")
                return False
                
            # List repository contents
            logger.info("Repository directory contents:")
            for item in self.repo_path.iterdir():
                logger.info(f"  {item.name}")
                
            # Check refs directory
            refs_path = self.repo_path / "refs"
            if not refs_path.exists():
                logger.error(f"No refs directory found at {refs_path}")
                return False
                
            # Ensure refs/remotes exists (required by OSTree)
            refs_remotes_path = refs_path / "remotes"
            if not refs_remotes_path.exists():
                logger.info("Creating missing refs/remotes directory")
                refs_remotes_path.mkdir(parents=True, exist_ok=True)
                
            # Try basic ostree commands first
            logger.info("Testing basic OSTree commands...")
            try:
                result = subprocess.run(
                    ["ostree", "refs", "--repo", str(self.repo_path)],
                    capture_output=True, text=True, check=True
                )
                logger.info(f"Available refs: {result.stdout.strip()}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to list refs: {e.stderr}")
                return False
            
            # Update and sign repository summary
            passphrase = os.getenv("FLATPAK_GPG_PASSPHRASE")
            
            cmd = [
                "ostree", "summary", "--update", 
                "--repo", str(self.repo_path),
                f"--gpg-sign={self.gpg_key_id}",
                "--gpg-homedir", os.path.expanduser("~/.gnupg")
            ]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            
            # Set up GPG environment for signing
            env = {
                **os.environ,
                "GPG_TTY": "",
                "GNUPGHOME": os.path.expanduser("~/.gnupg")
            }
            
            # Use GPG agent with pinentry loopback for automated signing
            process = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )
            
            if process.returncode != 0:
                logger.error(f"Failed to sign repository: {process.stderr}")
                return False
                
            # Generate static deltas for better performance
            try:
                subprocess.run([
                    "ostree", "static-delta", "generate", 
                    "--repo", str(self.repo_path),
                    "--min-fallback-size", "0"
                ], check=True, capture_output=True)
                logger.info("Generated static deltas")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to generate static deltas: {e}")
            
            logger.info("Repository successfully signed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sign repository: {e}")
            return False
    
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
    <p>If you prefer manual steps:</p>
    
    <h3>1. Add the repository</h3>
    <div class="code">flatpak remote-add --user windsurf-repo {base_url}/repo/ --gpg-import=windsurf-gpg-key.asc</div>
    
    <h3>2. Install the application</h3>
    <div class="code">flatpak install --user windsurf-repo {app_info['name']}</div>
    
    <h3>3. Run the application</h3>
    <div class="code">flatpak run {app_info['name']}</div>

    <h2>🔐 GPG Verification</h2>
    <p>This repository is signed with GPG for security. The public key is available here:</p>
    <div class="code"><a href="windsurf-gpg-key.asc">windsurf-gpg-key.asc</a></div>

    <div class="info">
        <strong>ℹ️ Note:</strong> This Flatpak version has limitations compared to native packages. 
        See the <a href="https://github.com/stone-w4tch3r/com.windsurf.ide">repository README</a> for details.
    </div>

    <h2>🆘 Support</h2>
    <p>For issues specific to this Flatpak build, please visit the 
    <a href="https://github.com/stone-w4tch3r/com.windsurf.ide/issues">GitHub repository</a>.</p>
    
    <hr>
    <footer>
        <p><small>Generated automatically by Windsurf Flatpak automation • Repository signed with GPG</small></p>
    </footer>
</body>
</html>"""
        return html_content
    
    def generate_pages_content(self, base_url: str) -> bool:
        """Generate all GitHub Pages content.
        
        Args:
            base_url: Base URL for the GitHub Pages site
            
        Returns:
            True if generation successful, False otherwise
        """
        try:
            # Create output directory
            self.output_path.mkdir(parents=True, exist_ok=True)
            
            # Copy signed repository
            repo_dest = self.output_path / "repo"
            if repo_dest.exists():
                shutil.rmtree(repo_dest)
            shutil.copytree(self.repo_path, repo_dest)
            
            # Generate .flatpakref file
            app_info = self.get_app_info()
            flatpakref_content = self.generate_flatpakref(base_url)
            flatpakref_path = self.output_path / f"{app_info['name']}.flatpakref"
            flatpakref_path.write_text(flatpakref_content)
            
            # Save GPG public key
            gpg_key_path = self.output_path / "windsurf-gpg-key.asc"
            gpg_key_path.write_text(self.gpg_public_key)
            
            # Generate index.html
            html_content = self.generate_index_html(base_url)
            index_path = self.output_path / "index.html"
            index_path.write_text(html_content)
            
            # Create .nojekyll to disable Jekyll processing
            nojekyll_path = self.output_path / ".nojekyll"
            nojekyll_path.touch()
            
            # Create CNAME file if custom domain is needed (commented out)
            # cname_path = self.output_path / "CNAME"
            # cname_path.write_text("your-domain.com")
            
            logger.info(f"GitHub Pages content generated in {self.output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate Pages content: {e}")
            return False
    
    def publish(self, base_url: str) -> bool:
        """Complete publishing workflow: sign repository and generate Pages content.
        
        Args:
            base_url: Base URL for the GitHub Pages site
            
        Returns:
            True if publishing successful, False otherwise
        """
        logger.info("Starting Flatpak repository publishing...")
        
        # Setup GPG
        if not self.setup_gpg():
            return False
            
        # Sign repository
        if not self.sign_repository():
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
    publisher = FlatpakPagesPublisher()
    
    # Run publishing workflow
    success = publisher.publish(base_url)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()