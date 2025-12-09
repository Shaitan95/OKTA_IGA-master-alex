"""Endpoint utilities bridging config JSON with static definitions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from okta_iga.endpoints import get_global_endpoints, get_resource_endpoints


@dataclass
class EndpointSpec:
    name: str
    definition: Dict
    kind: str  # "global" or "resource"

    @property
    def supports_pagination(self) -> bool:
        return bool(self.definition.get("supports_pagination", False))


class EndpointResolver:
    """Resolves enabled endpoints using the existing endpoint maps."""

    def __init__(self, endpoint_loader):
        self.endpoint_loader = endpoint_loader
        self.global_definitions = get_global_endpoints()
        self.resource_definitions = get_resource_endpoints()

    def enabled_global(self) -> List[EndpointSpec]:
        enabled = self.endpoint_loader.get_enabled_global_endpoints()
        return [
            EndpointSpec(name=name, definition=self.global_definitions[name], kind="global")
            for name in enabled
            if name in self.global_definitions
        ]

    def enabled_resource(self) -> List[EndpointSpec]:
        enabled = self.endpoint_loader.get_enabled_resource_endpoints()
        return [
            EndpointSpec(name=name, definition=self.resource_definitions[name], kind="resource")
            for name in enabled
            if name in self.resource_definitions
        ]

    def enabled_all(self) -> Iterable[EndpointSpec]:
        yield from self.enabled_global()
        yield from self.enabled_resource()
