"""Pure calculation models for Home Energy Monitor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from math import isfinite
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
    eg4_load_source_fresh: bool | None = None


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
    eg4_hour_count: int | None
    srp_duplicate_count: int
    gross_throughput_kwh: float
    net_residual_percent: float | None
    gross_residual_percent: float | None
    absolute_tolerance_kwh: float
    relative_tolerance_percent: float


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
    elif (
        shortfall
        and forecast_valid
        and inputs.battery_source_fresh
        and minutes_to_reserve is not None
        and inputs.peak_minutes_remaining is not None
        and minutes_to_reserve <= inputs.peak_minutes_remaining
    ):
        peak_status = "On peak — battery may reach reserve before peak ends"
    elif battery_net is not None and battery_net > 300.0:
        peak_status = "On peak — battery is supplementing the home"
    else:
        peak_status = "On peak — monitoring battery and grid"

    return LiveCalculation(
        combined_solar_power_w=combined_solar,
        combined_ac_supply_power_w=combined_ac,
        whole_home_load_w=whole_home,
        eg4_metered_load_w=(
            inputs.eg4_metered_load_w
            if (
                inputs.eg4_load_source_fresh
                if inputs.eg4_load_source_fresh is not None
                else inputs.model_sources_fresh
            )
            else None
        ),
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


def _local_date(timestamp: int | float) -> date:
    """Return the Arizona date for recorder seconds or WebSocket milliseconds."""
    seconds = float(timestamp)
    if abs(seconds) >= 100_000_000_000:
        seconds /= 1000.0
    return datetime.fromtimestamp(seconds, UTC).astimezone(PHOENIX).date()


def calculate_reconciliation(
    *,
    srp_hourly: list[dict[str, Any]],
    eg4_import_daily: list[dict[str, Any]] | None = None,
    eg4_export_daily: list[dict[str, Any]] | None = None,
    eg4_import_hourly: list[dict[str, Any]] | None = None,
    eg4_export_hourly: list[dict[str, Any]] | None = None,
    today: date | None = None,
    absolute_tolerance_kwh: float = 1.0,
    relative_tolerance_percent: float = 2.0,
) -> Reconciliation | None:
    """Compare raw SRP hourly net states with same-day EG4 CT counter changes.

    SRP external-statistic ``sum`` values are deliberately ignored. The source's
    raw hourly ``state`` is the billing-ledger interval value and can be grouped
    safely by the Arizona calendar day.
    """
    if (
        not isfinite(absolute_tolerance_kwh)
        or absolute_tolerance_kwh < 0
        or not isfinite(relative_tolerance_percent)
        or not 0 <= relative_tolerance_percent <= 100
    ):
        raise ValueError("Reconciliation tolerances must be finite and non-negative")
    today = today or datetime.now(PHOENIX).date()

    def hourly_values(
        rows: list[dict[str, Any]], key: str, *, non_negative: bool = False
    ) -> tuple[dict[date, dict[int, float]], dict[date, int]]:
        values: dict[date, dict[int, float]] = {}
        duplicates: dict[date, int] = {}
        invalid: set[date] = set()
        for row in rows:
            try:
                timestamp = float(row["start"])
                if abs(timestamp) >= 100_000_000_000:
                    timestamp /= 1000.0
                local = datetime.fromtimestamp(timestamp, UTC).astimezone(PHOENIX)
            except (KeyError, TypeError, ValueError, OverflowError, OSError):
                continue
            day = local.date()
            if day >= today:
                continue
            try:
                value = float(row[key])
            except (KeyError, TypeError, ValueError):
                invalid.add(day)
                continue
            if (
                not isfinite(value)
                or (non_negative and value < 0)
                or local.minute != 0
                or local.second != 0
                or local.microsecond != 0
            ):
                invalid.add(day)
                continue
            hours = values.setdefault(day, {})
            if local.hour in hours:
                duplicates[day] = duplicates.get(day, 0) + 1
                # Exact duplicate records are harmless; conflicting revisions
                # need a fresh settled read instead of an arbitrary winner.
                if hours[local.hour] != value:
                    invalid.add(day)
            else:
                hours[local.hour] = value
        return (
            {day: hours for day, hours in values.items() if day not in invalid},
            duplicates,
        )

    srp_by_day, srp_duplicates = hourly_values(srp_hourly, "state")

    def daily_changes(rows: list[dict[str, Any]]) -> dict[date, float]:
        values: dict[date, float] = {}
        invalid: set[date] = set()
        for row in rows:
            try:
                day = _local_date(row["start"])
                value = float(row["change"])
            except (KeyError, TypeError, ValueError, OverflowError, OSError):
                continue
            if not isfinite(value) or value < 0:
                invalid.add(day)
                continue
            if day < today:
                if day in values and values[day] != value:
                    invalid.add(day)
                values[day] = value
        return {day: value for day, value in values.items() if day not in invalid}

    hourly_eg4 = eg4_import_hourly is not None or eg4_export_hourly is not None
    if hourly_eg4:
        import_hours, _ = hourly_values(eg4_import_hourly or [], "change", non_negative=True)
        export_hours, _ = hourly_values(eg4_export_hourly or [], "change", non_negative=True)
        imports = {
            day: sum(hours.values()) for day, hours in import_hours.items() if len(hours) == 24
        }
        exports = {
            day: sum(hours.values()) for day, hours in export_hours.items() if len(hours) == 24
        }
    else:
        # Retain support for callers already holding day aggregates. The live
        # coordinator supplies hourly rows so both meters' coverage is checked.
        imports = daily_changes(eg4_import_daily or [])
        exports = daily_changes(eg4_export_daily or [])
    candidates = sorted(set(srp_by_day) & set(imports) & set(exports), reverse=True)
    for day in candidates:
        hourly = srp_by_day[day]
        if len(hourly) != 24:
            continue
        srp_net = sum(hourly.values())
        eg4_net = imports[day] - exports[day]
        residual = eg4_net - srp_net
        net_scale = max(abs(srp_net), abs(eg4_net))
        gross = imports[day] + exports[day]
        tolerance = max(absolute_tolerance_kwh, relative_tolerance_percent / 100.0 * net_scale)
        return Reconciliation(
            day=day,
            srp_net_kwh=srp_net,
            eg4_import_kwh=imports[day],
            eg4_export_kwh=exports[day],
            eg4_net_kwh=eg4_net,
            residual_kwh=residual,
            tolerance_kwh=tolerance,
            matches=abs(residual) <= tolerance + 1e-9,
            srp_hour_count=len(hourly),
            eg4_hour_count=24 if hourly_eg4 else None,
            srp_duplicate_count=srp_duplicates.get(day, 0),
            gross_throughput_kwh=gross,
            net_residual_percent=100.0 * residual / net_scale if net_scale else None,
            gross_residual_percent=100.0 * residual / gross if gross else None,
            absolute_tolerance_kwh=absolute_tolerance_kwh,
            relative_tolerance_percent=relative_tolerance_percent,
        )
    return None
