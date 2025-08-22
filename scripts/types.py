"""Type definitions for the Windsurf Flatpak automation."""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass


@dataclass
class WindsurfVersionInfo:
    """Information about a Windsurf version."""
    version: str
    url: str
    sha256: str
    size: int
    timestamp: Optional[str] = None


@dataclass
class VSCodiumVersionInfo:
    """Information about a VSCodium version."""
    version: str
    amd64_url: str
    amd64_sha256: str
    arm64_url: str
    arm64_sha256: str
    timestamp: Optional[str] = None


@dataclass
class FlatpakSource:
    """A Flatpak source definition."""
    type: str
    url: Optional[str] = None
    sha256: Optional[str] = None
    size: Optional[int] = None
    path: Optional[str] = None
    dest_filename: Optional[str] = None
    only_arches: Optional[List[str]] = None
    x_checker_data: Optional[Dict[str, Any]] = None
    commands: Optional[List[str]] = None
    filename: Optional[str] = None


@dataclass
class FlatpakModule:
    """A Flatpak module definition."""
    name: str
    buildsystem: Optional[str] = None
    build_commands: Optional[List[str]] = None
    config_opts: Optional[List[str]] = None
    sources: Optional[List[FlatpakSource]] = None
    cleanup: Optional[List[str]] = None
    post_install: Optional[List[str]] = None
    subdir: Optional[str] = None


@dataclass
class FlatpakManifest:
    """A complete Flatpak manifest."""
    app_id: str
    runtime: str
    runtime_version: str
    sdk: str
    base: str
    base_version: str
    command: str
    finish_args: List[str]
    modules: List[FlatpakModule]
    separate_locales: bool = False
    cleanup: Optional[List[str]] = None
    add_extensions: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


# Type aliases
JSONDict = Dict[str, Any]
FlatpakYAML = Dict[str, Any]