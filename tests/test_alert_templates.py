"""Render maintained Node-generated alert templates with HA's native Jinja engine."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from homeassistant.helpers.template import Template

from custom_components.home_energy_monitor.sensor import (
    HomeEnergySensor,
    HomeEnergySensorDescription,
)


@pytest.fixture(scope="module")
def generated():
    script = r"""
import {discoveryContract} from './src/discovery.mjs';
import {buildAutomations, householdShortfallTemplate,
  demandReviewTemplates, jeremyEmailAvailableTemplate} from './src/site-config.mjs';
const slug=(s)=>s.toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_|_$/g,'');
const e={...discoveryContract.static};
for(const [key,[domain,name]] of Object.entries(discoveryContract.calculated))
 e[key]=`${domain}.home_energy_${slug(name)}`;
for(const [key,[platform,domain,name]] of Object.entries(discoveryContract.sources))
 e[key]=`${domain}.${platform}_${slug(name)}`;
console.log(JSON.stringify({e,automations:buildAutomations(e),
 shortfall:householdShortfallTemplate(e), demand:demandReviewTemplates(e),
 emailAvailable:jeremyEmailAvailableTemplate(e)}));
"""
    return json.loads(
        subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )


@pytest.fixture
async def context(hass, freezer, generated):
    await hass.config.async_set_time_zone("America/Phoenix")
    freezer.move_to("2026-11-05T12:10:00+00:00")
    e = generated["e"]
    now = datetime.now(UTC)
    for entity in [
        e["peakWindow"],
        e["peakScheduleValid"],
        "input_boolean.juicebox_srp_schedule_enabled",
    ]:
        hass.states.async_set(entity, "on")
    hass.states.async_set(
        "automation.juicebox_apply_local_charge_policy", "on", {"last_triggered": now}
    )
    for entity, value, unit in [
        (e["batteryNetPower"], -1985, "W"),
        (e["batterySoc"], 89, "%"),
        (e["gridNetPower"], 3851, "W"),
        (e["wholeHomeLoad"], 1825, "W"),
        (e["combinedSolarPower"], 0, "W"),
    ]:
        hass.states.async_set(entity, str(value), {"unit_of_measurement": unit})
    hass.states.async_set(
        e["sourceHealth"],
        "Healthy",
        {
            "source_ages_minutes": {
                "EG4 battery": 0.2,
                "EG4 battery SOC": 0.2,
                "EG4 grid CT": 0.2,
            }
        },
    )
    hass.states.async_set(
        "sensor.home_energy_inverter_schedule_status",
        "Applied and verified",
        {
            "profile": "winter-weekday",
            "season": "winter",
            "day_kind": "weekday",
            "shared_tariff_validated": True,
        },
    )
    return e


def render(hass, template, **variables):
    return Template(template, hass).async_render(variables, parse_result=True)


def automation(generated, name):
    return next(a["config"] for a in generated["automations"] if a["id"] == name)


async def test_observed_failed_start_is_a_dispatch_fault_below_the_existing5kw(
    hass, context, generated
):
    cfg = automation(generated, "home_energy_dispatch_failure_alert")
    assert cfg["triggers"][0]["for"] == "00:10:00"
    assert render(hass, cfg["triggers"][0]["value_template"]) is True
    hass.states.async_set(context["batteryNetPower"], "1600", {"unit_of_measurement": "W"})
    assert render(hass, cfg["triggers"][0]["value_template"]) is False


@pytest.mark.parametrize(
    ("field", "value", "unit"),
    [
        ("batterySoc", 25, "%"),
        ("gridNetPower", 500, "W"),
        ("combinedSolarPower", 2000, "W"),
        ("wholeHomeLoad", "unavailable", "W"),
        ("batteryNetPower", 400, "W"),
    ],
)
async def test_dispatch_fault_requires_every_opportunity_gate(
    hass, context, generated, field, value, unit
):
    cfg = automation(generated, "home_energy_dispatch_failure_alert")
    hass.states.async_set(context[field], str(value), {"unit_of_measurement": unit})
    assert render(hass, cfg["triggers"][0]["value_template"]) is False


async def test_critical_eg4_failure_detects_unavailable_even_with_recent_report(
    hass, context, generated
):
    cfg = automation(generated, "home_energy_eg4_unusable_alert")
    assert render(hass, cfg["triggers"][0]["value_template"]) is False
    hass.states.async_set(context["wholeHomeLoad"], "unavailable", {"unit_of_measurement": "W"})
    assert render(hass, cfg["triggers"][0]["value_template"]) is False
    hass.states.async_set(context["batterySoc"], "unavailable", {"unit_of_measurement": "%"})
    assert render(hass, cfg["triggers"][0]["value_template"]) is True
    assert cfg["triggers"][0]["for"] == "00:10:00"


@pytest.mark.parametrize("age", [-1, 181])
async def test_stale_or_future_shared_rules_cannot_claim_peak_failure(
    hass, context, generated, age
):
    hass.states.async_set(
        "automation.juicebox_apply_local_charge_policy",
        "on",
        {
            "last_triggered": datetime.now(UTC) - timedelta(seconds=age),
        },
    )
    for name in ["home_energy_dispatch_failure_alert", "home_energy_eg4_unusable_alert"]:
        cfg = automation(generated, name)
        assert render(hass, cfg["triggers"][0]["value_template"]) is False


@pytest.mark.parametrize(
    ("status", "age", "expected"),
    [
        ("Recovery required", 0, True),
        ("Automatic retries stopped", 0, True),
        ("Blocked", 1799, False),
        ("Blocked", 1800, True),
        ("Applied and verified", 2000, False),
    ],
)
async def test_operational_fault_age_and_latch_do_not_repeat_the_same_incident(
    hass, context, generated, freezer, status, age, expected
):
    cfg = automation(generated, "home_energy_controller_fault_alert")
    now = datetime.now(UTC)
    freezer.move_to(now - timedelta(seconds=age))
    hass.states.async_set("sensor.home_energy_inverter_schedule_status", status)
    freezer.move_to(now)
    assert render(hass, cfg["conditions"][0]["value_template"]) is expected
    key = render(hass, cfg["variables"]["alert_key"])
    hass.states.async_set("input_text.home_energy_controller_fault_alert_key", key)
    assert render(hass, cfg["conditions"][1]["value_template"], alert_key=key) is False


@pytest.mark.parametrize(
    ("season", "kind", "expected"),
    [
        ("winter", "weekday", "winter-weekday"),
        ("winter", "weekend", "winter-weekend"),
        ("winter", "holiday", "winter-holiday"),
        ("summer", "weekend", "summer-weekly"),
        ("summer", "weekday", "summer-weekly"),
        ("summer", "holiday", "summer-holiday"),
    ],
)
async def test_expected_profile_uses_controller_calendar_instead_of_a_second_holiday_calendar(
    hass, context, generated, season, kind, expected
):
    cfg = automation(generated, "home_energy_profile_mismatch_alert")
    hass.states.async_set(
        "sensor.home_energy_inverter_schedule_status",
        "Applied and verified",
        {
            "season": season,
            "day_kind": kind,
            "profile": "old-profile",
            "shared_tariff_validated": True,
        },
    )
    assert render(hass, cfg["variables"]["expected_profile"]) == expected
    assert (
        render(hass, cfg["conditions"][0]["value_template"], expected_profile=expected) is True
    )
    hass.states.async_set(
        "sensor.home_energy_inverter_schedule_status",
        "Applied and verified",
        {
            "season": season,
            "day_kind": kind,
            "profile": expected,
            "shared_tariff_validated": True,
        },
    )
    assert (
        render(hass, cfg["conditions"][0]["value_template"], expected_profile=expected) is False
    )


@pytest.mark.parametrize(
    ("central", "conservative", "remaining", "valid", "expected"),
    [
        (462, 150.48, 208, True, False),
        (306.35, 141.36, 168, True, False),
        (42, 22.8, 90, True, True),
        (42, 22.8, 90, False, False),
        (None, 22.8, 90, True, False),
    ],
)
async def test_family_shortfall_requires_two_valid_short_forecasts(
    hass, context, generated, central, conservative, remaining, valid, expected
):
    hass.states.async_set(
        context["batteryMinutesToReserve"],
        str(conservative),
        {
            "central_minutes": central,
            "conservative_minutes": conservative,
            "forecast_valid": valid,
        },
    )
    hass.states.async_set(context["peakMinutesRemaining"], str(remaining))
    assert render(hass, generated["shortfall"]) is expected


async def test_peak_latches_allow_only_one_report_in_each_actual_peak(
    hass, context, generated, freezer
):
    for name in ["home_energy_dispatch_failure_alert", "home_energy_eg4_unusable_alert"]:
        cfg = automation(generated, name)
        key = render(hass, cfg["variables"]["alert_key"])
        latch = cfg["actions"][1]["target"]["entity_id"]
        hass.states.async_set(latch, key)
        assert render(hass, cfg["conditions"][1]["value_template"], alert_key=key) is False
        freezer.move_to(
            "2026-11-05T00:10:00+00:00"
        )  # Prior local day PM; distinct actual window.
        changed = render(hass, cfg["variables"]["alert_key"])
        assert changed != key
        assert render(hass, cfg["conditions"][1]["value_template"], alert_key=changed) is True
        freezer.move_to("2026-11-05T12:10:00+00:00")


async def test_new_templates_render_during_startup_and_deployer_prevalidation(
    hass, context, generated
):
    # The deployer renders each expression alone, before action variables execute.
    # Missing runtime variables/source values must remain a safe diagnostic.
    hass.states.async_remove(context["sourceHealth"])
    hass.states.async_remove("sensor.home_energy_inverter_schedule_status")
    hass.states.async_remove(context["batteryMinutesToReserve"])

    def templates(value):
        if isinstance(value, str) and ("{{" in value or "{%" in value):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from templates(child)
        elif isinstance(value, list):
            for child in value:
                yield from templates(child)

    names = [
        "home_energy_dispatch_failure_alert",
        "home_energy_eg4_unusable_alert",
        "home_energy_controller_fault_alert",
        "home_energy_profile_mismatch_alert",
        "home_energy_peak_battery_forecast_alert",
    ]
    for name in names:
        for expression in templates(automation(generated, name)):
            render(
                hass,
                expression,
                alert_key="test",
                event_key="test",
                this={"entity_id": "automation.offline_test"},
            )


async def demand_context(hass, freezer, generated, *, status="matches", maximum=7.2, **changes):
    freezer.move_to("2026-11-06T17:05:00+00:00")
    e = generated["e"]
    attrs = {
        "last_checked": datetime.now(UTC).isoformat(),
        "latest_complete_day": "2026-11-05",
        "latest_daily_max_kw": maximum,
        "content_hash": "a" * 64,
        "billed_cost_verified": False,
        "caveats": ["Utility readings may revise"],
        "latest_complete_day_winning_intervals": [
            {
                "start": "2026-11-05T17:00:00-07:00",
                "end": "2026-11-05T17:30:00-07:00",
                "demand_kw": maximum,
            }
        ],
    }
    attrs.update(changes)
    hass.states.async_set(e["srpDemandAudit"], status, attrs)
    hass.states.async_set(e["peakImportThreshold"], "5", {"unit_of_measurement": "kW"})
    return attrs


@pytest.mark.parametrize(
    ("status", "maximum", "email", "local"),
    [
        ("matches", 7.2, True, False),
        ("matches", 5, True, False),
        ("matches", 4.9, False, False),
        ("mismatch", 2, True, False),
        ("incomplete", 9, False, True),
        ("unsupported", 9, False, True),
    ],
)
async def test_daily_demand_email_is_only_recent_material_utility_data(
    hass, context, generated, freezer, status, maximum, email, local
):
    await demand_context(hass, freezer, generated, status=status, maximum=maximum)
    assert render(hass, generated["demand"]["email"]) is email
    assert render(hass, generated["demand"]["local"]) is local


@pytest.mark.parametrize(
    "changes",
    [
        {"last_checked": "2026-11-06T10:59:00+00:00"},
        {"last_checked": "2026-11-06T17:06:00+00:00"},
        {"latest_complete_day": "2026-11-03"},
        {"latest_complete_day": "2026-11-06"},
        {"latest_complete_day": None},
        {"content_hash": ""},
    ],
)
async def test_stale_future_partial_or_backfilled_demand_cannot_email(
    hass, context, generated, freezer, changes
):
    await demand_context(hass, freezer, generated, **changes)
    assert render(hass, generated["demand"]["email"]) is False
    assert render(hass, generated["demand"]["local"]) is True


async def test_daily_demand_latches_one_attempt_and_ignores_nonmaterial_revisions(
    hass, context, generated, freezer
):
    await demand_context(hass, freezer, generated)
    key = render(hass, generated["demand"]["key"])
    assert render(hass, generated["demand"]["email"]) is True
    hass.states.async_set("input_text.home_energy_demand_review_key", key)
    assert render(hass, generated["demand"]["email"]) is False
    await demand_context(hass, freezer, generated, content_hash="b" * 64)
    assert render(hass, generated["demand"]["email"]) is False
    await demand_context(hass, freezer, generated, maximum=9)
    assert render(hass, generated["demand"]["email"]) is True
    hass.states.async_set("input_text.home_energy_demand_review_day", "2026-11-06")
    assert render(hass, generated["demand"]["email"]) is False


async def test_email_notifier_requires_service_and_existing_nonunavailable_account(
    hass, context, generated
):
    description = HomeEnergySensorDescription(
        key="source_health",
        name="Source health",
        classification="Derived",
        value_fn=lambda _: "Healthy",
    )
    entity = HomeEnergySensor(
        SimpleNamespace(hass=hass, data=None),
        SimpleNamespace(entry_id="mail-test"),
        description,
    )

    def publish_capability():
        attrs = entity.extra_state_attributes
        hass.states.async_set(context["sourceHealth"], "Healthy", attrs)
        return render(hass, generated["emailAvailable"])

    assert publish_capability() is False
    hass.services.async_register("email_notifier", "send", lambda call: None)
    assert publish_capability() is False
    hass.states.async_set("notify.email_notification_sender_1", "unknown")
    assert publish_capability() is True
    hass.states.async_set("notify.email_notification_sender_1", "unavailable")
    assert publish_capability() is False
    hass.states.async_set("notify.email_notification_sender_1", "unknown")
    hass.services.async_remove("email_notifier", "send")
    assert publish_capability() is False


async def test_demand_messages_and_prevalidation_variables_remain_safe(
    hass, context, generated, freezer
):
    await demand_context(hass, freezer, generated)
    text = render(hass, generated["demand"]["message"])
    assert "2026-11-05T17:00:00-07:00" in text and "7.2 kW" in text
    assert "Demand-charge dollars remain unverified" in text
    assert "do not identify which appliance" in text
    cfg = automation(generated, "home_energy_srp_demand_review")

    def templates(value):
        if isinstance(value, str) and ("{{" in value or "{%" in value):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from templates(child)
        elif isinstance(value, list):
            for child in value:
                yield from templates(child)

    for template in templates(cfg):
        render(
            hass,
            template,
            alert_key="test",
            event_key="test",
            this={"entity_id": "automation.test"},
        )
