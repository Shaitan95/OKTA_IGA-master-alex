"""
Configuration loader for Okta IGA Backup System
Supports multiple environments and configuration validation.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


class ConfigLoader:
    """Loads and validates configuration from JSON files."""
    
    def __init__(self, config_file: str = "configs/config.json", environment: str = None):
        """
        Initialize config loader.

        Args:
            config_file: Path to configuration file
            environment: Environment ("eu", "us", "beta", "local")
        """
        self.config_file = config_file
        self.config = {}
        self.environment = environment or "us"
        self.base_path = Path(__file__).parent.parent.parent  # Go up to project root
        self._load_environment_config()
        self._load_config()
        self._validate_config()
        
    def _load_environment_config(self):
        """Load environment-specific configuration"""
        # First load the main .env file to get OKTA_ENVIRONMENT
        main_env_path = self.base_path / 'envs' / '.env'
        if main_env_path.exists():
            load_dotenv(main_env_path, override=False)
            print(f"[OK] Loaded main env config from {main_env_path}")
            
            # Update environment from the loaded OKTA_ENVIRONMENT variable
            env_from_file = os.getenv('OKTA_ENVIRONMENT')
            if env_from_file:
                self.environment = env_from_file
                print(f"[OK] Environment set to: {self.environment}")
        
        # Then load the environment-specific file
        env_file_path = self.base_path / 'envs' / f'.env.{self.environment}'
        if env_file_path.exists():
            load_dotenv(env_file_path, override=True)
            print(f"[OK] Loaded {self.environment} specific config from {env_file_path}")
        else:
            print(f"[!] Environment config file not found: {env_file_path}")
        
    def _load_config(self):
        """Load configuration from JSON file."""
        config_path = self.base_path / self.config_file
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            print(f"Loaded configuration from: {config_path}")
        except FileNotFoundError:
            raise Exception(f"Configuration file {config_path} not found")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON in configuration file {config_path}: {e}")
            
    def _validate_config(self):
        """Validate required configuration sections."""
        required_sections = ["async_config", "backup", "endpoints", "environment"]
        
        for section in required_sections:
            if section not in self.config:
                raise Exception(f"Missing required configuration section: {section}")
            
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path (e.g., "async_config.concurrency.max_concurrent_api_calls")
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
            
    def get_okta_config(self) -> Dict[str, Any]:
        """Get Okta-specific configuration (deprecated - credentials come from database)."""
        return self.config.get("okta", {})
        
    def get_async_config(self) -> Dict[str, Any]:
        """Get asynchronous mode configuration."""
        return self.config["async_config"]
        
    def get_backup_config(self) -> Dict[str, Any]:
        """Get backup-specific configuration."""
        return self.config["backup"]
        
    def get_endpoint_config(self) -> Dict[str, Any]:
        """Get endpoint-specific configuration."""
        return self.config["endpoints"]
        
    def get_environment(self) -> str:
        """Get current environment."""
        return self.environment
        
    def load_env_config(self) -> Dict[str, str]:
        """Load environment-specific configuration from .env file."""
        environment = self.get_environment()
        env_file = f"envs/.env.{environment}"
        
        env_config = {}
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_config[key] = value
            return env_config
        except FileNotFoundError:
            print(f"Warning: Environment file {env_file} not found")
            return {}
        
    def get_database_config(self) -> Dict[str, str]:
        """Get database configuration for the current environment."""
        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "3306"),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "name": os.getenv("DB_NAME", "sync_db")
        }
        
    def get_ssh_config(self) -> Dict[str, Any]:
        """Get SSH configuration for the current environment."""
        return {
            "enabled": bool(os.getenv("SSH_HOST")),
            "host": os.getenv("SSH_HOST", "localhost"),
            "port": int(os.getenv("SSH_PORT", "22")),
            "username": os.getenv("SSH_USERNAME", ""),
            "key_file": os.getenv("SSH_KEY_FILE", "")
        }
        
    def is_async_enabled(self) -> bool:
        """Check if async mode is enabled."""
        return self.get("async_config.enabled", False)
        
    def is_debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        return self.get("environment.debug", False)
        
    def get_output_directory(self, mode: str) -> str:
        """Get output directory for specified mode (test/full)."""
        return self.get(f"backup.modes.{mode}.output_directory", f"{mode}_backup")
        
    def get_rate_limit(self) -> int:
        """Get rate limit from async config."""
        return self.get("async_config.rate_limiting.rate_limit_per_minute", 50)
            
    def get_concurrent_limits(self) -> Dict[str, int]:
        """Get concurrency limits from async config."""
        return self.get("async_config.concurrency", {
            "max_concurrent_api_calls": 15,
            "max_concurrent_endpoints": 3,
            "max_detail_calls_per_endpoint": 10,
            "max_resource_discovery": 8
        })
        
    def setup_logging(self):
        """Setup logging based on configuration."""
        log_level = self.get("environment.log_level", "INFO")
        debug = self.is_debug_mode()
        
        level = getattr(logging, log_level.upper(), logging.INFO)
        
        format_str = "%(asctime)s - %(levelname)s - %(message)s" if debug else "%(message)s"
        
        logging.basicConfig(
            level=level,
            format=format_str,
            handlers=[logging.StreamHandler()]
        )
        
        if debug:
            print(f"Debug mode enabled")
            print(f"Async mode: {'enabled' if self.is_async_enabled() else 'disabled'}")
            print(f"Rate limit: {self.get_rate_limit()} req/min")
            
    def print_summary(self):
        """Print configuration summary."""
        print(f"Configuration Summary:")
        print(f"  Environment: {self.get('environment.name', 'unknown')}")
        print(f"  Async Mode: {'enabled' if self.is_async_enabled() else 'disabled'}")
        print(f"  Rate Limit: {self.get_rate_limit()} req/min")
        print(f"  Debug Mode: {'enabled' if self.is_debug_mode() else 'disabled'}")
        print(f"  Note: Okta credentials (domain, tokens) are fetched from database")
        
        if self.is_async_enabled():
            limits = self.get_concurrent_limits()
            print(f"  Concurrency Limits:")
            for key, value in limits.items():
                print(f"    {key}: {value}")


# Convenience function for quick config loading
def load_config(config_file: str = "config.json", environment: str = None) -> ConfigLoader:
    """
    Load configuration from specified file.
    
    Args:
        config_file: Path to configuration file
        environment: Environment ("eu", "us", "beta", "local")
        
    Returns:
        ConfigLoader instance
    """
    return ConfigLoader(config_file=config_file, environment=environment)


if __name__ == "__main__":
    # Test configuration loading
    try:
        config = load_config()
        config.setup_logging()
        config.print_summary()
        print("SUCCESS: Configuration loaded successfully!")
    except Exception as e:
        print(f"ERROR: Configuration error: {e}")