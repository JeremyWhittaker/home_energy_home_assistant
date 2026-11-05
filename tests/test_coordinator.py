"""Measurement-source selection, freshness, and Recorder failure regressions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import State
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_monitor import coordinator as coordinator_module
from custom_components.home_energy_monitor.const import DOMAIN
from custom_components.home_energy_monitor.coordinator import (
    HomeEnergyCoordinator,
    _energy_kwh,
    _power_w,
)
from custom_components.home_energy_monitor.discovery import SourceEntities
from custom_components.home_energy_monitor.sensor import (
    _enphase_attrs,
    _reconciliation_attrs,
    _tigo_comparison_attrs,
)


def state(entity_id, value, *, sampled_at=None, unit="W", attributes=None):
    """Build a source report whose measurement time can differ from retrieval time."""
    sampled_at = sampled_at or datetime.now(UTC)
    return State(
        entity_id,
        str(value),
        {"unit_of_measurement": unit, **(attributes or {})},
        last_changed=sampled_at,
        last_updated=sampled_at,
        last_reported=sampled_at,
    )


@pytest.fixture
def model(hass, monkeypatch):
    """A real coordinator with controlled integration state reports."""
    sources = SourceEntities(
        eg4_pv_power="sensor.eg4_pv",
        eg4_ac_power="sensor.eg4_ac",
        eg4_rectifier_power="sensor.eg4_rectifier",
        eg4_metered_load_power="sensor.eg4_load",
        eg4_grid_power="sensor.eg4_grid",
        eg4_battery_power="sensor.eg4_battery",
        eg4_battery_soc="sensor.eg4_soc",
        eg4_yield_lifetime="sensor.eg4_yield",
        eg4_grid_import_lifetime="sensor.eg4_import_total",
        eg4_grid_export_lifetime="sensor.eg4_export_total",
        enphase_power="sensor.envoy_power",
        enphase_lifetime="sensor.envoy_energy",
        enphase_cloud_power="sensor.enphase_cloud_power",
        tigo_power="sensor.tigo_power",
        tigo_last_cloud_update="sensor.tigo_sample",
    )
    entry = MockConfigEntry(domain=DOMAIN, data={"allow_enphase_cloud_power_fallback": True})
    entry.add_to_hass(hass)
    coordinator = HomeEnergyCoordinator(hass, entry, sources)
    reports: dict[str, State] = {}
    monkeypatch.setattr(coordinator, "_state", reports.get)
    return coordinator, reports


def cloud_report(now, *, age=timedelta(minutes=4), **changes):
    """The verified cloud integration's normal publication metadata."""
    attributes = {
        "source": "app-api:get_latest_power",
        "sampled_at_utc": (now - age).isoformat(),
        "freshness_reference_utc": (now - age).isoformat(),
        "using_stale": False,
        "using_cached": False,
    }
    attributes.update(changes)
    return state("sensor.enphase_cloud_power", 500, attributes=attributes)


@pytest.mark.parametrize(
    ("unit", "value", "expected"),
    [
        ("kW", "1.5", 1500),
        ("mW", "1000", 1),
        ("kWh", "1", None),
        ("", "1", None),
        ("W", "nan", None),
        ("W", "inf", None),
    ],
)
def test_power_rejects_unknown_units_and_nonfinite_reports(unit, value, expected):
    assert _power_w(state("sensor.power", value, unit=unit)) == expected


def test_cumulative_units_are_converted_without_guessing():
    assert _energy_kwh(state("sensor.energy", "1.5", unit="MWh")) == 1500
    assert _energy_kwh(state("sensor.energy", "1.5", unit="W")) is None
    assert _energy_kwh(state("sensor.energy", "nan", unit="kWh")) is None


async def test_local_enphase_is_selected_once_even_when_cloud_is_present(model):
    coordinator, reports = model
    now = datetime.now(UTC)
    reports["sensor.envoy_power"] = state("sensor.envoy_power", 1.25, unit="kW")
    reports["sensor.enphase_cloud_power"] = cloud_report(now)

    selected = coordinator._enphase_power(now)

    assert selected.power_w == 1250
    assert selected.entity_id == "sensor.envoy_power"
    assert selected.cloud_fallback is False


async def test_cloud_cannot_fill_outage_before_whole_array_equivalence_is_verified(model, hass):
    coordinator, reports = model
    now = datetime.now(UTC)
    reports["sensor.enphase_cloud_power"] = cloud_report(now)
    hass.config_entries.async_update_entry(coordinator.entry, data={})

    assert coordinator._enphase_power(now).power_w is None


@pytest.mark.parametrize(
    "changes",
    [
        {"using_stale": True},
        {"using_cached": True},
        {"source": "unverified-provider"},
        {"sampled_at_utc": "2026-11-04T12:00:00"},
        {"freshness_reference_utc": "invalid"},
        {"sampled_at_utc": None},
    ],
)
async def test_unverified_or_cached_cloud_never_fills_a_local_outage(model, changes):
    coordinator, reports = model
    now = datetime.now(UTC)
    reports["sensor.envoy_power"] = state("sensor.envoy_power", "unavailable")
    reports["sensor.enphase_cloud_power"] = cloud_report(now, **changes)

    selected = coordinator._enphase_power(now)

    assert selected.power_w is None
    assert selected.cloud_fallback is False


async def test_cloud_sample_time_not_recent_ha_retrieval_controls_expiry(model):
    coordinator, reports = model
    now = datetime.now(UTC)
    reports["sensor.enphase_cloud_power"] = cloud_report(now, age=timedelta(minutes=11))

    assert coordinator._enphase_power(now).power_w is None

    reports["sensor.enphase_cloud_power"] = cloud_report(now, age=timedelta(minutes=-2))
    assert coordinator._enphase_power(now).power_w is None


async def test_outage_fallback_is_estimated_and_never_splices_energy_counters(
    model, monkeypatch
):
    coordinator, reports = model
    now = datetime.now(UTC)
    powers = {
        "sensor.eg4_pv": 10000,
        "sensor.eg4_ac": 9500,
        "sensor.eg4_rectifier": 0,
        "sensor.eg4_load": 5500,
        "sensor.eg4_grid": -4000,
        "sensor.eg4_battery": 0,
    }
    reports.update({entity: state(entity, value) for entity, value in powers.items()})
    reports["sensor.eg4_soc"] = state("sensor.eg4_soc", 80, unit="%")
    reports["sensor.eg4_yield"] = state("sensor.eg4_yield", 1000, unit="kWh")
    reports["sensor.envoy_power"] = state("sensor.envoy_power", "unavailable")
    reports["sensor.envoy_energy"] = state("sensor.envoy_energy", "unavailable", unit="MWh")
    reports["sensor.enphase_cloud_power"] = cloud_report(now)
    monkeypatch.setattr(coordinator, "_async_refresh_reconciliation", AsyncMock())
    monkeypatch.setattr(coordinator, "_async_refresh_tigo_alignment", AsyncMock())

    snapshot = await coordinator._async_update_data()

    assert snapshot.calculation.combined_solar_power_w == 10500
    assert snapshot.calculation.whole_home_load_w == 6000
    assert snapshot.calculation.grid_export_w == 4000
    assert snapshot.calculation.combined_solar_energy_kwh is None
    assert snapshot.enphase_cloud_fallback is True
    assert snapshot.telemetry_healthy is False
    assert snapshot.source_health == "degraded"
    provenance = _enphase_attrs(snapshot)
    assert provenance["enphase_power_entity"] == "sensor.enphase_cloud_power"
    assert "Estimate" in provenance["power_quality"]

    # Local recovery returns to its original history/measurement family.
    reports["sensor.envoy_power"] = state("sensor.envoy_power", 0.75, unit="kW")
    reports["sensor.envoy_energy"] = state("sensor.envoy_energy", 2, unit="MWh")
    recovered = await coordinator._async_update_data()
    assert recovered.enphase_cloud_fallback is False
    assert recovered.enphase_power_entity == "sensor.envoy_power"
    assert recovered.calculation.combined_solar_power_w == 10750
    assert recovered.calculation.combined_solar_energy_kwh == 3000


async def test_tigo_comparison_expires_even_if_provider_timestamp_stays_unchanged(
    model, monkeypatch
):
    coordinator, reports = model
    now = datetime.now(UTC)
    sampled_at = now - timedelta(minutes=5)
    reports["sensor.tigo_power"] = state("sensor.tigo_power", 1000)
    reports["sensor.tigo_sample"] = state("sensor.tigo_sample", sampled_at.isoformat())
    eg4 = state("sensor.eg4_pv", 2000, sampled_at=sampled_at + timedelta(seconds=45))
    recorder = SimpleNamespace(
        async_add_executor_job=AsyncMock(return_value={"sensor.eg4_pv": [eg4]})
    )
    monkeypatch.setattr(coordinator_module, "get_instance", lambda _hass: recorder)

    await coordinator._async_refresh_tigo_alignment(now)
    assert coordinator._tigo_ratio_percent == 50
    assert coordinator._tigo_alignment_skew_seconds == 45
    assert coordinator._tigo_aligned_sample_at == sampled_at + timedelta(seconds=45)

    await coordinator._async_refresh_tigo_alignment(now + timedelta(minutes=41))
    assert coordinator._tigo_ratio_percent is None
    assert coordinator._tigo_aligned_eg4_w is None
    assert "stale" in coordinator._tigo_alignment_reason
    assert recorder.async_add_executor_job.await_count == 1


async def test_tigo_stops_publishing_previous_ratio_when_current_report_is_missing(
    model, monkeypatch
):
    coordinator, reports = model
    now = datetime.now(UTC)
    reports["sensor.tigo_power"] = state("sensor.tigo_power", 1000)
    reports["sensor.tigo_sample"] = state("sensor.tigo_sample", now.isoformat())
    recorder = SimpleNamespace(
        async_add_executor_job=AsyncMock(
            return_value={"sensor.eg4_pv": [state("sensor.eg4_pv", 2000)]}
        )
    )
    monkeypatch.setattr(coordinator_module, "get_instance", lambda _hass: recorder)
    await coordinator._async_refresh_tigo_alignment(now)
    assert coordinator._tigo_ratio_percent == 50

    reports["sensor.tigo_power"] = state("sensor.tigo_power", "unavailable")
    await coordinator._async_refresh_tigo_alignment(now + timedelta(minutes=1))
    assert coordinator._tigo_ratio_percent is None
    assert coordinator._tigo_aligned_sample_at is None


async def test_tigo_rejects_a_close_looking_ratio_when_time_skew_is_too_large(
    model, monkeypatch
):
    coordinator, reports = model
    now = datetime.now(UTC)
    reports["sensor.tigo_power"] = state("sensor.tigo_power", 1000)
    reports["sensor.tigo_sample"] = state("sensor.tigo_sample", now.isoformat())
    eg4 = state("sensor.eg4_pv", 1001, sampled_at=now - timedelta(minutes=4))
    recorder = SimpleNamespace(
        async_add_executor_job=AsyncMock(return_value={"sensor.eg4_pv": [eg4]})
    )
    monkeypatch.setattr(coordinator_module, "get_instance", lambda _hass: recorder)

    await coordinator._async_refresh_tigo_alignment(now)

    assert coordinator._tigo_ratio_percent is None
    assert coordinator._tigo_alignment_skew_seconds is None
    assert "three minutes" in coordinator._tigo_alignment_reason


async def test_reconciliation_failure_clears_previously_matching_comparison(model, monkeypatch):
    coordinator, _reports = model
    now = datetime(2026, 11, 4, 15, tzinfo=UTC)
    midnight = datetime(2026, 11, 3, 7, tzinfo=UTC)
    hours = [(midnight + timedelta(hours=hour)).timestamp() for hour in range(24)]
    metadata = {"srp_energy_monitor:test_energy_net": object()}
    srp = {"srp_energy_monitor:test_energy_net": [{"start": t, "state": 1} for t in hours]}
    eg4 = {
        "sensor.eg4_import_total": [{"start": t, "change": 2} for t in hours],
        "sensor.eg4_export_total": [{"start": t, "change": 1} for t in hours],
    }
    recorder = SimpleNamespace(
        async_add_executor_job=AsyncMock(side_effect=[metadata, srp, eg4])
    )
    monkeypatch.setattr(coordinator_module, "get_instance", lambda _hass: recorder)

    await coordinator._async_refresh_reconciliation(now)
    assert coordinator._reconciliation is not None
    assert coordinator._reconciliation.matches is True
    assert (
        _reconciliation_attrs(
            SimpleNamespace(
                reconciliation=coordinator._reconciliation,
                reconciliation_refreshed_at=coordinator._reconciliation_refreshed_at,
                reconciliation_error=coordinator._reconciliation_error,
            )
        )["eg4_hour_count"]
        == 24
    )

    recorder.async_add_executor_job = AsyncMock(
        side_effect=RuntimeError("Recorder unavailable")
    )
    await coordinator._async_refresh_reconciliation(now + timedelta(hours=5))
    assert coordinator._reconciliation is None
    assert coordinator._reconciliation_error is not None
    assert coordinator._reconciliation_refreshed_at == now


def test_tigo_provenance_includes_both_measurement_times():
    sample = datetime(2026, 11, 4, 22, tzinfo=UTC)
    attrs = _tigo_comparison_attrs(
        SimpleNamespace(
            tigo_sample_at=sample,
            tigo_aligned_sample_at=sample + timedelta(seconds=30),
            tigo_cloud_age_minutes=6,
            tigo_alignment_skew_seconds=30,
            tigo_alignment_reason="Comparable samples",
            tigo_to_eg4_percent=50,
        )
    )
    assert attrs["tigo_sample_at"] != attrs["eg4_sample_at"]
    assert attrs["alignment_skew_seconds"] == 30
    assert attrs["ratio_available"] is True


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        ("unavailable", "W"),
        ("unknown", "W"),
        ("nan", "W"),
        ("inf", "W"),
        ("100", "kWh"),
    ],
)
async def test_invalid_power_has_no_ha_report_age_even_when_republished(model, value, unit):
    coordinator, reports = model
    now = datetime.now(UTC)
    reports["sensor.eg4_battery"] = state(
        "sensor.eg4_battery", value, unit=unit, sampled_at=now
    )
    assert coordinator._age_minutes("sensor.eg4_battery", now) is None


@pytest.mark.parametrize("soc", ["unavailable", "nan", -1, 101])
async def test_invalid_soc_has_no_ha_report_age(model, soc):
    coordinator, reports = model
    now = datetime.now(UTC)
    reports["sensor.eg4_soc"] = state("sensor.eg4_soc", soc, unit="%", sampled_at=now)
    assert coordinator._age_minutes("sensor.eg4_soc", now) is None


async def test_valid_zero_retains_report_age_and_future_report_is_not_fresh(model):
    coordinator, reports = model
    now = datetime.now(UTC)
    reports["sensor.eg4_grid"] = state(
        "sensor.eg4_grid", 0, sampled_at=now - timedelta(minutes=2)
    )
    assert coordinator._age_minutes("sensor.eg4_grid", now) == 2
    reports["sensor.eg4_grid"] = state(
        "sensor.eg4_grid", 0, sampled_at=now + timedelta(minutes=2)
    )
    assert coordinator._age_minutes("sensor.eg4_grid", now) is None


async def test_soc_with_wrong_units_has_no_report_age(model):
    coordinator, reports = model
    now = datetime.now(UTC)
    reports["sensor.eg4_soc"] = state("sensor.eg4_soc", 80, unit="W", sampled_at=now)
    assert coordinator._age_minutes("sensor.eg4_soc", now) is None
