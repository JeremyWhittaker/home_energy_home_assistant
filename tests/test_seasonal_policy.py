"""Seasonal calendar boundaries and inverter admission policy scenarios."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from custom_components.home_energy_monitor.seasonal_policy import (
    ChargeWindow,
    InverterProfile,
    PeakWindow,
    SharedSchedule,
    TimeWindow,
    build_profile_plan,
    desired_daily_profile,
    evaluate_tariff,
    srp_holidays,
    weekly_ac_reference,
)


def at(value: str) -> datetime:
    return datetime.fromisoformat(value + "-07:00")


def shared(on_peak: bool | None, **changes: object) -> SharedSchedule:
    values = dict(enabled=True, valid=True, on_peak=on_peak, time_zone="America/Phoenix")
    values.update(changes)
    return SharedSchedule(**values)


@pytest.mark.parametrize(
    ("stamp", "expected"),
    [
        ("2026-11-04T04:59:59", False),
        ("2026-11-04T05:00:00", True),
        ("2026-11-04T08:59:59", True),
        ("2026-11-04T09:00:00", False),
        ("2026-11-04T16:59:59", False),
        ("2026-11-04T17:00:00", True),
        ("2026-11-04T20:59:59", True),
        ("2026-11-04T21:00:00", False),
        ("2026-07-08T13:59:59", False),
        ("2026-07-08T14:00:00", True),
        ("2026-07-08T19:59:59", True),
        ("2026-07-08T20:00:00", False),
    ],
)
def test_exact_tariff_boundaries(stamp: str, expected: bool) -> None:
    status = evaluate_tariff(at(stamp), shared=shared(expected))
    assert status.valid
    assert status.on_peak is expected
    assert status.ev_charging_allowed is (not expected)


def test_calendar_uses_phoenix_not_host_utc_or_dst() -> None:
    assert evaluate_tariff(datetime(2026, 11, 4, 12, tzinfo=UTC)).on_peak is True
    assert evaluate_tariff(datetime(2026, 7, 8, 21, tzinfo=UTC)).on_peak is True
    assert evaluate_tariff(at("2026-10-30T17:00:00")).season == "summer"
    assert evaluate_tariff(at("2026-11-02T05:00:00")).season == "winter"
    assert evaluate_tariff(at("2027-04-30T17:00:00")).season == "winter"
    assert evaluate_tariff(at("2027-05-03T17:00:00")).season == "summer"


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-01-01T17:30:00",  # New Year's Day
        "2026-05-25T17:30:00",  # Memorial Day
        "2026-07-03T17:30:00",  # Independence Day observed Friday
        "2026-09-07T17:30:00",  # Labor Day
        "2026-11-26T17:30:00",  # Thanksgiving
        "2026-12-25T17:30:00",  # Christmas
        "2027-12-31T17:30:00",  # Next year's New Year's Day observed Friday
    ],
)
def test_six_holidays_and_cross_year_observance(stamp: str) -> None:
    status = evaluate_tariff(at(stamp), shared=shared(False))
    assert status.valid
    assert status.day_kind == "holiday"
    assert status.holiday_name
    assert status.peak_windows == ()
    assert status.ev_charging_allowed
    assert len({name for name in srp_holidays(2026).values()}) == 6


def test_weekend_is_off_peak_and_next_boundary_skips_holiday() -> None:
    status = evaluate_tariff(at("2026-09-04T20:00:00"), shared=shared(False))
    assert status.next_transition == at("2026-09-08T14:00:00")
    weekend = evaluate_tariff(at("2026-11-07T18:00:00"), shared=shared(False))
    assert weekend.day_kind == "weekend"
    assert weekend.next_transition == at("2026-11-09T05:00:00")


def test_remaining_time_includes_seconds_and_skips_current_boundary() -> None:
    status = evaluate_tariff(at("2026-11-04T20:59:30"), shared=shared(True))
    assert status.minutes_to_transition == 0.5
    assert evaluate_tariff(at("2026-11-04T21:00:00")).next_transition == at(
        "2026-11-05T05:00:00"
    )


@pytest.mark.parametrize(
    "evidence",
    [
        shared(None),
        shared(False),  # Mismatch: calendar says peak.
        shared(True, enabled=False),
        shared(True, valid=None),
        shared(True, time_zone="America/Denver"),
    ],
)
def test_shared_unknown_disabled_invalid_or_mismatched_state_blocks(
    evidence: SharedSchedule,
) -> None:
    status = evaluate_tariff(at("2026-11-04T18:00:00"), shared=evidence)
    assert not status.valid
    assert status.expected_on_peak is True
    assert status.on_peak is None
    assert not status.ev_charging_allowed
    assert status.next_transition is None


def test_reference_calendar_alone_cannot_release_charging_or_admit_writes() -> None:
    stamp = at("2026-11-04T10:00:00")
    status = evaluate_tariff(stamp)
    assert status.valid and status.on_peak is False
    assert not status.shared_validated
    assert not status.ev_charging_allowed
    plan = build_profile_plan(
        stamp, shared=None, native_weekly_enabled=False, daily_plan_verified=True
    )
    assert not plan.can_apply


def test_naive_time_and_unknown_configuration_fail_closed() -> None:
    naive = evaluate_tariff(datetime(2026, 11, 4, 18))
    assert not naive.valid and naive.on_peak is None
    status = evaluate_tariff(at("2026-11-04T10:00:00"), schedule_valid=None)
    assert not status.valid and not status.ev_charging_allowed
    assert desired_daily_profile(datetime(2026, 11, 4, 18)) is None


def test_winter_profile_preserves_full_screenshot_combination() -> None:
    profile = desired_daily_profile(at("2026-11-04T10:00:00"))
    assert profile is not None
    assert [
        (x.window.start, x.window.end, x.power_kw, x.stop_soc) for x in profile.ac_windows
    ] == [
        ("21:00", "05:00", 2, 101),
        ("15:00", "17:00", 2, 101),
    ]
    assert profile.pv_windows == (TimeWindow("09:00", "15:00"),)
    assert [
        (x.window.start, x.window.end, x.grid_limit_kw, x.start_soc)
        for x in profile.peak_windows
    ] == [
        ("05:00", "09:00", 0, 21),
        ("17:00", "21:00", 0, 20),
    ]
    assert profile.global_ac_power_kw == 2
    assert profile.pv_power_kw == 12 and profile.pv_stop_soc == 100
    assert not profile.backup_enabled
    assert not profile.forced_discharge_enabled
    assert not profile.export_pv_only
    assert not profile.sporadic_charge
    # Every winter peak minute is excluded from AC/PV charging windows.
    for minute in list(range(5 * 60, 9 * 60)) + list(range(17 * 60, 21 * 60)):
        assert not any(x.window.contains_minute(minute) for x in profile.ac_windows)
        assert not any(x.contains_minute(minute) for x in profile.pv_windows)


@pytest.mark.parametrize("stamp", ["2026-11-07T18:00:00", "2026-11-26T18:00:00"])
def test_non_peak_day_disables_battery_peak_dispatch_and_preserves_bounded_power(
    stamp: str,
) -> None:
    profile = desired_daily_profile(at(stamp), off_peak_power_kw=2)
    assert profile is not None
    assert not profile.peak_shaving_enabled and profile.peak_windows == ()
    assert not profile.pv_priority_enabled and profile.pv_windows == ()
    assert profile.ac_windows[0].all_day_intent
    assert profile.ac_windows[0].power_kw == 2
    assert profile.ac_windows[0].stop_soc == 101


def test_weekly_authority_requires_full_backup_and_verified_daily_plan() -> None:
    stamp = at("2026-11-04T10:00:00")
    for weekly_state, backup, verified in [
        (None, True, True),
        (True, False, True),
        (True, True, False),
    ]:
        plan = build_profile_plan(
            stamp,
            shared=shared(False),
            native_weekly_enabled=weekly_state,
            weekly_backup_verified=backup,
            daily_plan_verified=verified,
        )
        assert not plan.can_apply and not plan.disable_native_weekly
    plan = build_profile_plan(
        stamp,
        shared=shared(False),
        native_weekly_enabled=True,
        weekly_backup_verified=True,
        daily_plan_verified=True,
    )
    assert plan.can_apply and plan.disable_native_weekly
    daily = build_profile_plan(
        stamp, shared=shared(False), native_weekly_enabled=False, daily_plan_verified=True
    )
    assert daily.can_apply and not daily.disable_native_weekly


def summer_baseline() -> InverterProfile:
    return InverterProfile(
        name="secure-live-backup",
        season="summer",
        day_kind="weekday",
        ac_windows=(ChargeWindow(TimeWindow("20:05", "09:00"), 2, 101),),
        pv_windows=(TimeWindow("09:00", "13:55"),),
        peak_windows=(PeakWindow(TimeWindow("13:55", "20:05"), 0, 21),),
    )


def test_summer_requires_full_verified_daily_baseline_and_preserves_it() -> None:
    stamp = at("2026-07-08T12:00:00")
    assert desired_daily_profile(stamp) is None
    baseline = summer_baseline()
    unverified = build_profile_plan(
        stamp,
        shared=shared(False),
        native_weekly_enabled=False,
        daily_plan_verified=True,
        summer_daily_profile=baseline,
    )
    assert not unverified.can_apply
    plan = build_profile_plan(
        stamp,
        shared=shared(False),
        native_weekly_enabled=False,
        daily_plan_verified=True,
        summer_daily_profile=baseline,
        summer_baseline_verified=True,
    )
    assert plan.can_apply and plan.desired_profile is not None
    assert plan.desired_profile.ac_windows == baseline.ac_windows
    assert plan.desired_profile.pv_windows == baseline.pv_windows
    assert plan.desired_profile.peak_windows == baseline.peak_windows
    assert plan.desired_profile.global_ac_power_kw == 2


def test_weekly_reference_never_silently_turns_weekday_four_kw_into_global_power() -> None:
    weekday = weekly_ac_reference(at("2026-07-06T10:00:00"))
    assert [(x.window.start, x.window.end, x.power_kw, x.stop_soc) for x in weekday] == [
        ("00:00", "13:55", 2, 100),
        ("20:05", "23:59", 4, 100),
    ]
    weekend = weekly_ac_reference(at("2026-07-11T10:00:00"))
    assert weekend[0].power_kw == 4 and weekend[0].all_day_intent
    assert weekly_ac_reference(at("2026-11-04T10:00:00")) == ()
    differing = InverterProfile(
        name="weekly-reference-not-global",
        season="summer",
        day_kind="weekday",
        ac_windows=weekday,
        pv_windows=(),
        peak_windows=(),
    )
    assert differing.global_ac_power_kw is None


def test_overnight_window_and_ambiguous_equal_boundaries() -> None:
    overnight = TimeWindow("21:00", "05:00")
    assert overnight.contains_minute(23 * 60)
    assert overnight.contains_minute(4 * 60 + 59)
    assert not overnight.contains_minute(5 * 60)
    with pytest.raises(ValueError):
        TimeWindow("00:00", "00:00")
    with pytest.raises(ValueError):
        TimeWindow("24:00", "05:00")
    with pytest.raises(ValueError):
        ChargeWindow(TimeWindow("00:00", "23:59"), 2, 102)


@pytest.mark.parametrize(
    "changes",
    [
        {"forced_discharge_enabled": True},
        {"backup_enabled": True},
        {"ac_windows": ()},
        {"peak_shaving_enabled": False},
        {"peak_windows": (PeakWindow(TimeWindow("15:00", "20:05"), 0, 21),)},
        {"ac_charge_enabled": "true"},
        {"pv_power_kw": 13},
        {"ac_charge_basis": "voltage"},
        {"ac_windows": (ChargeWindow(TimeWindow("19:00", "09:00"), 2, 101),)},
        {
            "ac_windows": (
                ChargeWindow(TimeWindow("00:00", "13:55"), 2, 100),
                ChargeWindow(TimeWindow("20:05", "23:59"), 4, 100),
            )
        },
    ],
)
def test_incomplete_or_contradictory_live_baseline_is_not_admitted(changes: dict) -> None:
    plan = build_profile_plan(
        at("2026-07-08T12:00:00"),
        shared=shared(False),
        native_weekly_enabled=False,
        daily_plan_verified=True,
        summer_daily_profile=replace(summer_baseline(), **changes),
        summer_baseline_verified=True,
    )
    assert not plan.can_apply
    assert plan.reasons
