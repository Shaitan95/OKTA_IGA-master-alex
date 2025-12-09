"""Async API client that reuses Okta authentication and config knobs."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import aiohttp

from okta_iga.auth import OktaAuthenticator


class ApiClient:
    def __init__(self, base_url: str, api_token: str, config_loader):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.config_loader = config_loader

        rate_config = config_loader.get("async_config.rate_limiting", {}) if config_loader else {}
        self.rate_limit_per_minute = rate_config.get("rate_limit_per_minute", 50)
        self.burst_size = rate_config.get("burst_size", 10)
        self.retry_429_delay = rate_config.get("retry_429_delay", 10)
        self.backoff_multiplier = rate_config.get("backoff_multiplier", 1.5)
        self.max_retry_delay = rate_config.get("max_retry_delay", 300)

        concurrency_config = config_loader.get("async_config.concurrency", {}) if config_loader else {}
        self.max_concurrent_api_calls = concurrency_config.get("max_concurrent_api_calls", 5)

        perf_config = config_loader.get("async_config.performance", {}) if config_loader else {}
        self.connection_pool_size = perf_config.get("connection_pool_size", 20)
        self.connection_timeout = perf_config.get("connection_timeout", 10)
        self.read_timeout = perf_config.get("read_timeout", 30)
        self.keep_alive = perf_config.get("keep_alive", True)

        self.session: Optional[aiohttp.ClientSession] = None
        self.authenticator: Optional[OktaAuthenticator] = None
        self.api_semaphore: Optional[asyncio.Semaphore] = None

        self.request_count = 0
        self.start_time = time.time()
        self.rate_limit_lock = asyncio.Lock()

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=self.connection_pool_size,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=60 if self.keep_alive else 0,
            enable_cleanup_closed=True,
        )
        timeout = aiohttp.ClientTimeout(total=None, connect=self.connection_timeout, sock_read=self.read_timeout)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        self.authenticator = OktaAuthenticator(self.base_url, self.session)
        self.authenticator.set_api_token(self.api_token)
        await self.authenticator.setup_authentication()
        self.api_semaphore = asyncio.Semaphore(self.max_concurrent_api_calls)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def check_rate_limit(self):
        async with self.rate_limit_lock:
            current_time = time.time()
            elapsed = current_time - self.start_time
            if elapsed >= 60:
                self.request_count = 0
                self.start_time = current_time
                elapsed = 0
            accumulated_requests = int((elapsed / 60) * self.rate_limit_per_minute)
            available_requests = self.burst_size + accumulated_requests
            if self.request_count >= available_requests:
                requests_per_second = self.rate_limit_per_minute / 60
                sleep_time = max(1.0 / requests_per_second, 0)
                if sleep_time > 0:
                    await asyncio.sleep(min(sleep_time, 60))
            self.request_count += 1

    async def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict], Optional[aiohttp.typedefs.LooseHeaders]]:
        if not self.session or not self.authenticator or not self.api_semaphore:
            raise RuntimeError("ApiClient not initialized; use async context manager")

        async with self.api_semaphore:
            await self.check_rate_limit()
            headers = await self.authenticator.get_headers()
            url = f"{self.base_url}{endpoint}"
            backoff = self.retry_429_delay
            while True:
                try:
                    async with self.session.get(url, params=params, headers=headers) as response:
                        if response.status == 429:
                            await asyncio.sleep(backoff)
                            backoff = min(int(backoff * self.backoff_multiplier), self.max_retry_delay)
                            continue
                        if response.status >= 400:
                            return None, None
                        data = await response.json()
                        return data, response.headers
                except asyncio.TimeoutError:
                    return None, None
                except Exception:
                    return None, None

    async def fetch_paginated(
        self,
        endpoint: str,
        supports_pagination: bool,
        pagination_params: Optional[List[str]] = None,
        base_params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        all_items: List[Dict] = []
        params = dict(base_params or {})
        if supports_pagination:
            params.setdefault("limit", 200)
        next_url: Optional[str] = None

        while True:
            query_params = dict(params)
            if next_url:
                parsed = urlparse(next_url)
                qs = parse_qs(parsed.query)
                if "after" in qs:
                    query_params["after"] = qs["after"][0]
            payload, headers = await self._request(endpoint if not next_url else next_url.replace(self.base_url, ""), query_params)
            if payload is None:
                break
            if isinstance(payload, list):
                all_items.extend(payload)
            elif isinstance(payload, dict):
                items = payload.get("items") or payload.get("value") or []
                if isinstance(items, list):
                    all_items.extend(items)
                else:
                    all_items.append(payload)
            if not supports_pagination:
                break
            link_header = headers.get("link") if headers else None
            next_url = self._extract_next_from_link(link_header)
            if not next_url:
                break
        return all_items

    @staticmethod
    def _extract_next_from_link(link_header: Optional[str]) -> Optional[str]:
        if not link_header:
            return None
        parts = [p.strip() for p in link_header.split(",")]
        for part in parts:
            if "rel=\"next\"" in part:
                url_part = part.split(";")[0].strip()
                if url_part.startswith("<") and url_part.endswith(">"):
                    return url_part[1:-1]
        return None
