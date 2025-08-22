"""Custom exceptions for the Windsurf Flatpak automation."""


class WindsurfAutomationError(Exception):
    """Base exception for Windsurf automation errors."""
    pass


class VersionFetchError(WindsurfAutomationError):
    """Error fetching version information."""
    pass


class ManifestFetchError(WindsurfAutomationError):
    """Error fetching Flatpak manifest."""
    pass


class ManifestTransformError(WindsurfAutomationError):
    """Error transforming manifest."""
    pass


class ValidationError(WindsurfAutomationError):
    """Error during validation."""
    pass


class FileOperationError(WindsurfAutomationError):
    """Error during file operations."""
    pass


class NetworkError(WindsurfAutomationError):
    """Network-related error."""
    pass