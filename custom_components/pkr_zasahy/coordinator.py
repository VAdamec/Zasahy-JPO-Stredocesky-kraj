"""Coordinator: stahuje stránku, parsuje ji a posílá eventy o nových zásazích."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_AKTUALIZACE,
    EVENT_NOVY_ZASAH,
)
from .models import ParseError, PeriodHistory, Zasah, rozdil
from .providers import create_provider
from .providers.base import async_fetch  # noqa: F401 - compatibility import

_LOGGER = logging.getLogger(__name__)

# Jak dlouho si pamatujeme řádky, které už ze stránky zmizely
# (stránka ukazuje zhruba poslední týden).
PAMET = timedelta(days=10)

type PkrConfigEntry = ConfigEntry["PkrCoordinator"]


@dataclass
class PkrData:
    zasahy: list[Zasah] = field(default_factory=list)
    stazeno: datetime | None = None
    history_start: datetime | None = None
    period_history: PeriodHistory | None = None


class PkrCoordinator(DataUpdateCoordinator[PkrData]):
    """Pravidelně stahuje seznam zásahů."""

    config_entry: PkrConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PkrConfigEntry) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=minutes),
        )
        self._session = async_get_clientsession(hass)
        self.provider = create_provider(hass, self._session, entry.data)
        self._zname: dict[str, Zasah] = {}
        self._prvni_beh = True

    async def _async_update_data(self) -> PkrData:
        try:
            zasahy = await self.provider.async_fetch_incidents(dt_util.now())
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Data se nepodařilo stáhnout: {err}") from err
        except ParseError as err:
            raise UpdateFailed(f"Zdroj má neočekávanou strukturu: {err}") from err

        self._zpracuj_eventy(zasahy)
        period_history = None
        if self.provider.supports_period_history:
            period_history = await self.provider.async_fetch_period_history(
                dt_util.now(), zasahy
            )
        return PkrData(
            zasahy=zasahy,
            stazeno=dt_util.now(),
            history_start=self.provider.history_start,
            period_history=period_history,
        )

    def _zpracuj_eventy(self, zasahy: list[Zasah]) -> None:
        # První načtení po startu jen naplní paměť, ať po restartu HA
        # nepřijde dávka notifikací za celý týden.
        if not self._prvni_beh:
            nove, aktualizovane = rozdil(self._zname, zasahy)
            for z in nove:
                _LOGGER.debug("Nový zásah: %s", z.nazev)
                self.hass.bus.async_fire(EVENT_NOVY_ZASAH, self._event_data(z))
            for predchozi, z in aktualizovane:
                data = self._event_data(z)
                data["predchozi_stav"] = predchozi.stav
                self.hass.bus.async_fire(EVENT_AKTUALIZACE, data)
        self._prvni_beh = False

        now = dt_util.now()
        hranice = now - PAMET
        native_limit = now - timedelta(days=30)
        self._zname = {
            uid: z
            for uid, z in self._zname.items()
            if z.cas >= (native_limit if z.native_id is not None else hranice)
        }
        self._zname.update({z.uid: z for z in zasahy})

    def _event_data(self, z: Zasah) -> dict:
        data = z.as_dict()
        data["entry_id"] = self.config_entry.entry_id
        data["provider"] = self.provider.name
        data["source_url"] = self.provider.url
        return data
