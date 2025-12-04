"""
Simple OKTA IGA Backup Runner
Usage: python run_backup.py
"""
import asyncio
from okta_iga import OktaIGABackupAsync

async def run_backup():
    """Run backup with hardcoded parameters - modify these as needed"""
    
    # CONFIGURATION - Modify these parameters as needed
    tenant_id = 1                              # Change this to your tenant ID from credentials.json
    test_mode = False                          # Change this: True for test mode, False for full backup
    use_json_credentials = True                # Set to True to use credentials.json, False to use database
    credentials_file = "configs/credential.json"  # Path to your credentials JSON file
    backup_dir = 'test_backup' if test_mode else 'backup'
    
    # Print configuration
    mode_text = "TEST MODE (1 object per endpoint)" if test_mode else "FULL BACKUP (all objects)"
    cred_source = "JSON file" if use_json_credentials else "Database"
    print("=" * 60)
    print(f"OKTA IGA BACKUP SYSTEM - {mode_text}")
    print("=" * 60)
    print(f"Tenant ID: {tenant_id}")
    print(f"Credentials Source: {cred_source}")
    if use_json_credentials:
        print(f"Credentials File: {credentials_file}")
    else:
        print(f"Environment: Will be loaded from envs/.env")
    print(f"Backup Directory: {backup_dir}")
    print("=" * 60)
    
    # Run backup
    async with OktaIGABackupAsync(
        tenant_id=tenant_id,
        backup_dir=backup_dir,
        test_mode=test_mode,
        credentials_file=credentials_file,
        use_json_credentials=use_json_credentials
    ) as backup_system:
        
        try:
            summary = await backup_system.run_complete_backup()
            
            print("=" * 60)
            print("BACKUP COMPLETED!")
            print("=" * 60)
            print(f"Total objects backed up: {summary.get('total_objects', 0)}")
            print(f"Backup location: {summary.get('backup_path', 'N/A')}")
            
            successful_endpoints = [
                name for name, info in summary.get('endpoints_backed_up', {}).items()
                if info.get('status') == 'success' and info.get('total_objects', 0) > 0
            ]
            
            print(f"\nSuccessful endpoints ({len(successful_endpoints)}):")
            for endpoint in successful_endpoints:
                objects = summary['endpoints_backed_up'][endpoint].get('total_objects', 0)
                print(f"  {endpoint}: {objects} objects")
                
            return True
            
        except Exception as e:
            print(f"ERROR: Backup failed: {str(e)}")
            return False

def main():
    """Main entry point"""
    success = asyncio.run(run_backup())
    exit(0 if success else 1)

if __name__ == "__main__":
    main()