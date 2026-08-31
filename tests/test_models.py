"""Tests for the auditable energy calculations."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from custom_components.home_energy_monitor.models import (
    LiveInputs,
    LiveOptions,
    calculate_live,
    calculate_reconciliation,
)


def options() -> LiveOptions:
    """Return the commissioned defaults."""
    return LiveOptions(
        battery_capacity_kwh=28.0,
        reserve_percent=20.0,
        peak_import_threshold_kw=5.0,
        minimum_discharge_kw=0.3,
        planning_discharge_kw=7.0,
    )


def inputs(**changes: object) -> LiveInputs:
    """Return one synchronized live snapshot."""
    values: dict[str, object] = {
        "eg4_pv_w": 10_870.0,
        "eg4_ac_w": 10_403.0,
        "eg4_rectifier_w": 0.0,
        "eg4_metered_load_w": 3_913.0,
        "grid_net_w": -6_490.0,
        "battery_raw_w": 0.0,
        "battery_soc_percent": 100.0,
        "eg4_yield_lifetime_kwh": 37_600.7,
        "enphase_power_w": 3_563.0,
        "enphase_lifetime_kwh": 10_834.3,
        "model_sources_fresh": True,
        "solar_sources_fresh": True,
        "grid_source_fresh": True,
        "battery_source_fresh": True,
        "average_battery_discharge_w": None,
        "p80_battery_discharge_w": None,
        "battery_sample_count": 0,
        "battery_sample_span_minutes": 0.0,
        "on_peak": False,
        "peak_schedule_valid": True,
        "peak_minutes_remaining": None,
    }
    values.update(changes)
    return LiveInputs(**values)  # type: ignore[arg-type]


def test_whole_home_equation_and_signs() -> None:
    """Enphase corrects EG4's derived metered load without double counting Tigo."""
    result = calculate_live(
        inputs(),
        options(),
        now=datetime(2026, 8, 30, 20, 10, tzinfo=UTC),
    )

    assert result.model_valid is True
    assert result.model_balance_residual_w == 0
    assert result.combined_solar_power_w == 14_433
    assert result.combined_ac_supply_power_w == 13_966
    assert result.whole_home_load_w == 7_476
    assert result.grid_import_w == 0
    assert result.grid_export_w == 6_490
    assert result.battery_net_w == 0
    assert result.combined_solar_energy_kwh == pytest.approx(48_435.0)


def test_rectifier_is_part_of_certified_identity() -> None:
    """Grid charging is removed from load using EG4 Rectifier Power."""
    result = calculate_live(
        inputs(
            eg4_ac_w=0.0,
            eg4_rectifier_w=2_000.0,
            eg4_metered_load_w=4_000.0,
            grid_net_w=6_000.0,
            enphase_power_w=0.0,
        ),
        options(),
    )

    assert result.model_valid is True
    assert result.model_balance_residual_w == 0
    assert result.whole_home_load_w == 4_000


def test_invalid_balance_fails_closed() -> None:
    """A materially inconsistent source does not become a plausible load."""
    result = calculate_live(inputs(grid_net_w=-4_000.0), options())

    assert result.model_valid is False
    assert result.whole_home_load_w is None
    assert result.combined_ac_supply_power_w is None


def test_missing_enphase_never_becomes_zero() -> None:
    """Partial telemetry is unavailable instead of under-reporting the home."""
    result = calculate_live(inputs(enphase_power_w=None), options())

    assert result.combined_solar_power_w is None
    assert result.whole_home_load_w is None
    assert result.model_valid is False


def test_conservative_battery_forecast_flags_peak_shortfall() -> None:
    """The risk ETA uses the commissioned 7 kW planning floor."""
    now = datetime(2026, 8, 30, 1, 0, tzinfo=UTC)
    result = calculate_live(
        inputs(
            battery_raw_w=-5_900.0,
            battery_soc_percent=50.0,
            average_battery_discharge_w=5_900.0,
            p80_battery_discharge_w=6_500.0,
            battery_sample_count=8,
            battery_sample_span_minutes=12.0,
            on_peak=True,
            peak_minutes_remaining=90.0,
            grid_net_w=0.0,
            eg4_metered_load_w=10_403.0,
        ),
        options(),
        now=now,
    )

    assert result.battery_available_kwh == pytest.approx(8.4)
    assert result.battery_minutes_to_reserve == pytest.approx(85.42, rel=0.01)
    assert result.battery_risk_minutes_to_reserve == pytest.approx(68.4, rel=0.01)
    assert result.battery_reserve_eta is not None
    assert result.peak_forecast_shortfall is True


def test_forecast_requires_sample_coverage() -> None:
    """A handful of samples cannot claim an ETA."""
    result = calculate_live(
        inputs(
            battery_raw_w=-7_000.0,
            battery_soc_percent=50.0,
            average_battery_discharge_w=7_000.0,
            p80_battery_discharge_w=7_000.0,
            battery_sample_count=4,
            battery_sample_span_minutes=7.9,
            on_peak=True,
            peak_minutes_remaining=90.0,
        ),
        options(),
    )

    assert result.battery_forecast_valid is False
    assert result.battery_minutes_to_reserve is None
    assert result.battery_risk_minutes_to_reserve is None
    assert result.peak_forecast_shortfall is False


def test_exact_reserve_is_detected() -> None:
    """The inverter's exact 20% floor must not repeat the legacy <20 bug."""
    result = calculate_live(
        inputs(battery_soc_percent=20.0, on_peak=True),
        options(),
    )

    assert result.battery_at_reserve is True
    assert result.battery_minutes_to_reserve == 0


def test_stale_enphase_does_not_suppress_battery_or_grid_alerts() -> None:
    """Independent critical feeds remain usable when solar/model data is stale."""
    result = calculate_live(
        inputs(
            model_sources_fresh=False,
            solar_sources_fresh=False,
            battery_soc_percent=20.0,
            grid_net_w=6_000.0,
            on_peak=True,
        ),
        options(),
    )

    assert result.model_valid is False
    assert result.combined_solar_power_w is None
    assert result.battery_at_reserve is True
    assert result.battery_soc_percent == 20.0
    assert result.grid_import_w == 6_000.0
    assert result.peak_import_risk is True


def test_stale_battery_does_not_invalidate_whole_home_model() -> None:
    """Whole-home load and grid remain available when only battery data is stale."""
    result = calculate_live(inputs(battery_source_fresh=False), options())

    assert result.model_valid is True
    assert result.whole_home_load_w == 7_476.0
    assert result.grid_export_w == 6_490.0
    assert result.battery_soc_percent is None
    assert result.battery_at_reserve is False


def _row(day: int, *, state: float | None = None, change: float | None = None):
    # statistics_during_period() returns epoch seconds inside Home Assistant.
    timestamp = datetime(2026, 8, day, 7, tzinfo=UTC).timestamp()
    return {"start": timestamp, "state": state, "change": change}


def test_reconciliation_uses_raw_hourly_state_not_corruptible_sum() -> None:
    """Latest complete Arizona day compares like-for-like meter net."""
    phoenix_midnight_utc = datetime(2026, 8, 27, 7, tzinfo=UTC)
    srp = [
        {
            "start": (phoenix_midnight_utc + timedelta(hours=hour)).timestamp(),
            "state": 6.0,
            "sum": 999_999.0,
        }
        for hour in range(24)
    ]
    result = calculate_reconciliation(
        srp_hourly=srp,
        eg4_import_daily=[_row(27, change=180.0)],
        eg4_export_daily=[_row(27, change=36.0)],
        today=date(2026, 8, 30),
    )

    assert result is not None
    assert result.day == date(2026, 8, 27)
    assert result.srp_net_kwh == 144.0
    assert result.eg4_net_kwh == 144.0
    assert result.residual_kwh == 0
    assert result.matches is True


def test_reconciliation_defensively_accepts_websocket_milliseconds() -> None:
    """A diagnostics/API payload in milliseconds cannot collapse into 1970."""
    midnight = datetime(2026, 8, 27, 7, tzinfo=UTC)
    result = calculate_reconciliation(
        srp_hourly=[
            {
                "start": (midnight + timedelta(hours=hour)).timestamp() * 1000,
                "state": 1.0,
            }
            for hour in range(24)
        ],
        eg4_import_daily=[
            {"start": midnight.timestamp() * 1000, "change": 30.0}
        ],
        eg4_export_daily=[
            {"start": midnight.timestamp() * 1000, "change": 6.0}
        ],
        today=date(2026, 8, 30),
    )

    assert result is not None
    assert result.day == date(2026, 8, 27)
    assert result.residual_kwh == 0


def test_reconciliation_rejects_partial_srp_day() -> None:
    """A telemetry gap cannot masquerade as a low meter day."""
    result = calculate_reconciliation(
        srp_hourly=[_row(27, state=1.0) for _ in range(19)],
        eg4_import_daily=[_row(27, change=50.0)],
        eg4_export_daily=[_row(27, change=5.0)],
        today=date(2026, 8, 30),
    )

    assert result is None
