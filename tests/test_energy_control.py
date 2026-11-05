"""Guarded cloud scheduling, mode switching, durable recovery and shared authority."""

from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import TCPConnector, web
from aiohttp.resolver import ThreadedResolver

from custom_components.home_energy_monitor.energy_control import (
    FUNCTION_ENDPOINT,
    READ_ENDPOINT,
    WEEKLY,
    WEEKLY_ENDPOINT,
    Command,
    ControlError,
    Eg4CloudBackend,
    EnergyControlManager,
    build_control_sensors,
    build_control_switches,
)


def winter_parameters() -> dict:
    """Actual field names and units from the pre-change cloud read, without IDs."""
    result = {
        WEEKLY: True,
        "FUNC_AC_CHARGE": True,
        "FUNC_FORCED_CHG_EN": True,
        "FUNC_GRID_PEAK_SHAVING": True,
        "FUNC_FORCED_DISCHG_EN": False,
        "FUNC_BATTERY_BACKUP_CTRL": False,
        "FUNC_PV_SELL_TO_GRID_EN": False,
        "FUNC_SPORADIC_CHARGE": False,
        "BIT_AC_CHARGE_TYPE": 0,
        "HOLD_AC_CHARGE_POWER_CMD": 2,
        "HOLD_AC_CHARGE_SOC_LIMIT": 101,
        "HOLD_FORCED_CHG_POWER_CMD": 12,
        "HOLD_FORCED_CHG_SOC_LIMIT": 100,
        "_12K_HOLD_GRID_PEAK_SHAVING_POWER": 0,
        "_12K_HOLD_GRID_PEAK_SHAVING_SOC": 23,
        "_12K_HOLD_GRID_PEAK_SHAVING_POWER_2": 0,
        "_12K_HOLD_GRID_PEAK_SHAVING_SOC_2": 20,
        "HOLD_DISCHG_CUT_OFF_SOC_EOD": 20,
    }
    for prefix, first in (
        ("HOLD_AC_CHARGE", (20, 5, 9, 0)),
        ("HOLD_FORCED_CHARGE", (9, 0, 13, 55)),
    ):
        for index in range(3):
            suffix = "" if index == 0 else f"_{index}"
            values = first if index == 0 else (0, 0, 0, 0)
            for field, value in zip(
                ("START_HOUR", "START_MINUTE", "END_HOUR", "END_MINUTE"), values, strict=True
            ):
                result[f"{prefix}_{field}{suffix}"] = value
    for index, value in enumerate((13, 55, 20, 5, 0, 0, 0, 0), 37):
        result[f"LSP_HOLD_DIS_CHG_POWER_TIME_{index}"] = value
    return result


def weekly_values() -> dict:
    result = {}
    for prefix in ("ubACChg", "ubForcedChg", "ubForcedDischg", "ubGridPeakShav"):
        for day in range(1, 8):
            for slot in (1, 2):
                for field in (
                    "PowerCMD",
                    "SOCLimit",
                    "VoltLimit",
                    "StartHour",
                    "StartMinute",
                    "EndHour",
                    "EndMinute",
                ):
                    result[f"{prefix}{field}{slot}_Day_{day}"] = 0
    return result


class MemoryStore:
    def __init__(self) -> None:
        self.data = None
        self.saves = []
        self.fail = False

    async def async_load(self):
        return deepcopy(self.data)

    async def async_save(self, data):
        if self.fail:
            raise OSError("private store unavailable")
        self.data = deepcopy(data)
        self.saves.append(deepcopy(data))


class FakeBackend:
    def __init__(self, store: MemoryStore) -> None:
        self.parameters = winter_parameters()
        self.weekly = weekly_values()
        self.store = store
        self.events = []
        self.fail_once = None
        self.ignore_once = None
        self.fail_all_writes = False
        self.fail_rollback = False
        self.clock_override = None
        self.now = None

    async def snapshot(self, *, weekly):
        self.events.append(("read", weekly, self.parameters[WEEKLY]))
        return {
            "serial": "test-inverter",
            "globals": deepcopy(self.parameters),
            "weekly": deepcopy(self.weekly) if weekly else {},
            "read_at": "2026-11-04T23:00:00+00:00",
            "clock_received_at": {
                key: self.now().isoformat()
                for key in ("HOLD_TIME", "inverterRuntimeDeviceTime")
            },
            "clock": self.clock_override
            if self.clock_override is not None
            else {
                "HOLD_TIME": self.now().strftime("%Y-%m-%d %H:%M:%S"),
                "inverterRuntimeDeviceTime": self.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        }

    async def write(self, command):
        # A persisted transaction must exist before even the first device write.
        assert self.store.data and self.store.data["transaction"]
        journal = self.store.data["transaction"]
        assert journal.get("pending") or journal.get("rollback_pending")
        self.events.append(
            ("write", command.parameter, command.values, self.parameters[WEEKLY])
        )
        if self.fail_all_writes:
            raise ControlError("simulated unreachable inverter")
        if command.parameter == self.fail_once:
            self.fail_once = None
            # A timeout may happen after the inverter actually accepted a write.
            for key, value in zip(command.keys, command.values, strict=True):
                self.parameters[key] = value
            if self.fail_rollback:
                self.fail_all_writes = True
            raise ControlError("simulated acknowledgement loss")
        if command.parameter == self.ignore_once:
            self.ignore_once = None
            return
        for key, value in zip(command.keys, command.values, strict=True):
            self.parameters[key] = value


async def manager(hass, stamp="2026-11-04T16:30:00-07:00"):
    await hass.config.async_set_time_zone("America/Phoenix")
    clock = [datetime.fromisoformat(stamp)]
    for entity in (
        "input_boolean.juicebox_srp_schedule_enabled",
        "input_boolean.juicebox_srp_schedule_valid",
    ):
        hass.states.async_set(entity, "on")
    hass.states.async_set("input_boolean.juicebox_srp_on_peak", "off")
    hass.states.async_set(
        "automation.juicebox_apply_local_charge_policy", "on", {"last_triggered": clock[0]}
    )
    store = MemoryStore()
    backend = FakeBackend(store)
    backend.now = lambda: clock[0]
    control = EnergyControlManager(
        hass,
        SimpleNamespace(entry_id="test-control"),
        SimpleNamespace(),
        backend=backend,
        store=store,
        now=lambda: clock[0],
    )
    control.enabled = True
    return control, backend, store, clock


def fresh_helper(hass, clock, stamp, on_peak=False):
    clock[0] = datetime.fromisoformat(stamp)
    hass.states.async_set("input_boolean.juicebox_srp_on_peak", "on" if on_peak else "off")
    hass.states.async_set(
        "automation.juicebox_apply_local_charge_policy", "on", {"last_triggered": clock[0]}
    )


async def test_program_and_verify_daily_before_switching_weekly_authority(hass):
    control, backend, store, _ = await manager(hass)
    result = await control.async_apply()
    assert result["status"] == "Applied and verified"
    writes = [x for x in backend.events if x[0] == "write"]
    assert writes[-1][1:3] == (WEEKLY, (False,))
    assert all(x[3] is True for x in writes)
    assert any(x[0] == "read" for x in backend.events[1:-2])
    assert backend.parameters["HOLD_AC_CHARGE_START_HOUR"] == 21
    assert backend.parameters["HOLD_AC_CHARGE_END_HOUR"] == 5
    assert backend.parameters["HOLD_AC_CHARGE_START_HOUR_1"] == 15
    assert backend.parameters["HOLD_AC_CHARGE_END_HOUR_1"] == 17
    assert backend.parameters["HOLD_FORCED_CHARGE_END_HOUR"] == 15
    assert [backend.parameters[f"LSP_HOLD_DIS_CHG_POWER_TIME_{n}"] for n in range(37, 45)] == [
        5,
        0,
        9,
        0,
        17,
        0,
        21,
        0,
    ]
    assert backend.parameters["HOLD_AC_CHARGE_SOC_LIMIT"] == 101
    assert backend.parameters["HOLD_FORCED_CHG_POWER_CMD"] == 12  # Already kW, not120.
    assert backend.parameters["HOLD_DISCHG_CUT_OFF_SOC_EOD"] == 20
    assert store.data["transaction"]["state"] == "verified"


async def test_idempotent_periodic_reads_reverify_without_rewriting(hass):
    control, backend, _, clock = await manager(hass)
    await control.async_apply()
    events = len(backend.events)
    await control.async_apply()
    assert len(backend.events) == events
    fresh_helper(hass, clock, "2026-11-04T16:46:00-07:00")
    await control.async_apply()
    assert any(x[0] == "read" for x in backend.events[events:])
    assert not any(x[0] == "write" for x in backend.events[events:])


@pytest.mark.parametrize("failure", ["timeout", "ignored_write"])
async def test_partial_failure_restores_original_settings_and_does_not_switch_mode(
    hass, failure
):
    control, backend, store, _ = await manager(hass)
    original = deepcopy(backend.parameters)
    if failure == "timeout":
        backend.fail_once = "HOLD_AC_CHARGE_END_TIME"
    else:
        backend.ignore_once = "HOLD_AC_CHARGE_END_TIME"
    result = await control.async_apply()
    assert result["status"] == "Error; prior settings restored"
    assert backend.parameters == original
    assert store.data["transaction"]["state"] == "restored"
    assert not any(
        x[0] == "write" and x[1] == WEEKLY and x[2] == (False,) for x in backend.events
    )


async def test_durable_backup_failure_prevents_any_device_write(hass):
    control, backend, store, _ = await manager(hass)
    store.fail = True
    result = await control.async_apply()
    assert result["status"] == "Blocked"
    assert not any(x[0] == "write" for x in backend.events)


async def test_rollback_failure_disables_master_and_requires_recovery(hass):
    control, backend, store, _ = await manager(hass)
    backend.fail_once = "HOLD_AC_CHARGE_END_TIME"
    backend.fail_rollback = True
    result = await control.async_apply()
    assert result["status"] == "Recovery required"
    assert not control.enabled and control.recovery_required
    assert store.data["recovery_required"]
    with pytest.raises(ControlError, match="Restore"):
        await control.async_set_enabled(True)


@pytest.mark.parametrize("state", ["writing", "restoring"])
async def test_restart_with_interrupted_journal_stays_disabled(hass, state):
    control, _, store, _ = await manager(hass)
    store.data = {"enabled": True, "transaction": {"state": state}}
    await control.async_load()
    assert not control.enabled and control.recovery_required
    await control.async_shutdown()


async def test_weekend_full_day_profile_and_summer_restoration_preserve_weekly_table(hass):
    control, backend, _, clock = await manager(hass)
    original = deepcopy(backend.parameters)
    await control.async_apply()
    fresh_helper(hass, clock, "2026-11-07T16:30:00-07:00")
    await control.async_apply()
    assert backend.parameters["FUNC_GRID_PEAK_SHAVING"] is False
    assert backend.parameters["HOLD_AC_CHARGE_POWER_CMD"] == 4
    assert backend.parameters["HOLD_AC_CHARGE_START_HOUR"] == 0
    assert backend.parameters["HOLD_AC_CHARGE_END_HOUR"] == 12
    assert backend.parameters["HOLD_AC_CHARGE_START_HOUR_1"] == 12
    assert backend.parameters["HOLD_AC_CHARGE_END_HOUR_1"] == 0
    assert backend.parameters["HOLD_FORCED_CHARGE_START_HOUR"] == 9
    assert backend.parameters["HOLD_FORCED_CHARGE_END_HOUR"] == 15
    weekly = deepcopy(backend.weekly)
    fresh_helper(hass, clock, "2027-05-03T10:00:00-07:00")
    result = await control.async_apply()
    assert result["status"] == "Applied and verified"
    assert backend.parameters[WEEKLY] is True
    assert (
        backend.parameters["_12K_HOLD_GRID_PEAK_SHAVING_SOC"]
        == original["_12K_HOLD_GRID_PEAK_SHAVING_SOC"]
    )
    assert (
        backend.parameters["HOLD_AC_CHARGE_POWER_CMD"] == original["HOLD_AC_CHARGE_POWER_CMD"]
    )
    assert backend.weekly == weekly


async def test_changed_native_weekly_table_blocks_summer_restoration(hass):
    control, backend, _, clock = await manager(hass)
    await control.async_apply()
    backend.weekly["ubACChgPowerCMD1_Day_1"] = 9
    count = len([x for x in backend.events if x[0] == "write"])
    fresh_helper(hass, clock, "2027-05-03T10:00:00-07:00")
    result = await control.async_apply()
    assert result["status"] == "Blocked"
    assert len([x for x in backend.events if x[0] == "write"]) == count


@pytest.mark.parametrize("change", ["disabled", "stale", "future", "mismatch", "invalid"])
async def test_shared_policy_failure_never_mutates_inverter(hass, change):
    control, backend, _, clock = await manager(hass)
    if change == "disabled":
        hass.states.async_set("automation.juicebox_apply_local_charge_policy", "off")
    elif change in ("stale", "future"):
        delta = timedelta(seconds=-181 if change == "stale" else 1)
        hass.states.async_set(
            "automation.juicebox_apply_local_charge_policy",
            "on",
            {"last_triggered": clock[0] + delta},
        )
    elif change == "mismatch":
        hass.states.async_set("input_boolean.juicebox_srp_on_peak", "on")
    else:
        hass.states.async_set("input_boolean.juicebox_srp_schedule_valid", "off")
    result = await control.async_apply()
    assert result["status"] == "Blocked"
    assert backend.events == []


async def test_dry_run_and_disabled_master_do_not_write(hass):
    control, backend, _, _ = await manager(hass)
    control.enabled = False
    result = await control.async_apply(dry_run=True)
    assert result["dry_run"] and result["changes"] and result["authority_change"]
    assert not any(x[0] == "write" for x in backend.events)
    await control.async_apply()
    assert control.status == "Disabled"


async def test_entity_factories_build_real_sensor_and_switch_entities(hass):
    control, _, _, _ = await manager(hass)
    owner = SimpleNamespace(energy_control=control)
    sensors, switches = build_control_sensors(owner), build_control_switches(owner)
    assert [x.entity_id for x in sensors] == [
        "sensor.home_energy_inverter_schedule_status",
        "sensor.home_energy_srp_period",
    ]
    assert switches[0].entity_id == "switch.home_energy_automatic_inverter_schedule"
    assert sensors[1].native_value == "Winter off peak"
    assert sensors[0].extra_state_attributes["shared_tariff_validated"]


async def test_cloud_adapter_uses_uncached_verified_request_shapes():
    client = SimpleNamespace(_request=AsyncMock(return_value={"success": True}))
    backend = Eg4CloudBackend(client, "test-inverter")
    await backend.write(Command("time", "HOLD_PEAK_SHAVING_START_TIME_1", ("h", "m"), (5, 0)))
    kwargs = client._request.call_args.kwargs
    assert kwargs["data"] == {
        "inverterSn": "test-inverter",
        "clientType": "WEB",
        "remoteSetType": "NORMAL",
        "timeParam": "HOLD_PEAK_SHAVING_START_TIME_1",
        "hour": 5,
        "minute": 0,
    }
    assert "cache_key" not in kwargs
    await backend.write(Command("function", WEEKLY, (WEEKLY,), (False,)))
    assert client._request.call_args.args[1] == FUNCTION_ENDPOINT
    assert client._request.call_args.kwargs["data"]["enable"] == "false"
    await backend.write(Command("number", "HOLD_AC_CHARGE_SOC_LIMIT", ("soc",), (101.0,)))
    assert client._request.call_args.kwargs["data"]["valueText"] == "101"
    await backend.write(Command("number", "HOLD_AC_CHARGE_POWER_CMD", ("power",), (2.5,)))
    assert client._request.call_args.kwargs["data"]["valueText"] == "2.5"
    client._request.return_value = {"success": True, WEEKLY: True}
    await backend.snapshot(weekly=False)
    calls = client._request.call_args_list[-4:]
    assert all(x.args[1] == READ_ENDPOINT and "cache_key" not in x.kwargs for x in calls)
    assert calls[-1].kwargs["data"]["startRegister"] == 233


async def test_daily_to_weekly_failure_restores_daily_fields_before_releasing_weekly(hass):
    control, backend, _, clock = await manager(hass)
    await control.async_apply()
    before = deepcopy(backend.parameters)
    fresh_helper(hass, clock, "2027-05-03T10:00:00-07:00")
    backend.fail_once = WEEKLY  # Device enables weekly, acknowledgement is lost.
    result = await control.async_apply()
    assert result["status"] == "Error; prior settings restored"
    assert backend.parameters == before
    rollback_release = [x for x in backend.events if x[0] == "write" and x[1] == WEEKLY][-1]
    assert rollback_release[2] == (False,)
    # The formerly active daily window was restored before that final release.
    assert backend.parameters["HOLD_AC_CHARGE_START_HOUR"] == 21


@pytest.mark.parametrize(
    "clocks",
    [
        {},
        {"HOLD_TIME": "bad"},
        {
            "HOLD_TIME": "2026-11-04 16:27:59",
            "inverterRuntimeDeviceTime": "2026-11-04 16:30:00",
        },
        {
            "HOLD_TIME": "2026-11-04 16:30:00",
            "inverterRuntimeDeviceTime": "2026-11-04 16:32:01",
        },
    ],
)
async def test_missing_invalid_or_skewed_inverter_clock_blocks_writes(hass, clocks):
    control, backend, _, _ = await manager(hass)
    backend.clock_override = clocks
    result = await control.async_apply()
    assert result["status"] == "Blocked"
    assert result["error"]
    assert not any(x[0] == "write" for x in backend.events)


async def test_periodic_readback_preserves_last_real_rollback_journal(hass):
    control, backend, store, clock = await manager(hass)
    await control.async_apply()
    transaction = deepcopy(store.data["transaction"])
    assert transaction["undo"]
    fresh_helper(hass, clock, "2026-11-04T16:46:00-07:00")
    writes = [x for x in backend.events if x[0] == "write"]
    await control.async_apply()
    assert store.data["transaction"] == transaction
    assert [x for x in backend.events if x[0] == "write"] == writes
    await control.async_rollback()
    assert backend.parameters == winter_parameters()


@pytest.mark.parametrize(
    "client",
    [
        SimpleNamespace(
            base_url="https://example.invalid", verify_ssl=False, _request=AsyncMock()
        ),
        SimpleNamespace(
            base_url="http://example.invalid", verify_ssl=True, _request=AsyncMock()
        ),
        SimpleNamespace(base_url="https://example.invalid", verify_ssl=True),
    ],
)
async def test_loaded_backend_rejects_unverified_or_noncloud_client(hass, client):
    from homeassistant.config_entries import ConfigEntryState

    control, _, _, _ = await manager(hass)
    control._backend_override = None
    coordinator = SimpleNamespace(
        require_client=lambda: client, data={"devices": {"test": {"type": "inverter"}}}
    )
    entry = SimpleNamespace(state=ConfigEntryState.LOADED, runtime_data=coordinator)
    with (
        patch.object(hass.config_entries, "async_entries", return_value=[entry]),
        pytest.raises(ControlError, match="certificate-verified"),
    ):
        control._backend()


async def test_cloud_weekly_backup_uses_exact_portal_ranges_and_retains_clocks():
    async def response(_method, endpoint, *, data):
        if endpoint == WEEKLY_ENDPOINT:
            assert data["startRegister"] in (500, 612)
            return {"success": True, **weekly_values()}
        return {
            "success": True,
            WEEKLY: True,
            "HOLD_TIME": "2026-11-04 16:30:00",
            "inverterRuntimeDeviceTime": "2026-11-04 16:29:50",
        }

    client = SimpleNamespace(_request=AsyncMock(side_effect=response))
    snapshot = await Eg4CloudBackend(client, "test-inverter").snapshot(weekly=True)
    calls = client._request.call_args_list[-3:]
    assert [
        (x.args[1], x.kwargs["data"]["startRegister"], x.kwargs["data"]["pointNumber"])
        for x in calls
    ] == [(READ_ENDPOINT, 200, 40), (WEEKLY_ENDPOINT, 500, 112), (WEEKLY_ENDPOINT, 612, 112)]
    assert snapshot["clock"]["HOLD_TIME"] == "2026-11-04 16:30:00"
    assert len(snapshot["weekly"]) == 392


async def test_snapshot_routes_real_encoded_forms_to_the_correct_register_endpoint(
    aiohttp_client, socket_enabled
):
    """Exercise HTTP encoding and reject the selector/table mix-up the mock hid."""
    received = []

    async def portal(request):
        assert request.method == "POST"
        assert request.content_type == "application/x-www-form-urlencoded"
        form = dict(await request.post())
        received.append((request.path, form))
        assert form["inverterSn"] == "test-inverter"
        if "autoRetry" in form:
            # aiohttp encodes bool False as text "False"; the live API accepts it.
            assert form["autoRetry"].lower() == "false"
        start, count = int(form["startRegister"]), int(form["pointNumber"])
        if request.path == WEEKLY_ENDPOINT:
            if (start, count) not in ((500, 112), (612, 112)):
                return web.json_response({"success": False, "msg": "PARAM_ERROR"})
            prefixes = (
                ("ubACChg", "ubForcedChg")
                if start == 500
                else ("ubForcedDischg", "ubGridPeakShav")
            )
            return web.json_response(
                {
                    "success": True,
                    **{k: v for k, v in weekly_values().items() if k.startswith(prefixes)},
                }
            )
        assert request.path == READ_ENDPOINT
        assert (start, count) in ((0, 127), (127, 127), (240, 127), (233, 1), (200, 40))
        data = {"success": True}
        if start in (127, 233, 200):
            data[WEEKLY] = True
        if start == 0:
            data["HOLD_TIME"] = "2026-11-04 16:30:00"
        return web.json_response(data)

    app = web.Application()
    app.router.add_post(READ_ENDPOINT, portal)
    app.router.add_post(WEEKLY_ENDPOINT, portal)
    # A numeric loopback host needs no DNS. Avoid the optional c-ares resolver's
    # background shutdown thread, keeping HA's strict resource cleanup intact.
    http = await aiohttp_client(app, connector=TCPConnector(resolver=ThreadedResolver()))

    class FormClient:
        async def _request(self, method, endpoint, *, data):
            async with http.request(method, endpoint, data=data) as response:
                return await response.json()

    backend = Eg4CloudBackend(FormClient(), "test-inverter")
    snapshot = await backend.snapshot(weekly=True)

    assert [
        (path, int(form["startRegister"]), int(form["pointNumber"])) for path, form in received
    ] == [
        (READ_ENDPOINT, 0, 127),
        (READ_ENDPOINT, 127, 127),
        (READ_ENDPOINT, 240, 127),
        (READ_ENDPOINT, 233, 1),
        (READ_ENDPOINT, 200, 40),
        (WEEKLY_ENDPOINT, 500, 112),
        (WEEKLY_ENDPOINT, 612, 112),
    ]
    assert snapshot["globals"][WEEKLY] is True
    assert snapshot["weekly"] == weekly_values()
    assert snapshot["clock"]["HOLD_TIME"] == "2026-11-04 16:30:00"
    with pytest.raises(ControlError, match="did not accept"):
        await backend._request(
            WEEKLY_ENDPOINT,
            {"inverterSn": "test-inverter", "startRegister": 200, "pointNumber": 40},
        )


async def test_explicit_rollback_will_not_reactivate_a_changed_weekly_table(hass):
    control, backend, _, _ = await manager(hass)
    await control.async_apply()
    backend.weekly["ubACChgPowerCMD1_Day_1"] = 9
    before = deepcopy(backend.parameters)
    result = await control.async_rollback()
    assert result["status"] == "Rollback blocked"
    assert backend.parameters == before
    assert backend.parameters[WEEKLY] is False
    assert not control.recovery_required
    assert control.transaction["state"] == "verified"


async def test_summer_weekends_keep_the_preserved_native_weekly_recipe(hass):
    control, backend, _, clock = await manager(hass)
    await control.async_set_enabled(True)
    fresh_helper(hass, clock, "2027-05-08T10:00:00-07:00")
    result = await control.async_apply()
    assert result["profile"] == "summer-weekly"
    assert backend.parameters[WEEKLY] is True
    assert backend.weekly == control.baseline["weekly"]
    assert (
        backend.parameters["HOLD_AC_CHARGE_SOC_LIMIT"]
        == (control.baseline["globals"]["HOLD_AC_CHARGE_SOC_LIMIT"])
    )


@pytest.mark.parametrize("failure", ["invalid", "stale", "future"])
async def test_tariff_recovery_requires_a_fresh_read_even_inside_verification_cache(
    hass, failure
):
    control, backend, store, clock = await manager(hass)
    await control.async_apply()
    original = deepcopy(store.data["transaction"])
    if failure == "invalid":
        hass.states.async_set("input_boolean.juicebox_srp_schedule_valid", "off")
    else:
        delta = timedelta(seconds=-181 if failure == "stale" else 1)
        hass.states.async_set(
            "automation.juicebox_apply_local_charge_policy",
            "on",
            {"last_triggered": clock[0] + delta},
        )
    assert (await control.async_apply())["status"] == "Blocked"
    fresh_helper(hass, clock, "2026-11-04T16:31:00-07:00")
    hass.states.async_set("input_boolean.juicebox_srp_schedule_valid", "on")
    before = len(backend.events)
    result = await control.async_apply()
    assert result["status"] == "Applied and verified" and result["error"] is None
    assert result["last_verified"] == clock[0].isoformat()
    assert any(x[0] == "read" for x in backend.events[before:])
    assert not any(x[0] == "write" for x in backend.events[before:])
    assert store.data["transaction"] == original


@pytest.mark.parametrize("latched", [False, True])
async def test_failed_preview_and_recovered_preview_preserve_operating_state(hass, latched):
    control, backend, store, clock = await manager(hass)
    await control.async_apply()
    if latched:
        control.enabled = False
        control.recovery_required = True
        control.status, control.error = "Recovery required", "Prior recovery failed"
        control.backoff_until = clock[0] + timedelta(minutes=2)
    before = deepcopy(control.state())
    saved = deepcopy(store.saves)
    events = len(backend.events)
    backend.clock_override = {
        "HOLD_TIME": (clock[0] - timedelta(seconds=66)).strftime("%Y-%m-%d %H:%M:%S"),
        "inverterRuntimeDeviceTime": (clock[0] - timedelta(seconds=131)).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }
    failed = await control.async_apply(dry_run=True)
    assert failed["dry_run"] and not failed["preview_ready"]
    assert "Runtime frame" in failed["preview_error"]
    assert failed["runtime_frame_age_seconds"] == 131
    assert control.state() == before
    backend.clock_override = None
    good = await control.async_apply(dry_run=True)
    assert good["preview_ready"] and good["preview_error"] is None
    assert control.state() == before
    assert store.saves == saved
    assert not any(x[0] == "write" for x in backend.events[events:])
    if latched:
        with pytest.raises(ControlError, match="Restore"):
            await control.async_set_enabled(True)


async def test_tariff_invalid_preview_preserves_latched_error_and_backoff(hass):
    control, backend, _, clock = await manager(hass)
    control.recovery_required = True
    control.status, control.error = "Recovery required", "Interrupted write"
    control.backoff_until = clock[0] + timedelta(minutes=5)
    before = deepcopy(control.state())
    hass.states.async_set("input_boolean.juicebox_srp_schedule_valid", "off")
    result = await control.async_apply(dry_run=True)
    assert not result["preview_ready"] and "invalid" in result["preview_error"]
    assert control.status == before["status"] and control.error == before["error"]
    assert control.backoff_until == clock[0] + timedelta(minutes=5)
    assert control.recovery_required and backend.events == []


async def test_initial_preview_captures_baseline_once_without_changing_operating_state(hass):
    control, backend, store, _ = await manager(hass)
    control.enabled, control.status = False, "Disabled"
    before = deepcopy(control.state())
    first = await control.async_apply(dry_run=True)
    assert first["preview_ready"] and first["changes"]
    assert control.baseline and len(store.saves) == 1
    await control.async_apply(dry_run=True)
    assert len(store.saves) == 1
    assert control.state() == before
    assert not any(x[0] == "write" for x in backend.events)


@pytest.mark.parametrize(
    ("hold_offset", "frame_age", "message"),
    [
        (121, 0, "RTC"),
        (-121, 0, "RTC"),
        (66, 131, "Runtime frame is older"),
        (0, -1, "Runtime frame timestamp is in the future"),
    ],
)
async def test_actual_rtc_and_frame_age_have_distinct_strict_failures(
    hass, hold_offset, frame_age, message
):
    control, backend, _, clock = await manager(hass)
    backend.clock_override = {
        "HOLD_TIME": (clock[0] - timedelta(seconds=hold_offset)).strftime("%Y-%m-%d %H:%M:%S"),
        "inverterRuntimeDeviceTime": (clock[0] - timedelta(seconds=frame_age)).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }
    result = await control.async_apply()
    assert result["status"] == "Blocked" and message in result["error"]
    assert not any(x[0] == "write" for x in backend.events)
    if frame_age == 131:
        assert result["clock_skew_seconds"] == {"HOLD_TIME": 66}
        assert result["runtime_frame_age_seconds"] == 131
        backend.clock_override = None
        fresh_helper(hass, clock, "2026-11-04T16:36:00-07:00")
        assert (await control.async_apply())["status"] == "Applied and verified"


async def test_receipt_provenance_separates_rtc_offset_from_bulk_read_elapsed_time(hass):
    control, backend, _, clock = await manager(hass)
    snap = await backend.snapshot(weekly=True)
    snap["clock"]["HOLD_TIME"] = (clock[0] - timedelta(seconds=120)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    clock[0] += timedelta(seconds=4)
    control._validate_clock(snap)
    assert control.clock_skew_seconds == {"HOLD_TIME": 120}
    assert control.runtime_frame_age_seconds == 4
    assert control.clock_receipt_age_seconds["HOLD_TIME"] == 4
    clock[0] += timedelta(seconds=117)
    with pytest.raises(ControlError, match="receipt is stale"):
        control._validate_clock(snap)


@pytest.mark.parametrize("receipt", [None, "2026-11-04T16:30:00", "2026-11-04T16:30:01-07:00"])
async def test_missing_naive_or_future_receipt_cannot_admit_a_write(hass, receipt):
    control, backend, _, _ = await manager(hass)
    snapshot = await backend.snapshot(weekly=True)
    snapshot["clock_received_at"]["HOLD_TIME"] = receipt
    with pytest.raises(ControlError, match="receipt"):
        control._validate_clock(snapshot)
    assert not any(x[0] == "write" for x in backend.events)


async def test_persistent_postwrite_mismatch_stops_after_three_rollbacks_and_can_resume(hass):
    control, backend, store, clock = await manager(hass)
    write = backend.write
    broken = True

    async def persistently_ignore_target(command):
        if (
            broken
            and command.parameter == "HOLD_AC_CHARGE_END_TIME"
            and command.values == (5, 0)
        ):
            backend.ignore_once = command.parameter
        await write(command)

    backend.write = persistently_ignore_target
    original = deepcopy(backend.parameters)
    for attempt, stamp in enumerate(
        [
            "2026-11-04T16:30:00-07:00",
            "2026-11-04T16:36:00-07:00",
            "2026-11-04T16:42:00-07:00",
        ],
        1,
    ):
        fresh_helper(hass, clock, stamp)
        result = await control.async_apply()
        assert control.post_write_failures == attempt
        assert backend.parameters == original  # Every rollback really restored its basis.
        assert not control.recovery_required
    assert result["status"] == "Automatic retries stopped"
    assert not control.enabled and control.retry_exhausted
    assert store.data["retry_exhausted"] and store.data["post_write_failures"] == 3
    before = list(backend.events)
    assert (await control.async_apply())["status"] == "Automatic retries stopped"
    assert backend.events == before
    await control.async_load()
    assert not control.enabled and control.retry_exhausted
    broken = False
    result = await control.async_set_enabled(True)
    assert result["status"] == "Applied and verified"
    assert control.post_write_failures == 0 and not store.data["retry_exhausted"]
    await control.async_shutdown()


async def test_readonly_failure_does_not_consume_postwrite_retry_budget(hass):
    control, backend, _, clock = await manager(hass)
    backend.clock_override = {"HOLD_TIME": "bad"}
    for stamp in ["2026-11-04T16:30:00-07:00", "2026-11-04T16:36:00-07:00"]:
        fresh_helper(hass, clock, stamp)
        await control.async_apply()
    assert control.post_write_failures == 0 and not control.retry_exhausted
    assert not any(x[0] == "write" for x in backend.events)


async def test_rollback_without_a_journal_is_a_prewrite_refusal_not_a_recovery_latch(hass):
    control, backend, store, _ = await manager(hass)
    result = await control.async_rollback()
    assert result["status"] == "Rollback blocked"
    assert not control.recovery_required and not store.data["recovery_required"]
    assert not any(x[0] == "write" for x in backend.events)
    assert (await control.async_set_enabled(True))["status"] == "Applied and verified"


async def test_interrupted_rollback_refusal_keeps_the_real_latch(hass):
    control, backend, store, _ = await manager(hass)
    await control.async_apply()
    control.transaction["state"] = "writing"
    control.recovery_required = True
    backend.weekly["ubACChgPowerCMD1_Day_1"] = 99
    before = len(backend.events)
    result = await control.async_rollback()
    assert result["status"] == "Recovery required"
    assert control.recovery_required and store.data["recovery_required"]
    assert not any(x[0] == "write" for x in backend.events[before:])
    with pytest.raises(ControlError, match="Restore"):
        await control.async_set_enabled(True)


@pytest.mark.parametrize(
    "stamp",
    ["2026-11-07T16:30:00-07:00", "2026-11-26T16:30:00-07:00", "2026-07-03T16:30:00-07:00"],
)
async def test_nonpeak_preview_and_applied_settings_use_the_admitted_pure_recipe(hass, stamp):
    from custom_components.home_energy_monitor.seasonal_policy import build_profile_plan

    control, backend, _, clock = await manager(hass)
    await control.async_apply()
    fresh_helper(hass, clock, stamp)
    plan = build_profile_plan(
        clock[0],
        shared=control._shared(),
        native_weekly_enabled=False,
        weekly_backup_verified=True,
        daily_plan_verified=True,
    )
    assert plan.can_apply
    profile = plan.desired_profile
    assert profile is not None
    preview = await control.async_apply(dry_run=True)
    assert preview["preview_ready"]
    assert (await control.async_apply())["status"] == "Applied and verified"
    for change in preview["changes"]:
        assert [backend.parameters[key] for key in change["keys"]] == list(change["values"])
    for index, window in enumerate(profile.ac_windows):
        suffix = "" if index == 0 else f"_{index}"
        assert (
            f"{backend.parameters['HOLD_AC_CHARGE_START_HOUR' + suffix]:02}:00"
            == window.window.start
        )
        assert (
            f"{backend.parameters['HOLD_AC_CHARGE_END_HOUR' + suffix]:02}:00"
            == window.window.end
        )
        assert backend.parameters["HOLD_AC_CHARGE_POWER_CMD"] == window.power_kw == 4
    assert backend.parameters["FUNC_FORCED_CHG_EN"] is profile.pv_priority_enabled is True
    assert profile.pv_windows[0].start == "09:00"
    assert backend.parameters["HOLD_FORCED_CHARGE_START_HOUR"] == 9
    assert profile.pv_windows[0].end == "15:00"
    assert backend.parameters["HOLD_FORCED_CHARGE_END_HOUR"] == 15
    assert backend.parameters["FUNC_GRID_PEAK_SHAVING"] is profile.peak_shaving_enabled is False
    assert backend.parameters["HOLD_DISCHG_CUT_OFF_SOC_EOD"] == 20


async def test_snapshot_retains_receipts_for_each_range_and_its_actual_clock_origin():
    clock = datetime.fromisoformat("2026-11-04T16:30:00-07:00")

    async def response(_method, _endpoint, *, data):
        if data["startRegister"] == 0:
            return {
                "success": True,
                WEEKLY: True,
                "HOLD_TIME": "2026-11-04 16:29:08",
                "inverterRuntimeDeviceTime": "2026-11-04 16:30:00",
            }
        return {"success": True, WEEKLY: True}

    with patch("custom_components.home_energy_monitor.energy_control.datetime") as dates:
        dates.now.side_effect = [clock + timedelta(seconds=x) for x in (0, 1, 2, 3, 4)]
        snapshot = await Eg4CloudBackend(
            SimpleNamespace(_request=AsyncMock(side_effect=response)), "test-inverter"
        ).snapshot(weekly=False)
    assert [r["start"] for r in snapshot["read_receipts"]] == [0, 127, 240, 233]
    assert (
        snapshot["read_receipts"][-1]["received_at"]
        == (clock + timedelta(seconds=3)).isoformat()
    )
    assert snapshot["clock_received_at"] == {
        "HOLD_TIME": clock.isoformat(),
        "inverterRuntimeDeviceTime": clock.isoformat(),
    }
    assert snapshot["read_at"] == (clock + timedelta(seconds=4)).isoformat()


async def test_rollback_clock_refusal_before_a_write_preserves_verified_journal(hass):
    control, backend, store, clock = await manager(hass)
    await control.async_apply()
    before = len(backend.events)
    journal = deepcopy(store.data["transaction"])
    backend.clock_override = {
        "HOLD_TIME": clock[0].strftime("%Y-%m-%d %H:%M:%S"),
        "inverterRuntimeDeviceTime": (clock[0] - timedelta(seconds=131)).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }
    result = await control.async_rollback()
    assert result["status"] == "Rollback blocked" and not control.recovery_required
    assert control.transaction == journal == store.data["transaction"]
    assert not any(x[0] == "write" for x in backend.events[before:])
    backend.clock_override = None
    assert (await control.async_rollback())["status"] == "Restored prior settings"


async def test_restore_journal_save_failure_before_first_write_does_not_latch(hass):
    control, backend, store, _ = await manager(hass)
    await control.async_apply()
    before = len(backend.events)
    snapshot = backend.snapshot

    async def reject_store_after_preflight(*, weekly):
        value = await snapshot(weekly=weekly)
        store.fail = True
        return value

    backend.snapshot = reject_store_after_preflight
    result = await control.async_rollback()
    assert result["status"] == "Rollback blocked" and not control.recovery_required
    assert control.transaction["state"] == "verified"
    assert "rollback_pending" not in control.transaction
    assert not any(x[0] == "write" for x in backend.events[before:])
    assert store.data["transaction"]["state"] == "verified"
