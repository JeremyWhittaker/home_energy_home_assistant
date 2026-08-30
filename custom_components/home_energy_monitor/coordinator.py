"""Live aggregation and historical reconciliation coordinator."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from functools import partial
from statistics import mean

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.statistics import (
    get_metadata,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BATTERY_MINIMUM_SAMPLE_SPAN,
    BATTERY_SMOOTHING_WINDOW,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_RESERVE_PERCENT,
    CONF_MIN_DISCHARGE_KW,
    CONF_PEAK_IMPORT_THRESHOLD_KW,
    CONF_PLANNING_DISCHARGE_KW,
    DEFAULT_BATTERY_CAPACITY_KWH,
    DEFAULT_BATTERY_RESERVE_PERCENT,
    DEFAULT_MIN_DISCHARGE_KW,
    DEFAULT_PEAK_IMPORT_THRESHOLD_KW,
    DEFAULT_PLANNING_DISCHARGE_KW,
    DOMAIN,
    EG4_STALE_AFTER,
    ENPHASE_STALE_AFTER,
    HELPER_BATTERY_CAPACITY,
    HELPER_BATTERY_RESERVE,
    HELPER_PEAK_IMPORT_THRESHOLD,
    HELPER_PLANNING_DISCHARGE,
    PEAK_ON,
    PEAK_SCHEDULE_VALID,
    PEAK_SUMMER_END,
    PEAK_SUMMER_END_MONTH,
    PEAK_SUMMER_START,
    PEAK_SUMMER_START_MONTH,
    PEAK_WINTER_1_END,
    PEAK_WINTER_1_START,
    PEAK_WINTER_2_END,
    PEAK_WINTER_2_START,
    RECONCILIATION_INTERVAL,
    TIGO_STALE_AFTER,
    UNKNOWN_STATES,
    UPDATE_INTERVAL,
)
from .discovery import SourceEntities
from .models import (
    LiveCalculation,
    LiveInputs,
    LiveOptions,
    Reconciliation,
    calculate_live,
    calculate_reconciliation,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HomeEnergySnapshot:
    """All values exposed by this integration."""

    calculation: LiveCalculation
    reconciliation: Reconciliation | None
    source_health: str
    telemetry_healthy: bool
    source_ages_minutes: dict[str, float | None]
    issues: tuple[str, ...]
    tigo_power_w: float | None
    tigo_reporting_modules: int | None
    tigo_configured_modules: int | None
    tigo_cloud_age_minutes: float | None
    tigo_aligned_eg4_power_w: float | None
    tigo_to_eg4_percent: float | None
    tigo_problem: bool
    enphase_problem: bool
    enphase_active_microinverters: int | None
    srp_available: bool
    srp_data_through: str | None
    current_srp_demand_kw: float | None
    billed_srp_peak_kw: float | None
    srp_bill_projection_usd: float | None
    peak_minutes_remaining: float | None
    options: LiveOptions


def _percentile_80(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * 0.8)]


def _state_time(state: State) -> datetime:
    return getattr(state, "last_reported", None) or state.last_updated


def _is_valid_state(state: State | None) -> bool:
    return bool(state and state.state.strip().casefold() not in UNKNOWN_STATES)


def _to_number(state: State | None) -> float | None:
    if not _is_valid_state(state):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _power_w(state: State | None) -> float | None:
    value = _to_number(state)
    if value is None:
        return None
    unit = str(state.attributes.get("unit_of_measurement", "W")).casefold()
    factors = {"w": 1.0, "kw": 1000.0, "mw": 1_000_000.0}
    return value * factors.get(unit, 1.0)


def _energy_kwh(state: State | None) -> float | None:
    value = _to_number(state)
    if value is None:
        return None
    unit = str(state.attributes.get("unit_of_measurement", "kWh")).casefold()
    factors = {"wh": 0.001, "kwh": 1.0, "mwh": 1000.0}
    return value * factors.get(unit, 1.0)


def _bool_state(state: State | None) -> bool | None:
    if not _is_valid_state(state):
        return None
    value = state.state.strip().casefold()
    if value in {"on", "true", "yes", "1", "allowed"}:
        return True
    if value in {"off", "false", "no", "0", "blocked"}:
        return False
    return None


def _parse_time(state: State | None) -> time | None:
    if not _is_valid_state(state):
        return None
    try:
        return time.fromisoformat(state.state)
    except ValueError:
        return None


def _contains(current: time, start: time, end: time) -> bool:
    if start < end:
        return start <= current < end
    return current >= start or current < end


class HomeEnergyCoordinator(DataUpdateCoordinator[HomeEnergySnapshot]):
    """Read existing integrations and publish one coherent energy model."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        sources: SourceEntities,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self.sources = sources
        self._battery_samples: deque[tuple[datetime, float]] = deque()
        self._last_battery_report: datetime | None = None
        self._last_reconciliation_update: datetime | None = None
        self._reconciliation: Reconciliation | None = None
        self._last_tigo_sample: str | None = None
        self._tigo_aligned_eg4_w: float | None = None
        self._tigo_ratio_percent: float | None = None

    def _state(self, entity_id: str | None) -> State | None:
        return self.hass.states.get(entity_id) if entity_id else None

    def _option(self, helper: str, key: str, default: float) -> float:
        helper_value = _to_number(self._state(helper))
        if helper_value is not None:
            return helper_value
        value = self.entry.options.get(key, self.entry.data.get(key, default))
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _options(self) -> LiveOptions:
        return LiveOptions(
            battery_capacity_kwh=self._option(
                HELPER_BATTERY_CAPACITY,
                CONF_BATTERY_CAPACITY_KWH,
                DEFAULT_BATTERY_CAPACITY_KWH,
            ),
            reserve_percent=self._option(
                HELPER_BATTERY_RESERVE,
                CONF_BATTERY_RESERVE_PERCENT,
                DEFAULT_BATTERY_RESERVE_PERCENT,
            ),
            peak_import_threshold_kw=self._option(
                HELPER_PEAK_IMPORT_THRESHOLD,
                CONF_PEAK_IMPORT_THRESHOLD_KW,
                DEFAULT_PEAK_IMPORT_THRESHOLD_KW,
            ),
            minimum_discharge_kw=float(
                self.entry.options.get(
                    CONF_MIN_DISCHARGE_KW,
                    self.entry.data.get(CONF_MIN_DISCHARGE_KW, DEFAULT_MIN_DISCHARGE_KW),
                )
            ),
            planning_discharge_kw=self._option(
                HELPER_PLANNING_DISCHARGE,
                CONF_PLANNING_DISCHARGE_KW,
                DEFAULT_PLANNING_DISCHARGE_KW,
            ),
        )

    def _age_minutes(self, entity_id: str | None, now: datetime) -> float | None:
        state = self._state(entity_id)
        if state is None:
            return None
        return max(0.0, (now - _state_time(state)).total_seconds() / 60.0)

    def _fresh(self, entity_id: str | None, now: datetime, maximum: timedelta) -> bool:
        state = self._state(entity_id)
        return bool(
            _is_valid_state(state) and state is not None and now - _state_time(state) <= maximum
        )

    def _peak_minutes_remaining(self, now: datetime) -> float | None:
        if _bool_state(self._state(PEAK_ON)) is not True:
            return None
        if _bool_state(self._state(PEAK_SCHEDULE_VALID)) is not True:
            return None
        local = dt_util.as_local(now)
        start_month = int(_to_number(self._state(PEAK_SUMMER_START_MONTH)) or 5)
        end_month = int(_to_number(self._state(PEAK_SUMMER_END_MONTH)) or 10)
        summer = (
            start_month <= local.month <= end_month
            if start_month <= end_month
            else local.month >= start_month or local.month <= end_month
        )
        windows: list[tuple[time | None, time | None]]
        if summer:
            windows = [
                (
                    _parse_time(self._state(PEAK_SUMMER_START)),
                    _parse_time(self._state(PEAK_SUMMER_END)),
                )
            ]
        else:
            windows = [
                (
                    _parse_time(self._state(PEAK_WINTER_1_START)),
                    _parse_time(self._state(PEAK_WINTER_1_END)),
                ),
                (
                    _parse_time(self._state(PEAK_WINTER_2_START)),
                    _parse_time(self._state(PEAK_WINTER_2_END)),
                ),
            ]
        for start, end in windows:
            if start is None or end is None or not _contains(local.time(), start, end):
                continue
            end_at = datetime.combine(local.date(), end, tzinfo=local.tzinfo)
            if end <= start and local.time() >= start:
                end_at += timedelta(days=1)
            return max(0.0, (end_at - local).total_seconds() / 60.0)
        return None

    def _update_battery_samples(self, now: datetime, raw_battery_w: float | None) -> None:
        state = self._state(self.sources.eg4_battery_power)
        if state is not None and raw_battery_w is not None:
            reported = _state_time(state)
            if self._last_battery_report is None or reported > self._last_battery_report:
                self._battery_samples.append((reported, max(-raw_battery_w, 0.0)))
                self._last_battery_report = reported
        cutoff = now - BATTERY_SMOOTHING_WINDOW
        while self._battery_samples and self._battery_samples[0][0] < cutoff:
            self._battery_samples.popleft()

    def _battery_window(self) -> tuple[float | None, float | None, int, float]:
        if not self._battery_samples:
            return None, None, 0, 0.0
        values = [value for _, value in self._battery_samples]
        span = (
            self._battery_samples[-1][0] - self._battery_samples[0][0]
        ).total_seconds() / 60.0
        if span < BATTERY_MINIMUM_SAMPLE_SPAN.total_seconds() / 60.0:
            return None, None, len(values), span
        return mean(values), _percentile_80(values), len(values), span

    async def _async_refresh_reconciliation(self, now: datetime) -> None:
        if (
            self._last_reconciliation_update is not None
            and now - self._last_reconciliation_update < RECONCILIATION_INTERVAL
        ):
            return
        self._last_reconciliation_update = now
        try:
            recorder = get_instance(self.hass)
            metadata = await recorder.async_add_executor_job(
                partial(get_metadata, self.hass, statistic_source="srp_energy_monitor")
            )
            srp_ids = [
                statistic_id
                for statistic_id in metadata
                if statistic_id.endswith("_energy_net")
            ]
            if len(srp_ids) != 1:
                _LOGGER.warning(
                    "Expected one SRP net statistic for reconciliation; found %s",
                    len(srp_ids),
                )
                return
            start = now - timedelta(days=21)
            srp = await recorder.async_add_executor_job(
                partial(
                    statistics_during_period,
                    self.hass,
                    start,
                    now,
                    {srp_ids[0]},
                    "hour",
                    None,
                    {"state"},
                )
            )
            eg4 = await recorder.async_add_executor_job(
                partial(
                    statistics_during_period,
                    self.hass,
                    start,
                    now,
                    {
                        self.sources.eg4_grid_import_lifetime,
                        self.sources.eg4_grid_export_lifetime,
                    },
                    "day",
                    None,
                    {"change"},
                )
            )
            self._reconciliation = calculate_reconciliation(
                srp_hourly=list(srp.get(srp_ids[0], [])),
                eg4_import_daily=list(eg4.get(self.sources.eg4_grid_import_lifetime, [])),
                eg4_export_daily=list(eg4.get(self.sources.eg4_grid_export_lifetime, [])),
                today=dt_util.as_local(now).date(),
            )
        except Exception:  # Recorder availability must not break live power.
            _LOGGER.exception("Could not refresh the settled SRP/EG4 reconciliation")

    async def _async_refresh_tigo_alignment(self, now: datetime) -> None:
        sample_state = self._state(self.sources.tigo_last_cloud_update)
        tigo_power = _power_w(self._state(self.sources.tigo_power))
        if not _is_valid_state(sample_state) or tigo_power is None:
            return
        sample_text = sample_state.state
        if sample_text == self._last_tigo_sample:
            return
        sample_time = dt_util.parse_datetime(sample_text)
        if sample_time is None:
            return
        if sample_time.tzinfo is None:
            sample_time = sample_time.replace(tzinfo=UTC)
        sample_time = sample_time.astimezone(UTC)
        if now - sample_time > TIGO_STALE_AFTER:
            return
        try:
            recorder = get_instance(self.hass)
            history = await recorder.async_add_executor_job(
                partial(
                    get_significant_states,
                    self.hass,
                    sample_time - timedelta(minutes=15),
                    sample_time + timedelta(minutes=15),
                    [self.sources.eg4_pv_power],
                    include_start_time_state=True,
                    significant_changes_only=False,
                    no_attributes=True,
                )
            )
            candidates = history.get(self.sources.eg4_pv_power, [])
            numeric = [
                (abs((_state_time(state) - sample_time).total_seconds()), _power_w(state))
                for state in candidates
                if isinstance(state, State) and _power_w(state) is not None
            ]
            if not numeric:
                return
            _, aligned = min(numeric, key=lambda item: item[0])
            assert aligned is not None
            self._tigo_aligned_eg4_w = aligned
            self._tigo_ratio_percent = 100.0 * tigo_power / aligned if aligned > 50 else None
            self._last_tigo_sample = sample_text
        except Exception:
            _LOGGER.exception("Could not align the Tigo sample to EG4 Recorder history")

    async def _async_update_data(self) -> HomeEnergySnapshot:
        now = datetime.now(UTC)
        try:
            core_sources = {
                "EG4 PV": (self.sources.eg4_pv_power, EG4_STALE_AFTER),
                "EG4 AC": (self.sources.eg4_ac_power, EG4_STALE_AFTER),
                "EG4 rectifier": (self.sources.eg4_rectifier_power, EG4_STALE_AFTER),
                "EG4 metered load": (
                    self.sources.eg4_metered_load_power,
                    EG4_STALE_AFTER,
                ),
                "EG4 grid CT": (self.sources.eg4_grid_power, EG4_STALE_AFTER),
                "EG4 battery": (self.sources.eg4_battery_power, EG4_STALE_AFTER),
                "EG4 battery SOC": (self.sources.eg4_battery_soc, EG4_STALE_AFTER),
                "Enphase local": (self.sources.enphase_power, ENPHASE_STALE_AFTER),
            }
            source_ages = {
                name: self._age_minutes(entity_id, now)
                for name, (entity_id, _) in core_sources.items()
            }
            runtime = _bool_state(self._state(self.sources.eg4_runtime_data))
            connection_lost = _bool_state(self._state(self.sources.eg4_connection_lost))
            eg4_runtime_ok = runtime is not False and connection_lost is not True
            model_sources_fresh = eg4_runtime_ok and all(
                self._fresh(entity_id, now, maximum)
                for entity_id, maximum in (
                    core_sources["EG4 AC"],
                    core_sources["EG4 rectifier"],
                    core_sources["EG4 metered load"],
                    core_sources["EG4 grid CT"],
                    core_sources["Enphase local"],
                )
            )
            solar_sources_fresh = eg4_runtime_ok and all(
                self._fresh(entity_id, now, maximum)
                for entity_id, maximum in (
                    core_sources["EG4 PV"],
                    core_sources["Enphase local"],
                )
            )
            grid_source_fresh = eg4_runtime_ok and self._fresh(
                self.sources.eg4_grid_power, now, EG4_STALE_AFTER
            )
            battery_source_fresh = eg4_runtime_ok and all(
                self._fresh(entity_id, now, maximum)
                for entity_id, maximum in (
                    core_sources["EG4 battery"],
                    core_sources["EG4 battery SOC"],
                )
            )

            raw_battery_w = _power_w(self._state(self.sources.eg4_battery_power))
            self._update_battery_samples(now, raw_battery_w)
            average_discharge, p80_discharge, sample_count, sample_span = self._battery_window()
            battery_age = source_ages.get("EG4 battery")
            bms_allowed = _bool_state(self._state(self.sources.eg4_bms_discharge_allowed))
            if (
                not battery_source_fresh
                or battery_age is None
                or battery_age > 3.5
                or bms_allowed is False
            ):
                average_discharge = None
                p80_discharge = None

            peak_remaining = self._peak_minutes_remaining(now)
            options = self._options()
            calculation = calculate_live(
                LiveInputs(
                    eg4_pv_w=_power_w(self._state(self.sources.eg4_pv_power)),
                    eg4_ac_w=_power_w(self._state(self.sources.eg4_ac_power)),
                    eg4_rectifier_w=_power_w(self._state(self.sources.eg4_rectifier_power)),
                    eg4_metered_load_w=_power_w(
                        self._state(self.sources.eg4_metered_load_power)
                    ),
                    grid_net_w=_power_w(self._state(self.sources.eg4_grid_power)),
                    battery_raw_w=raw_battery_w,
                    battery_soc_percent=_to_number(self._state(self.sources.eg4_battery_soc)),
                    eg4_yield_lifetime_kwh=_energy_kwh(
                        self._state(self.sources.eg4_yield_lifetime)
                    ),
                    enphase_power_w=_power_w(self._state(self.sources.enphase_power)),
                    enphase_lifetime_kwh=_energy_kwh(
                        self._state(self.sources.enphase_lifetime)
                    ),
                    model_sources_fresh=model_sources_fresh,
                    solar_sources_fresh=solar_sources_fresh,
                    grid_source_fresh=grid_source_fresh,
                    battery_source_fresh=battery_source_fresh,
                    average_battery_discharge_w=average_discharge,
                    p80_battery_discharge_w=p80_discharge,
                    battery_sample_count=sample_count,
                    battery_sample_span_minutes=sample_span,
                    on_peak=_bool_state(self._state(PEAK_ON)),
                    peak_schedule_valid=_bool_state(self._state(PEAK_SCHEDULE_VALID)),
                    peak_minutes_remaining=peak_remaining,
                ),
                options,
                now=now,
            )

            await self._async_refresh_reconciliation(now)
            await self._async_refresh_tigo_alignment(now)

            tigo_reporting = _to_number(self._state(self.sources.tigo_reporting_modules))
            tigo_configured = _to_number(self._state(self.sources.tigo_configured_modules))
            tigo_age = _to_number(self._state(self.sources.tigo_cloud_age))
            tigo_problem = bool(
                tigo_reporting is not None
                and tigo_configured is not None
                and tigo_reporting < tigo_configured
            )
            srp_state = self._state(self.sources.srp_daily_net)
            srp_available = _is_valid_state(srp_state)
            enphase_service = self._state(self.sources.enphase_service_status)
            enphase_gateway = self._state(self.sources.enphase_gateway_status)
            enphase_problem = any(
                _is_valid_state(state)
                and state is not None
                and state.state.casefold() not in {"online", "normal", "ok", "healthy"}
                for state in (enphase_service, enphase_gateway)
            )

            issues: list[str] = []
            if not model_sources_fresh:
                issues.append("Whole-home balance sources are unavailable or stale")
            if not solar_sources_fresh:
                issues.append("Combined solar sources are unavailable or stale")
            if not grid_source_fresh:
                issues.append("The EG4 whole-property grid CT is unavailable or stale")
            if not battery_source_fresh:
                issues.append("Battery power or SOC telemetry is unavailable or stale")
            if model_sources_fresh and not calculation.model_valid:
                issues.append("The certified AC-bus balance is outside tolerance")
            if tigo_problem:
                issues.append(
                    f"Tigo reports {int(tigo_reporting or 0)} of "
                    f"{int(tigo_configured or 0)} modules; C4 is the known outage"
                )
            if tigo_age is not None and tigo_age > TIGO_STALE_AFTER.total_seconds() / 60:
                issues.append("Tigo cloud data is stale")
            if enphase_problem:
                issues.append("Enphase reports a degraded gateway/service state")
            if not srp_available:
                issues.append("SRP Home Assistant credentials require reauthentication")
            if self._reconciliation is not None:
                age = dt_util.as_local(now).date() - self._reconciliation.day
                if age.days > 2:
                    issues.append("SRP settled reconciliation is stale")

            telemetry_healthy = (
                model_sources_fresh
                and solar_sources_fresh
                and grid_source_fresh
                and battery_source_fresh
                and calculation.model_valid
            )
            source_health = (
                "unavailable"
                if not telemetry_healthy
                else "healthy"
                if not issues
                else "degraded"
            )
            return HomeEnergySnapshot(
                calculation=calculation,
                reconciliation=self._reconciliation,
                source_health=source_health,
                telemetry_healthy=telemetry_healthy,
                source_ages_minutes=source_ages,
                issues=tuple(issues),
                tigo_power_w=_power_w(self._state(self.sources.tigo_power)),
                tigo_reporting_modules=(
                    int(tigo_reporting) if tigo_reporting is not None else None
                ),
                tigo_configured_modules=(
                    int(tigo_configured) if tigo_configured is not None else None
                ),
                tigo_cloud_age_minutes=tigo_age,
                tigo_aligned_eg4_power_w=self._tigo_aligned_eg4_w,
                tigo_to_eg4_percent=self._tigo_ratio_percent,
                tigo_problem=tigo_problem,
                enphase_problem=enphase_problem,
                enphase_active_microinverters=(
                    int(value)
                    if (
                        value := _to_number(
                            self._state(self.sources.enphase_active_microinverters)
                        )
                    )
                    is not None
                    else None
                ),
                srp_available=srp_available,
                srp_data_through=(
                    str(srp_state.attributes.get("data_through"))
                    if srp_state and srp_state.attributes.get("data_through")
                    else None
                ),
                current_srp_demand_kw=_to_number(self._state(self.sources.srp_current_demand)),
                billed_srp_peak_kw=_to_number(self._state(self.sources.srp_billed_cycle_peak)),
                srp_bill_projection_usd=_to_number(
                    self._state(self.sources.srp_bill_projection)
                ),
                peak_minutes_remaining=peak_remaining,
                options=options,
            )
        except Exception as err:
            raise UpdateFailed(f"Could not calculate whole-home energy: {err}") from err
