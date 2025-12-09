import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from iga_pipeline.pipeline import run_pipeline


class FakeClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def fetch_paginated(self, endpoint, supports_pagination, pagination_params=None, base_params=None):
        if "campaigns" in endpoint:
            return [
                {
                    "id": "camp-1",
                    "name": "Campaign 1",
                    "resourceSettings": {"targetResources": [{"resourceId": "app-1"}]},
                }
            ]
        if "reviews" in endpoint:
            return [
                {
                    "id": "rev-1",
                    "name": "Review 1",
                    "resourceId": "app-1",
                }
            ]
        if "grants" in endpoint:
            return [
                {
                    "id": "grant-1",
                    "principalName": "user1",
                    "entitlementName": "ent-1",
                }
            ]
        return []


def test_pipeline_writes_snapshots(tmp_path):
    creds = {
        "tenants": [
            {"id": 99, "customer_id": "abc", "okta_domain": "example.okta.com", "api_token": "token"}
        ]
    }
    cred_file = tmp_path / "credentials.json"
    cred_file.write_text(json.dumps(creds))

    output_root = tmp_path / "out"
    summary = run_pipeline(
        output_mode="file",
        endpoints_file="configs/endpoints_test.json",
        tenant_id=99,
        config_file="configs/config.json",
        credentials_file=str(cred_file),
        test_mode=True,
        api_client_factory=lambda settings: FakeClient(),
        backup_root_override=str(output_root),
    )

    env_dir = Path(output_root) / "us"
    snapshots = list(env_dir.rglob("*.json"))
    assert snapshots, "Expected snapshot files to be written"
    names = {p.name for p in snapshots}
    assert {"campaigns.json", "reviews.json", "grants.json"}.issubset(names)
    # Ensure parsed content is stored
    campaigns_path = next(p for p in snapshots if p.name == "campaigns.json")
    data = json.loads(campaigns_path.read_text())
    assert data[0]["object_type"] == "campaigns"
    assert summary["written"].get("campaigns") == 1
