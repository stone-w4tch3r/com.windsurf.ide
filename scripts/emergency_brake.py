"""Pre-flight checks to prevent automation runaway."""

import logging
from typing import Optional
from datetime import datetime, timedelta
from .github_client import GitHubClient


logger = logging.getLogger(__name__)


class EmergencyBrake:
    """Pre-flight checks to prevent automation runaway."""

    def __init__(self, github_client: GitHubClient):
        """Initialize the emergency brake.

        Args:
            github_client: GitHub API client
        """
        self.github = github_client

    def check(self) -> tuple[bool, Optional[str]]:
        """Run all pre-flight checks.

        Returns:
            Tuple of (is_safe, reason). Returns (True, None) if safe to proceed,
            (False, reason) if should abort.

        Thresholds (independent per PR type):
        - Windsurf update PRs: >2
        - VSCodium update PRs: >2
        - Orphaned branches: >10 windsurf/vscodium branches

        Note: Each PR type has its own independent threshold. This allows
        both automation streams to operate concurrently without blocking each other.

        Workflow failure checking is not implemented due to GitHub API
        limitations. The brake relies on PR and orphaned branch counts as proxies
        for automation health.
        """
        # Check each PR type independently
        pr_counts = self._count_open_prs_by_type()

        if pr_counts["windsurf"] > 2:
            reason = f"Too many Windsurf update PRs ({pr_counts['windsurf']} > threshold of 2). Automation may be stalled."
            logger.warning(f"Emergency brake triggered: {reason}")
            return False, reason

        if pr_counts["vscodium"] > 2:
            reason = f"Too many VSCodium update PRs ({pr_counts['vscodium']} > threshold of 2). Automation may be stalled."
            logger.warning(f"Emergency brake triggered: {reason}")
            return False, reason

        # Check orphaned branches
        orphaned_branches = self._count_orphaned_branches()
        if orphaned_branches > 10:
            reason = f"Too many orphaned branches ({orphaned_branches} > threshold of 10). Manual cleanup may be needed."
            logger.warning(f"Emergency brake triggered: {reason}")
            return False, reason

        logger.info("Emergency brake check passed: safe to proceed")
        return True, None

    def _count_open_prs_by_type(self) -> dict[str, int]:
        """Count open automation-related pull requests by type.

        Only counts PRs created by the automation (with windsurf-update or
        vscodium-update labels) to avoid false positives from manual PRs.

        Returns:
            Dict with keys "windsurf" and "vscodium" containing respective counts
        """
        result = {"windsurf": 0, "vscodium": 0}

        try:
            url = f"https://api.github.com/repos/{self.github.owner}/{self.github.repo}/pulls"
            params = {"state": "open", "per_page": 100}
            response = self.github.session.get(url, params=params, timeout=self.github.timeout)
            response.raise_for_status()
            prs = response.json()

            for pr in prs:
                pr_labels = {label.get("name") for label in pr.get("labels", [])}

                if "windsurf-update" in pr_labels:
                    result["windsurf"] += 1
                if "vscodium-update" in pr_labels:
                    result["vscodium"] += 1

            return result
        except Exception as e:
            logger.error(f"Failed to count open PRs by type: {e}")
            # Assume safe if we can't check
            return result

    def _count_orphaned_branches(self) -> int:
        """Count orphaned windsurf/vscodium branches.

        Returns:
            Number of orphaned branches
        """
        try:
            url = f"https://api.github.com/repos/{self.github.owner}/{self.github.repo}/git/refs/heads"
            response = self.github.session.get(url, timeout=self.github.timeout)
            response.raise_for_status()
            refs = response.json()

            # Count branches matching windsurf or vscodium patterns
            count = 0
            for ref in refs:
                branch_name = ref.get("ref", "")
                if any(pattern in branch_name for pattern in ["update-windsurf", "vscodium-update"]):
                    count += 1

            return count
        except Exception as e:
            logger.error(f"Failed to count orphaned branches: {e}")
            # Assume safe if we can't check
            return 0
