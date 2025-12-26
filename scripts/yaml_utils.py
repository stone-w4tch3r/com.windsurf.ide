"""YAML utility functions using ruamel.yaml for formatting preservation."""

import logging
from typing import Any, Dict
from io import StringIO

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

logger = logging.getLogger(__name__)


def load_yaml(content: str) -> Dict[str, Any]:
    """Load YAML content while preserving formatting.

    Args:
        content: Raw YAML string content

    Returns:
        Parsed YAML as dictionary

    Raises:
        ValueError: If YAML cannot be parsed
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.preserve_order = True

    try:
        return yaml.load(StringIO(content))
    except Exception as e:
        raise ValueError(f"Failed to parse YAML: {e}") from e


def dump_yaml(data: Dict[str, Any]) -> str:
    """Dump dictionary to YAML while preserving formatting.

    Args:
        data: Dictionary to dump

    Returns:
        YAML string with preserved formatting
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.preserve_order = True
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=2, offset=2)
    yaml.width = 100

    stream = StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


def safe_load_yaml(content: str) -> Dict[str, Any]:
    """Load YAML using standard pyyaml (for comparison/analysis).

    Args:
        content: Raw YAML string content

    Returns:
        Parsed YAML as dictionary
    """
    import yaml
    return yaml.safe_load(content)
