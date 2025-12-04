"""
Configuration management for Okta IGA system.
"""

from .endpoint_config import EndpointConfigLoader
from .config_loader import ConfigLoader

__all__ = ["EndpointConfigLoader", "ConfigLoader"]