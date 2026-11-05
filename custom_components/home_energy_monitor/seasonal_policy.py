"""Pure E-15 calendar checks and proposed EG4 profiles; no device writes.

The existing shared HA tariff helpers remain the operational authority. The E-15
calendar here detects disagreement and selects a proposed inverter profile; it
never updates helpers or releases a charger independently. Parameters and native
weekly scheduling must be backed up and verified by the separate apply layer.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

PHOENIX = ZoneInfo("America/Phoenix")
Season = Literal["summer", "winter"]
DayKind = Literal["weekday", "weekend", "holiday"]


def _minute(value: str) -> int:
    """Parse an unambiguous 24-hour, minute-resolution boundary."""
    if (
        not isinstance(value, str)
        or len(value) != 5
        or value[2] != ":"
        or not value.replace(":", "").isdigit()
    ):
        raise ValueError("Schedule times must use HH:MM")
    hour, minute = int(value[:2]), int(value[3:])
    if hour > 23 or minute > 59:
        raise ValueError("Schedule time is outside the local day")
    return hour * 60 + minute


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """A start-inclusive/end-exclusive window, including overnight windows."""

    start: str
    end: str

    def __post_init__(self) -> None:
        if _minute(self.start) == _minute(self.end):
            raise ValueError("Equal boundaries are not an explicit full-day window")

    def contains_minute(self, minute: int) -> bool:
        """Evaluate reference time windows, never an undocumented firmware rule."""
        if not 0 <= minute < 1440:
            raise ValueError("Minute must be within the local day")
        start, end = _minute(self.start), _minute(self.end)
        return start <= minute < end if start < end else minute >= start or minute < end


WINTER_PEAK = (TimeWindow("05:00", "09:00"), TimeWindow("17:00", "21:00"))
SUMMER_PEAK = (TimeWindow("14:00", "20:00"),)


@dataclass(frozen=True, slots=True)
class SharedSchedule:
    """Observed shared-helper values, not a replacement tariff controller."""

    enabled: bool | None
    valid: bool | None
    on_peak: bool | None
    time_zone: str | None


@dataclass(frozen=True, slots=True)
class TariffState:
    """Reference calendar plus any shared-helper validation result."""

    local_now: datetime | None
    season: Season | None
    day_kind: DayKind | None
    holiday_name: str | None
    expected_on_peak: bool | None
    on_peak: bool | None
    valid: bool
    shared_validated: bool
    peak_windows: tuple[TimeWindow, ...]
    next_transition: datetime | None
    reason: str

    @property
    def ev_charging_allowed(self) -> bool:
        """A valid shared off-peak state is necessary, not sufficient, to charge."""
        return self.valid and self.shared_validated and self.on_peak is False

    @property
    def minutes_to_transition(self) -> float | None:
        if self.local_now is None or self.next_transition is None:
            return None
        return (self.next_transition - self.local_now).total_seconds() / 60


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def srp_holidays(year: int) -> dict[date, str]:
    """Return the six E-15 holidays, including observed fixed-date holidays.

    Adjacent years matter: next year's New Year's Day can be observed on
    December 31 of the requested year. Actual weekend dates are included for
    descriptive status; weekends are off peak independently.
    """
    holidays: dict[date, str] = {}
    for current in (year - 1, year, year + 1):
        for month, day, name in (
            (1, 1, "New Year's Day"),
            (7, 4, "Independence Day"),
            (12, 25, "Christmas Day"),
        ):
            actual = date(current, month, day)
            for item in (actual, _observed(actual)):
                if item.year == year:
                    holidays[item] = name
        may_last = date(current, 5, 31)
        memorial = may_last - timedelta(days=may_last.weekday())
        september_first = date(current, 9, 1)
        labor = september_first + timedelta(days=(-september_first.weekday()) % 7)
        november_first = date(current, 11, 1)
        thanksgiving = november_first + timedelta(days=(3 - november_first.weekday()) % 7 + 21)
        for item, name in (
            (memorial, "Memorial Day"),
            (labor, "Labor Day"),
            (thanksgiving, "Thanksgiving Day"),
        ):
            if item.year == year:
                holidays[item] = name
    return holidays


def _day_info(day: date) -> tuple[Season, DayKind, str | None]:
    season: Season = "summer" if 5 <= day.month <= 10 else "winter"
    holiday = srp_holidays(day.year).get(day)
    kind: DayKind = "holiday" if holiday else "weekend" if day.weekday() >= 5 else "weekday"
    return season, kind, holiday


def _windows(day: date) -> tuple[TimeWindow, ...]:
    season, kind, _ = _day_info(day)
    return () if kind != "weekday" else SUMMER_PEAK if season == "summer" else WINTER_PEAK


def _next_transition(local_now: datetime) -> datetime:
    """Find the next actual peak boundary, skipping weekends and holidays."""
    # Fourteen days comfortably spans the longest gap in this fixed six-holiday
    # calendar. No model or network polling participates in this calculation.
    for offset in range(15):
        day = local_now.date() + timedelta(days=offset)
        for window in _windows(day):
            for boundary in (window.start, window.end):
                minute = _minute(boundary)
                candidate = datetime.combine(day, time(minute // 60, minute % 60), PHOENIX)
                if candidate > local_now:
                    return candidate
    raise ValueError("No peak transition in the E-15 calendar horizon")


def evaluate_tariff(
    now: datetime,
    *,
    schedule_valid: bool | None = True,
    shared: SharedSchedule | None = None,
) -> TariffState:
    """Check the E-15 reference calendar against optional shared HA evidence.

    A naive timestamp is unknown, not silently interpreted in the host timezone.
    Without shared evidence this returns reference status only: the charging
    permission remains false and an apply plan will refuse activation.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        return TariffState(
            None,
            None,
            None,
            None,
            None,
            None,
            False,
            False,
            (),
            None,
            "A timezone-aware timestamp is required",
        )
    local_now = now.astimezone(PHOENIX)
    season, kind, holiday = _day_info(local_now.date())
    windows = _windows(local_now.date())
    minute = local_now.hour * 60 + local_now.minute
    expected = any(window.contains_minute(minute) for window in windows)
    reasons = []
    if schedule_valid is not True:
        reasons.append("Tariff configuration is unknown or invalid")
    if shared is not None:
        if shared.enabled is not True:
            reasons.append("Shared tariff schedule is disabled or unreadable")
        if shared.valid is not True:
            reasons.append("Shared tariff schedule is invalid or unreadable")
        if shared.time_zone != "America/Phoenix":
            reasons.append("Home Assistant timezone must be America/Phoenix")
        if not isinstance(shared.on_peak, bool):
            reasons.append("Shared on-peak state is unreadable")
        elif shared.on_peak != expected:
            reasons.append("Shared on-peak state disagrees with the E-15 calendar")
    valid = not reasons
    return TariffState(
        local_now=local_now,
        season=season,
        day_kind=kind,
        holiday_name=holiday,
        expected_on_peak=expected,
        on_peak=expected if valid else None,
        valid=valid,
        shared_validated=shared is not None and valid,
        peak_windows=windows,
        next_transition=_next_transition(local_now) if valid else None,
        reason="; ".join(reasons) if reasons else "On peak" if expected else "Off peak",
    )


@dataclass(frozen=True, slots=True)
class ChargeWindow:
    """A proposed AC window; per-window power belongs to the weekly table."""

    window: TimeWindow
    power_kw: float
    stop_soc: int
    all_day_intent: bool = False

    def __post_init__(self) -> None:
        if not 0 < self.power_kw <= 12:
            raise ValueError("AC charge power must be positive and bounded")
        # 101 is the literal existing global-profile workaround, not measured SOC.
        if not 1 <= self.stop_soc <= 101:
            raise ValueError("Unsupported AC charge stop setting")
        if self.all_day_intent and self.window != TimeWindow("00:00", "23:59"):
            raise ValueError("Full-day intent requires the documented screenshot shape")


@dataclass(frozen=True, slots=True)
class PeakWindow:
    window: TimeWindow
    grid_limit_kw: float
    start_soc: int

    def __post_init__(self) -> None:
        if not 0 <= self.grid_limit_kw <= 12 or not 0 <= self.start_soc <= 100:
            raise ValueError("Unsupported peak-shaving setting")


@dataclass(frozen=True, slots=True)
class InverterProfile:
    """Desired global daily settings, without transport/register assumptions."""

    name: str
    season: Season
    day_kind: DayKind
    ac_windows: tuple[ChargeWindow, ...]
    pv_windows: tuple[TimeWindow, ...]
    peak_windows: tuple[PeakWindow, ...]
    ac_charge_enabled: bool = True
    ac_charge_basis: str = "time"
    pv_priority_enabled: bool = True
    pv_power_kw: float = 12
    pv_stop_soc: int = 100
    peak_shaving_enabled: bool = True
    backup_enabled: bool = False
    forced_discharge_enabled: bool = False
    export_pv_only: bool = False
    sporadic_charge: bool = False

    @property
    def global_ac_power_kw(self) -> float | None:
        """Never collapse differing native-weekly powers into one global value."""
        powers = {item.power_kw for item in self.ac_windows}
        return next(iter(powers)) if len(powers) == 1 else None


@dataclass(frozen=True, slots=True)
class ProfilePlan:
    """An apply-layer admission result; never an instruction to write blindly."""

    tariff: TariffState
    desired_profile: InverterProfile | None
    can_apply: bool
    disable_native_weekly: bool
    native_weekly_enabled: bool | None
    weekly_ac_reference: tuple[ChargeWindow, ...]
    reasons: tuple[str, ...]


def weekly_ac_reference(now: datetime) -> tuple[ChargeWindow, ...]:
    """Return saved summer AC examples, without asserting all day tabs match.

    The images prove Monday and Saturday only. These values cannot be passed to
    a global daily power setter: weekday T1/T2 have different charge powers.
    """
    tariff = evaluate_tariff(now)
    if tariff.season != "summer":
        return ()
    if tariff.day_kind == "weekday":
        return (
            ChargeWindow(TimeWindow("00:00", "13:55"), 2, 100),
            ChargeWindow(TimeWindow("20:05", "23:59"), 4, 100),
        )
    return (ChargeWindow(TimeWindow("00:00", "23:59"), 4, 100, all_day_intent=True),)


def desired_daily_profile(
    now: datetime,
    *,
    summer_daily_profile: InverterProfile | None = None,
    off_peak_power_kw: float = 4,
) -> InverterProfile | None:
    """Propose a daily profile, preserving a supplied summer live baseline.

    Winter comes from the complete uploaded daily screenshot set. No full
    summer daily baseline was uploaded, so it must be supplied from verified
    live backup instead of inventing a global equivalent of weekly settings.
    Non-peak days use the approved two-window 4 kW preservation recipe.
    Firmware behavior at the midnight endpoint still needs field verification.
    """
    tariff = evaluate_tariff(now)
    if not tariff.valid or tariff.season is None or tariff.day_kind is None:
        return None
    if tariff.day_kind != "weekday":
        return InverterProfile(
            name=f"{tariff.season}-{tariff.day_kind}",
            season=tariff.season,
            day_kind=tariff.day_kind,
            ac_windows=(
                ChargeWindow(TimeWindow("00:00", "12:00"), off_peak_power_kw, 101),
                ChargeWindow(TimeWindow("12:00", "00:00"), off_peak_power_kw, 101),
            ),
            pv_windows=(TimeWindow("09:00", "15:00"),),
            peak_windows=(),
            pv_priority_enabled=True,
            peak_shaving_enabled=False,
        )
    if tariff.season == "summer":
        if (
            summer_daily_profile is None
            or summer_daily_profile.season != "summer"
            or summer_daily_profile.day_kind != "weekday"
        ):
            return None
        return replace(
            summer_daily_profile, name="summer-weekday", season="summer", day_kind="weekday"
        )
    return InverterProfile(
        name="winter-weekday",
        season="winter",
        day_kind="weekday",
        ac_windows=(
            ChargeWindow(TimeWindow("21:00", "05:00"), 2, 101),
            ChargeWindow(TimeWindow("15:00", "17:00"), 2, 101),
        ),
        pv_windows=(TimeWindow("09:00", "15:00"),),
        peak_windows=(
            PeakWindow(TimeWindow("05:00", "09:00"), 0, 21),
            PeakWindow(TimeWindow("17:00", "21:00"), 0, 20),
        ),
    )


def _profile_issues(profile: InverterProfile) -> list[str]:
    """Reject incomplete or contradictory global targets before transport use."""
    reasons = []
    flags = (
        profile.ac_charge_enabled,
        profile.pv_priority_enabled,
        profile.peak_shaving_enabled,
        profile.backup_enabled,
        profile.forced_discharge_enabled,
        profile.export_pv_only,
        profile.sporadic_charge,
    )
    if any(not isinstance(value, bool) for value in flags):
        reasons.append("Every proposed mode flag must be an explicit boolean")
    if not 0 < profile.pv_power_kw <= 12 or not 1 <= profile.pv_stop_soc <= 100:
        reasons.append("The proposed PV charge limit is outside the screenshot-derived bounds")
    if profile.day_kind == "weekday":
        expected = SUMMER_PEAK if profile.season == "summer" else WINTER_PEAK
        if not profile.peak_shaving_enabled or any(
            expected_window.contains_minute(minute)
            and not any(
                item.grid_limit_kw == 0 and item.window.contains_minute(minute)
                for item in profile.peak_windows
            )
            for expected_window in expected
            for minute in range(1440)
        ):
            reasons.append("The zero-grid peak-shaving plan does not cover the E-15 peaks")
    elif profile.peak_shaving_enabled or profile.peak_windows:
        reasons.append("A non-peak day must not schedule battery peak shaving")
    if profile.ac_charge_basis != "time":
        reasons.append("The daily controller requires a verified time-based AC-charge profile")
    if profile.ac_charge_enabled and not profile.ac_windows:
        reasons.append("Enabled AC charging requires an explicit window")
    if profile.ac_windows and profile.global_ac_power_kw is None:
        reasons.append("Per-window weekly AC powers cannot be written as one global power")
    if profile.pv_priority_enabled and not profile.pv_windows:
        reasons.append("Enabled PV priority requires an explicit window")
    if profile.peak_shaving_enabled and not profile.peak_windows:
        reasons.append("Enabled peak shaving requires an explicit window")
    if (
        len(profile.ac_windows) > 3
        or len(profile.pv_windows) > 3
        or len(profile.peak_windows) > 2
    ):
        reasons.append("The profile exceeds the verified daily window counts")
    if profile.backup_enabled or profile.forced_discharge_enabled or profile.export_pv_only:
        reasons.append("This policy does not admit backup or forced-export mode changes")
    if profile.sporadic_charge:
        reasons.append("Sporadic grid charging is outside the screenshot-derived policy")
    if profile.peak_shaving_enabled:
        for minute in range(1440):
            if not any(item.window.contains_minute(minute) for item in profile.peak_windows):
                continue
            if (
                profile.ac_charge_enabled
                and any(item.window.contains_minute(minute) for item in profile.ac_windows)
            ) or (
                profile.pv_priority_enabled
                and any(item.contains_minute(minute) for item in profile.pv_windows)
            ):
                reasons.append("Charging priority overlaps a peak-shaving window")
                break
    return reasons


def build_profile_plan(
    now: datetime,
    *,
    shared: SharedSchedule | None,
    native_weekly_enabled: bool | None,
    weekly_backup_verified: bool = False,
    daily_plan_verified: bool = False,
    summer_daily_profile: InverterProfile | None = None,
    summer_baseline_verified: bool = False,
    off_peak_power_kw: float = 4,
) -> ProfilePlan:
    """Admit a proposed global plan only after shared/authority evidence.

    This function has no API map and never changes native weekly scheduling.
    The apply layer must securely preserve every weekly day before declaring
    ``weekly_backup_verified`` and prove supported global daily mappings before
    declaring ``daily_plan_verified``. Unknown evidence always refuses writes.
    """
    tariff = evaluate_tariff(now, shared=shared)
    reasons = []
    if not tariff.valid:
        reasons.append(tariff.reason)
    if not tariff.shared_validated:
        reasons.append("Validated shared tariff evidence is required")
    if not isinstance(native_weekly_enabled, bool):
        reasons.append("Native weekly scheduling state is unknown")
    elif native_weekly_enabled and not weekly_backup_verified:
        reasons.append("Every native weekly day must be securely backed up before disabling it")
    if not daily_plan_verified:
        reasons.append("The owner daily plan and supported parameter mapping are unverified")
    profile = desired_daily_profile(
        now,
        summer_daily_profile=summer_daily_profile,
        off_peak_power_kw=off_peak_power_kw,
    )
    if profile is None:
        reasons.append("A complete daily profile or verified summer baseline is required")
    elif (
        tariff.season == "summer"
        and tariff.day_kind == "weekday"
        and not summer_baseline_verified
    ):
        reasons.append("The supplied summer daily baseline has not been verified")
    if profile is not None:
        reasons.extend(_profile_issues(profile))
    can_apply = not reasons
    return ProfilePlan(
        tariff=tariff,
        desired_profile=profile,
        can_apply=can_apply,
        disable_native_weekly=can_apply and native_weekly_enabled is True,
        native_weekly_enabled=native_weekly_enabled,
        weekly_ac_reference=weekly_ac_reference(now),
        reasons=tuple(reasons),
    )
