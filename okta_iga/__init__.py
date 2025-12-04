"""
Okta IGA Backup System - Refactored Package
Complete backup solution for all GET endpoints with async/await and aiohttp.
"""

__version__ = "1.0.0"
__author__ = "Okta IGA Backup System"

from .backup_system import OktaIGABackupAsync

__all__ = ["OktaIGABackupAsync"]