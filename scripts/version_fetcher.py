"""Fetch version information for Windsurf and VSCodium."""

import hashlib
import logging
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .types import WindsurfVersionInfo, VSCodiumVersionInfo
from .exceptions import VersionFetchError, NetworkError


logger = logging.getLogger(__name__)


class VersionFetcher:
    """Fetches version information for Windsurf and VSCodium."""
    
    def __init__(self, timeout: int = 30, retries: int = 3):
        """Initialize the version fetcher.
        
        Args:
            timeout: Request timeout in seconds
            retries: Number of retry attempts
        """
        self.timeout = timeout
        self.session = requests.Session()
        
        # Configure retries
        retry_strategy = Retry(
            total=retries,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def fetch_windsurf_version(self) -> WindsurfVersionInfo:
        """Fetch the latest Windsurf version information.
        
        Returns:
            WindsurfVersionInfo with version details
            
        Raises:
            VersionFetchError: If version information cannot be fetched
        """
        try:
            logger.info("Fetching Windsurf version information")
            
            # Fetch version info from Windsurf API
            response = self.session.get(
                "https://windsurf-stable.codeium.com/api/update/linux-x64/stable/latest",
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract required fields
            version = data.get("windsurfVersion")
            url = data.get("url")
            
            if not version or not url:
                raise VersionFetchError("Missing version or URL in API response")
            
            logger.info(f"Found Windsurf version: {version}")
            
            # Fetch file size and compute SHA256
            file_info = self._fetch_file_info(url)
            
            return WindsurfVersionInfo(
                version=version,
                url=url,
                sha256=file_info["sha256"],
                size=file_info["size"],
                timestamp=data.get("publishedAt")
            )
            
        except requests.RequestException as e:
            raise VersionFetchError(f"Failed to fetch Windsurf version: {e}") from e
        except (KeyError, ValueError) as e:
            raise VersionFetchError(f"Invalid Windsurf API response: {e}") from e

    def fetch_vscodium_version(self) -> VSCodiumVersionInfo:
        """Fetch the latest VSCodium version information.
        
        Returns:
            VSCodiumVersionInfo with version details
            
        Raises:
            VersionFetchError: If version information cannot be fetched
        """
        try:
            logger.info("Fetching VSCodium version information")
            
            # Fetch latest release info from GitHub API
            response = self.session.get(
                "https://api.github.com/repos/VSCodium/vscodium/releases/latest",
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            version = data.get("tag_name")
            if not version:
                raise VersionFetchError("Missing tag_name in GitHub API response")
            
            logger.info(f"Found VSCodium version: {version}")
            
            # Find AMD64 and ARM64 .deb files
            assets = data.get("assets", [])
            
            amd64_asset = None
            arm64_asset = None
            
            for asset in assets:
                name = asset.get("name", "")
                if name.endswith("_amd64.deb") and "codium_" in name:
                    amd64_asset = asset
                elif name.endswith("_arm64.deb") and "codium_" in name:
                    arm64_asset = asset
            
            if not amd64_asset or not arm64_asset:
                raise VersionFetchError("Missing AMD64 or ARM64 .deb files in release")
            
            # Get download URLs
            amd64_url = amd64_asset.get("browser_download_url")
            arm64_url = arm64_asset.get("browser_download_url")
            
            if not amd64_url or not arm64_url:
                raise VersionFetchError("Missing download URLs for .deb files")
            
            # Compute SHA256 hashes (we'll need to download file headers)
            amd64_info = self._fetch_file_info(amd64_url)
            arm64_info = self._fetch_file_info(arm64_url)
            
            return VSCodiumVersionInfo(
                version=version,
                amd64_url=amd64_url,
                amd64_sha256=amd64_info["sha256"],
                arm64_url=arm64_url,
                arm64_sha256=arm64_info["sha256"],
                timestamp=data.get("published_at")
            )
            
        except requests.RequestException as e:
            raise VersionFetchError(f"Failed to fetch VSCodium version: {e}") from e
        except (KeyError, ValueError) as e:
            raise VersionFetchError(f"Invalid VSCodium API response: {e}") from e

    def _fetch_file_info(self, url: str) -> Dict[str, Any]:
        """Fetch file size and SHA256 hash for a URL.
        
        Args:
            url: URL to fetch file info for
            
        Returns:
            Dict with 'size' and 'sha256' keys
            
        Raises:
            NetworkError: If file info cannot be fetched
        """
        try:
            logger.debug(f"Fetching file info for {url}")
            
            # Get Content-Length header first
            head_response = self.session.head(url, timeout=self.timeout)
            head_response.raise_for_status()
            
            content_length = head_response.headers.get("Content-Length")
            if not content_length:
                raise NetworkError(f"No Content-Length header for {url}")
            
            size = int(content_length)
            
            # Download file to compute SHA256
            logger.debug(f"Downloading {url} to compute SHA256")
            response = self.session.get(url, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            sha256_hash = hashlib.sha256()
            downloaded_size = 0
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    sha256_hash.update(chunk)
                    downloaded_size += len(chunk)
            
            # Verify size matches
            if downloaded_size != size:
                raise NetworkError(
                    f"Downloaded size {downloaded_size} != expected size {size} for {url}"
                )
            
            return {
                "size": size,
                "sha256": sha256_hash.hexdigest()
            }
            
        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch file info for {url}: {e}") from e
        except ValueError as e:
            raise NetworkError(f"Invalid Content-Length for {url}: {e}") from e