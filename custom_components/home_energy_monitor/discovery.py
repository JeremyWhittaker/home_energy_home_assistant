"""Semantic discovery of the existing energy integrations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er


class SourceDiscoveryError(RuntimeError):
    """Raised when a required logical source is absent or ambiguous."""


@dataclass(frozen=True, slots=True)
class SourceEntities:
    """Entity IDs grouped by their physical/logical role."""

    eg4_pv_power: str
    eg4_ac_power: str
    eg4_rectifier_power: str
    eg4_metered_load_power: str
    eg4_grid_power: str
    eg4_battery_power: str
    eg4_battery_soc: str
    eg4_yield_lifetime: str
    eg4_grid_import_lifetime: str
    eg4_grid_export_lifetime: str
    enphase_power: str
    enphase_lifetime: str
    enphase_service_status: str | None = None
    enphase_gateway_status: str | None = None
    enphase_active_microinverters: str | None = None
    eg4_runtime_data: str | None = None
    eg4_connection_lost: str | None = None
    eg4_bms_discharge_allowed: str | None = None
    tigo_power: str | None = None
    tigo_reporting_modules: str | None = None
    tigo_configured_modules: str | None = None
    tigo_cloud_age: str | None = None
    tigo_last_cloud_update: str | None = None
    srp_daily_net: str | None = None
    srp_current_demand: str | None = None
    srp_billed_cycle_peak: str | None = None
    srp_bill_projection: str | None = None

    @property
    def entity_ids(self) -> tuple[str, ...]:
        """Return every discovered entity ID."""
        return tuple(
            value
            for field in fields(self)
            if isinstance((value := getattr(self, field.name)), str)
        )


def _normalize(value: object) -> str:
    return str(value or "").strip().casefold()


def _is_eg4_inverter(device: dr.DeviceEntry | None) -> bool:
    return bool(
        device
        and _normalize(device.manufacturer) == "eg4 electronics"
        and _normalize(device.model) == "18kpv"
        and device.disabled_by is None
    )


def _is_eg4_battery(device: dr.DeviceEntry | None) -> bool:
    return bool(
        device
        and _normalize(device.manufacturer) == "eg4 electronics"
        and "battery bank" in _normalize(device.model)
        and device.disabled_by is None
    )


def _find(
    entries: Iterable[er.RegistryEntry],
    devices: dict[str, dr.DeviceEntry],
    *,
    platform: str,
    original_name: str,
    device_test: Callable[[dr.DeviceEntry | None], bool] | None = None,
    required: bool = True,
) -> str | None:
    matches = [
        entry.entity_id
        for entry in entries
        if entry.platform == platform
        and entry.disabled_by is None
        and _normalize(entry.original_name) == _normalize(original_name)
        and (
            device_test is None
            or device_test(devices.get(entry.device_id) if entry.device_id else None)
        )
    ]
    if len(matches) == 1:
        return matches[0]
    if not required and not matches:
        return None
    detail = ", ".join(matches) if matches else "none"
    kind = "required" if required else "optional"
    raise SourceDiscoveryError(
        f"Expected one enabled {kind} {platform} {original_name!r} entity; "
        f"found {len(matches)}: {detail}"
    )


def discover_sources(
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> SourceEntities:
    """Discover all sources without depending on serial-bearing entity IDs."""
    entries = list(entity_registry.entities.values())
    devices = dict(device_registry.devices)

    required_eg4 = {
        "eg4_pv_power": "PV Total Power",
        "eg4_ac_power": "AC Power",
        "eg4_rectifier_power": "Rectifier Power",
        "eg4_metered_load_power": "Consumption Power",
        "eg4_grid_power": "Grid Power",
        "eg4_battery_power": "Battery Power",
        "eg4_battery_soc": "State of Charge",
        "eg4_yield_lifetime": "Yield (Lifetime)",
        "eg4_grid_import_lifetime": "Grid Import (Lifetime)",
        "eg4_grid_export_lifetime": "Grid Export (Lifetime)",
    }
    values: dict[str, str | None] = {
        key: _find(
            entries,
            devices,
            platform="eg4_web_monitor",
            original_name=name,
            device_test=_is_eg4_inverter,
        )
        for key, name in required_eg4.items()
    }
    values.update(
        {
            "enphase_power": _find(
                entries,
                devices,
                platform="enphase_envoy",
                original_name="Current power production",
            ),
            "enphase_lifetime": _find(
                entries,
                devices,
                platform="enphase_envoy",
                original_name="Lifetime energy production",
            ),
            "eg4_runtime_data": _find(
                entries,
                devices,
                platform="eg4_web_monitor",
                original_name="Has Runtime Data",
                device_test=_is_eg4_inverter,
                required=False,
            ),
            "eg4_connection_lost": _find(
                entries,
                devices,
                platform="eg4_web_monitor",
                original_name="Connection Lost",
                device_test=_is_eg4_inverter,
                required=False,
            ),
            "eg4_bms_discharge_allowed": _find(
                entries,
                devices,
                platform="eg4_web_monitor",
                original_name="BMS Discharge Allowed",
                device_test=_is_eg4_battery,
                required=False,
            ),
        }
    )

    optional = {
        "enphase_service_status": ("enphase_ev", "Service Status"),
        "enphase_gateway_status": ("enphase_ev", "Gateway Status"),
        "enphase_active_microinverters": ("enphase_ev", "Active Microinverters"),
        "tigo_power": ("tigo_energy", "Current power"),
        "tigo_reporting_modules": ("tigo_energy", "Reporting modules"),
        "tigo_configured_modules": ("tigo_energy", "Configured modules"),
        "tigo_cloud_age": ("tigo_energy", "Cloud data age"),
        "tigo_last_cloud_update": ("tigo_energy", "Last cloud update"),
        "srp_daily_net": ("srp_energy_monitor", "Daily net energy"),
        "srp_current_demand": ("srp_energy_monitor", "Current demand"),
        "srp_billed_cycle_peak": ("srp_energy_monitor", "Billed cycle peak"),
        "srp_bill_projection": ("srp_energy_monitor", "Bill projection"),
    }
    values.update(
        {
            key: _find(
                entries,
                devices,
                platform=platform,
                original_name=name,
                required=False,
            )
            for key, (platform, name) in optional.items()
        }
    )
    return SourceEntities(**values)  # type: ignore[arg-type]
