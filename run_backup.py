"""
Simple OKTA IGA Backup Runner.
Delegates to the lightweight iga_pipeline orchestrator by default while keeping
an option to run the legacy async backup.
"""
import argparse
import asyncio

from iga_pipeline.pipeline import run_pipeline
from okta_iga import OktaIGABackupAsync


def run_legacy_backup(tenant_id: int, test_mode: bool, credentials_file: str) -> bool:
    backup_dir = "test_backup" if test_mode else "backup"
    async def _run():
        async with OktaIGABackupAsync(
            tenant_id=tenant_id,
            backup_dir=backup_dir,
            test_mode=test_mode,
            credentials_file=credentials_file,
            use_json_credentials=True,
        ) as backup_system:
            summary = await backup_system.run_complete_backup()
            print(summary)
            return True
    try:
        return asyncio.run(_run())
    except Exception as exc:  # pragma: no cover - legacy path
        print(f"Legacy backup failed: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run Okta IGA backup")
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--endpoints-file", default="configs/endpoints_test.json")
    parser.add_argument("--credentials-file", default="configs/credential.json")
    parser.add_argument("--config-file", default="configs/config.json")
    parser.add_argument("--test-mode", action="store_true", help="Force test mode")
    parser.add_argument("--full-mode", action="store_true", help="Force full mode")
    parser.add_argument("--legacy", action="store_true", help="Use legacy backup system")
    parser.add_argument("--output-mode", default="file", choices=["file", "log"], help="Sink to use")
    args = parser.parse_args()

    if args.legacy:
        success = run_legacy_backup(args.tenant_id, args.test_mode, args.credentials_file)
        exit(0 if success else 1)

    inferred_test = args.test_mode
    if args.full_mode:
        inferred_test = False
    summary = run_pipeline(
        output_mode=args.output_mode,
        endpoints_file=args.endpoints_file,
        tenant_id=args.tenant_id,
        config_file=args.config_file,
        credentials_file=args.credentials_file,
        test_mode=inferred_test if inferred_test is not None else None,
    )
    print("Pipeline summary:", summary)


if __name__ == "__main__":
    main()
