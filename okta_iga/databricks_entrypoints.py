import asyncio
from typing import Optional, Callable, Dict, Any

from .backup_system import OktaIGABackupAsync


def run_backup_sync(
    tenant_id: int,
    backup_dir: str = "backup",
    test_mode: bool = False,
    config_file: str = "configs/config.json",
    endpoint_config_file: str = "configs/endpoints.json",
    credentials_file: str = "configs/credential.json",
    object_sink: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    credential_provider=None,
) -> Dict[str, Any]:
    """
    Synchronous helper to run a full Okta IGA backup.

    This is intended for use from Databricks notebooks or simple scripts
    that don't want to manage asyncio directly.
    """

    async def _run():
        async with OktaIGABackupAsync(
            tenant_id=tenant_id,
            backup_dir=backup_dir,
            test_mode=test_mode,
            config_file=config_file,
            endpoint_config_file=endpoint_config_file,
            credentials_file=credentials_file,
            object_sink=object_sink,
            credential_provider=credential_provider,
        ) as backup:
            return await backup.run_complete_backup()

    # In most environments (including Databricks) asyncio.run is fine here.
    return asyncio.run(_run())
