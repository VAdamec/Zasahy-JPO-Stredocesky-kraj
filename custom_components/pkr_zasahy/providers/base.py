"""Small provider interface and shared HTTP transport."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Protocol

import aiohttp

from ..const import USER_AGENT
from ..models import ParseError, Zasah


async def async_fetch(session: aiohttp.ClientSession, url: str) -> str:
    """Read a response completely and release the connection."""
    async with asyncio.timeout(30):
        async with session.get(
            url, headers={"User-Agent": USER_AGENT, "Accept-Language": "cs"}
        ) as response:
            response.raise_for_status()
            return await response.text()


async def async_json(session: aiohttp.ClientSession, url: str, params=None):
    """Fetch JSON; a successful HTTP response is not proof of a valid payload."""
    async with asyncio.timeout(30):
        async with session.get(
            url, params=params, headers={"User-Agent": USER_AGENT}
        ) as response:
            response.raise_for_status()
            try:
                return await response.json()
            except (ValueError, aiohttp.ContentTypeError) as err:
                raise ParseError("Invalid JSON response") from err


class IncidentProvider(Protocol):
    """Source-specific transport/normalization consumed by the coordinator."""

    name: str
    manufacturer: str
    model: str
    url: str
    history_start: datetime | None

    async def async_fetch_incidents(self, now: datetime) -> list[Zasah]:
        """Return a validated snapshot, newest first, or raise an error."""
