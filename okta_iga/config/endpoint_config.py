"""
Endpoint configuration loader for dynamic endpoint control.
"""

import json
import os
from typing import Dict, Any, Optional


class EndpointConfigLoader:
    """Loads and manages endpoint configuration from JSON files."""

    def __init__(self, config_file: str = "configs/endpoints.json"):
        self.config_file = config_file
        self._config: Optional[Dict[str, Any]] = None

    def load_config(self) -> Dict[str, Any]:
        """Load endpoint configuration from JSON file."""
        if self._config is not None:
            return self._config

        if not os.path.exists(self.config_file):
            print(f"[WARNING] Endpoint config file not found: {self.config_file}")
            print("[INFO] Using default configuration (all endpoints enabled)")
            return self._get_default_config()

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            print(f"[OK] Loaded endpoint configuration from: {self.config_file}")
            return self._config
        except Exception as e:
            print(f"[ERROR] Failed to load endpoint config: {e}")
            print("[INFO] Using default configuration (all endpoints enabled)")
            return self._get_default_config()

    def is_global_endpoint_enabled(self, endpoint_name: str) -> bool:
        """Check if a global endpoint is enabled."""
        config = self.load_config()
        global_endpoints = config.get("global_endpoints", {})
        endpoint_config = global_endpoints.get(endpoint_name, {})
        return endpoint_config.get("enabled", False)

    def is_resource_endpoint_enabled(self, endpoint_name: str) -> bool:
        """Check if a resource endpoint is enabled."""
        config = self.load_config()
        resource_endpoints = config.get("resource_endpoints", {})
        endpoint_config = resource_endpoints.get(endpoint_name, {})
        return endpoint_config.get("enabled", False)

    def get_enabled_global_endpoints(self) -> list:
        """Get list of enabled global endpoint names."""
        config = self.load_config()
        global_endpoints = config.get("global_endpoints", {})
        return [
            name for name, endpoint_config in global_endpoints.items()
            if endpoint_config.get("enabled", False)
        ]

    def get_enabled_resource_endpoints(self) -> list:
        """Get list of enabled resource endpoint names."""
        config = self.load_config()
        resource_endpoints = config.get("resource_endpoints", {})
        return [
            name for name, endpoint_config in resource_endpoints.items()
            if endpoint_config.get("enabled", False)
        ]

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration with all endpoints enabled."""
        return {
            "global_endpoints": {
                "campaigns": {"enabled": True},
                "reviews": {"enabled": True},
                "request_types": {"enabled": True},
                "requests_v1": {"enabled": True},
                "requests_v2": {"enabled": True},
                "request_settings_global": {"enabled": True},
                "entitlement_bundles": {"enabled": True},
                "collections": {"enabled": True},
                "risk_rules": {"enabled": True},
                "delegates": {"enabled": True}
            },
            "resource_endpoints": {
                "grants": {"enabled": True},
                "entitlements": {"enabled": True},
                "request_conditions": {"enabled": True},
                "request_settings": {"enabled": True},
                "request_sequences": {"enabled": True},
                "principal_entitlements": {"enabled": True},
                "principal_access": {"enabled": True}
            }
        }

    def get_config_summary(self) -> str:
        """Get a summary of the current configuration."""
        enabled_global = self.get_enabled_global_endpoints()
        enabled_resource = self.get_enabled_resource_endpoints()

        summary = f"Endpoint Configuration Summary:\n"
        summary += f"  Global endpoints enabled: {len(enabled_global)} ({', '.join(enabled_global)})\n"
        summary += f"  Resource endpoints enabled: {len(enabled_resource)} ({', '.join(enabled_resource)})"

        return summary