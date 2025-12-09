"""High-level pipeline orchestration built on existing Okta IGA pieces."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from .api_client import ApiClient
from .config import PipelineSettings, load_pipeline_settings
from .endpoints import EndpointResolver, EndpointSpec
from .parser import Parser
from .sinks.file_sink import FileSink, LoggingSink

ApiClientFactory = Callable[[PipelineSettings], Any]


def _resource_ids_from(endpoint: str, items: Iterable[Dict[str, Any]]) -> Set[str]:
    collected: Set[str] = set()
    for item in items:
        if endpoint == "reviews":
            res_id = item.get("resourceId")
            if res_id:
                collected.add(res_id)
        elif endpoint == "campaigns":
            for target in item.get("resourceSettings", {}).get("targetResources", []):
                res_id = target.get("resourceId")
                if res_id:
                    collected.add(res_id)
    return collected


def _limit(items: List[Any], limit: int) -> List[Any]:
    if limit is None or limit < 0:
        return items
    return items[:limit]


def _default_client_factory(settings: PipelineSettings):
    return ApiClient(settings.tenant.base_url, settings.tenant.api_token, settings.config_loader)


async def _fetch_resource(
    client: ApiClient,
    spec: EndpointSpec,
    resource_id: Optional[str] = None,
    object_limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    definition = spec.definition
    path = definition.get("list")
    params: Dict[str, Any] = {}
    if resource_id:
        path = definition.get("resource_list", path)
        if path:
            path = path.format(resourceId=resource_id)
        if definition.get("filter_template"):
            params["filter"] = definition["filter_template"].format(resourceId=resource_id)
    supports_pagination = spec.supports_pagination
    pagination_params = definition.get("pagination_params", [])
    items = await client.fetch_paginated(path, supports_pagination, pagination_params, params)
    return _limit(items, object_limit if object_limit is not None else -1)


async def _run_pipeline_async(
    settings: PipelineSettings,
    output_mode: str = "file",
    api_client_factory: ApiClientFactory = _default_client_factory,
    backup_root_override: Optional[str] = None,
) -> Dict[str, Any]:
    parser = Parser()
    resolver = EndpointResolver(settings.endpoint_loader)

    sink = LoggingSink() if output_mode == "log" else FileSink(
        backup_root_override or settings.backup_root,
        settings.environment,
        settings.tenant.tenant_id,
        settings.tenant.customer_id,
    )

    object_limit = settings.config_loader.get(
        "backup.modes.test.objects_per_endpoint" if settings.test_mode else "backup.modes.full.objects_per_endpoint",
        -1,
    )
    resources_per_context = settings.config_loader.get(
        "backup.modes.test.resources_per_context" if settings.test_mode else "backup.modes.full.resources_per_context",
        -1,
    )

    summary: Dict[str, Any] = {"written": {}, "resource_ids": set()}

    async with api_client_factory(settings) as client:
        # Global endpoints
        for spec in resolver.enabled_global():
            try:
                items = await _fetch_resource(client, spec, object_limit=object_limit)
                parsed = parser.parse_many(spec.name, items)
                sink.write(spec.name, parsed)
                summary["written"][spec.name] = len(parsed)
                summary["resource_ids"].update(_resource_ids_from(spec.name, items))
            except Exception as exc:  # pragma: no cover - defensive
                summary["written"][spec.name] = f"error: {exc}" if exc else "error"

        # Resource endpoints
        resource_ids = list(summary["resource_ids"])
        if resources_per_context and resources_per_context > 0:
            resource_ids = resource_ids[:resources_per_context]

        for spec in resolver.enabled_resource():
            if definition := spec.definition:
                if definition.get("requires_filter", False) and not resource_ids:
                    summary["written"][spec.name] = 0
                    continue
            aggregated: List[Dict[str, Any]] = []
            targets = resource_ids or [None]
            for rid in targets:
                try:
                    items = await _fetch_resource(client, spec, resource_id=rid, object_limit=object_limit)
                    aggregated.extend(items)
                except Exception as exc:  # pragma: no cover - defensive
                    summary["written"][spec.name] = f"error: {exc}" if exc else "error"
            parsed = parser.parse_many(spec.name, aggregated)
            sink.write(spec.name, parsed)
            summary["written"][spec.name] = len(parsed)

    return summary


def run_pipeline(
    output_mode: str = "file",
    endpoints_file: str = "configs/endpoints_test.json",
    tenant_id: int = 1,
    config_file: str = "configs/config.json",
    credentials_file: str = "configs/credential.json",
    test_mode: Optional[bool] = None,
    api_client_factory: ApiClientFactory = _default_client_factory,
    backup_root_override: Optional[str] = None,
) -> Dict[str, Any]:
    settings = load_pipeline_settings(
        tenant_id=tenant_id,
        config_file=config_file,
        endpoints_file=endpoints_file,
        credentials_file=credentials_file,
        test_mode=test_mode,
    )
    return asyncio.run(
        _run_pipeline_async(
            settings,
            output_mode=output_mode,
            api_client_factory=api_client_factory,
            backup_root_override=backup_root_override,
        )
    )
