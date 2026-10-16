"""Fire Brno website JSON backend; no browser runtime is required."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp

from ..const import FIREBRNO_API, FIREBRNO_URL
from ..models import ParseError, PeriodHistory, Zasah
from .base import async_json

_LOGGER = logging.getLogger(__name__)
TZ = ZoneInfo("Europe/Prague")
LOOKUP_TTL = timedelta(days=1)
HISTORY_DAYS = 7
# Bounded independently of history; disappearance must never imply closure.
ACTIVE_DAYS = 30
OPEN_STATUSES = frozenset({210, 400, 410, 420, 430, 440, 500})
CLOSED_STATUSES = frozenset({510, 520, 600, 610, 620, 700, 710, 750, 760, 780, 800})
LOOKUPS = ("typy", "podtypy", "stavy")


def lookup_index(data, name: str) -> dict[int, dict]:
    if not isinstance(data, list) or any(
        not isinstance(row, dict)
        or type(row.get("id")) is not int
        or not isinstance(row.get("nazev"), str)
        or not row["nazev"].strip()
        for row in data
    ):
        raise ParseError(f"Invalid {name} lookup")
    result = {row["id"]: row for row in data}
    if not result or len(result) != len(data):
        raise ParseError(f"Empty or duplicate {name} lookup")
    return result


async def async_search_units(
    session: aiohttp.ClientSession, term: str
) -> dict[int, dict]:
    """Resolve a name to selectable native IDs; an empty result is valid."""
    data = await async_json(session, FIREBRNO_API + "jednotky", {"term": term})
    if data == []:
        return {}
    return lookup_index(data, "jednotky")


def parse_time(value, name: str, optional=False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ParseError(f"Invalid {name}")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as err:
        raise ParseError(f"Invalid {name}") from err
    if result.tzinfo is None:
        raise ParseError(f"Missing timezone in {name}")
    return result.astimezone(TZ)


def _text(row, key):
    value = row.get(key)
    if value is not None and not isinstance(value, str):
        raise ParseError(f"Invalid {key}")
    return value


def _place(row, key):
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, dict) or not isinstance(value.get("nazev"), str):
        raise ParseError(f"Invalid {key}")
    return value["nazev"]


def parse_incidents(data, lookups: dict[str, dict[int, dict]]) -> list[Zasah]:
    """Normalize complete records atomically; malformed rows cannot become zeros."""
    if not isinstance(data, list):
        raise ParseError("Incidents response must be a list")
    result = []
    seen = set()
    for row in data:
        if not isinstance(row, dict) or any(
            type(row.get(key)) is not int
            for key in ("id", "stavId", "typId", "podtypId")
        ):
            raise ParseError("Missing or invalid incident IDs")
        if row["id"] in seen:
            raise ParseError("Duplicate incident ID")
        seen.add(row["id"])
        labels = []
        for key, lookup in (
            ("typId", "typy"),
            ("podtypId", "podtypy"),
            ("stavId", "stavy"),
        ):
            item = lookups[lookup].get(row[key])
            labels.append(item["nazev"].lower() if item else f"neznámý ({row[key]})")
        category, subtype, status = labels
        status_id = row["stavId"]
        active = (
            True
            if status_id in OPEN_STATUSES
            else False
            if status_id in CLOSED_STATUSES
            else None
        )
        reported = parse_time(row.get("casOhlaseni"), "casOhlaseni")
        municipality = _text(row, "obec") or ""
        result.append(
            Zasah(
                nazev=" - ".join(
                    part for part in (category, subtype, municipality) if part
                ),
                kategorie=category,
                podtyp=subtype,
                typ=category,
                stav=status,
                obec=municipality,
                okres=_place(row, "okres"),
                stupen=None,
                cas=reported,
                provider="firebrno",
                native_id=row["id"],
                stav_id=status_id,
                active_state=active,
                cas_ohlaseni=reported,
                cas_vzniku=parse_time(row.get("casVzniku"), "casVzniku", True),
                kraj=_place(row, "kraj"),
                cast_obce=_text(row, "castObce"),
                orp=_text(row, "ORP"),
                ulice=_text(row, "ulice"),
                silnice=_text(row, "silnice"),
                poznamka=_text(row, "poznamkaProMedia"),
            )
        )
    return sorted(result, key=lambda item: item.cas, reverse=True)


class FireBrnoProvider:
    supports_period_history = True
    name = "firebrno"
    manufacturer = "HZS Jihomoravského kraje"
    model = "Fire Brno – přehled událostí HZS"
    url = FIREBRNO_URL

    def __init__(
        self,
        session: aiohttp.ClientSession,
        region: int,
        district: int | None = None,
        unit: int | None = None,
    ):
        self.session = session
        self.region = region
        self.district = district
        self.unit = unit
        self.lookups: dict[str, dict[int, dict]] = {}
        self._loaded: datetime | None = None
        self._unknown_refresh: datetime | None = None
        self.history_start: datetime | None = None
        self._tracked_ids: dict[str, datetime] = {}
        self._archive: dict[str, Zasah] | None = None
        self._archive_year: int | None = None
        self._archive_refreshed: datetime | None = None
        self._archive_attempt: datetime | None = None
        self._archive_failed = False

    async def async_load_lookups(self, now: datetime, force=False):
        if not force and self._loaded and now - self._loaded < LOOKUP_TTL:
            return
        try:
            fresh = {}
            for name in LOOKUPS:
                fresh[name] = lookup_index(
                    await async_json(self.session, FIREBRNO_API + name), name
                )
        except (aiohttp.ClientError, TimeoutError, ParseError):
            if not self.lookups:
                raise
            self._loaded = now
            _LOGGER.warning(
                "Fire Brno lookup refresh failed; using cached dictionaries",
                exc_info=True,
            )
            return
        self.lookups = fresh
        self._loaded = now

    async def _query(self, start, end, statuses):
        params = [
            ("casOd", start.astimezone(UTC).isoformat()),
            ("casDo", end.astimezone(UTC).isoformat()),
            ("krajId", str(self.region)),
        ]
        if self.district:
            params.append(("okresId", str(self.district)))
        if self.unit is not None:
            params.append(("jednotkaId", str(self.unit)))
        params.extend(("stavIds", str(value)) for value in sorted(statuses))
        return await async_json(self.session, FIREBRNO_API, params)

    async def async_fetch_incidents(self, now: datetime) -> list[Zasah]:
        await self.async_load_lookups(now)
        local_now = now.astimezone(TZ)
        history_start = local_now - timedelta(days=HISTORY_DAYS)
        # Include all dictionary statuses so new codes remain visible as unknown.
        history = await self._query(history_start, local_now, self.lookups["stavy"])
        older_open = await self._query(
            local_now - timedelta(days=ACTIVE_DAYS),
            history_start,
            self.lookups["stavy"],
        )
        if not isinstance(history, list) or not isinstance(older_open, list):
            raise ParseError("Incidents response must be a list")
        rows = history + older_open
        if any(not isinstance(row, dict) for row in rows):
            raise ParseError("Invalid incident row")
        if any(
            row.get(key) not in self.lookups[lookup]
            for row in rows
            for key, lookup in (
                ("typId", "typy"),
                ("podtypId", "podtypy"),
                ("stavId", "stavy"),
            )
            if isinstance(row.get(key), int)
        ) and (
            self._unknown_refresh is None or now - self._unknown_refresh >= LOOKUP_TTL
        ):
            self._unknown_refresh = now
            await self.async_load_lookups(now, force=True)
        # Queries overlap at the boundary; the more recent history response wins.
        normalized_history = parse_incidents(history, self.lookups)
        normalized_open = parse_incidents(older_open, self.lookups)
        combined = {
            incident.uid: incident
            for incident in normalized_open
            if incident.aktivni is not False or incident.uid in self._tracked_ids
        }
        combined.update({incident.uid: incident for incident in normalized_history})
        tracked = {
            uid: reported
            for uid, reported in self._tracked_ids.items()
            if reported >= local_now - timedelta(days=ACTIVE_DAYS)
        }
        tracked.update(
            {
                incident.uid: incident.cas
                for incident in normalized_open + normalized_history
                if incident.aktivni is not False
            }
        )
        self._tracked_ids = tracked
        self.history_start = history_start
        return sorted(combined.values(), key=lambda item: item.cas, reverse=True)

    async def async_fetch_period_history(
        self, now: datetime, recent: list[Zasah]
    ) -> PeriodHistory:
        """Refresh the full-year base independently of recent-data availability."""
        local_now = now.astimezone(TZ)
        year_start = datetime(local_now.year, 1, 1, tzinfo=TZ)
        if self._archive_year != local_now.year:
            self._archive_year = local_now.year
            self._archive = None
            self._archive_refreshed = None
            self._archive_attempt = None
            self._archive_failed = False
        due = (
            self._archive_refreshed is None
            or self._archive_refreshed.date() != local_now.date()
        )
        retry_allowed = (
            self._archive_attempt is None
            or now - self._archive_attempt >= timedelta(hours=1)
        )
        refreshed = False
        if due and retry_allowed:
            self._archive_attempt = now
            try:
                payload = await self._query(
                    year_start, local_now, self.lookups["stavy"]
                )
                records = await asyncio.to_thread(
                    parse_incidents, payload, self.lookups
                )
            except (aiohttp.ClientError, TimeoutError, ParseError):
                self._archive_failed = True
                _LOGGER.warning(
                    "Fire Brno calendar history refresh failed; recent polling continues",
                    exc_info=True,
                )
            else:
                self._archive = {
                    z.uid: z for z in records if year_start <= z.cas <= local_now
                }
                self._archive_refreshed = local_now
                self._archive_failed = False
                refreshed = True
        if self._archive is not None:
            for z in recent:
                # The full-year request ran after recent polling; prefer its
                # copy when both responses contain the same incident.
                if year_start <= z.cas <= local_now and (
                    not refreshed or z.uid not in self._archive
                ):
                    self._archive[z.uid] = z
        return PeriodHistory(
            zasahy=(
                sorted(self._archive.values(), key=lambda z: z.cas, reverse=True)
                if self._archive is not None
                else None
            ),
            as_of=local_now,
            refreshed=self._archive_refreshed,
            stale=(
                self._archive_failed
                or self._archive_refreshed is None
                or self._archive_refreshed.date() != local_now.date()
            ),
        )
