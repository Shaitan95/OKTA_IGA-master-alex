"""Resource blueprints for normalized parsing."""
from __future__ import annotations

from typing import Callable, Dict


ResourceDefinition = Dict[str, Callable]


def _safe_get(obj, path, default=""):
    current = obj
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part, default)
        else:
            return default
    return current


RESOURCE_DEFINITIONS: Dict[str, ResourceDefinition] = {
    "campaigns": {
        "external_id": lambda obj: obj.get("id", ""),
        "display_name": lambda obj: obj.get("name", obj.get("title", "")),
    },
    "reviews": {
        "external_id": lambda obj: obj.get("id", ""),
        "display_name": lambda obj: obj.get("name", obj.get("title", "")),
    },
    "grants": {
        "external_id": lambda obj: obj.get("id", ""),
        "display_name": lambda obj: f"{obj.get('principalName', '')} -> {obj.get('entitlementName', '')}".strip(),
    },
    "entitlements": {
        "external_id": lambda obj: obj.get("id", ""),
        "display_name": lambda obj: obj.get("name", obj.get("displayName", "")),
    },
    "collections": {
        "external_id": lambda obj: obj.get("id", ""),
        "display_name": lambda obj: obj.get("name", ""),
    },
    "request_conditions": {
        "external_id": lambda obj: obj.get("id", ""),
        "display_name": lambda obj: _safe_get(obj, "name", obj.get("title", "")),
    },
    "request_settings": {
        "external_id": lambda obj: obj.get("id", ""),
        "display_name": lambda obj: obj.get("name", obj.get("description", "")),
    },
    "request_sequences": {
        "external_id": lambda obj: obj.get("id", ""),
        "display_name": lambda obj: obj.get("name", ""),
    },
    "principal_entitlements": {
        "external_id": lambda obj: obj.get("id", ""),
        "display_name": lambda obj: obj.get("displayName", ""),
    },
    "principal_access": {
        "external_id": lambda obj: obj.get("id", ""),
        "display_name": lambda obj: obj.get("displayName", ""),
    },
}
