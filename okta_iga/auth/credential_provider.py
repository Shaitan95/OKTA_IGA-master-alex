from typing import Protocol, Dict, Any
import json
import os


class CredentialProvider(Protocol):
    """Abstraction for fetching tenant credentials."""

    def get_tenant_credentials(self, tenant_id: int) -> Dict[str, Any]:
        ...


class JsonCredentialProvider:
    """
    Credential provider that reads tenant credentials from a JSON file
    like configs/credential.json.
    """

    def __init__(self, credentials_file: str = "configs/credential.json"):
        self.credentials_file = credentials_file

    def get_tenant_credentials(self, tenant_id: int) -> Dict[str, Any]:
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")

        with open(self.credentials_file, "r") as f:
            data = json.load(f)

        tenants = data.get("tenants", [])
        for t in tenants:
            if t.get("id") == tenant_id:
                return t

        raise ValueError(f"Tenant {tenant_id} not found in {self.credentials_file}")
