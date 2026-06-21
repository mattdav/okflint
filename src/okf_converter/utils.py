"""Utility functions shared across the application.

Examples:
    >>> from okf_converter.utils import get_package_dir
    >>> path = get_package_dir("config")
    >>> path.is_dir()
    True
"""

import importlib.resources
from pathlib import Path


def get_package_dir(subpackage: str) -> Path:
    """Return the absolute path of a subpackage directory.

    Uses importlib.resources.files (Python 3.11+) to resolve paths
    within the installed package, whether it runs from source or
    from a wheel.

    Args:
        subpackage: Name of the subpackage (e.g. "config", "data", "log").

    Returns:
        Absolute Path to the subpackage directory.

    Raises:
        ModuleNotFoundError: If the subpackage does not exist.

    Examples:
        >>> p = get_package_dir("config")
        >>> p.name
        'config'
    """
    package_name = __name__.split(".")[0]
    ref = importlib.resources.files(f"{package_name}.{subpackage}")
    return Path(str(ref))
