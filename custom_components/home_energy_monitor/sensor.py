"""Sensors for Home Energy Monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CALCULATION_VERSION, DOMAIN, MODEL_NAME
from .coordinator import HomeEnergyCoordinator, HomeEnergySnapshot

SensorValue = float | int | str | date | datetime | None


@dataclass(frozen=True, kw_only=True)
class HomeEnergySensorDescription(SensorEntityDescription):
    """Describe a calculated or normalized sensor."""

    value_fn: Callable[[HomeEnergySnapshot], SensorValue]
    classification: str
    formula: str | None = None
    attrs_fn: Callable[[HomeEnergySnapshot], dict[str, Any]] | None = None


def _reconciliation_value(
    attribute: str,
) -> Callable[[HomeEnergySnapshot], SensorValue]:
    def value(snapshot: HomeEnergySnapshot) -> SensorValue:
        reconciliation = snapshot.reconciliation
        return getattr(reconciliation, attribute) if reconciliation else None

    return value


def _forecast_attrs(snapshot: HomeEnergySnapshot) -> dict[str, Any]:
    calculation = snapshot.calculation
    return {
        "central_minutes": calculation.battery_minutes_to_reserve,
        "conservative_minutes": calculation.battery_risk_minutes_to_reserve,
        "sample_count": calculation.battery_sample_count,
        "sample_span_minutes": round(calculation.battery_sample_span_minutes, 1),
        "forecast_valid": calculation.battery_forecast_valid,
        "capacity_kwh": snapshot.options.battery_capacity_kwh,
        "reserve_percent": snapshot.options.reserve_percent,
        "planning_discharge_kw": snapshot.options.planning_discharge_kw,
    }


def _reconciliation_attrs(snapshot: HomeEnergySnapshot) -> dict[str, Any]:
    reconciliation = snapshot.reconciliation
    if reconciliation is None:
        return {}
    return {
        "date": reconciliation.day.isoformat(),
        "srp_net_kwh": round(reconciliation.srp_net_kwh, 3),
        "eg4_import_kwh": round(reconciliation.eg4_import_kwh, 3),
        "eg4_export_kwh": round(reconciliation.eg4_export_kwh, 3),
        "eg4_net_kwh": round(reconciliation.eg4_net_kwh, 3),
        "tolerance_kwh": round(reconciliation.tolerance_kwh, 3),
        "matches": reconciliation.matches,
        "srp_hour_count": reconciliation.srp_hour_count,
        "method": "sum raw SRP hourly net states; compare with EG4 daily import minus export",
    }


SENSORS: tuple[HomeEnergySensorDescription, ...] = (
    HomeEnergySensorDescription(
        key="combined_solar_power",
        name="Combined solar power",
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Estimated",
        formula="EG4 PV DC power + local Enphase AC production; Tigo is excluded",
        value_fn=lambda s: s.calculation.combined_solar_power_w,
    ),
    HomeEnergySensorDescription(
        key="combined_ac_supply_power",
        name="Combined AC supply power",
        icon="mdi:home-lightning-bolt-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Derived",
        formula="EG4 AC power + local Enphase AC production",
        value_fn=lambda s: s.calculation.combined_ac_supply_power_w,
    ),
    HomeEnergySensorDescription(
        key="whole_home_load_estimate",
        name="Whole home load estimate",
        icon="mdi:home-lightning-bolt",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Derived",
        formula="EG4 Consumption Power + local Enphase production",
        value_fn=lambda s: s.calculation.whole_home_load_w,
        attrs_fn=lambda s: {
            "equivalent_formula": "EG4 AC + Enphase + signed grid - rectifier",
            "balance_residual_w": s.calculation.model_balance_residual_w,
            "balance_tolerance_w": s.calculation.model_tolerance_w,
            "backup_regular_split": "unavailable without an independent panel submeter",
        },
    ),
    HomeEnergySensorDescription(
        key="eg4_metered_load_power",
        name="EG4 metered load power",
        icon="mdi:meter-electric-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Measured",
        formula="EG4 vendor Consumption Power; excludes external Enphase correction",
        value_fn=lambda s: s.calculation.eg4_metered_load_w,
    ),
    HomeEnergySensorDescription(
        key="grid_net_power",
        name="Grid net power",
        icon="mdi:transmission-tower",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Measured",
        formula="EG4 whole-property grid CT; positive import, negative export",
        value_fn=lambda s: s.calculation.grid_net_w,
    ),
    HomeEnergySensorDescription(
        key="grid_import_power",
        name="Grid import power",
        icon="mdi:transmission-tower-import",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Derived",
        formula="max(EG4 signed grid power, 0)",
        value_fn=lambda s: s.calculation.grid_import_w,
    ),
    HomeEnergySensorDescription(
        key="grid_export_power",
        name="Grid export power",
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Derived",
        formula="max(-EG4 signed grid power, 0)",
        value_fn=lambda s: s.calculation.grid_export_w,
    ),
    HomeEnergySensorDescription(
        key="battery_net_power",
        name="Battery net power",
        icon="mdi:battery-sync",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Derived",
        formula="negative of EG4 battery power; positive discharge, negative charge",
        value_fn=lambda s: s.calculation.battery_net_w,
    ),
    HomeEnergySensorDescription(
        key="battery_soc",
        name="Battery SOC",
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        classification="Measured",
        value_fn=lambda s: s.calculation.battery_soc_percent,
    ),
    HomeEnergySensorDescription(
        key="battery_available_energy",
        name="Battery energy above reserve",
        icon="mdi:battery-high",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        classification="Estimated",
        formula="capacity × max(SOC - reserve, 0) / 100",
        value_fn=lambda s: s.calculation.battery_available_kwh,
    ),
    HomeEnergySensorDescription(
        key="battery_discharge_average_15m",
        name="Battery discharge average 15m",
        icon="mdi:battery-arrow-down-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Derived",
        formula="mean of valid battery-discharge samples in the trailing 15 minutes",
        value_fn=lambda s: s.calculation.average_battery_discharge_w,
        attrs_fn=_forecast_attrs,
    ),
    HomeEnergySensorDescription(
        key="battery_discharge_p80_15m",
        name="Battery discharge p80 15m",
        icon="mdi:chart-bell-curve-cumulative",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Derived",
        formula="80th percentile of valid battery-discharge samples in 15 minutes",
        value_fn=lambda s: s.calculation.p80_battery_discharge_w,
        attrs_fn=_forecast_attrs,
    ),
    HomeEnergySensorDescription(
        key="battery_minutes_to_reserve",
        name="Battery minutes to reserve",
        icon="mdi:battery-clock-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        classification="Estimated",
        formula="95% × energy above reserve / max(p80 discharge, planning load)",
        value_fn=lambda s: s.calculation.battery_risk_minutes_to_reserve,
        attrs_fn=_forecast_attrs,
    ),
    HomeEnergySensorDescription(
        key="battery_reserve_eta",
        name="Battery reserve ETA",
        icon="mdi:clock-alert-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        classification="Estimated",
        value_fn=lambda s: s.calculation.battery_reserve_eta,
        attrs_fn=_forecast_attrs,
    ),
    HomeEnergySensorDescription(
        key="combined_solar_energy",
        name="Combined solar energy",
        icon="mdi:solar-panel-large",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        classification="Estimated",
        formula="EG4 lifetime PV yield + local Envoy lifetime production",
        value_fn=lambda s: s.calculation.combined_solar_energy_kwh,
    ),
    HomeEnergySensorDescription(
        key="peak_minutes_remaining",
        name="Peak minutes remaining",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        classification="Derived",
        formula="remaining time in the active editable SRP schedule window",
        value_fn=lambda s: s.peak_minutes_remaining,
    ),
    HomeEnergySensorDescription(
        key="peak_strategy_status",
        name="Peak strategy status",
        icon="mdi:shield-home-outline",
        classification="Derived",
        value_fn=lambda s: s.calculation.peak_strategy_status,
        attrs_fn=lambda s: {
            "on_peak_import_threshold_kw": s.options.peak_import_threshold_kw,
            "issues": list(s.issues),
        },
    ),
    HomeEnergySensorDescription(
        key="source_health",
        name="Source health",
        icon="mdi:heart-pulse",
        classification="Derived",
        value_fn=lambda s: s.source_health,
        attrs_fn=lambda s: {
            "issues": list(s.issues),
            "source_ages_minutes": {
                key: round(value, 1) if value is not None else None
                for key, value in s.source_ages_minutes.items()
            },
        },
    ),
    HomeEnergySensorDescription(
        key="tigo_array_power",
        name="Tigo diagnostic array power",
        icon="mdi:solar-panel",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Measured",
        formula="Tigo view of the EG4 array; diagnostic only and never added to solar",
        value_fn=lambda s: s.tigo_power_w,
        attrs_fn=lambda s: {
            "reporting_modules": s.tigo_reporting_modules,
            "configured_modules": s.tigo_configured_modules,
            "cloud_age_minutes": s.tigo_cloud_age_minutes,
        },
    ),
    HomeEnergySensorDescription(
        key="tigo_aligned_eg4_power",
        name="Tigo sample aligned EG4 power",
        icon="mdi:timeline-clock-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        classification="Measured",
        formula="EG4 Recorder value nearest the Tigo cloud sample timestamp",
        value_fn=lambda s: s.tigo_aligned_eg4_power_w,
    ),
    HomeEnergySensorDescription(
        key="tigo_to_eg4_ratio",
        name="Tigo to EG4 ratio",
        icon="mdi:compare-horizontal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        classification="Derived",
        formula="timestamp-aligned Tigo power / EG4 PV power; diagnostic only",
        value_fn=lambda s: s.tigo_to_eg4_percent,
    ),
    HomeEnergySensorDescription(
        key="enphase_active_microinverters",
        name="Enphase active microinverters",
        icon="mdi:solar-panel-large",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="microinverters",
        suggested_display_precision=0,
        classification="Measured",
        value_fn=lambda s: s.enphase_active_microinverters,
    ),
    HomeEnergySensorDescription(
        key="srp_settled_net_energy",
        name="SRP settled net energy",
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        classification="Utility settled",
        formula="sum of raw SRP hourly net states for the latest common settled day",
        value_fn=_reconciliation_value("srp_net_kwh"),
        attrs_fn=_reconciliation_attrs,
    ),
    HomeEnergySensorDescription(
        key="eg4_same_day_net_energy",
        name="EG4 same day net energy",
        icon="mdi:meter-electric",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        classification="Derived",
        formula="same-day EG4 lifetime import change minus export change",
        value_fn=_reconciliation_value("eg4_net_kwh"),
        attrs_fn=_reconciliation_attrs,
    ),
    HomeEnergySensorDescription(
        key="grid_reconciliation_residual",
        name="Grid reconciliation residual",
        icon="mdi:scale-balance",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        classification="Utility settled",
        formula="EG4 CT net energy minus SRP revenue-meter net energy",
        value_fn=_reconciliation_value("residual_kwh"),
        attrs_fn=_reconciliation_attrs,
    ),
    HomeEnergySensorDescription(
        key="grid_reconciliation_date",
        name="Grid reconciliation date",
        icon="mdi:calendar-check-outline",
        device_class=SensorDeviceClass.DATE,
        classification="Utility settled",
        value_fn=_reconciliation_value("day"),
        attrs_fn=_reconciliation_attrs,
    ),
    HomeEnergySensorDescription(
        key="srp_current_demand",
        name="SRP current cycle demand",
        icon="mdi:chart-timeline-variant",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=1,
        classification="Utility settled",
        formula="delayed SRP billing-cycle value; not live power",
        value_fn=lambda s: s.current_srp_demand_kw,
        attrs_fn=lambda s: {"data_through": s.srp_data_through},
    ),
    HomeEnergySensorDescription(
        key="srp_billed_cycle_peak",
        name="SRP billed cycle peak",
        icon="mdi:finance",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=1,
        classification="Utility settled",
        formula="delayed highest billed on-peak half-hour",
        value_fn=lambda s: s.billed_srp_peak_kw,
        attrs_fn=lambda s: {"data_through": s.srp_data_through},
    ),
    HomeEnergySensorDescription(
        key="srp_bill_projection",
        name="SRP bill projection",
        icon="mdi:cash-clock",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        classification="Utility settled",
        value_fn=lambda s: s.srp_bill_projection_usd,
        attrs_fn=lambda s: {"data_through": s.srp_data_through},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up calculated sensors."""
    coordinator: HomeEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HomeEnergySensor(coordinator, entry, description) for description in SENSORS
    )


class HomeEnergySensor(CoordinatorEntity[HomeEnergyCoordinator], SensorEntity):
    """One normalized or calculated energy sensor."""

    entity_description: HomeEnergySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomeEnergyCoordinator,
        entry: ConfigEntry,
        description: HomeEnergySensorDescription,
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
    def native_value(self) -> SensorValue:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Keep diagnostic text visible; fail unavailable numeric inputs closed."""
        if not super().available:
            return False
        if self.entity_description.key in {"source_health", "peak_strategy_status"}:
            return True
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Explain provenance and quality on every entity."""
        description = self.entity_description
        attrs: dict[str, Any] = {
            "classification": description.classification,
            "calculation_version": CALCULATION_VERSION,
            "measurement_model": MODEL_NAME,
        }
        if description.formula:
            attrs["formula"] = description.formula
        if description.attrs_fn:
            attrs.update(description.attrs_fn(self.coordinator.data))
        return attrs
