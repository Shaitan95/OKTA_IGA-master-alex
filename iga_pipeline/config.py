"""Configuration helpers for the lightweight pipeline."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from okta_iga.config import ConfigLoader, EndpointConfigLoader


@dataclass
class TenantConfig:
    tenant_id: int
    customer_id: str
    okta_domain: str
    api_token: str

    @property
    def base_url(self) -> str:
        if self.okta_domain.startswith(("http://", "https://")):
            return self.okta_domain
        return f"https://{self.okta_domain}"


@dataclass
class PipelineSettings:
    config_loader: ConfigLoader
    endpoint_loader: EndpointConfigLoader
    tenant: TenantConfig
    test_mode: bool
    endpoints_file: str

    @property
    def environment(self) -> str:
        return self.config_loader.environment

    @property
    def backup_root(self) -> str:
        mode = "test" if self.test_mode else "full"
        return self.config_loader.get_output_directory(mode)


def _load_tenant_from_file(tenant_id: int, credentials_file: str) -> Dict[str, Any]:
    if not os.path.exists(credentials_file):
        raise FileNotFoundError(f"Credentials file not found: {credentials_file}")

    with open(credentials_file, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    for tenant in data.get("tenants", []):
        if tenant.get("id") == tenant_id:
            return tenant
    raise ValueError(f"Tenant {tenant_id} not found in {credentials_file}")


def load_pipeline_settings(
    tenant_id: int,
    config_file: str = "configs/config.json",
    endpoints_file: str = "configs/endpoints_test.json",
    credentials_file: str = "configs/credential.json",
    test_mode: Optional[bool] = None,
) -> PipelineSettings:
    """Load pipeline settings with env-var overrides."""

    config_loader = ConfigLoader(config_file=config_file)
    endpoint_loader = EndpointConfigLoader(endpoints_file)

    tenant_data = _load_tenant_from_file(tenant_id, credentials_file)
    env_token = os.getenv("OKTA_API_TOKEN", "")
    env_domain = os.getenv("OKTA_DOMAIN", "")

    tenant = TenantConfig(
        tenant_id=tenant_id,
        customer_id=str(tenant_data.get("customer_id", "unknown")),
        okta_domain=env_domain or tenant_data.get("okta_domain", ""),
        api_token=env_token or tenant_data.get("api_token", ""),
    )

    if not tenant.okta_domain:
        raise ValueError("okta_domain is required via credentials file or OKTA_DOMAIN env var")
    if not tenant.api_token:
        raise ValueError("api_token is required via credentials file or OKTA_API_TOKEN env var")

    inferred_test = test_mode
    if inferred_test is None:
        inferred_test = "test" in Path(endpoints_file).stem

    return PipelineSettings(
        config_loader=config_loader,
        endpoint_loader=endpoint_loader,
        tenant=tenant,
        test_mode=bool(inferred_test),
        endpoints_file=endpoints_file,
    )
