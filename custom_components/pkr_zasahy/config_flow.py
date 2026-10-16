"""Config flow pro Zásahy JPO."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DISTRICT,
    CONF_PROVIDER,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_REGION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_URL,
    DOMAIN,
    FIREBRNO_API,
    FIREBRNO_URL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    PROVIDER_FIREBRNO,
    PROVIDER_PKR,
    URL_PREFIX,
)
from .parser import ParseError, parse_okres, parse_zasahy
from .providers.base import async_fetch, async_json
from .providers.firebrno import FireBrnoProvider, lookup_index


def _normalizuj(url: str) -> str:
    """Seřadí query parametry a zahodí prázdné, ať jde URL použít jako unique_id."""
    parts = urlsplit(url.strip())
    query = sorted((k, v) for k, v in parse_qsl(parts.query) if v)
    return f"{URL_PREFIX}?{urlencode(query)}" if query else URL_PREFIX


class PkrConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if user_input.get(CONF_PROVIDER) == PROVIDER_FIREBRNO:
                return await self.async_step_firebrno_region()
            if user_input.get(CONF_PROVIDER) == PROVIDER_PKR:
                return await self.async_step_pkr()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROVIDER, default=PROVIDER_PKR
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {
                                    "value": PROVIDER_PKR,
                                    "label": "Středočeský kraj (PKR)",
                                },
                                {
                                    "value": PROVIDER_FIREBRNO,
                                    "label": "Fire Brno (HZS)",
                                },
                            ]
                        )
                    ),
                }
            ),
        )

    async def async_step_pkr(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            raw = user_input[CONF_URL].strip()
            if not raw.startswith(URL_PREFIX):
                errors[CONF_URL] = "invalid_url"
            else:
                url = _normalizuj(raw)
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                try:
                    html = await async_fetch(async_get_clientsession(self.hass), url)
                    await self.hass.async_add_executor_job(parse_zasahy, html)
                except (aiohttp.ClientError, TimeoutError):
                    errors["base"] = "cannot_connect"
                except ParseError:
                    errors["base"] = "invalid_page"
                else:
                    okres = parse_okres(html)
                    title = f"Zásahy JPO – {okres}" if okres else "Zásahy JPO"
                    return self.async_create_entry(
                        title=title, data={CONF_URL: url, CONF_PROVIDER: PROVIDER_PKR}
                    )

        return self.async_show_form(
            step_id="pkr",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL,
                        default=(user_input or {}).get(CONF_URL, DEFAULT_URL),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
                    )
                }
            ),
            errors=errors,
        )

    async def _async_places(self):
        if hasattr(self, "_regions"):
            return
        session = async_get_clientsession(self.hass)
        regions = lookup_index(
            await async_json(session, FIREBRNO_API + "kraje"), "kraje"
        )
        districts = lookup_index(
            await async_json(session, FIREBRNO_API + "okresy"), "okresy"
        )
        if any(type(row.get("krajId")) is not int for row in districts.values()):
            raise ParseError("Invalid district region")
        self._regions, self._districts = regions, districts

    async def async_step_firebrno_region(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        try:
            await self._async_places()
        except (aiohttp.ClientError, TimeoutError):
            errors["base"] = "cannot_connect"
        except ParseError:
            errors["base"] = "invalid_page"
        if not errors and user_input is not None:
            try:
                region = int(user_input[CONF_REGION])
            except (ValueError, TypeError, KeyError):
                region = None
            if region not in self._regions:
                errors["base"] = "invalid_filter"
            else:
                self._region = region
                return await self.async_step_firebrno()
        options = [
            {"value": str(key), "label": row["nazev"]}
            for key, row in getattr(self, "_regions", {}).items()
        ]
        schema = (
            vol.Schema(
                {
                    vol.Required(
                        CONF_REGION, default=str(DEFAULT_REGION)
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            )
            if options
            else vol.Schema({})
        )
        return self.async_show_form(
            step_id="firebrno_region", data_schema=schema, errors=errors
        )

    async def async_step_firebrno(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        districts = {
            key: row
            for key, row in self._districts.items()
            if row["krajId"] == self._region
        }
        if user_input is not None:
            try:
                district = int(user_input.get(CONF_DISTRICT, "0")) or None
            except (ValueError, TypeError):
                district = -1
            if district is not None and district not in districts:
                errors["base"] = "invalid_filter"
            else:
                await self.async_set_unique_id(
                    f"firebrno:{self._region}:{district or 'all'}"
                )
                self._abort_if_unique_id_configured()
                provider = FireBrnoProvider(
                    async_get_clientsession(self.hass), self._region, district
                )
                try:
                    await provider.async_fetch_incidents(dt_util.now())
                except (aiohttp.ClientError, TimeoutError):
                    errors["base"] = "cannot_connect"
                except ParseError:
                    errors["base"] = "invalid_page"
                else:
                    place = (
                        districts[district]["nazev"]
                        if district
                        else self._regions[self._region]["nazev"]
                    )
                    return self.async_create_entry(
                        title=f"Zásahy JPO – {place}",
                        data={
                            CONF_PROVIDER: PROVIDER_FIREBRNO,
                            CONF_REGION: self._region,
                            CONF_DISTRICT: district,
                            CONF_URL: FIREBRNO_URL,
                        },
                    )
        return self.async_show_form(
            step_id="firebrno",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DISTRICT, default="0"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {
                                    "value": "0",
                                    "label": self._regions[self._region]["nazev"],
                                },
                                *[
                                    {"value": str(key), "label": row["nazev"]}
                                    for key, row in districts.items()
                                ],
                            ]
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> PkrOptionsFlow:
        return PkrOptionsFlow()


class PkrOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            unit_of_measurement="min",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )
