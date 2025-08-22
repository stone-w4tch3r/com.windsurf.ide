"""Validation logic for Flatpak manifests and updates."""

import logging
import re
from typing import List, Dict, Any, Optional
import yaml
import jsonschema

from .exceptions import ValidationError


logger = logging.getLogger(__name__)


class FlatpakValidator:
    """Validates Flatpak manifests and updates."""
    
    # Basic Flatpak manifest schema
    MANIFEST_SCHEMA = {
        "type": "object",
        "required": ["app-id", "runtime", "runtime-version", "sdk", "command", "modules"],
        "properties": {
            "app-id": {"type": "string", "pattern": r"^[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+$"},
            "runtime": {"type": "string"},
            "runtime-version": {"type": "string"},
            "sdk": {"type": "string"},
            "base": {"type": "string"},
            "base-version": {"type": "string"},
            "command": {"type": "string"},
            "finish-args": {
                "type": "array",
                "items": {"type": "string"}
            },
            "modules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "buildsystem": {"type": "string"},
                        "sources": {
                            "type": "array",
                            "items": {"type": "object"}
                        }
                    }
                }
            }
        }
    }
    
    def __init__(self):
        """Initialize the validator."""
        pass
    
    def validate_manifest(self, manifest_content: str) -> List[str]:
        """Validate a Flatpak manifest.
        
        Args:
            manifest_content: YAML manifest content
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        try:
            # Parse YAML
            try:
                manifest_data = yaml.safe_load(manifest_content)
            except yaml.YAMLError as e:
                issues.append(f"Invalid YAML syntax: {e}")
                return issues
            
            # Schema validation
            try:
                jsonschema.validate(manifest_data, self.MANIFEST_SCHEMA)
            except jsonschema.ValidationError as e:
                issues.append(f"Schema validation error: {e.message}")
            
            # Custom validation rules
            issues.extend(self._validate_app_id(manifest_data))
            issues.extend(self._validate_modules(manifest_data))
            issues.extend(self._validate_sources(manifest_data))
            issues.extend(self._validate_finish_args(manifest_data))
            
        except Exception as e:
            issues.append(f"Validation error: {e}")
        
        return issues
    
    def validate_windsurf_manifest(self, manifest_content: str) -> List[str]:
        """Validate Windsurf-specific manifest requirements.
        
        Args:
            manifest_content: YAML manifest content
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = self.validate_manifest(manifest_content)
        
        try:
            manifest_data = yaml.safe_load(manifest_content)
            
            # Windsurf-specific validations
            if manifest_data.get("app-id") != "com.windsurf.ide":
                issues.append("App ID must be 'com.windsurf.ide'")
            
            if manifest_data.get("command") != "windsurf":
                issues.append("Command must be 'windsurf'")
            
            # Check for windsurf module
            modules = manifest_data.get("modules", [])
            windsurf_module = None
            for module in modules:
                if module.get("name") == "windsurf":
                    windsurf_module = module
                    break
            
            if not windsurf_module:
                issues.append("Missing 'windsurf' module")
            else:
                issues.extend(self._validate_windsurf_module(windsurf_module))
            
        except yaml.YAMLError:
            # Already handled in base validation
            pass
        
        return issues
    
    def validate_version_update(self, old_content: str, new_content: str) -> List[str]:
        """Validate a version update.
        
        Args:
            old_content: Original manifest content
            new_content: Updated manifest content
            
        Returns:
            List of validation issues
        """
        issues = []
        
        try:
            old_data = yaml.safe_load(old_content)
            new_data = yaml.safe_load(new_content)
            
            # Check that only version-related fields changed
            allowed_changes = {
                "modules.windsurf.sources.extra-data.url",
                "modules.windsurf.sources.extra-data.sha256", 
                "modules.windsurf.sources.extra-data.size"
            }
            
            changes = self._find_changes(old_data, new_data)
            
            for change_path in changes:
                if not any(change_path.startswith(allowed) for allowed in allowed_changes):
                    issues.append(f"Unexpected change in version update: {change_path}")
            
            # Validate new version is actually newer
            old_version = self._extract_version_from_url(old_data)
            new_version = self._extract_version_from_url(new_data)
            
            if old_version and new_version:
                if not self._is_version_newer(new_version, old_version):
                    issues.append(f"New version {new_version} is not newer than {old_version}")
            
        except Exception as e:
            issues.append(f"Version update validation error: {e}")
        
        return issues
    
    def _validate_app_id(self, manifest_data: dict) -> List[str]:
        """Validate app ID format."""
        issues = []
        app_id = manifest_data.get("app-id", "")
        
        if not re.match(r"^[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+$", app_id):
            issues.append(f"Invalid app-id format: {app_id}")
        
        return issues
    
    def _validate_modules(self, manifest_data: dict) -> List[str]:
        """Validate modules structure."""
        issues = []
        modules = manifest_data.get("modules", [])
        
        if not modules:
            issues.append("No modules defined")
            return issues
        
        module_names = set()
        for i, module in enumerate(modules):
            if not isinstance(module, dict):
                issues.append(f"Module {i} is not an object")
                continue
            
            name = module.get("name")
            if not name:
                issues.append(f"Module {i} missing name")
                continue
            
            if name in module_names:
                issues.append(f"Duplicate module name: {name}")
            module_names.add(name)
        
        return issues
    
    def _validate_sources(self, manifest_data: dict) -> List[str]:
        """Validate module sources."""
        issues = []
        modules = manifest_data.get("modules", [])
        
        for module in modules:
            if not isinstance(module, dict):
                continue
            
            sources = module.get("sources", [])
            if not sources:
                continue
            
            for i, source in enumerate(sources):
                if not isinstance(source, dict):
                    issues.append(f"Source {i} in module {module.get('name')} is not an object")
                    continue
                
                source_type = source.get("type")
                if not source_type:
                    issues.append(f"Source {i} in module {module.get('name')} missing type")
                    continue
                
                # Validate source based on type
                if source_type == "extra-data":
                    issues.extend(self._validate_extra_data_source(source, module.get("name")))
                elif source_type == "file":
                    issues.extend(self._validate_file_source(source, module.get("name")))
        
        return issues
    
    def _validate_extra_data_source(self, source: dict, module_name: str) -> List[str]:
        """Validate extra-data source."""
        issues = []
        
        required_fields = ["url", "sha256", "size"]
        for field in required_fields:
            if field not in source:
                issues.append(f"Extra-data source in module {module_name} missing {field}")
        
        # Validate URL format
        url = source.get("url", "")
        if url and not url.startswith(("http://", "https://")):
            issues.append(f"Invalid URL in extra-data source: {url}")
        
        # Validate SHA256 format
        sha256 = source.get("sha256", "")
        if sha256 and not re.match(r"^[a-f0-9]{64}$", sha256):
            issues.append(f"Invalid SHA256 format in extra-data source: {sha256}")
        
        # Validate size
        size = source.get("size")
        if size is not None and (not isinstance(size, int) or size <= 0):
            issues.append(f"Invalid size in extra-data source: {size}")
        
        return issues
    
    def _validate_file_source(self, source: dict, module_name: str) -> List[str]:
        """Validate file source."""
        issues = []
        
        if "path" not in source and "url" not in source:
            issues.append(f"File source in module {module_name} missing path or url")
        
        return issues
    
    def _validate_finish_args(self, manifest_data: dict) -> List[str]:
        """Validate finish-args."""
        issues = []
        finish_args = manifest_data.get("finish-args", [])
        
        for arg in finish_args:
            if not isinstance(arg, str):
                issues.append(f"Finish-arg is not a string: {arg}")
                continue
            
            if not arg.startswith("--"):
                issues.append(f"Finish-arg must start with '--': {arg}")
        
        return issues
    
    def _validate_windsurf_module(self, windsurf_module: dict) -> List[str]:
        """Validate Windsurf-specific module requirements."""
        issues = []
        
        # Check for required sources
        sources = windsurf_module.get("sources", [])
        has_extra_data = False
        has_windsurf_script = False
        
        for source in sources:
            if source.get("type") == "extra-data":
                has_extra_data = True
                # Validate Windsurf URL pattern
                url = source.get("url", "")
                if "windsurf" not in url.lower():
                    issues.append("Extra-data URL does not appear to be a Windsurf download")
            elif source.get("type") == "file" and source.get("path") == "windsurf.sh":
                has_windsurf_script = True
        
        if not has_extra_data:
            issues.append("Windsurf module missing extra-data source")
        
        if not has_windsurf_script:
            issues.append("Windsurf module missing windsurf.sh script")
        
        return issues
    
    def _find_changes(self, old_data: dict, new_data: dict, prefix: str = "") -> List[str]:
        """Find changes between two dictionaries."""
        changes = []
        
        # This is a simplified implementation
        # In practice, you'd want a more sophisticated diff algorithm
        
        def compare_values(old_val, new_val, path):
            if old_val != new_val:
                changes.append(path)
        
        # Compare at module level for simplicity
        old_modules = {m.get("name"): m for m in old_data.get("modules", [])}
        new_modules = {m.get("name"): m for m in new_data.get("modules", [])}
        
        for module_name in old_modules:
            if module_name in new_modules:
                old_sources = old_modules[module_name].get("sources", [])
                new_sources = new_modules[module_name].get("sources", [])
                
                for old_src, new_src in zip(old_sources, new_sources):
                    if old_src.get("type") == "extra-data":
                        for field in ["url", "sha256", "size"]:
                            if old_src.get(field) != new_src.get(field):
                                changes.append(f"modules.{module_name}.sources.extra-data.{field}")
        
        return changes
    
    def _extract_version_from_url(self, manifest_data: dict) -> Optional[str]:
        """Extract version from Windsurf URL."""
        modules = manifest_data.get("modules", [])
        for module in modules:
            if module.get("name") == "windsurf":
                sources = module.get("sources", [])
                for source in sources:
                    if source.get("type") == "extra-data":
                        url = source.get("url", "")
                        match = re.search(r"Windsurf-linux-x64-([0-9.]+)\.tar\.gz", url)
                        if match:
                            return match.group(1)
        return None
    
    def _is_version_newer(self, new_version: str, old_version: str) -> bool:
        """Check if new version is newer than old version."""
        try:
            # Simple version comparison (assumes semantic versioning)
            new_parts = [int(x) for x in new_version.split(".")]
            old_parts = [int(x) for x in old_version.split(".")]
            
            # Pad shorter version with zeros
            max_len = max(len(new_parts), len(old_parts))
            new_parts.extend([0] * (max_len - len(new_parts)))
            old_parts.extend([0] * (max_len - len(old_parts)))
            
            return new_parts > old_parts
        except ValueError:
            # If version parsing fails, assume it's newer
            return True