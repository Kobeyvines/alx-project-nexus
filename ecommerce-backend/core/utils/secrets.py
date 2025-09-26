"""Utility functions for managing secrets and environment variables."""
import os
from typing import Any, Optional
from django.core.exceptions import ImproperlyConfigured


def get_secret(key: str, default: Optional[Any] = None, required: bool = True) -> Any:
    """
    Get a secret from environment variables.
    
    Args:
        key: The name of the environment variable
        default: Default value if not found
        required: Whether the variable is required
        
    Returns:
        The value of the environment variable
        
    Raises:
        ImproperlyConfigured: If the variable is required but not found
    """
    value = os.getenv(key, default)
    if value is None and required:
        raise ImproperlyConfigured(f"Secret key '{key}' is required but not set")
    return value


def get_bool_secret(key: str, default: bool = False) -> bool:
    """Get a boolean secret from environment variables."""
    return str(get_secret(key, default, required=False)).lower() == 'true'


def get_int_secret(key: str, default: Optional[int] = None) -> Optional[int]:
    """Get an integer secret from environment variables."""
    value = get_secret(key, default, required=False)
    try:
        return int(value) if value is not None else None
    except ValueError:
        raise ImproperlyConfigured(f"Secret key '{key}' must be an integer")


def get_list_secret(key: str, default: Optional[list] = None, separator: str = ',') -> list:
    """Get a list secret from environment variables."""
    value = get_secret(key, default, required=False)
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [item.strip() for item in value.split(separator) if item.strip()]