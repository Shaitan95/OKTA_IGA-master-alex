"""
Okta IGA Backup System - Async Version
Complete backup solution for all GET endpoints with async/await and aiohttp.
Supports pagination, rate limiting, concurrency control, and individual object storage.
"""

import json
import time
import aiohttp
import asyncio
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from .config import ConfigLoader, EndpointConfigLoader
from .endpoints import get_global_endpoints, get_resource_endpoints
from .auth import OktaAuthenticator
# Database- and encryption-backed credentials removed.
# Use JSON credentials or environment variables instead.


class OktaIGABackupAsync:
    """
    Complete async backup system for Okta IGA API endpoints.
    Handles pagination, rate limiting, concurrency control, and individual object storage.
    """

    def __init__(self, tenant_id: int, backup_dir: str = "backup",
                 test_mode: bool = False, config: Optional[ConfigLoader] = None,
                 config_file: str = "configs/config.json", endpoint_config_file: str = "configs/endpoints.json",
                 credentials_file: str = "configs/credentials.json", use_json_credentials: bool = True):
        self.tenant_id = tenant_id
        self.customer_id = None  # Will be fetched from JSON or database
        self.backup_dir = backup_dir
        self.test_mode = test_mode
        self.config = config
        self.credentials_file = credentials_file
        self.use_json_credentials = use_json_credentials

        # Load config internally if not provided (config_loader will determine environment)
        self.config_manager = config or ConfigLoader(config_file=config_file)
        # Get environment from config_manager after it's loaded
        self.environment = self.config_manager.environment

        # Database and encryption modules removed; require JSON credentials
        if not self.use_json_credentials:
            raise RuntimeError("Database-backed credentials removed; set use_json_credentials=True")
        self.db_manager = None
        self.encryption_manager = None
        self.endpoint_config_loader = EndpointConfigLoader(endpoint_config_file)
        self.authenticator: Optional[OktaAuthenticator] = None

        # These will be fetched from JSON or database
        self.okta_domain = None
        self.api_token = None
        self.client_id = None
        self.client_secret = None
        self.base_url = None

        # Collect resourceIds during Step 1 (in-memory, more efficient than disk reading)
        self.collected_resource_ids = set()

        # Rate limiting configuration from async config
        rate_config = config.get("async_config.rate_limiting", {}) if config else {}
        self.rate_limit_per_minute = rate_config.get("rate_limit_per_minute", 50)
        self.burst_size = rate_config.get("burst_size", 10)
        self.retry_429_delay = rate_config.get("retry_429_delay", 10)
        self.adaptive_throttling = rate_config.get("adaptive_throttling", True)
        self.backoff_multiplier = rate_config.get("backoff_multiplier", 1.5)
        self.max_retry_delay = rate_config.get("max_retry_delay", 300)

        # Concurrency configuration from async config
        concurrency_config = config.get("async_config.concurrency", {}) if config else {}
        self.max_concurrent_api_calls = concurrency_config.get("max_concurrent_api_calls", 15)
        self.max_concurrent_endpoints = concurrency_config.get("max_concurrent_endpoints", 3)
        self.max_detail_calls_per_endpoint = concurrency_config.get("max_detail_calls_per_endpoint", 10)
        self.max_resource_discovery = concurrency_config.get("max_resource_discovery", 8)

        # Connection pool configuration from async config
        perf_config = config.get("async_config.performance", {}) if config else {}
        self.connection_pool_size = perf_config.get("connection_pool_size", 50)
        self.connection_timeout = perf_config.get("connection_timeout", 10)
        self.read_timeout = perf_config.get("read_timeout", 30)
        self.keep_alive = perf_config.get("keep_alive", True)

        # Session and semaphores (initialized in async context)
        self.session: Optional[aiohttp.ClientSession] = None
        self.api_semaphore: Optional[asyncio.Semaphore] = None
        self.endpoint_semaphore: Optional[asyncio.Semaphore] = None
        self.detail_semaphore: Optional[asyncio.Semaphore] = None
        self.resource_semaphore: Optional[asyncio.Semaphore] = None

        # Rate limiting state
        self.request_count = 0
        self.start_time = time.time()
        self.rate_limit_lock = asyncio.Lock()

        # Backup path will be set up after customer_id is fetched from database
        self.backup_path = None
        self.backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Setup logger
        self.logger = logging.getLogger('okta_iga_async')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - ASYNC - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        # Load endpoint configurations
        self.global_endpoints = get_global_endpoints()
        self.resource_endpoints = get_resource_endpoints()

    async def __aenter__(self):
        """Async context manager entry - initialize database or JSON, fetch credentials, and create session."""
        # Fetch tenant credentials from JSON (database support removed)
        self.fetch_tenant_credentials_from_json()

        # Create connector with connection pool settings
        connector = aiohttp.TCPConnector(
            limit=self.connection_pool_size,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=60 if self.keep_alive else 0,
            enable_cleanup_closed=True
        )

        # Create timeout settings
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=self.connection_timeout,
            sock_read=self.read_timeout
        )

        # Create session (headers will be set after authentication setup)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )

        # Initialize authenticator
        self.authenticator = OktaAuthenticator(self.base_url, self.session)
        if self.api_token:
            self.authenticator.set_api_token(self.api_token)
        if self.client_id and self.client_secret:
            self.authenticator.set_oauth_credentials(self.client_id, self.client_secret)

        # Initialize semaphores for concurrency control
        self.api_semaphore = asyncio.Semaphore(self.max_concurrent_api_calls)
        self.endpoint_semaphore = asyncio.Semaphore(self.max_concurrent_endpoints)
        self.detail_semaphore = asyncio.Semaphore(self.max_detail_calls_per_endpoint)
        self.resource_semaphore = asyncio.Semaphore(self.max_resource_discovery)

        # Setup authentication (must be done after session is created)
        await self.authenticator.setup_authentication()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup session and database."""
        if self.session:
            await self.session.close()

        # Database support removed — nothing to stop

    async def check_rate_limit(self):
        """Async rate limiting check with token bucket algorithm."""
        async with self.rate_limit_lock:
            current_time = time.time()
            elapsed = current_time - self.start_time

            # Reset counter every minute
            if elapsed >= 60:
                self.request_count = 0
                self.start_time = current_time
                elapsed = 0

            # Calculate available requests based on elapsed time
            # Start with burst capacity, then add accumulated requests over time
            accumulated_requests = int((elapsed / 60) * self.rate_limit_per_minute)
            available_requests = self.burst_size + accumulated_requests

            if self.request_count >= available_requests:
                # Calculate time until more requests are available
                requests_per_second = self.rate_limit_per_minute / 60
                sleep_time = 1.0 / requests_per_second  # Time for one more request to become available
                if sleep_time > 0:
                    await asyncio.sleep(min(sleep_time, 60))

            self.request_count += 1

    async def make_request(self, endpoint: str, params: Dict = None) -> Tuple[Optional[aiohttp.ClientResponse], bool]:
        """
        Make async HTTP request with rate limiting and error handling.
        Returns (response, success_flag)
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        async with self.api_semaphore:
            await self.check_rate_limit()

            # Get current headers (refreshes OAuth token if needed)
            headers = await self.authenticator.get_headers()

            url = f"{self.base_url}{endpoint}"

            try:
                # Use the current headers (either SSWS or Bearer token)
                async with self.session.get(url, params=params, headers=headers) as response:
                    print(f"GET {endpoint} -> Status: {response.status}")

                    # Handle rate limiting responses
                    if response.status == 429:
                        retry_after = response.headers.get('Retry-After', self.retry_429_delay)
                        try:
                            retry_delay = int(retry_after)
                        except (ValueError, TypeError):
                            retry_delay = self.retry_429_delay

                        print(f"Rate limited (429). Waiting {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        return None, False

                    # Handle other error responses
                    if response.status >= 400:
                        error_text = await response.text()
                        print(f"Request failed with status {response.status}: {error_text}")
                        return None, False

                    # Success - read response data
                    response_data = await response.json()
                    # Create a mock response object with the data for compatibility
                    class MockResponse:
                        def __init__(self, status, data, headers):
                            self.status_code = status
                            self.headers = headers
                            self._json_data = data

                        def json(self):
                            return self._json_data

                    mock_response = MockResponse(response.status, response_data, response.headers)
                    return mock_response, True

            except asyncio.TimeoutError:
                print(f"Request timeout for {endpoint}")
                return None, False
            except Exception as e:
                print(f"Request error for {endpoint}: {str(e)}")
                return None, False

    def save_object_to_file(self, object_data: Dict[Any, Any], endpoint_name: str, obj_id: str):
        """Save individual object to file with metadata."""
        # Check if individual files should be created
        storage_config = self.config_manager.config["backup"]["storage"]
        if not storage_config.get("create_individual_files", True):
            return

        # Create endpoint directory
        endpoint_dir = os.path.join(self.backup_path, endpoint_name)
        os.makedirs(endpoint_dir, exist_ok=True)

        # Prepare backup object with or without metadata
        if storage_config.get("include_metadata", True):
            backup_object = {
                "id": object_data.get('id', obj_id),
                "name": object_data.get('name', object_data.get('displayName', '')),
                "created": object_data.get('created') or object_data.get('createdAt'),
                "last_update": object_data.get('lastUpdated') or object_data.get('lastModified'),
                "backup_timestamp": datetime.now().isoformat(),
                "json": object_data
            }
        else:
            backup_object = object_data

        # Save individual file
        filename = f"{obj_id}.json"
        filepath = os.path.join(endpoint_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(backup_object, f, indent=2, ensure_ascii=False)

    def create_list_file(self, all_objects: List[Dict], endpoint_name: str):
        """Create list.json file with all objects in same structure as individual files."""
        # Create endpoint directory
        endpoint_dir = os.path.join(self.backup_path, endpoint_name)
        os.makedirs(endpoint_dir, exist_ok=True)

        # Prepare list with same structure as individual files
        storage_config = self.config_manager.config["backup"]["storage"]
        list_objects = []

        for obj in all_objects:
            obj_id = obj.get('id', 'unknown_id')
            if storage_config.get("include_metadata", True):
                backup_object = {
                    "id": obj.get('id', obj_id),
                    "name": obj.get('name', obj.get('displayName', '')),
                    "created": obj.get('created') or obj.get('createdAt'),
                    "last_update": obj.get('lastUpdated') or obj.get('lastModified'),
                    "backup_timestamp": datetime.now().isoformat(),
                    "json": obj
                }
            else:
                backup_object = obj
            list_objects.append(backup_object)

        # Save list file
        list_filepath = os.path.join(endpoint_dir, "list.json")
        with open(list_filepath, 'w', encoding='utf-8') as f:
            json.dump(list_objects, f, indent=2, ensure_ascii=False)

    def create_detailed_list_file(self, detailed_objects: List[Dict], endpoint_name: str):
        """Create list_detailed.json file with all detailed objects in same structure as individual files."""
        # Create endpoint directory
        endpoint_dir = os.path.join(self.backup_path, endpoint_name)
        os.makedirs(endpoint_dir, exist_ok=True)

        # Prepare detailed list with same structure as individual files
        storage_config = self.config_manager.config["backup"]["storage"]
        detailed_list_objects = []

        for obj in detailed_objects:
            obj_id = obj.get('id', 'unknown_id')
            if storage_config.get("include_metadata", True):
                backup_object = {
                    "id": obj.get('id', obj_id),
                    "name": obj.get('name', obj.get('displayName', '')),
                    "created": obj.get('created') or obj.get('createdAt'),
                    "last_update": obj.get('lastUpdated') or obj.get('lastModified'),
                    "backup_timestamp": datetime.now().isoformat(),
                    "json": obj
                }
            else:
                backup_object = obj
            detailed_list_objects.append(backup_object)

        # Save detailed list file
        detailed_list_filepath = os.path.join(endpoint_dir, "list_detailed.json")
        with open(detailed_list_filepath, 'w', encoding='utf-8') as f:
            json.dump(detailed_list_objects, f, indent=2, ensure_ascii=False)

    def extract_resource_ids_from_object(self, obj_data: Dict, endpoint_name: str):
        """Extract resourceIds from campaigns and reviews objects during backup."""
        try:
            if endpoint_name == "reviews":
                # Reviews: json.resourceId
                resource_id = obj_data.get('resourceId')
                if resource_id:
                    self.collected_resource_ids.add(resource_id)

            elif endpoint_name == "campaigns":
                # Campaigns: json.resourceSettings.targetResources[].resourceId
                resource_settings = obj_data.get('resourceSettings', {})
                target_resources = resource_settings.get('targetResources', [])
                for target in target_resources:
                    resource_id = target.get('resourceId')
                    if resource_id:
                        self.collected_resource_ids.add(resource_id)
        except Exception as e:
            # Don't fail backup if resourceId extraction fails
            print(f"    Warning: Failed to extract resourceId from {endpoint_name}: {e}")

    async def backup_endpoint_with_deep_details(self, endpoint_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Async version of deep backup with detail endpoint calls for each object.
        """
        start_time = time.time()
        self.logger.info(f"START: {endpoint_name}")

        async with self.endpoint_semaphore:
            list_endpoint = config["list"]
            detail_endpoint = config.get("detail")

            print(f"\nStarting backup of {endpoint_name}")
            print(f"  List endpoint: {list_endpoint}")
            if detail_endpoint:
                print(f"  Detail endpoint: {detail_endpoint}")

            all_objects = []  # From list endpoint
            detailed_objects = []  # From individual detail endpoints
            objects_with_details = 0
            fallback_objects = 0
            pages_fetched = 0
            next_url = None

            # Step 1: Get all objects from list endpoint with pagination
            while True:
                params = {"limit": 200}  # Reasonable page size

                # Add filter if specified (for resource-specific filter-based endpoints)
                if config.get("filter"):
                    params["filter"] = config["filter"]

                if next_url:
                    # Extract 'after' parameter from next URL
                    parsed = urlparse(next_url)
                    query_params = parse_qs(parsed.query)
                    if 'after' in query_params:
                        params['after'] = query_params['after'][0]

                response, success = await self.make_request(list_endpoint, params)

                if not success or not response:
                    if pages_fetched == 0:  # No pages fetched at all
                        elapsed = time.time() - start_time
                        self.logger.error(f"FAIL: {endpoint_name} - request_failed ({elapsed:.1f}s)")
                        return {
                            "status": "failed",
                            "reason": "request_failed",
                            "total_objects": 0
                        }
                    else:  # Some pages already fetched successfully
                        break

                try:
                    data = response.json()
                    pages_fetched += 1

                    # Handle different response formats
                    if isinstance(data, list):
                        objects_in_page = data
                    elif isinstance(data, dict):
                        # Try different possible array keys - prioritize 'data' for Okta IGA responses
                        # Check each key explicitly to avoid the 'or' chain issue
                        objects_in_page = []
                        if 'data' in data and data['data']:
                            objects_in_page = data['data']
                        elif 'results' in data and data['results']:
                            objects_in_page = data['results']
                        elif 'items' in data and data['items']:
                            objects_in_page = data['items']
                        elif endpoint_name.rstrip('s') in data and data[endpoint_name.rstrip('s')]:
                            objects_in_page = data[endpoint_name.rstrip('s')]
                        elif endpoint_name in data and data[endpoint_name]:
                            objects_in_page = data[endpoint_name]
                        elif data.get('id'):
                            objects_in_page = [data]  # Single object response
                    else:
                        objects_in_page = []

                    if not objects_in_page:
                        print(f"  No objects found in page {pages_fetched}")
                        break

                    print(f"  Page {pages_fetched}: Found {len(objects_in_page)} objects")
                    all_objects.extend(objects_in_page)

                    # Test mode: Only get first page with 1 object
                    if self.test_mode and len(all_objects) >= 1:
                        all_objects = all_objects[:1]  # Keep only first object
                        break

                    # Check for pagination - look for Link header or next URL in response
                    next_url = None
                    if hasattr(response, 'headers') and 'Link' in response.headers:
                        # aiohttp can have multiple Link headers - need to check all of them
                        if hasattr(response.headers, 'getall'):
                            # aiohttp CIMultiDictProxy - get all Link headers
                            link_headers = response.headers.getall('Link')
                        else:
                            # requests-style headers - single string with comma-separated links
                            link_headers = [response.headers['Link']]

                        # Check each Link header for rel="next"
                        for link_header in link_headers:
                            for link in link_header.split(','):
                                if 'rel="next"' in link:
                                    next_url = link.split('<')[1].split('>')[0]
                                    break
                            if next_url:  # Found it, no need to check more headers
                                break

                    # Also check for next URL in response data
                    if isinstance(data, dict) and 'next' in data:
                        next_url = data['next']

                    if not next_url:
                        break

                except Exception as e:
                    print(f"  ERROR parsing response: {e}")
                    break

            if not all_objects:
                elapsed = time.time() - start_time
                self.logger.error(f"FAIL: {endpoint_name} - no_entities_discovered ({elapsed:.1f}s)")
                return {
                    "status": "failed",
                    "reason": "no_entities_discovered",
                    "total_objects": 0
                }

            # Step 2: Get detailed information for each object (if detail endpoint exists and not list_only)
            if detail_endpoint and not config.get("list_only", False):
                print(f"  Fetching detailed data for {len(all_objects)} objects...")

                # Process details with concurrency control
                detail_tasks = []
                for obj in all_objects:
                    obj_id = obj.get('id')
                    if obj_id:
                        detail_tasks.append(self.fetch_object_detail(obj, detail_endpoint, endpoint_name, obj_id))

                # Execute detail tasks with controlled concurrency
                detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

                for result in detail_results:
                    if isinstance(result, Exception):
                        fallback_objects += 1
                    elif result and isinstance(result, dict):
                        if result.get("success"):
                            objects_with_details += 1
                            detailed_objects.append(result["data"])
                        else:
                            fallback_objects += 1
                            detailed_objects.append(result["data"])

            elif detail_endpoint and config.get("list_only", False):
                print(f"  OPTIMIZATION: Using list data only (list provides 100% identical data as detail)")
                # Use list data directly - save each object individually for consistency
                for obj in all_objects:
                    obj_id = obj.get('id', f"obj_{len(detailed_objects)}")
                    self.save_object_to_file(obj, endpoint_name, obj_id)
                    detailed_objects.append(obj)
                objects_with_details = len(all_objects)

            else:
                # No detail endpoint - save objects as-is
                for obj in all_objects:
                    obj_id = obj.get('id', f"obj_{len(all_objects)}")
                    self.save_object_to_file(obj, endpoint_name, obj_id)

                    # Extract resourceIds from basic list data too
                    self.extract_resource_ids_from_object(obj, endpoint_name)

            # Create list files if enabled and we have objects
            storage_config = self.config_manager.config["backup"]["storage"]
            if storage_config.get("create_list_files", True) and all_objects:
                # Create basic list.json from list endpoint data
                self.create_list_file(all_objects, endpoint_name)

                # Create detailed list_detailed.json if we have detailed objects
                if detailed_objects:
                    self.create_detailed_list_file(detailed_objects, endpoint_name)

            elapsed = time.time() - start_time
            self.logger.info(f"DONE: {endpoint_name} ({len(all_objects)} objects, {elapsed:.1f}s)")

            return {
                "status": "success",
                "total_objects": len(all_objects),
                "pages_fetched": pages_fetched,
                "detailed_objects": objects_with_details,
                "fallback_objects": fallback_objects,
                "endpoint": list_endpoint
            }

    async def fetch_object_detail(self, obj: Dict, detail_endpoint: str, endpoint_name: str, obj_id: str) -> Dict:
        """Fetch detailed information for a single object. Returns dict with success and data."""
        async with self.detail_semaphore:
            detail_url = detail_endpoint.format(id=obj_id)
            detail_response, detail_success = await self.make_request(detail_url)

            if detail_success and detail_response:
                try:
                    detailed_data = detail_response.json()
                    self.save_object_to_file(detailed_data, endpoint_name, obj_id)

                    # Extract resourceIds during backup (campaigns, reviews)
                    self.extract_resource_ids_from_object(detailed_data, endpoint_name)

                    return {"success": True, "data": detailed_data}
                except Exception as e:
                    print(f"    ERROR parsing detail for {obj_id}: {e}")

            # Fallback: save original object
            print(f"    Using fallback data for {obj_id}")
            self.save_object_to_file(obj, endpoint_name, obj_id)

            # Extract resourceIds from fallback data too
            self.extract_resource_ids_from_object(obj, endpoint_name)

            return {"success": False, "data": obj}

    async def run_complete_backup(self):
        """Run complete async deep backup of all GET endpoints."""
        mode_text = "TEST MODE (1 object per endpoint)" if self.test_mode else "FULL BACKUP MODE (all objects)"
        print(f"Starting Okta IGA DEEP backup - {mode_text}")
        print(f"Backup directory: {self.backup_path}")
        print(f"Async mode: {'Enabled' if self.config and self.config.is_async_enabled() else 'Disabled'}")
        print(f"Concurrency limits: API calls={self.max_concurrent_api_calls}, Endpoints={self.max_concurrent_endpoints}")

        backup_summary = {
            "backup_timestamp": datetime.now().isoformat(),
            "okta_domain": self.okta_domain,
            "backup_path": self.backup_path,
            "endpoints_backed_up": {},
            "total_objects": 0
        }

        # Step 1: Backup global endpoints (not resource-specific)
        print(f"\nStep 1: Backing up global endpoints...")
        print(f"Endpoint configuration: {self.endpoint_config_loader.get_config_summary()}")

        # Process global endpoints with controlled concurrency
        endpoint_tasks = []
        for object_type, config in self.global_endpoints.items():
            if "list" in config and self.endpoint_config_loader.is_global_endpoint_enabled(object_type):
                print(f"  Enabling {object_type}")
                endpoint_tasks.append(self.process_basic_endpoint(object_type, config, backup_summary))
            elif "list" in config:
                print(f"  Skipping {object_type} (disabled in config)")

        # Execute endpoint tasks with controlled concurrency
        self.logger.info(f"GATHER: Starting {len(endpoint_tasks)} basic endpoints...")
        gather_start = time.time()

        # Create tasks from coroutines
        tasks = [asyncio.create_task(coro) for coro in endpoint_tasks]

        # Create progress monitoring task
        async def monitor_progress():
            while True:
                await asyncio.sleep(30)  # Log every 30 seconds
                completed = sum(1 for task in tasks if task.done())
                elapsed = time.time() - gather_start
                self.logger.info(f"PROGRESS: {completed}/{len(tasks)} basic endpoints complete ({elapsed:.1f}s)")

        progress_task = asyncio.create_task(monitor_progress())

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass

        gather_elapsed = time.time() - gather_start
        self.logger.info(f"GATHER: All basic endpoints complete ({gather_elapsed:.1f}s)")

        # Step 2: Resource-specific endpoints
        print(f"\nStep 2: Backing up resource-specific endpoints...")

        # Get resources collected during Step 1 (campaigns + reviews)
        available_resources = self.get_collected_resource_ids()

        if available_resources:
            self.logger.info(f"GATHER: Starting {len(self.resource_endpoints)} resource endpoints...")
            resource_start = time.time()

            resource_tasks = []
            for object_type, config in self.resource_endpoints.items():
                if self.endpoint_config_loader.is_resource_endpoint_enabled(object_type):
                    print(f"  Enabling resource endpoint {object_type}")
                    resource_tasks.append(self.process_resource_endpoint(object_type, config, available_resources, backup_summary))
                else:
                    print(f"  Skipping resource endpoint {object_type} (disabled in config)")

            await asyncio.gather(*resource_tasks, return_exceptions=True)
            resource_elapsed = time.time() - resource_start
            self.logger.info(f"GATHER: All resource endpoints complete ({resource_elapsed:.1f}s)")

        # Create summary
        summary_file = os.path.join(self.backup_path, "backup_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(backup_summary, f, indent=2, ensure_ascii=False)

        print(f"\nBackup summary saved to: {summary_file}")

        return backup_summary

    async def process_basic_endpoint(self, object_type: str, config: Dict, backup_summary: Dict):
        """Process a basic endpoint with error handling."""
        try:
            # Only process non-filter-required endpoints here
            # Filter-required endpoints are handled separately
            if config.get("requires_filter", False):
                self.logger.info(f"SKIP: {object_type} - requires filter")
                print(f"Skipping {object_type} - requires filter (will be processed separately)")
                return

            # Regular deep backup
            result = await self.backup_endpoint_with_deep_details(object_type, config)

            backup_summary["endpoints_backed_up"][object_type] = result
            if result.get("status") == "success":
                backup_summary["total_objects"] += result.get("total_objects", 0)
        except Exception as e:
            self.logger.error(f"FAIL: {object_type} - exception: {str(e)}")
            print(f"Error processing {object_type}: {e}")
            backup_summary["endpoints_backed_up"][object_type] = {
                "status": "failed",
                "reason": f"exception: {str(e)}",
                "total_objects": 0
            }

    async def process_filter_endpoint(self, object_type: str, config: Dict, backup_summary: Dict):
        """Process a filter-required endpoint with error handling."""
        try:
            result = await self.backup_filter_required_endpoint(object_type, config, backup_summary)
            backup_summary["endpoints_backed_up"][object_type] = result
            if result.get("status") == "success":
                backup_summary["total_objects"] += result.get("total_objects", 0)
        except Exception as e:
            self.logger.error(f"FAIL: {object_type} - exception: {str(e)}")
            print(f"Error processing filter endpoint {object_type}: {e}")
            backup_summary["endpoints_backed_up"][object_type] = {
                "status": "failed",
                "reason": f"exception: {str(e)}",
                "total_objects": 0
            }

    async def process_resource_endpoint(self, object_type: str, config: Dict, resources: List[str], backup_summary: Dict):
        """Process a resource context endpoint."""
        print(f"\nBacking up {object_type} - RESOURCE CONTEXT MODE")

        if not resources:
            backup_summary["endpoints_backed_up"][object_type] = {
                "status": "failed",
                "reason": "no_resources_available",
                "total_objects": 0
            }
            return

        total_objects = 0
        successful_resources = 0
        failed_resources = 0

        print(f"  Processing {len(resources)} resources...")

        # Process resources with controlled concurrency
        resource_tasks = []
        for i, resource_id in enumerate(resources):
            resource_tasks.append(self.backup_single_resource_context(
                object_type, config, resource_id, i + 1, len(resources)
            ))

        # Execute with resource discovery semaphore
        async with self.resource_semaphore:
            results = await asyncio.gather(*resource_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                failed_resources += 1
            elif result:
                total_objects += result.get("objects", 0)
                if result.get("success", False):
                    successful_resources += 1
                else:
                    failed_resources += 1

        backup_summary["endpoints_backed_up"][object_type] = {
            "status": "success" if successful_resources > 0 else "failed",
            "total_objects": total_objects,
            "successful_resources": successful_resources,
            "failed_resources": failed_resources,
            "resources_processed": len(resources)
        }
        backup_summary["total_objects"] += total_objects

    async def backup_single_resource_context(self, object_type: str, config: Dict, resource_id: str,
                                           resource_num: int, total_resources: int) -> Dict:
        """Backup a single resource context endpoint."""
        print(f"    Resource {resource_num}/{total_resources}: {resource_id}")

        # Build the resource-specific endpoint
        if "resource_list" in config:
            resource_endpoint = config["resource_list"].replace("{resourceId}", resource_id)
        elif "list" in config and config.get("filter_template"):
            # Filter-based endpoint
            resource_endpoint = config["list"]
            filter_value = config["filter_template"].format(resourceId=resource_id)
        else:
            print(f"    ERROR: No valid endpoint configuration for {object_type}")
            return {"success": False, "objects": 0}

        # Create new hierarchical structure: resources/resourceId/endpoint_type
        resource_endpoint_name = f"resources/{resource_id}/{object_type}"

        try:
            # Prepare config for backup method
            backup_config = {
                "list": resource_endpoint,
                "detail": config.get("detail", "").replace("{resourceId}", resource_id) if config.get("detail") else None,
                "supports_pagination": config.get("supports_pagination", True),
                "pagination_params": config.get("pagination_params", ["limit", "after"]),
                "list_only": config.get("list_only", False)  # Copy list_only optimization flag
            }

            # Add filter for filter-based endpoints
            if "filter_template" in config:
                backup_config["filter"] = filter_value

            # Use the standard deep backup method
            result = await self.backup_endpoint_with_deep_details(resource_endpoint_name, backup_config)

            if result.get("status") == "success":
                return {"success": True, "objects": result.get("total_objects", 0)}
            else:
                return {"success": False, "objects": 0}

        except Exception as e:
            print(f"    ERROR backing up resource {resource_id}: {e}")
            return {"success": False, "objects": 0}

    async def backup_filter_required_endpoint(self, object_type: str, config: Dict, backup_summary: Dict) -> Dict:
        """Backup endpoints that require filters - single fast attempt per endpoint."""

        start_time = time.time()
        self.logger.info(f"START: {object_type}")

        list_endpoint = config["list"]

        # Single filter attempt based on endpoint type - no testing multiple filters
        if object_type == "entitlements":
            # Known from API docs: entitlements require resourceId filter
            test_filter = 'resourceId sw "0oa"'  # All Okta app IDs
        elif object_type in ["grants", "principal_entitlements", "principal_access"]:
            # Known from API docs: these require principalId filter
            test_filter = 'principalId sw "00u"'  # All user IDs
        else:
            # Unknown endpoint - try without filter first
            test_filter = None

        # Single attempt with known filter
        if test_filter:
            print(f"  Testing {object_type} with filter: {test_filter}")
            test_response, success = await self.make_request(list_endpoint, {"filter": test_filter, "limit": "1"})
        else:
            print(f"  Testing {object_type} without filter...")
            test_response, success = await self.make_request(list_endpoint, {"limit": "1"})

        elapsed = time.time() - start_time

        if success and test_response and test_response.status_code == 200:
            # Filter works - but we're not implementing full backup yet
            self.logger.info(f"DONE: {object_type} - filter works but not implemented ({elapsed:.1f}s)")
            print(f"  Filter works for {object_type}, but full implementation not ready")
            return {
                "status": "failed",
                "reason": "filter_works_but_not_implemented",
                "total_objects": 0
            }
        else:
            # Filter doesn't work - fail fast
            error_msg = "unknown_error"
            try:
                if test_response:
                    error_data = test_response.json()
                    error_msg = error_data.get('errorSummary', f'status_{test_response.status_code}')
            except:
                pass

            self.logger.error(f"FAIL: {object_type} - {error_msg} ({elapsed:.1f}s)")
            print(f"  Filter failed for {object_type}: {error_msg}")
            return {
                "status": "failed",
                "reason": "filter_failed",
                "total_objects": 0
            }

    async def get_resources_from_backup_files(self) -> List[str]:
        """Get resource IDs from reviews data only."""
        print(f"\nStep 2: Extracting resource IDs from backed up reviews...")

        extracted_resources = set()

        # Extract resourceIds from reviews files only
        reviews_dir = os.path.join(self.backup_path, "reviews")
        if os.path.exists(reviews_dir):
            review_files = [f for f in os.listdir(reviews_dir) if f.endswith('.json') and f != 'list.json']
            print(f"  Found {len(review_files)} review files")

            for review_file in review_files:
                try:
                    file_path = os.path.join(reviews_dir, review_file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        review_data = json.load(f)

                    # Extract resourceId from review data
                    json_data = review_data.get('json', {})
                    resource_id = json_data.get('resourceId')
                    if resource_id:
                        extracted_resources.add(resource_id)

                except Exception as e:
                    print(f"    Warning: Failed to parse {review_file}: {e}")
        else:
            print(f"  No reviews directory found")

        unique_resources = list(extracted_resources)

        if unique_resources:
            print(f"  SUCCESS: Extracted {len(unique_resources)} unique resource IDs from reviews")
            print(f"  Resources: {unique_resources[:5]}{'...' if len(unique_resources) > 5 else ''}")
            return unique_resources

        # No reviews = no resources need governance features
        print(f"  No resources found in reviews - no governance features to backup")
        return []

    def get_collected_resource_ids(self) -> List[str]:
        """Get resource IDs collected during Step 1 (in-memory, more efficient)."""
        print(f"\nStep 2: Using collected resource IDs from campaigns and reviews...")

        unique_resources = list(self.collected_resource_ids)

        if unique_resources:
            print(f"  SUCCESS: Collected {len(unique_resources)} unique resource IDs during backup")
            print(f"  Resources: {unique_resources[:5]}{'...' if len(unique_resources) > 5 else ''}")
            return unique_resources

        # No resources collected = no resources need governance features
        print(f"  No resources found in campaigns/reviews - no governance features to backup")
        return []

    async def find_working_resources(self, resource_ids: List[str]) -> List[str]:
        """Test resources to automatically find ones that work with request-conditions endpoint."""
        working_resources = []

        print(f"  Testing {len(resource_ids)} resources to find working ones...")

        # Test each resource with request-conditions endpoint (most common resource-context endpoint)
        for i, resource_id in enumerate(resource_ids[:10], 1):  # Limit to first 10 for performance
            try:
                test_url = f"/governance/api/v2/resources/{resource_id}/request-conditions"
                response, success = await self.make_request(test_url, {"limit": "1"})

                if success and response:
                    # Handle both direct response objects and wrapped responses
                    status = getattr(response, 'status', None)
                    if status == 200:
                        working_resources.append(resource_id)
                        print(f"    Resource {i}: {resource_id} - WORKS")

                        if self.test_mode and len(working_resources) >= 1:
                            break  # Only need one for test mode
                    elif status == 404:
                        print(f"    Resource {i}: {resource_id} - Not found")
                    else:
                        print(f"    Resource {i}: {resource_id} - Failed ({status})")
                else:
                    print(f"    Resource {i}: {resource_id} - Failed (No response)")

            except Exception as e:
                print(f"    Resource {i}: {resource_id} - Error: {str(e)}")

            # Small delay to avoid overwhelming API
            await asyncio.sleep(0.2)

        return working_resources

    def fetch_tenant_credentials_from_json(self):
        """Fetch tenant credentials from JSON file instead of database."""
        try:
            if not os.path.exists(self.credentials_file):
                raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")

            with open(self.credentials_file, 'r') as f:
                credentials_data = json.load(f)

            # Find the tenant in the JSON file
            tenant = None
            for t in credentials_data.get('tenants', []):
                if t.get('id') == self.tenant_id:
                    tenant = t
                    break

            if not tenant:
                raise ValueError(f"Tenant {self.tenant_id} not found in {self.credentials_file}")

            # Extract credentials from JSON
            self.okta_domain = tenant.get('okta_domain')
            self.api_token = tenant.get('api_token')
            self.client_id = tenant.get('oauth_client_id')
            self.client_secret = tenant.get('oauth_client_secret')
            self.customer_id = tenant.get('customer_id')

            if not self.okta_domain:
                raise ValueError(f"okta_domain not found for tenant {self.tenant_id}")
            if not self.api_token:
                raise ValueError(f"api_token not found for tenant {self.tenant_id}")

            # Set base_url - add https:// only if not already present
            if self.okta_domain.startswith(('http://', 'https://')):
                self.base_url = self.okta_domain
            else:
                self.base_url = f"https://{self.okta_domain}"

            # Setup backup directory now that we have customer_id
            if self.backup_path is None:
                tenant_folder = f"tenant_{self.tenant_id}_customer_{self.customer_id}"
                self.backup_path = os.path.join(
                    self.backup_dir,
                    self.environment,
                    tenant_folder,
                    f"backup_{self.backup_timestamp}"
                )
                os.makedirs(self.backup_path, exist_ok=True)

            print(f"[OK] Successfully loaded credentials from JSON for tenant {self.tenant_id}, customer {self.customer_id}")
            print(f"  Domain: {self.okta_domain}")
            print(f"  Backup directory: {self.backup_path}")

        except Exception as e:
            raise RuntimeError(f"Failed to fetch tenant credentials from JSON: {e}")

    def fetch_tenant_credentials(self):
        """Database-backed credential fetching removed.

        This project no longer supports fetching encrypted credentials from a
        database. Use JSON credentials or environment variables instead.
        """
        raise RuntimeError("Database-backed credentials removed; use JSON credentials")