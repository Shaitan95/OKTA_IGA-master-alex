"""
Resource-specific endpoint definitions for Okta IGA API.
These endpoints require resourceId and are processed in Step 2 of the backup.
"""

from typing import Dict, Any


def get_resource_endpoints() -> Dict[str, Any]:
    """Get resource-specific endpoints configuration."""
    return {
        # 1. Grants (filter-based)
        "grants": {
            "list": "/governance/api/v1/grants",
            "detail": "/governance/api/v1/grants/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after", "filter"],
            "filter_support": True,
            "requires_filter": True,
            "filter_template": "target.externalId eq \"{resourceId}\" AND target.type eq \"APPLICATION\"",
            "list_only": True  # List endpoint returns 100% identical data as detail - skip detail calls
        },

        # 2. Entitlements (filter-based)
        "entitlements": {
            "list": "/governance/api/v1/entitlements",
            "detail": "/governance/api/v1/entitlements/{id}",
            "values_list": "/governance/api/v1/entitlements/{id}/values",
            "values_detail": "/governance/api/v1/entitlements/{id}/values/{value_id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after", "filter"],
            "filter_support": True,
            "requires_filter": True,
            "filter_template": "target.externalId eq \"{resourceId}\" AND target.type eq \"APPLICATION\""
        },

        # 3. Request Conditions (URL-based)
        "request_conditions": {
            "resource_list": "/governance/api/v2/resources/{resourceId}/request-conditions",
            "detail": "/governance/api/v2/request-conditions/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after"],
            "filter_support": False
        },

        # 4. Request Settings (URL-based)
        "request_settings": {
            "resource_list": "/governance/api/v2/resources/{resourceId}/request-settings",
            "supports_pagination": False,
            "filter_support": False
        },

        # 5. Request Sequences (URL-based)
        "request_sequences": {
            "resource_list": "/governance/api/v2/resources/{resourceId}/request-sequences",
            "detail": "/governance/api/v2/request-sequences/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after"],
            "filter_support": False,
            "list_only": True  # List endpoint returns 100% identical data as detail - skip detail calls
        },

        # 6. Principal Entitlements (filter-based)
        "principal_entitlements": {
            "list": "/governance/api/v1/principal-entitlements",
            "supports_pagination": True,
            "pagination_params": ["limit", "after", "filter"],
            "filter_support": True,
            "requires_filter": True,
            "filter_template": "resource.externalId eq \"{resourceId}\" AND resource.type eq \"APPLICATION\""
        },

        # 7. Principal Access (filter-based)
        "principal_access": {
            "list": "/governance/api/v1/principal-access",
            "supports_pagination": True,
            "pagination_params": ["limit", "after", "filter"],
            "filter_support": True,
            "requires_filter": True,
            "filter_template": "resource.externalId eq \"{resourceId}\" AND resource.type eq \"APPLICATION\""
        }
    }