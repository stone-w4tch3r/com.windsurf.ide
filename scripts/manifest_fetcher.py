"""Fetch VSCodium Flatpak manifest from the official repository."""

import logging
from typing import Dict, Any
import requests
import yaml

from .exceptions import ManifestFetchError, NetworkError


logger = logging.getLogger(__name__)


class ManifestFetcher:
    """Fetches VSCodium Flatpak manifest from GitHub."""
    
    def __init__(self, timeout: int = 30):
        """Initialize the manifest fetcher.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
    
    def fetch_vscodium_manifest(self) -> Dict[str, Any]:
        """Fetch the latest VSCodium Flatpak manifest.
        
        Returns:
            Parsed YAML manifest as dictionary
            
        Raises:
            ManifestFetchError: If manifest cannot be fetched or parsed
        """
        try:
            logger.info("Fetching VSCodium Flatpak manifest")
            
            # Fetch from flathub/com.vscodium.codium repository
            url = "https://raw.githubusercontent.com/flathub/com.vscodium.codium/master/com.vscodium.codium.yaml"
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse YAML
            try:
                manifest = yaml.safe_load(response.text)
                if not isinstance(manifest, dict):
                    raise ManifestFetchError("Manifest is not a valid YAML object")
                
                logger.info("Successfully fetched VSCodium manifest")
                return manifest
                
            except yaml.YAMLError as e:
                raise ManifestFetchError(f"Failed to parse YAML manifest: {e}") from e
            
        except requests.RequestException as e:
            raise ManifestFetchError(f"Failed to fetch VSCodium manifest: {e}") from e
    
    def fetch_vscodium_metainfo(self) -> str:
        """Fetch VSCodium metainfo.xml file.
        
        Returns:
            Raw metainfo.xml content
            
        Raises:
            ManifestFetchError: If metainfo cannot be fetched
        """
        try:
            logger.info("Fetching VSCodium metainfo.xml")
            
            url = "https://raw.githubusercontent.com/flathub/com.vscodium.codium/master/com.vscodium.codium.metainfo.xml"
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            logger.info("Successfully fetched VSCodium metainfo.xml")
            return response.text
            
        except requests.RequestException as e:
            raise ManifestFetchError(f"Failed to fetch VSCodium metainfo.xml: {e}") from e
    
    def fetch_file_content(self, url: str) -> str:
        """Fetch raw file content from a URL.
        
        Args:
            url: URL to fetch content from
            
        Returns:
            Raw file content as string
            
        Raises:
            NetworkError: If content cannot be fetched
        """
        try:
            logger.debug(f"Fetching file content from {url}")
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            return response.text
            
        except requests.RequestException as e:
            raise NetworkError(f"Failed to fetch content from {url}: {e}") from e