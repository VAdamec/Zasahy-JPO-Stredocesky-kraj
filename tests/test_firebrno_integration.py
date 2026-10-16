"""Exercise source selection, shared HA sensors, events, and legacy entries."""

import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.pkr_zasahy.const import DOMAIN, FIREBRNO_API

FIXTURES = Path(__file__).parent / "fixtures" / "firebrno"


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def register(mock, rows=None, status=200):
    for name in ("typy", "podtypy", "stavy", "kraje", "okresy"):
        mock.get(FIREBRNO_API + name, json=fixture(name))
    mock.get(
        FIREBRNO_API, json=fixture("incidents") if rows is None else rows, status=status
    )


async def start_firebrno(hass, district="3702", region="116"):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"provider": "firebrno"}
    )
    assert result["step_id"] == "firebrno_region"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"region": region}
    )
    assert result["step_id"] == "firebrno"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"district": district}
    )


def sensor(hass, entry, key):
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{key}"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def refresh(hass, entry):
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_flow_shared_sensors_events_outage_and_restart(
    hass, aioclient_mock, freezer
):
    await hass.config.async_set_time_zone("Europe/Prague")
    freezer.move_to("2026-10-16T12:00:00Z")
    register(aioclient_mock)
    new = async_capture_events(hass, "pkr_zasahy_novy_zasah")
    updates = async_capture_events(hass, "pkr_zasahy_aktualizace_zasahu")
    result = await start_firebrno(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Zásahy JPO – Brno-město"
    assert result["data"]["provider"] == "firebrno"
    assert result["data"]["district"] == 3702
    await hass.async_block_till_done()
    entry = result["result"]
    assert sensor(hass, entry, "dnes").state == "1"
    assert sensor(hass, entry, "aktivni").state == "1"
    assert sensor(hass, entry, "vse").state == "1"
    assert sensor(hass, entry, "posledni_cas").state == "2026-10-16T10:15:00+00:00"
    assert sensor(hass, entry, "posledni").attributes["stupen"] is None
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device.manufacturer == "HZS Jihomoravského kraje"
    assert device.configuration_url == "https://udalosti.firebrno.cz/"
    assert not new and not updates
    await refresh(hass, entry)
    assert not new and not updates

    rows = fixture("incidents")
    second = deepcopy(rows[0])
    second["id"] = 102
    rows.append(second)
    aioclient_mock.clear_requests()
    register(aioclient_mock, rows)
    await refresh(hass, entry)
    assert len(new) == 1 and not updates
    assert new[0].data["native_id"] == 102
    assert new[0].data["provider"] == "firebrno"
    assert new[0].data["entry_id"] == entry.entry_id

    rows[1]["stavId"] = 510  # Same report time, different status.
    aioclient_mock.clear_requests()
    register(aioclient_mock, rows)
    await refresh(hass, entry)
    assert len(new) == 1 and len(updates) == 1
    assert updates[0].data["predchozi_stav"] == "sap na místě"
    assert updates[0].data["aktivni"] is False
    assert sensor(hass, entry, "aktivni").state == "1"

    aioclient_mock.clear_requests()
    register(aioclient_mock, rows, status=503)
    await refresh(hass, entry)
    assert sensor(hass, entry, "dnes").state == "unavailable"
    assert len(entry.runtime_data._zname) == 2
    aioclient_mock.clear_requests()
    register(aioclient_mock, rows)
    await refresh(hass, entry)
    assert sensor(hass, entry, "dnes").state == "2"
    assert len(new) == 1 and len(updates) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(new) == 1 and len(updates) == 1

    duplicate = await start_firebrno(hass)
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "already_configured"


async def test_empty_unknown_status_and_weekly_window(hass, aioclient_mock, freezer):
    freezer.move_to("2026-10-16T12:00:00Z")
    register(aioclient_mock, [])
    result = await start_firebrno(hass, district="0")
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.data["district"] is None
    assert sensor(hass, entry, "aktivni").state == "0"
    assert sensor(hass, entry, "posledni").state == "unknown"

    rows = fixture("incidents")
    rows[0]["casOhlaseni"] = "2026-10-01T10:00:00Z"
    rows[0]["stavId"] = 999
    aioclient_mock.clear_requests()
    register(aioclient_mock, rows)
    await refresh(hass, entry)
    assert sensor(hass, entry, "aktivni").state == "unknown"
    assert (
        sensor(hass, entry, "aktivni").attributes["neznamy_stav"][0]["stav_id"] == 999
    )
    assert sensor(hass, entry, "vse").state == "0"


@pytest.mark.parametrize(
    ("status", "payload", "error"),
    [
        (503, [], "cannot_connect"),
        (200, {}, "invalid_page"),
    ],
)
async def test_setup_failure_is_not_empty_success(
    hass, aioclient_mock, status, payload, error
):
    register(aioclient_mock, payload, status)
    result = await start_firebrno(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_legacy_entry_keeps_entity_unique_ids(hass, aioclient_mock, freezer):
    await hass.config.async_set_time_zone("Europe/Prague")
    freezer.move_to("2026-10-09T16:00:00Z")
    url = "https://pkr.kr-stredocesky.cz/pkr/zasahy-jpo/?r_cast_uzemi__in=1192"
    html = (Path(__file__).parent / "fixtures" / "rakovnik.html").read_text()
    aioclient_mock.get(url, text=html)
    entry = MockConfigEntry(
        domain=DOMAIN, title="Existing Rakovník", unique_id=url, data={"url": url}
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_dnes",
        config_entry=entry,
        suggested_object_id="my_existing_incidents",
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity.entity_id).state == "5"
    assert entry.runtime_data.provider.name == "pkr"
    assert entry.unique_id == url and "provider" not in entry.data
    assert registry.async_get(entity.entity_id).unique_id == f"{entry.entry_id}_dnes"


async def test_place_lookup_failure_can_be_retried(hass, aioclient_mock):
    aioclient_mock.get(FIREBRNO_API + "kraje", status=503)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"provider": "firebrno"}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    aioclient_mock.clear_requests()
    register(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "firebrno_region"
    assert result["data_schema"].schema


async def test_options_reload_firebrno(hass, aioclient_mock):
    register(aioclient_mock)
    result = await start_firebrno(hass)
    await hass.async_block_till_done()
    entry = result["result"]
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], {"scan_interval": 15}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval == timedelta(minutes=15)
