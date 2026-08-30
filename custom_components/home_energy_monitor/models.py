"""Pure calculation models for Home Energy Monitor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

PHOENIX = ZoneInfo("America/Phoenix")


@dataclass(frozen=True, slots=True)
class LiveInputs:
    """Normalized source measurements."""

    eg4_pv_w: float | None
    eg4_ac_w: float | None
    eg4_rectifier_w: float | None
    eg4_metered_load_w: float | None
    grid_net_w: float | None
    battery_raw_w: float | None
    battery_soc_percent: float | None
    eg4_yield_lifetime_kwh: float | None
    enphase_power_w: float | None
    enphase_lifetime_kwh: float | None
    model_sources_fresh: bool
    solar_sources_fresh: bool
    grid_source_fresh: bool
    battery_source_fresh: bool
    average_battery_discharge_w: float | None
    p80_battery_discharge_w: float | None
    battery_sample_count: int
    battery_sample_span_minutes: float
    on_peak: bool | None
    peak_schedule_valid: bool | None
    peak_minutes_remaining: float | None


@dataclass(frozen=True, slots=True)
class LiveOptions:
    """User-tunable calculation settings."""

    battery_capacity_kwh: float
    reserve_percent: float
    peak_import_threshold_kw: float
    minimum_discharge_kw: float
    planning_discharge_kw: float


@dataclass(frozen=True, slots=True)
class LiveCalculation:
    """Derived whole-home state."""

    combined_solar_power_w: float | None
    combined_ac_supply_power_w: float | None
    whole_home_load_w: float | None
    eg4_metered_load_w: float | None
    grid_net_w: float | None
    grid_import_w: float | None
    grid_export_w: float | None
    battery_net_w: float | None
    battery_soc_percent: float | None
    battery_available_kwh: float | None
    average_battery_discharge_w: float | None
    p80_battery_discharge_w: float | None
    battery_sample_count: int
    battery_sample_span_minutes: float
    battery_forecast_valid: bool
    battery_minutes_to_reserve: float | None
    battery_risk_minutes_to_reserve: float | None
    battery_reserve_eta: datetime | None
    combined_solar_energy_kwh: float | None
    model_balance_residual_w: float | None
    model_tolerance_w: float | None
    model_valid: bool
    battery_at_reserve: bool
    peak_forecast_shortfall: bool
    peak_import_risk: bool
    peak_strategy_status: str


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """One settled calendar-day comparison."""

    day: date
    srp_net_kwh: float
    eg4_import_kwh: float
    eg4_export_kwh: float
    eg4_net_kwh: float
    residual_kwh: float
    tolerance_kwh: float
    matches: bool
    srp_hour_count: int


def calculate_live(
    inputs: LiveInputs,
    options: LiveOptions,
    *,
    now: datetime | None = None,
) -> LiveCalculation:
    """Calculate the live model without converting missing data to zero."""
    now = now or datetime.now(UTC)
    core = (
        inputs.eg4_ac_w,
        inputs.eg4_rectifier_w,
        inputs.eg4_metered_load_w,
        inputs.grid_net_w,
        inputs.enphase_power_w,
    )
    complete = inputs.model_sources_fresh and all(value is not None for value in core)

    balance_residual: float | None = None
    tolerance: float | None = None
    model_valid = False
    combined_ac: float | None = None
    whole_home: float | None = None
    if complete:
        assert inputs.eg4_ac_w is not None
        assert inputs.eg4_rectifier_w is not None
        assert inputs.eg4_metered_load_w is not None
        assert inputs.grid_net_w is not None
        assert inputs.enphase_power_w is not None
        balance_residual = (
            inputs.eg4_ac_w
            + inputs.grid_net_w
            - inputs.eg4_rectifier_w
            - inputs.eg4_metered_load_w
        )
        tolerance = max(
            100.0,
            0.03
            * max(
                abs(inputs.eg4_ac_w),
                abs(inputs.grid_net_w),
                abs(inputs.eg4_metered_load_w),
                1000.0,
            ),
        )
        candidate = (
            inputs.eg4_ac_w
            + inputs.enphase_power_w
            + inputs.grid_net_w
            - inputs.eg4_rectifier_w
        )
        model_valid = abs(balance_residual) <= tolerance and candidate >= -100.0
        if model_valid:
            combined_ac = inputs.eg4_ac_w + inputs.enphase_power_w
            whole_home = max(0.0, candidate)

    combined_solar = None
    if (
        inputs.solar_sources_fresh
        and inputs.eg4_pv_w is not None
        and inputs.enphase_power_w is not None
    ):
        combined_solar = inputs.eg4_pv_w + inputs.enphase_power_w

    combined_energy = None
    if inputs.eg4_yield_lifetime_kwh is not None and inputs.enphase_lifetime_kwh is not None:
        combined_energy = inputs.eg4_yield_lifetime_kwh + inputs.enphase_lifetime_kwh

    grid_import = (
        None
        if not inputs.grid_source_fresh or inputs.grid_net_w is None
        else max(inputs.grid_net_w, 0.0)
    )
    grid_export = (
        None
        if not inputs.grid_source_fresh or inputs.grid_net_w is None
        else max(-inputs.grid_net_w, 0.0)
    )
    battery_net = (
        None
        if not inputs.battery_source_fresh or inputs.battery_raw_w is None
        else -inputs.battery_raw_w
    )

    available_kwh = None
    at_reserve = False
    if inputs.battery_source_fresh and inputs.battery_soc_percent is not None:
        at_reserve = inputs.battery_soc_percent <= options.reserve_percent + 0.05
        available_kwh = max(
            0.0,
            (inputs.battery_soc_percent - options.reserve_percent)
            / 100.0
            * options.battery_capacity_kwh,
        )

    minutes_to_reserve = None
    risk_minutes_to_reserve = None
    reserve_eta = None
    average_discharge = inputs.average_battery_discharge_w
    p80_discharge = inputs.p80_battery_discharge_w
    forecast_valid = (
        inputs.battery_sample_count >= 5
        and inputs.battery_sample_span_minutes >= 8.0
        and average_discharge is not None
        and p80_discharge is not None
    )
    if available_kwh == 0.0 and inputs.battery_soc_percent is not None:
        minutes_to_reserve = 0.0
        risk_minutes_to_reserve = 0.0
        reserve_eta = now
    elif (
        available_kwh is not None
        and forecast_valid
        and average_discharge is not None
        and average_discharge >= options.minimum_discharge_kw * 1000.0
    ):
        minutes_to_reserve = 60.0 * available_kwh / (average_discharge / 1000.0)
        planning_w = max(
            p80_discharge or 0.0,
            options.planning_discharge_kw * 1000.0,
        )
        risk_minutes_to_reserve = 60.0 * 0.95 * available_kwh / (planning_w / 1000.0)
        reserve_eta = now + timedelta(minutes=risk_minutes_to_reserve)

    schedule_ready = inputs.peak_schedule_valid is True
    on_peak = inputs.on_peak is True
    shortfall = bool(
        schedule_ready
        and on_peak
        and risk_minutes_to_reserve is not None
        and inputs.peak_minutes_remaining is not None
        and risk_minutes_to_reserve <= inputs.peak_minutes_remaining
    )
    import_risk = bool(
        schedule_ready
        and on_peak
        and grid_import is not None
        and grid_import >= options.peak_import_threshold_kw * 1000.0
    )

    if inputs.peak_schedule_valid is False:
        peak_status = "Schedule invalid — fail-safe attention required"
    elif inputs.on_peak is None or inputs.peak_schedule_valid is None:
        peak_status = "Peak schedule unavailable"
    elif not on_peak:
        peak_status = "Off peak"
    elif import_risk and at_reserve:
        peak_status = "On peak — importing after battery reserve"
    elif import_risk:
        peak_status = "On peak — sustained import can raise billed demand"
    elif shortfall:
        peak_status = "On peak — battery may reach reserve before peak ends"
    elif battery_net is not None and battery_net > 300.0:
        peak_status = "On peak — battery is supplementing the home"
    else:
        peak_status = "On peak — monitoring battery and grid"

    return LiveCalculation(
        combined_solar_power_w=combined_solar,
        combined_ac_supply_power_w=combined_ac,
        whole_home_load_w=whole_home,
        eg4_metered_load_w=(inputs.eg4_metered_load_w if inputs.model_sources_fresh else None),
        grid_net_w=inputs.grid_net_w if inputs.grid_source_fresh else None,
        grid_import_w=grid_import,
        grid_export_w=grid_export,
        battery_net_w=battery_net,
        battery_soc_percent=(
            inputs.battery_soc_percent if inputs.battery_source_fresh else None
        ),
        battery_available_kwh=available_kwh,
        average_battery_discharge_w=(
            average_discharge if inputs.battery_source_fresh else None
        ),
        p80_battery_discharge_w=(p80_discharge if inputs.battery_source_fresh else None),
        battery_sample_count=inputs.battery_sample_count,
        battery_sample_span_minutes=inputs.battery_sample_span_minutes,
        battery_forecast_valid=forecast_valid and inputs.battery_source_fresh,
        battery_minutes_to_reserve=minutes_to_reserve,
        battery_risk_minutes_to_reserve=risk_minutes_to_reserve,
        battery_reserve_eta=reserve_eta,
        combined_solar_energy_kwh=combined_energy,
        model_balance_residual_w=balance_residual,
        model_tolerance_w=tolerance,
        model_valid=model_valid,
        battery_at_reserve=at_reserve,
        peak_forecast_shortfall=shortfall,
        peak_import_risk=import_risk,
        peak_strategy_status=peak_status,
    )


def _local_date(timestamp_ms: int | float) -> date:
    return datetime.fromtimestamp(float(timestamp_ms) / 1000.0, UTC).astimezone(PHOENIX).date()


def calculate_reconciliation(
    *,
    srp_hourly: list[dict[str, Any]],
    eg4_import_daily: list[dict[str, Any]],
    eg4_export_daily: list[dict[str, Any]],
    today: date | None = None,
) -> Reconciliation | None:
    """Compare raw SRP hourly net states with same-day EG4 CT counter changes.

    SRP external-statistic ``sum`` values are deliberately ignored. The source's
    raw hourly ``state`` is the billing-ledger interval value and can be grouped
    safely by the Arizona calendar day.
    """
    today = today or datetime.now(PHOENIX).date()
    srp_by_day: dict[date, list[float]] = {}
    for row in srp_hourly:
        try:
            day = _local_date(row["start"])
            value = float(row["state"])
        except (KeyError, TypeError, ValueError):
            continue
        if day < today:
            srp_by_day.setdefault(day, []).append(value)

    def daily_changes(rows: list[dict[str, Any]]) -> dict[date, float]:
        values: dict[date, float] = {}
        for row in rows:
            try:
                day = _local_date(row["start"])
                value = float(row["change"])
            except (KeyError, TypeError, ValueError):
                continue
            if day < today:
                values[day] = value
        return values

    imports = daily_changes(eg4_import_daily)
    exports = daily_changes(eg4_export_daily)
    candidates = sorted(set(srp_by_day) & set(imports) & set(exports), reverse=True)
    for day in candidates:
        hourly = srp_by_day[day]
        if len(hourly) < 20:
            continue
        srp_net = sum(hourly)
        eg4_net = imports[day] - exports[day]
        residual = eg4_net - srp_net
        tolerance = max(1.0, 0.05 * (abs(imports[day]) + abs(exports[day])))
        return Reconciliation(
            day=day,
            srp_net_kwh=srp_net,
            eg4_import_kwh=imports[day],
            eg4_export_kwh=exports[day],
            eg4_net_kwh=eg4_net,
            residual_kwh=residual,
            tolerance_kwh=tolerance,
            matches=abs(residual) <= tolerance,
            srp_hour_count=len(hourly),
        )
    return None
