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
    assert "clock" in result["error"]
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
    assert result["status"] == "Recovery required"
    assert backend.parameters == before
    assert backend.parameters[WEEKLY] is False
    assert control.recovery_required


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
