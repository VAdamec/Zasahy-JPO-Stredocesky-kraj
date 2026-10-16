"""Senzory zásahů JPO."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import PkrConfigEntry, PkrCoordinator, PkrData
from .models import Zasah


def _dnes(zasahy: list[Zasah]) -> list[Zasah]:
    today = dt_util.now().date()
    return [z for z in zasahy if dt_util.as_local(z.cas).date() == today]


def _aktivni(zasahy: list[Zasah]) -> list[Zasah]:
    return [z for z in zasahy if z.aktivni]


def _history(data: PkrData) -> list[Zasah]:
    return [
        z
        for z in data.zasahy
        if data.history_start is None or z.cas >= data.history_start
    ]


def _active_count(data: PkrData) -> int | None:
    if any(z.aktivni is None for z in data.zasahy):
        return None
    return len(_aktivni(data.zasahy))


def _active_attrs(data: PkrData) -> dict[str, Any]:
    attrs = _seznam(_aktivni(data.zasahy))
    unknown = [z.as_dict() for z in data.zasahy if z.aktivni is None]
    if unknown:
        attrs["neznamy_stav"] = unknown
    return attrs


def _seznam(zasahy: list[Zasah]) -> dict[str, Any]:
    return {"zasahy": [z.as_dict() for z in zasahy]}


def _posledni_attrs(zasahy: list[Zasah]) -> dict[str, Any]:
    if not zasahy:
        return {}
    data = zasahy[0].as_dict()
    data.pop("nazev")
    return data


@dataclass(frozen=True, kw_only=True)
class PkrSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PkrData], Any]
    attrs_fn: Callable[[PkrData], dict[str, Any]] | None = None


SENSORS: tuple[PkrSensorDescription, ...] = (
    PkrSensorDescription(
        key="dnes",
        translation_key="dnes",
        icon="mdi:fire-truck",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(_dnes(d.zasahy)),
        attrs_fn=lambda d: _seznam(_dnes(d.zasahy)),
    ),
    PkrSensorDescription(
        key="aktivni",
        translation_key="aktivni",
        icon="mdi:fire-alert",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_active_count,
        attrs_fn=_active_attrs,
    ),
    PkrSensorDescription(
        key="vse",
        translation_key="vse",
        icon="mdi:format-list-bulleted",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(_history(d)),
        attrs_fn=lambda d: _seznam(_history(d)),
    ),
    PkrSensorDescription(
        key="posledni",
        translation_key="posledni",
        icon="mdi:fire",
        value_fn=lambda d: d.zasahy[0].nazev[:255] if d.zasahy else None,
        attrs_fn=lambda d: _posledni_attrs(d.zasahy),
    ),
    PkrSensorDescription(
        key="posledni_cas",
        translation_key="posledni_cas",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.zasahy[0].cas if d.zasahy else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PkrConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PkrSensor(coordinator, desc) for desc in SENSORS)


class PkrSensor(CoordinatorEntity[PkrCoordinator], SensorEntity):
    """Senzor nad daty coordinatoru."""

    _attr_has_entity_name = True
    # Seznam zásahů v atributech by zbytečně nafukoval databázi recorderu
    _unrecorded_attributes = frozenset({"zasahy", "neznamy_stav"})
    entity_description: PkrSensorDescription

    def __init__(self, coordinator: PkrCoordinator, desc: PkrSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = desc
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=coordinator.provider.manufacturer,
            model=coordinator.provider.model,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.provider.url,
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn else None
