"""Quality and risk binary sensors for Home Energy Monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CALCULATION_VERSION, DOMAIN, MODEL_NAME
from .coordinator import HomeEnergyCoordinator, HomeEnergySnapshot


@dataclass(frozen=True, kw_only=True)
class HomeEnergyBinaryDescription(BinarySensorEntityDescription):
    """Describe one model quality/risk flag."""

    value_fn: Callable[[HomeEnergySnapshot], bool]
    classification: str
    attrs_fn: Callable[[HomeEnergySnapshot], dict[str, Any]] | None = None


BINARY_SENSORS: tuple[HomeEnergyBinaryDescription, ...] = (
    HomeEnergyBinaryDescription(
        key="measurement_model_valid",
        name="Measurement model valid",
        icon="mdi:check-decagram-outline",
        value_fn=lambda s: s.calculation.model_valid,
        classification="Derived",
        attrs_fn=lambda s: {
            "balance_residual_w": s.calculation.model_balance_residual_w,
            "balance_tolerance_w": s.calculation.model_tolerance_w,
        },
    ),
    HomeEnergyBinaryDescription(
        key="telemetry_healthy",
        name="Telemetry healthy",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda s: s.telemetry_healthy,
        classification="Derived",
        attrs_fn=lambda s: {"issues": list(s.issues)},
    ),
    HomeEnergyBinaryDescription(
        key="tigo_module_problem",
        name="Tigo module problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda s: s.tigo_problem,
        classification="Measured",
        attrs_fn=lambda s: {
            "reporting_modules": s.tigo_reporting_modules,
            "configured_modules": s.tigo_configured_modules,
            "known_unavailable_position": "C4",
        },
    ),
    HomeEnergyBinaryDescription(
        key="enphase_system_problem",
        name="Enphase system problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda s: s.enphase_problem,
        classification="Measured",
        attrs_fn=lambda s: {
            "active_microinverters": s.enphase_active_microinverters,
            "known_zero_power_location": "Pool shade",
        },
    ),
    HomeEnergyBinaryDescription(
        key="srp_integration_available",
        name="SRP integration available",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda s: s.srp_available,
        classification="Utility settled",
        attrs_fn=lambda s: {"data_through": s.srp_data_through},
    ),
    HomeEnergyBinaryDescription(
        key="battery_at_reserve",
        name="Battery at reserve",
        icon="mdi:battery-alert-variant-outline",
        value_fn=lambda s: s.calculation.battery_at_reserve,
        classification="Derived",
        attrs_fn=lambda s: {
            "reserve_percent": s.options.reserve_percent,
            "soc_percent": s.calculation.battery_soc_percent,
        },
    ),
    HomeEnergyBinaryDescription(
        key="peak_forecast_shortfall",
        name="Peak forecast shortfall",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda s: s.calculation.peak_forecast_shortfall,
        classification="Estimated",
        attrs_fn=lambda s: {
            "minutes_to_reserve": s.calculation.battery_risk_minutes_to_reserve,
            "peak_minutes_remaining": s.peak_minutes_remaining,
            "forecast_valid": s.calculation.battery_forecast_valid,
        },
    ),
    HomeEnergyBinaryDescription(
        key="live_peak_import_risk",
        name="Live peak import risk",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda s: s.calculation.peak_import_risk,
        classification="Derived",
        attrs_fn=lambda s: {
            "grid_import_w": s.calculation.grid_import_w,
            "threshold_kw": s.options.peak_import_threshold_kw,
            "meaning": "live import can increase billed demand; SRP demand is delayed",
        },
    ),
    HomeEnergyBinaryDescription(
        key="grid_reconciliation_matches",
        name="Grid reconciliation matches",
        icon="mdi:scale-balance",
        value_fn=lambda s: bool(s.reconciliation and s.reconciliation.matches),
        classification="Utility settled",
        attrs_fn=lambda s: (
            {
                "date": s.reconciliation.day.isoformat(),
                "residual_kwh": s.reconciliation.residual_kwh,
                "tolerance_kwh": s.reconciliation.tolerance_kwh,
            }
            if s.reconciliation
            else {}
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up quality/risk binary sensors."""
    coordinator: HomeEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HomeEnergyBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSORS
    )


class HomeEnergyBinarySensor(CoordinatorEntity[HomeEnergyCoordinator], BinarySensorEntity):
    """One quality/risk flag."""

    entity_description: HomeEnergyBinaryDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomeEnergyCoordinator,
        entry: ConfigEntry,
        description: HomeEnergyBinaryDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"whole_home_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "whole_home")},
            name="Home Energy",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Local calculation",
            model="Whole-home energy model",
            sw_version=CALCULATION_VERSION,
        )

    @property
    def is_on(self) -> bool:
        """Return the current flag."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Explain provenance on every flag."""
        attrs: dict[str, Any] = {
            "classification": self.entity_description.classification,
            "calculation_version": CALCULATION_VERSION,
            "measurement_model": MODEL_NAME,
        }
        if self.entity_description.attrs_fn:
            attrs.update(self.entity_description.attrs_fn(self.coordinator.data))
        return attrs
