"""
Global endpoint definitions for Okta IGA API.
These endpoints are not resource-specific and can be called directly.
"""

from typing import Dict, Any


def get_global_endpoints() -> Dict[str, Any]:
    """Get global endpoints configuration."""
    return {
        # 1. Campaigns
        "campaigns": {
            "list": "/governance/api/v1/campaigns",
            "detail": "/governance/api/v1/campaigns/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after"],
            "filter_support": True
        },

        # 2. Reviews
        "reviews": {
            "list": "/governance/api/v1/reviews",
            "detail": "/governance/api/v1/reviews/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after", "orderBy"],
            "filter_support": True
        },

        # 3. Request Types
        "request_types": {
            "list": "/governance/api/v1/request-types",
            "detail": "/governance/api/v1/request-types/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after"],
            "filter_support": False
        },

        # 4. Requests (v1)
        "requests_v1": {
            "list": "/governance/api/v1/requests",
            "detail": "/governance/api/v1/requests/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after"],
            "filter_support": True
        },

        # 5. Requests (v2)
        "requests_v2": {
            "list": "/governance/api/v2/requests",
            "detail": "/governance/api/v2/requests/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after"],
            "filter_support": True
        },

        # 6. Request Settings (v2) - Global
        "request_settings_global": {
            "list": "/governance/api/v2/request-settings",
            "supports_pagination": False,
            "filter_support": False
        },

        # 7. Entitlement Bundles (global)
        "entitlement_bundles": {
            "list": "/governance/api/v1/entitlement-bundles",
            "detail": "/governance/api/v1/entitlement-bundles/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after"],
            "filter_support": False
        },

        # 8. Collections
        "collections": {
            "list": "/governance/api/v1/collections",
            "detail": "/governance/api/v1/collections/{id}",
            "resources": "/governance/api/v1/collections/{id}/resources",
            "supports_pagination": True,
            "pagination_params": ["limit", "after"],
            "filter_support": False
        },

        # 9. Risk Rules (Separation of Duties)
        "risk_rules": {
            "list": "/governance/api/v1/risk-rules",
            "detail": "/governance/api/v1/risk-rules/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after"],
            "filter_support": False
        },

        # 10. Delegates
        "delegates": {
            "list": "/governance/api/v1/delegates",
            "detail": "/governance/api/v1/delegates/{id}",
            "supports_pagination": True,
            "pagination_params": ["limit", "after"],
            "filter_support": False
        },

        # 11. My Settings - COMMENTED OUT
        # "my_settings": {
        #     "list": "/governance/api/v1/my/settings",
        #     "supports_pagination": False,
        #     "filter_support": False
        # },
    }