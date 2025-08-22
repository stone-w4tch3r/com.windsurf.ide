"""Main entry point for Windsurf Flatpak automation scripts."""

import argparse
import logging
import os
import sys
from typing import Optional

from .github_client import GitHubClient
from .windsurf_updater import WindsurfUpdater
from .vscodium_updater import VSCodiumUpdater
from .validator import FlatpakValidator
from .exceptions import WindsurfAutomationError


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def get_github_client() -> GitHubClient:
    """Create GitHub client from environment variables."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise WindsurfAutomationError("GITHUB_TOKEN environment variable required")
    owner = os.getenv("GITHUB_OWNER")
    if not owner:
        raise WindsurfAutomationError("GITHUB_OWNER environment variable required")
    repo = os.getenv("GITHUB_REPO")
    if not repo:
        raise WindsurfAutomationError("GITHUB_REPO environment variable required")
    
    return GitHubClient(token=token, owner=owner, repo=repo)


def cmd_check_windsurf(args) -> int:
    """Check for Windsurf version updates."""
    try:
        github = get_github_client()
        updater = WindsurfUpdater(github)
        
        pr_url = updater.check_and_update()
        
        if pr_url:
            print(f"✅ Created Windsurf update PR: {pr_url}")
            return 0
        else:
            print("ℹ️ Windsurf is already up to date")
            return 0
            
    except WindsurfAutomationError as e:
        print(f"❌ Windsurf update failed: {e}")
        return 1
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        return 1


def cmd_check_vscodium(args) -> int:
    """Check for VSCodium Flatpak updates."""
    try:
        github = get_github_client()
        updater = VSCodiumUpdater(github)
        
        pr_url = updater.check_and_update()
        
        if pr_url:
            print(f"✅ Created VSCodium update PR: {pr_url}")
            return 0
        else:
            print("ℹ️ Windsurf Flatpak is compatible with current VSCodium base")
            return 0
            
    except WindsurfAutomationError as e:
        print(f"❌ VSCodium update failed: {e}")
        return 1
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        return 1


def cmd_validate(args) -> int:
    """Validate Flatpak manifest."""
    try:
        validator = FlatpakValidator()
        
        with open(args.manifest, 'r') as f:
            content = f.read()
        
        if args.windsurf:
            issues = validator.validate_windsurf_manifest(content)
        else:
            issues = validator.validate_manifest(content)
        
        if issues:
            print("❌ Validation failed:")
            for issue in issues:
                print(f"  - {issue}")
            return 1
        else:
            print("✅ Manifest validation passed")
            return 0
            
    except Exception as e:
        print(f"💥 Validation error: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Windsurf Flatpak automation tools"
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Windsurf update command
    windsurf_parser = subparsers.add_parser(
        "check-windsurf",
        help="Check for Windsurf version updates"
    )
    windsurf_parser.set_defaults(func=cmd_check_windsurf)
    
    # VSCodium update command
    vscodium_parser = subparsers.add_parser(
        "check-vscodium",
        help="Check for VSCodium Flatpak updates"
    )
    vscodium_parser.set_defaults(func=cmd_check_vscodium)
    
    # Validation command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate Flatpak manifest"
    )
    validate_parser.add_argument(
        "manifest",
        help="Path to manifest file"
    )
    validate_parser.add_argument(
        "--windsurf",
        action="store_true",
        help="Use Windsurf-specific validation rules"
    )
    validate_parser.set_defaults(func=cmd_validate)
    
    args = parser.parse_args()
    
    setup_logging(args.debug)
    
    if not hasattr(args, 'func'):
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())