"""GitHub API client for creating and managing pull requests."""

import logging
from typing import Optional, Dict, Any, List
import requests
import base64
import json

from .exceptions import NetworkError, ValidationError


logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API client for repository operations."""
    
    def __init__(self, token: str, owner: str, repo: str, timeout: int = 30):
        """Initialize GitHub client.
        
        Args:
            token: GitHub personal access token
            owner: Repository owner/organization
            repo: Repository name
            timeout: Request timeout in seconds
        """
        self.token = token
        self.owner = owner
        self.repo = repo
        self.timeout = timeout
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "windsurf-flatpak-automation"
        })
    
    def get_file_content(self, path: str, ref: str = "master") -> Optional[str]:
        """Get file content from repository.
        
        Args:
            path: File path in repository
            ref: Git reference (branch/commit)
            
        Returns:
            File content as string, or None if file doesn't exist
            
        Raises:
            NetworkError: If API request fails
        """
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{path}"
            response = self.session.get(url, params={"ref": ref}, timeout=self.timeout)
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("type") != "file":
                raise ValidationError(f"Path {path} is not a file")
            
            # Decode base64 content
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content
            
        except requests.RequestException as e:
            raise NetworkError(f"Failed to get file {path}: {e}") from e
    
    def create_or_update_file(self, path: str, content: str, message: str, 
                            branch: str, sha: Optional[str] = None) -> Dict[str, Any]:
        """Create or update a file in repository.
        
        Args:
            path: File path in repository
            content: New file content
            message: Commit message
            branch: Target branch
            sha: Current file SHA (for updates)
            
        Returns:
            API response data
            
        Raises:
            NetworkError: If API request fails
        """
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{path}"
            
            data = {
                "message": message,
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": branch
            }
            
            if sha:
                data["sha"] = sha
            
            response = self.session.put(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise NetworkError(f"Failed to update file {path}: {e}") from e
    
    def create_branch(self, branch_name: str, base_branch: str = "master") -> Dict[str, Any]:
        """Create a new branch.
        
        Args:
            branch_name: Name of new branch
            base_branch: Base branch to create from
            
        Returns:
            API response data
            
        Raises:
            NetworkError: If API request fails
        """
        try:
            # Get base branch SHA
            base_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/git/ref/heads/{base_branch}"
            base_response = self.session.get(base_url, timeout=self.timeout)
            base_response.raise_for_status()
            base_sha = base_response.json()["object"]["sha"]
            
            # Create new branch
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/git/refs"
            data = {
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha
            }
            
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise NetworkError(f"Failed to create branch {branch_name}: {e}") from e
    
    def create_pull_request(self, title: str, head: str, base: str = "master", 
                          body: Optional[str] = None, labels: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a pull request.
        
        Args:
            title: PR title
            head: Head branch
            base: Base branch
            body: PR description
            labels: List of label names
            
        Returns:
            API response data
            
        Raises:
            NetworkError: If API request fails
        """
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls"
            
            data = {
                "title": title,
                "head": head,
                "base": base
            }
            
            if body:
                data["body"] = body
            
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            
            pr_data = response.json()
            
            # Add labels if specified
            if labels:
                self.add_labels_to_pr(pr_data["number"], labels)
            
            return pr_data
            
        except requests.RequestException as e:
            raise NetworkError(f"Failed to create pull request: {e}") from e
    
    def add_labels_to_pr(self, pr_number: int, labels: List[str]) -> None:
        """Add labels to a pull request.
        
        Args:
            pr_number: PR number
            labels: List of label names
            
        Raises:
            NetworkError: If API request fails
        """
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{pr_number}/labels"
            
            response = self.session.post(url, json={"labels": labels}, timeout=self.timeout)
            response.raise_for_status()
            
        except requests.RequestException as e:
            raise NetworkError(f"Failed to add labels to PR {pr_number}: {e}") from e
    
    def enable_auto_merge(self, pr_number: int, merge_method: str = "squash") -> Dict[str, Any]:
        """Enable auto-merge for a pull request.
        
        Args:
            pr_number: PR number
            merge_method: Merge method (merge, squash, rebase)
            
        Returns:
            API response data
            
        Raises:
            NetworkError: If API request fails
        """
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{pr_number}/merge"
            
            data = {"merge_method": merge_method}
            
            # Use GraphQL for auto-merge (REST API doesn't support it yet)
            graphql_url = "https://api.github.com/graphql"
            query = """
            mutation EnableAutoMerge($pullRequestId: ID!, $mergeMethod: PullRequestMergeMethod!) {
                enablePullRequestAutoMerge(input: {
                    pullRequestId: $pullRequestId,
                    mergeMethod: $mergeMethod
                }) {
                    pullRequest {
                        id
                        autoMergeRequest {
                            enabledAt
                        }
                    }
                }
            }
            """
            
            # First get PR ID
            pr_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{pr_number}"
            pr_response = self.session.get(pr_url, timeout=self.timeout)
            pr_response.raise_for_status()
            pr_id = pr_response.json()["node_id"]
            
            variables = {
                "pullRequestId": pr_id,
                "mergeMethod": merge_method.upper()
            }
            
            response = self.session.post(
                graphql_url,
                json={"query": query, "variables": variables},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise NetworkError(f"Failed to enable auto-merge for PR {pr_number}: {e}") from e
    
    def get_file_sha(self, path: str, ref: str = "master") -> Optional[str]:
        """Get the SHA of a file.
        
        Args:
            path: File path in repository
            ref: Git reference
            
        Returns:
            File SHA or None if file doesn't exist
            
        Raises:
            NetworkError: If API request fails
        """
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{path}"
            response = self.session.get(url, params={"ref": ref}, timeout=self.timeout)
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            return response.json()["sha"]
            
        except requests.RequestException as e:
            raise NetworkError(f"Failed to get SHA for {path}: {e}") from e
    
    def enable_repository_auto_merge(self) -> bool:
        """Enable auto-merge feature on the repository.
        
        Returns:
            True if auto-merge was enabled or already enabled, False if failed
            
        Raises:
            NetworkError: If API request fails
        """
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
            
            # First check if auto-merge is already enabled
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            current_settings = response.json()
            if current_settings.get("allow_auto_merge", False):
                logger.info("Repository auto-merge already enabled")
                return True
            
            # Enable auto-merge
            logger.info("Enabling repository auto-merge feature")
            data = {"allow_auto_merge": True}
            
            response = self.session.patch(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            
            logger.info("Repository auto-merge enabled successfully")
            return True
            
        except requests.RequestException as e:
            logger.warning(f"Failed to enable repository auto-merge: {e}")
            return False