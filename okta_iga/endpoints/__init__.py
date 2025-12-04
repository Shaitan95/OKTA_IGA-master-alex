"""
Endpoint definitions for Okta IGA API.
"""

from .global_endpoints import get_global_endpoints
from .resource_endpoints import get_resource_endpoints

__all__ = ["get_global_endpoints", "get_resource_endpoints"]