"""
Authentication handling for Okta IGA API.
Supports both SSWS API tokens and OAuth 2.0 client credentials flow.
"""

import base64
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Optional, Any


class OktaAuthenticator:
    """Handles authentication for Okta IGA API requests."""

    def __init__(self, base_url: str, session: aiohttp.ClientSession):
        self.base_url = base_url
        self.session = session

        # Credentials
        self.api_token: Optional[str] = None
        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None

        # OAuth state
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

        # Headers will be set after authentication setup
        self.headers: Optional[Dict[str, str]] = None

    def set_api_token(self, api_token: str):
        """Set SSWS API token for authentication."""
        self.api_token = api_token

    def set_oauth_credentials(self, client_id: str, client_secret: str):
        """Set OAuth 2.0 client credentials."""
        self.client_id = client_id
        self.client_secret = client_secret

    async def fetch_oauth_token(self) -> Optional[str]:
        """Fetch OAuth 2.0 bearer token using client credentials flow."""
        if not self.client_id or not self.client_secret:
            return None

        token_url = f"{self.base_url}/oauth2/v1/token"

        # Prepare OAuth token request
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }

        data = {
            "grant_type": "client_credentials",
            "scope": "okta.governance.accessRequests.read okta.governance.accessCertifications.read okta.governance.access.read"
        }

        try:
            async with self.session.post(token_url, headers=headers, data=data) as response:
                print(f"OAuth token request -> Status: {response.status}")

                if response.status == 200:
                    token_data = await response.json()
                    access_token = token_data.get("access_token")
                    expires_in = token_data.get("expires_in", 3600)  # Default 1 hour

                    if access_token:
                        # Set token expiration (subtract 5 minutes for safety margin)
                        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
                        print(f"[OK] OAuth token obtained, expires at {self.token_expires_at}")
                        return access_token
                else:
                    error_text = await response.text()
                    print(f"[ERROR] Failed to get OAuth token: {response.status} - {error_text}")

        except Exception as e:
            print(f"[ERROR] OAuth token request failed: {e}")

        return None

    async def ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token, refresh if needed."""
        # Check if token is about to expire (within 5 minutes)
        if (self.access_token and self.token_expires_at and
            datetime.now() < self.token_expires_at):
            return True  # Token is still valid

        # Token expired or doesn't exist, fetch new one
        print("[INFO] Fetching new OAuth token...")
        self.access_token = await self.fetch_oauth_token()
        return self.access_token is not None

    async def setup_authentication(self) -> Dict[str, str]:
        """Setup authentication headers based on available credentials."""
        # Priority: API token first, then OAuth
        if self.api_token:
            # Use SSWS API Token authentication
            self.headers = {
                "Authorization": f"SSWS {self.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            print(f"[OK] Using SSWS API Token authentication")

        elif self.client_id and self.client_secret:
            # Use OAuth 2.0 Client Credentials flow
            if await self.ensure_valid_token():
                self.headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                print(f"[OK] Using OAuth 2.0 Bearer Token authentication")
            else:
                raise RuntimeError("Failed to obtain OAuth access token")

        else:
            raise RuntimeError("No authentication credentials available (neither API token nor OAuth client credentials)")

        return self.headers

    async def get_headers(self) -> Dict[str, str]:
        """Get current authentication headers, refreshing OAuth token if needed."""
        # For OAuth, ensure token is still valid
        if self.client_id and self.client_secret and not self.api_token:
            if not await self.ensure_valid_token():
                raise RuntimeError("Failed to refresh OAuth token")
            # Update headers with current token
            self.headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

        return self.headers