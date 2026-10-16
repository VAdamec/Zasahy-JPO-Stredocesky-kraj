"""JSON normalization, identity, time semantics, and provider failure handling."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant")

from custom_components.pkr_zasahy.models import ParseError, rozdil
from custom_components.pkr_zasahy.providers.firebrno import (
    FireBrnoProvider,
    lookup_index,
    parse_incidents,
    parse_time,
)

FIXTURES = Path(__file__).parent / "fixtures" / "firebrno"
NOW = datetime(2026, 10, 16, 12, tzinfo=UTC)


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def lookups():
    return {
        name: lookup_index(fixture(name), name) for name in ("typy", "podtypy", "stavy")
    }


def test_normalization_and_nullable_fields():
    incident = parse_incidents(fixture("incidents"), lookups())[0]
    assert incident.uid == "firebrno:101"
    assert incident.kategorie == "požár"
    assert incident.podtyp == "popelnice, kontejner"
    assert incident.aktivni is True
    assert incident.cas.hour == 12
    assert incident.cas.utcoffset() == timedelta(hours=2)
    assert incident.obec == "Brno" and incident.okres == "Brno-město"
    data = incident.as_dict()
    assert data["stupen"] is None
    assert data["cas_vzniku"] is None
    assert data["cas_aktualizace"] is None
    assert data["native_id"] == 101
    assert data["cast_obce"] == "Zábrdovice"
    assert data["ulice"] is None


@pytest.mark.parametrize(("status", "active"), [(500, True), (510, False), (999, None)])
def test_numeric_status_overrides_label(status, active):
    rows = fixture("incidents")
    rows[0]["stavId"] = status
    incident = parse_incidents(rows, lookups())[0]
    assert incident.aktivni is active
    if status == 500:
        assert incident.stav == "ukončená"


def test_native_identity_and_content_diff():
    incident = parse_incidents(fixture("incidents"), lookups())[0]
    changed = replace(incident, stav_id=510, stav="ukončená", active_state=False)
    other = replace(incident, native_id=102)
    assert changed.cas == incident.cas
    assert rozdil({incident.uid: incident}, [incident]) == ([], [])
    assert rozdil({incident.uid: incident}, [changed]) == ([], [(incident, changed)])
    assert rozdil({incident.uid: incident}, [other]) == ([other], [])
    note = replace(incident, poznamka="Nová informace")
    assert rozdil({incident.uid: incident}, [note]) == ([], [(incident, note)])


@pytest.mark.parametrize("payload", [{}, None, [None], [{"id": 1}]])
def test_malformed_response_fails(payload):
    with pytest.raises(ParseError):
        parse_incidents(payload, lookups())


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("id", "101"),
        ("stavId", True),
        ("casOhlaseni", "bad"),
        ("casOhlaseni", "2026-10-16T10:00:00"),
        ("obec", 12),
        ("okres", "Brno"),
    ],
)
def test_invalid_row_fails_atomically(key, value):
    rows = fixture("incidents")
    broken = deepcopy(rows[0])
    broken[key] = value
    with pytest.raises(ParseError):
        parse_incidents(rows + [broken], lookups())


def test_empty_and_duplicate_responses():
    assert parse_incidents([], lookups()) == []
    rows = fixture("incidents")
    with pytest.raises(ParseError):
        parse_incidents(rows + rows, lookups())


def test_unknown_lookup_id_is_explicit():
    rows = fixture("incidents")
    rows[0]["typId"] = 9999
    assert parse_incidents(rows, lookups())[0].kategorie == "neznámý (9999)"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        [],
        [{"id": "1", "nazev": "test"}],
        [{"id": 1, "nazev": "test"}, {"id": 1, "nazev": "test"}],
    ],
)
def test_invalid_dictionary(payload):
    with pytest.raises(ParseError):
        lookup_index(payload, "test")


@pytest.mark.parametrize(
    ("stamp", "hour", "offset"),
    [
        ("2026-10-15T22:30:00Z", 0, 2),
        ("2026-10-25T00:30:00Z", 2, 2),
        ("2026-10-25T01:30:00Z", 2, 1),
    ],
)
def test_prague_midnight_and_dst(stamp, hour, offset):
    result = parse_time(stamp, "time")
    assert result.hour == hour
    assert result.utcoffset() == timedelta(hours=offset)


async def test_query_filters_cache_and_bounds():
    provider = FireBrnoProvider(None, 116, 3702)
    requests = []

    async def fetch(session, url, params=None):
        requests.append((url, params))
        if params is None:
            return fixture(url.rsplit("/", 1)[-1])
        return fixture("incidents")

    with patch(
        "custom_components.pkr_zasahy.providers.firebrno.async_json", side_effect=fetch
    ):
        records = await provider.async_fetch_incidents(NOW)
        assert len(records) == 1  # Boundary duplicates are merged.
        await provider.async_fetch_incidents(NOW + timedelta(minutes=10))
    assert len([r for r in requests if r[1] is None]) == 3
    params = requests[3][1]
    assert ("krajId", "116") in params and ("okresId", "3702") in params
    assert len([key for key, _ in params if key == "stavIds"]) == 4
    assert datetime.fromisoformat(dict(params)["casOd"]) == NOW - timedelta(days=7)
    assert provider.history_start == NOW + timedelta(minutes=10) - timedelta(days=7)


async def test_older_open_closure_and_disappearance():
    provider = FireBrnoProvider(None, 116)
    provider.lookups = lookups()
    provider._loaded = NOW
    older = fixture("incidents")
    older[0]["casOhlaseni"] = "2026-10-01T10:00:00Z"
    closed = deepcopy(older)
    closed[0]["stavId"] = 510
    with patch.object(
        provider, "_query", new=AsyncMock(side_effect=[[], older, [], [], [], closed])
    ):
        first = await provider.async_fetch_incidents(NOW)
        assert len(first) == 1 and first[0].aktivni
        # Disappearance alone produces no closure record.
        assert await provider.async_fetch_incidents(NOW + timedelta(minutes=10)) == []
        # Next successful snapshot reports closure for the known old incident.
        third = await provider.async_fetch_incidents(NOW + timedelta(minutes=20))
        assert len(third) == 1 and third[0].aktivni is False
        assert rozdil({first[0].uid: first[0]}, third)[1]


async def test_lookup_failure_uses_valid_cache_but_not_empty_success():
    provider = FireBrnoProvider(None, 116)
    with patch(
        "custom_components.pkr_zasahy.providers.firebrno.async_json",
        side_effect=TimeoutError,
    ):
        with pytest.raises(TimeoutError):
            await provider.async_load_lookups(NOW)
        provider.lookups = lookups()
        await provider.async_load_lookups(NOW)
    assert provider.lookups == lookups()


async def test_unknown_lookup_refresh_is_bounded():
    provider = FireBrnoProvider(None, 116)
    provider.lookups = lookups()
    provider._loaded = NOW
    rows = fixture("incidents")
    rows[0]["typId"] = 9999
    with (
        patch.object(provider, "_query", new=AsyncMock(return_value=rows)),
        patch(
            "custom_components.pkr_zasahy.providers.firebrno.async_json",
            side_effect=lambda session, url: fixture(url.rsplit("/", 1)[-1]),
        ) as fetch,
    ):
        await provider.async_fetch_incidents(NOW)
        await provider.async_fetch_incidents(NOW + timedelta(minutes=10))
    assert fetch.call_count == 3


@pytest.mark.parametrize("unit", [None, 6203010])
async def test_unit_filter_is_applied_to_both_query_windows(unit):
    provider = FireBrnoProvider(None, 116, 3703, unit)
    provider.lookups = lookups()
    provider._loaded = NOW
    with patch(
        "custom_components.pkr_zasahy.providers.firebrno.async_json",
        return_value=fixture("incidents"),
    ) as fetch:
        await provider.async_fetch_incidents(NOW)
    assert fetch.call_count == 2
    for call in fetch.call_args_list:
        params = dict(call.args[2])
        assert params["krajId"] == "116" and params["okresId"] == "3703"
        if unit is not None:
            assert params["jednotkaId"] == str(unit)
        else:
            assert "jednotkaId" not in params


@pytest.mark.parametrize("payload", [None, {}, [{"id": "1", "nazev": "Invalid"}]])
async def test_unit_search_rejects_invalid_payloads(payload):
    from custom_components.pkr_zasahy.providers.firebrno import async_search_units

    with (
        patch(
            "custom_components.pkr_zasahy.providers.firebrno.async_json",
            return_value=payload,
        ),
        pytest.raises(ParseError),
    ):
        await async_search_units(None, "Tišnov")


async def test_unit_search_empty_and_matching_names():
    from custom_components.pkr_zasahy.providers.firebrno import async_search_units

    with patch(
        "custom_components.pkr_zasahy.providers.firebrno.async_json",
        side_effect=[[], fixture("jednotky")],
    ) as fetch:
        assert await async_search_units(None, "No match") == {}
        units = await async_search_units(None, "Tišnov")
    assert units[6203010]["nazev"] == "HS Tišnov"
    assert fetch.call_args.args[2] == {"term": "Tišnov"}
