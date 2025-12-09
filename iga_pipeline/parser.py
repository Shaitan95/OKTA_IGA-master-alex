"""Parser to normalize raw API payloads."""
from __future__ import annotations

from typing import Dict, List

from .resources import RESOURCE_DEFINITIONS


class Parser:
    def __init__(self):
        self.definitions = RESOURCE_DEFINITIONS

    def parse_object(self, resource: str, raw: Dict) -> Dict:
        definition = self.definitions.get(resource, {})
        external_fn = definition.get("external_id", lambda obj: obj.get("id", ""))
        display_fn = definition.get("display_name", lambda obj: obj.get("name", ""))
        return {
            "object_type": resource,
            "external_id": external_fn(raw),
            "display_name": display_fn(raw),
            "data": raw,
        }

    def parse_many(self, resource: str, payload: List[Dict]) -> List[Dict]:
        return [self.parse_object(resource, item) for item in payload]
