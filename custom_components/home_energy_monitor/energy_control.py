"""Guarded seasonal EG4 scheduling through the existing loaded cloud client.

Default off. Every mutation has a durable local journal, uncached readback and
bounded rollback. This module never handles credentials or raw dongle writes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PEAK_ON, PEAK_SCHEDULE_VALID
from .seasonal_policy import (
    PHOENIX,
    ChargeWindow,
    InverterProfile,
    SharedSchedule,
    TimeWindow,
    build_profile_plan,
    evaluate_tariff,
)

WEEKLY = "FUNC_ENERTEK_WORKING_MODE"
VERIFY_INTERVAL = timedelta(minutes=15)
ERROR_BACKOFF = timedelta(minutes=5)
MAX_POST_WRITE_FAILURES = 3
READ_ENDPOINT = "/WManage/web/maintain/remoteRead/read"
WEEKLY_ENDPOINT = "/WManage/web/maintain/remoteWeeklyOperation/readValues"
WRITE_TIME_ENDPOINT = "/WManage/web/maintain/remoteSet/writeTime"
FUNCTION_ENDPOINT = "/WManage/web/maintain/remoteSet/functionControl"
WRITE_ENDPOINT = "/WManage/web/maintain/remoteSet/write"


class ControlError(Exception):
    """A sanitized error suitable for a household status entity."""


@dataclass(frozen=True, slots=True)
class Command:
    """One verified vendor operation and its corresponding readback fields."""

    kind: str
    parameter: str
    keys: tuple[str, ...]
    values: tuple[float | bool, ...]

    def matches(self, parameters: dict[str, float | bool]) -> bool:
        return all(
            parameters.get(key) == value
            for key, value in zip(self.keys, self.values, strict=True)
        )

    def inverse(self, parameters: dict[str, float | bool]) -> Command:
        if any(key not in parameters for key in self.keys):
            raise ControlError("A setting is missing from the rollback snapshot")
        return Command(
            self.kind, self.parameter, self.keys, tuple(parameters[k] for k in self.keys)
        )

    def record(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "parameter": self.parameter,
            "keys": self.keys,
            "values": self.values,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> Command:
        return cls(
            record["kind"], record["parameter"], tuple(record["keys"]), tuple(record["values"])
        )


def _numeric(response: dict[str, Any]) -> dict[str, float | bool]:
    """Retain numeric parameter data only, excluding account/device metadata."""
    result: dict[str, float | bool] = {}
    for key, value in response.items():
        if not key.startswith(("HOLD_", "FUNC_", "BIT_", "_12K_", "LSP_", "ub")):
            continue
        if isinstance(value, (bool, int, float)) and isfinite(value):
            result[key] = value
        elif isinstance(value, str):
            try:
                parsed = float(value)
                if isfinite(parsed):
                    result[key] = parsed
            except ValueError:
                continue
    return result


def _weekly_complete(parameters: dict[str, float | bool]) -> bool:
    fields = (
        "PowerCMD",
        "SOCLimit",
        "VoltLimit",
        "StartHour",
        "StartMinute",
        "EndHour",
        "EndMinute",
    )
    return all(
        f"{prefix}{field}{slot}_Day_{day}" in parameters
        for prefix in ("ubACChg", "ubForcedChg", "ubForcedDischg", "ubGridPeakShav")
        for field in fields
        for slot in (1, 2)
        for day in range(1, 8)
    )


def _safe_baseline(parameters: dict[str, float | bool]) -> None:
    """Refuse an ambiguous basis or an unrequested forced-export configuration."""
    required = (
        WEEKLY,
        "FUNC_AC_CHARGE",
        "FUNC_FORCED_CHG_EN",
        "FUNC_GRID_PEAK_SHAVING",
        "FUNC_FORCED_DISCHG_EN",
        "FUNC_BATTERY_BACKUP_CTRL",
        "FUNC_PV_SELL_TO_GRID_EN",
        "FUNC_SPORADIC_CHARGE",
        "BIT_AC_CHARGE_TYPE",
        "HOLD_FORCED_CHG_POWER_CMD",
    )
    if any(key not in parameters for key in required):
        raise ControlError("EG4 readback omitted required scheduling fields")
    if parameters["BIT_AC_CHARGE_TYPE"] != 0:
        raise ControlError("AC charging is not on the verified time basis")
    if not parameters["FUNC_FORCED_CHG_EN"]:
        raise ControlError("The preserved PV-priority mode is not enabled")
    if any(parameters[key] for key in required[4:8]):
        raise ControlError("Backup, forced export or sporadic charging needs operator review")


class Eg4CloudBackend:
    """Small adapter over the loaded integration's authenticated cloud client."""

    def __init__(self, client: Any, serial: str) -> None:
        self.client, self.serial = client, serial

    async def _request(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(2):
            try:
                # No cache key: an acknowledged write is not verification.
                response = await asyncio.wait_for(
                    self.client._request("POST", endpoint, data=data), timeout=25
                )
            except Exception as err:
                if attempt == 0:
                    await asyncio.sleep(0.2)
                    continue
                raise ControlError(f"EG4 request failed ({type(err).__name__})") from None
            if not isinstance(response, dict):
                raise ControlError("EG4 returned an unexpected response")
            if response.get("success") is not True:
                transient = "DATAFRAME_TIMEOUT" in str(
                    response.get("msg", response.get("message", ""))
                )
                if transient and attempt == 0:
                    await asyncio.sleep(0.2)
                    continue
                raise ControlError("EG4 did not accept the requested operation")
            return response
        raise ControlError("EG4 request retry limit reached")

    async def snapshot(self, *, weekly: bool) -> dict[str, Any]:
        parameters: dict[str, float | bool] = {}
        clocks: dict[str, str] = {}
        clock_received_at: dict[str, str] = {}
        read_receipts: list[dict[str, Any]] = []
        for start, count in ((0, 127), (127, 127), (240, 127), (233, 1)):
            response = await self._request(
                READ_ENDPOINT,
                {
                    "inverterSn": self.serial,
                    "startRegister": start,
                    "pointNumber": count,
                    "autoRetry": False,
                },
            )
            received_at = datetime.now(UTC).isoformat()
            read_receipts.append({"start": start, "count": count, "received_at": received_at})
            parameters.update(_numeric(response))
            for key in ("HOLD_TIME", "inverterRuntimeDeviceTime"):
                if key in response and isinstance(response[key], str):
                    clocks[key] = response[key]
                    clock_received_at[key] = received_at
        if WEEKLY not in parameters or parameters[WEEKLY] not in (True, False):
            raise ControlError("Native weekly authority could not be read")
        weekly_values: dict[str, float | bool] = {}
        if weekly:
            # The portal routes selector registers below 500 through remoteRead;
            # only the weekly tables use remoteWeeklyOperation/readValues.
            selector = await self._request(
                READ_ENDPOINT,
                {
                    "inverterSn": self.serial,
                    "startRegister": 200,
                    "pointNumber": 40,
                    "autoRetry": False,
                },
            )
            read_receipts.append(
                {"start": 200, "count": 40, "received_at": datetime.now(UTC).isoformat()}
            )
            if _numeric(selector).get(WEEKLY) != parameters[WEEKLY]:
                raise ControlError("Native weekly authority changed while reading its backup")
            for start, count in ((500, 112), (612, 112)):
                response = await self._request(
                    WEEKLY_ENDPOINT,
                    {
                        "inverterSn": self.serial,
                        "startRegister": start,
                        "pointNumber": count,
                    },
                )
                read_receipts.append(
                    {
                        "start": start,
                        "count": count,
                        "received_at": datetime.now(UTC).isoformat(),
                    }
                )
                weekly_values.update(_numeric(response))
            if not _weekly_complete(weekly_values):
                raise ControlError("The complete seven-day weekly backup could not be read")
        return {
            "serial": self.serial,
            "globals": parameters,
            "clock": clocks,
            "clock_received_at": clock_received_at,
            "read_receipts": read_receipts,
            "weekly": weekly_values,
            "read_at": datetime.now(UTC).isoformat(),
        }

    async def write(self, command: Command) -> None:
        data: dict[str, Any] = {
            "inverterSn": self.serial,
            "clientType": "WEB",
            "remoteSetType": "NORMAL",
        }
        if command.kind == "time":
            data.update(
                timeParam=command.parameter,
                hour=int(command.values[0]),
                minute=int(command.values[1]),
            )
            endpoint = WRITE_TIME_ENDPOINT
        elif command.kind == "function":
            data.update(
                functionParam=command.parameter,
                enable="true" if command.values[0] else "false",
            )
            endpoint = FUNCTION_ENDPOINT
        elif command.kind == "number":
            data.update(
                holdParam=command.parameter, valueText=format(float(command.values[0]), ".12g")
            )
            endpoint = WRITE_ENDPOINT
        else:
            raise ControlError("Unrecognized scheduling operation")
        await self._request(endpoint, data)


def _time_command(prefix: str, period: int, boundary: str, value: str) -> Command:
    suffix = "" if period == 0 else f"_{period}"
    hour, minute = (int(x) for x in value.split(":"))
    if prefix == "HOLD_PEAK_SHAVING":
        suffix = f"_{period + 1}"
        index = 37 + period * 4 + (2 if boundary == "END" else 0)
        keys = (
            f"LSP_HOLD_DIS_CHG_POWER_TIME_{index}",
            f"LSP_HOLD_DIS_CHG_POWER_TIME_{index + 1}",
        )
    else:
        keys = (f"{prefix}_{boundary}_HOUR{suffix}", f"{prefix}_{boundary}_MINUTE{suffix}")
    return Command("time", f"{prefix}_{boundary}_TIME{suffix}", keys, (hour, minute))


def _profile_commands(profile: InverterProfile) -> list[Command]:
    if profile.global_ac_power_kw is None:
        raise ControlError("Per-period weekly powers cannot be collapsed into a global setting")
    commands = []
    for prefix, windows, count in (
        ("HOLD_AC_CHARGE", tuple(x.window for x in profile.ac_windows), 3),
        ("HOLD_FORCED_CHARGE", profile.pv_windows, 3),
        ("HOLD_PEAK_SHAVING", tuple(x.window for x in profile.peak_windows), 2),
    ):
        for index in range(count):
            start, end = (
                (windows[index].start, windows[index].end)
                if index < len(windows)
                else ("00:00", "00:00")
            )
            commands.extend(
                (
                    _time_command(prefix, index, "START", start),
                    _time_command(prefix, index, "END", end),
                )
            )
    values = {
        "HOLD_AC_CHARGE_POWER_CMD": profile.global_ac_power_kw,
        "HOLD_AC_CHARGE_SOC_LIMIT": profile.ac_windows[0].stop_soc,
        "HOLD_FORCED_CHG_POWER_CMD": profile.pv_power_kw,
        "HOLD_FORCED_CHG_SOC_LIMIT": profile.pv_stop_soc,
    }
    for index, item in enumerate(profile.peak_windows):
        suffix = "" if index == 0 else "_2"
        values[f"_12K_HOLD_GRID_PEAK_SHAVING_POWER{suffix}"] = item.grid_limit_kw
        values[f"_12K_HOLD_GRID_PEAK_SHAVING_SOC{suffix}"] = item.start_soc
    commands.extend(Command("number", key, (key,), (value,)) for key, value in values.items())
    commands.extend(
        [
            Command("function", "FUNC_AC_CHARGE", ("FUNC_AC_CHARGE",), (True,)),
            Command(
                "function",
                "FUNC_GRID_PEAK_SHAVING",
                ("FUNC_GRID_PEAK_SHAVING",),
                (profile.peak_shaving_enabled,),
            ),
        ]
    )
    return commands


class EnergyControlManager:
    """One enabled master, locked apply transaction, and persisted rollback state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        owner: Any,
        *,
        backend: Any = None,
        store: Any = None,
        now: Callable[[], datetime] = dt_util.utcnow,
    ) -> None:
        self.hass, self.entry, self.owner = hass, entry, owner
        self.store = store or Store(hass, 1, f"{DOMAIN}_energy_control_{entry.entry_id}")
        self._backend_override, self._now = backend, now
        self.enabled = False
        self.baseline: dict[str, Any] | None = None
        self.transaction: dict[str, Any] | None = None
        self.status = "Disabled"
        self.error: str | None = None
        self.last_verified: datetime | None = None
        self.last_profile: str | None = None
        self.backoff_until: datetime | None = None
        self.recovery_required = False
        self.clock_skew_seconds: dict[str, float] = {}
        self.runtime_frame_age_seconds: float | None = None
        self.clock_receipt_age_seconds: dict[str, float] = {}
        self.clock_received_at: dict[str, str] = {}
        self.post_write_failures = 0
        self.retry_exhausted = False
        self._write_attempts = 0
        self._lock = asyncio.Lock()
        self._shutdown = False
        self._unsubscribe: Callable[[], None] | None = None
        self.signal = f"{DOMAIN}_energy_control_{entry.entry_id}"

    async def async_load(self) -> None:
        data = await self.store.async_load() or {}
        self.enabled = data.get("enabled") is True
        self.baseline, self.transaction = data.get("baseline"), data.get("transaction")
        self.post_write_failures = int(data.get("post_write_failures", 0))
        self.retry_exhausted = data.get("retry_exhausted") is True
        self.recovery_required = data.get("recovery_required") is True or bool(
            self.transaction
            and (
                self.transaction.get("state") in ("writing", "restoring")
                or self.transaction.get("rollback_pending")
            )
        )
        if self.recovery_required:
            self.enabled, self.status = False, "Recovery required"
        elif self.retry_exhausted:
            self.enabled, self.status = False, "Automatic retries stopped"
        self._unsubscribe = async_track_time_interval(
            self.hass, self._tick, timedelta(minutes=1)
        )

    async def _save(self) -> None:
        try:
            await self.store.async_save(
                {
                    "enabled": self.enabled,
                    "baseline": self.baseline,
                    "transaction": self.transaction,
                    "recovery_required": self.recovery_required,
                    "post_write_failures": self.post_write_failures,
                    "retry_exhausted": self.retry_exhausted,
                }
            )
        except Exception as err:
            raise ControlError(
                f"Private backup storage failed ({type(err).__name__})"
            ) from None

    def _publish(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    def _shared(self) -> SharedSchedule:
        def flag(entity: str) -> bool | None:
            state = self.hass.states.get(entity)
            return state.state == "on" if state and state.state in ("on", "off") else None

        calculator = self.hass.states.get("automation.juicebox_apply_local_charge_policy")
        last_run = calculator.attributes.get("last_triggered") if calculator else None
        if isinstance(last_run, str):
            last_run = dt_util.parse_datetime(last_run)
        fresh = (
            calculator is not None
            and calculator.state == "on"
            and isinstance(last_run, datetime)
            and last_run.tzinfo is not None
            and 0 <= (self._now() - last_run).total_seconds() <= 180
        )
        return SharedSchedule(
            flag("input_boolean.juicebox_srp_schedule_enabled") if fresh else None,
            flag(PEAK_SCHEDULE_VALID),
            flag(PEAK_ON),
            self.hass.config.time_zone,
        )

    def _backend(self) -> Any:
        if self._backend_override is not None:
            return self._backend_override
        candidates = []
        for entry in self.hass.config_entries.async_entries("eg4_web_monitor"):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            coordinator = getattr(entry, "runtime_data", None)
            if coordinator is None or not hasattr(coordinator, "require_client"):
                continue
            for serial, device in (coordinator.data or {}).get("devices", {}).items():
                if isinstance(device, dict) and device.get("type") == "inverter":
                    candidates.append((coordinator, serial))
        if len(candidates) != 1:
            raise ControlError("Exactly one loaded EG4 cloud inverter is required")
        coordinator, serial = candidates[0]
        client = coordinator.require_client()
        if (
            getattr(client, "verify_ssl", None) is not True
            or urlparse(getattr(client, "base_url", "")).scheme != "https"
            or not callable(getattr(client, "_request", None))
        ):
            raise ControlError("A certificate-verified HTTPS EG4 cloud client is required")
        return Eg4CloudBackend(client, serial)

    def _validate_clock(self, snapshot: dict[str, Any]) -> None:
        """Separate RTC offset at receipt from runtime-frame age at validation."""
        self.clock_skew_seconds = {}
        self.runtime_frame_age_seconds = None
        self.clock_receipt_age_seconds = {}
        self.clock_received_at = {}
        now = self._now().astimezone(PHOENIX)
        clocks = snapshot.get("clock", {})
        receipts = snapshot.get("clock_received_at", {})
        for key in ("HOLD_TIME", "inverterRuntimeDeviceTime"):
            label = "Inverter RTC" if key == "HOLD_TIME" else "Runtime frame"
            try:
                stamp = datetime.strptime(clocks[key], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=PHOENIX
                )
                received = datetime.fromisoformat(receipts[key])
                if received.tzinfo is None or received.utcoffset() is None:
                    raise ValueError("Naive receipt")
            except (KeyError, TypeError, ValueError):
                raise ControlError(f"{label} clock or receipt could not be verified") from None
            receipt_age = (now - received).total_seconds()
            self.clock_received_at[key] = received.isoformat()
            self.clock_receipt_age_seconds[key] = round(receipt_age, 1)
            if not 0 <= receipt_age <= 120:
                raise ControlError(f"{label} receipt is stale or in the future")
            if key == "HOLD_TIME":
                offset = (received - stamp).total_seconds()
                self.clock_skew_seconds[key] = round(offset, 1)
                if abs(offset) > 120:
                    raise ControlError(
                        "Inverter clock (RTC) differs from Phoenix time by over two minutes"
                    )
            else:
                frame_age = (now - stamp).total_seconds()
                self.runtime_frame_age_seconds = round(frame_age, 1)
                if stamp > received:
                    raise ControlError("Runtime frame timestamp is in the future")
                if not 0 <= frame_age <= 120:
                    raise ControlError("Runtime frame is older than two minutes")

    async def _tick(self, _now: datetime) -> None:
        if not self._shutdown:
            await self.async_apply()

    async def async_set_enabled(self, enabled: bool) -> dict[str, Any]:
        if enabled and self.recovery_required:
            raise ControlError("Restore the interrupted transaction before enabling control")
        self.enabled = bool(enabled)
        if enabled:
            # An explicit re-enable acknowledges a stopped retry series. A real
            # interrupted/failed rollback latch above still requires recovery.
            self.post_write_failures, self.retry_exhausted = 0, False
            self.backoff_until = None
        await self._save()
        if not self.enabled:
            self.status = (
                "Recovery required"
                if self.recovery_required
                else "Automatic retries stopped"
                if self.retry_exhausted
                else "Disabled"
            )
            self._publish()
            return self.state()
        return await self.async_apply()

    def state(self) -> dict[str, Any]:
        tariff = evaluate_tariff(self._now(), shared=self._shared())
        return {
            "enabled": self.enabled,
            "status": self.status,
            "error": self.error,
            "profile": self.last_profile,
            "recovery_required": self.recovery_required,
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "verification_age_seconds": (self._now() - self.last_verified).total_seconds()
            if self.last_verified
            else None,
            "clock_skew_seconds": self.clock_skew_seconds,
            "runtime_frame_age_seconds": self.runtime_frame_age_seconds,
            "clock_receipt_age_seconds": self.clock_receipt_age_seconds,
            "clock_received_at": self.clock_received_at,
            "post_write_failures": self.post_write_failures,
            "retry_exhausted": self.retry_exhausted,
            "shared_tariff_validated": tariff.shared_validated,
            "expected_on_peak": tariff.expected_on_peak,
            "on_peak": tariff.on_peak,
            "tariff_reason": tariff.reason,
            "season": tariff.season,
            "day_kind": tariff.day_kind,
            "next_transition": tariff.next_transition.isoformat()
            if tariff.next_transition
            else None,
        }

    async def _journaled_write(self, backend: Any, command: Command, inverse: Command) -> None:
        if self._shutdown or not self.enabled:
            raise ControlError("Control was disabled during the transaction")
        assert self.transaction is not None
        self.transaction["undo"].append(inverse.record())
        self.transaction["pending"] = command.record()
        await self._save()  # Must succeed before the device can be touched.
        self._write_attempts += 1
        await backend.write(command)

    async def _restore(self, backend: Any) -> None:
        if not self.transaction:
            raise ControlError("No rollback snapshot is available")
        original = self.transaction["snapshot"]["globals"]
        mode = Command("function", WEEKLY, (WEEKLY,), (bool(original[WEEKLY]),))
        undo = [Command.from_record(x) for x in self.transaction.get("undo", [])]
        actual = await backend.snapshot(weekly=bool(original[WEEKLY]))
        if actual["serial"] != self.transaction["snapshot"]["serial"]:
            raise ControlError("Rollback inverter identity does not match the private snapshot")
        if original[WEEKLY] and (
            not _weekly_complete(actual["weekly"])
            or actual["weekly"] != self.transaction["snapshot"]["weekly"]
        ):
            raise ControlError(
                "The original weekly table changed; automatic rollback is blocked"
            )

        self._validate_clock(actual)

        async def restore_one(command: Command) -> None:
            nonlocal actual
            if command.matches(actual["globals"]):
                return
            prior_state = self.transaction["state"]
            prior_pending = self.transaction.get("rollback_pending")
            self.transaction["state"] = "restoring"
            self.transaction["rollback_pending"] = command.record()
            try:
                await self._save()
            except ControlError:
                # A journal refusal before backend.write is not a partial restore.
                self.transaction["state"] = prior_state
                if prior_pending is None:
                    self.transaction.pop("rollback_pending", None)
                else:
                    self.transaction["rollback_pending"] = prior_pending
                raise
            self._write_attempts += 1
            await backend.write(command)
            actual = await backend.snapshot(weekly=False)
            self._validate_clock(actual)
            if not command.matches(actual["globals"]):
                raise ControlError("A rollback setting failed fresh readback")

        # If the original was weekly, its known prior table can take authority
        # before inactive daily fields are restored. If the original was daily,
        # keep any currently active weekly table until daily readback is restored.
        # Already-daily recovery is necessarily a bounded active multi-setting
        # restoration; never activate another unverified mode to hide that fact.
        if original[WEEKLY]:
            await restore_one(mode)
        for command in reversed(undo):
            if command.parameter != WEEKLY:
                await restore_one(command)
        if not original[WEEKLY]:
            await restore_one(mode)
        if not mode.matches(actual["globals"]) or any(
            not x.matches(actual["globals"]) for x in undo
        ):
            raise ControlError("Rollback readback did not match the original settings")
        self.transaction["state"] = "restored"
        self.transaction.pop("pending", None)
        self.transaction.pop("rollback_pending", None)
        self.recovery_required = False
        await self._save()

    async def async_rollback(self) -> dict[str, Any]:
        async with self._lock:
            self.enabled = False
            await self._save()
            was_interrupted = self.recovery_required or bool(
                self.transaction
                and (
                    self.transaction.get("state") in ("writing", "restoring")
                    or self.transaction.get("pending")
                    or self.transaction.get("rollback_pending")
                )
            )
            writes_before = self._write_attempts
            try:
                await self._restore(self._backend())
            except Exception as err:
                self.recovery_required = was_interrupted or self._write_attempts > writes_before
                self.status = (
                    "Recovery required" if self.recovery_required else "Rollback blocked"
                )
                self.error = (
                    str(err)
                    if isinstance(err, ControlError)
                    else f"Rollback failed ({type(err).__name__})"
                )
                with suppress(ControlError):
                    await self._save()
            else:
                self.status, self.error = "Restored prior settings", None
                self.post_write_failures, self.retry_exhausted = 0, False
                self.backoff_until = None
                await self._save()
            if self._write_attempts > writes_before or not self.error:
                self.last_verified, self.last_profile = None, None
            self._publish()
            return self.state()

    async def async_apply(self, dry_run: bool = False) -> dict[str, Any]:
        async with self._lock:
            if not dry_run:
                return await self._apply(dry_run=False)
            diagnostics = (
                self.clock_skew_seconds,
                self.runtime_frame_age_seconds,
                self.clock_receipt_age_seconds,
                self.clock_received_at,
            )
            try:
                return await self._apply(dry_run=True)
            finally:
                (
                    self.clock_skew_seconds,
                    self.runtime_frame_age_seconds,
                    self.clock_receipt_age_seconds,
                    self.clock_received_at,
                ) = diagnostics

    def _preview(self, error: str | None = None, **details: Any) -> dict[str, Any]:
        return {
            **self.state(),
            "dry_run": True,
            "preview_ready": error is None,
            "preview_error": error,
            **details,
        }

    async def _apply(self, dry_run: bool) -> dict[str, Any]:
        now = self._now()
        tariff = evaluate_tariff(now, shared=self._shared())
        if not self.enabled and not dry_run:
            self.status = (
                "Recovery required"
                if self.recovery_required
                else "Automatic retries stopped"
                if self.retry_exhausted
                else "Disabled"
            )
            self._publish()
            return self.state()
        if not tariff.shared_validated:
            if dry_run:
                return self._preview(tariff.reason)
            self.status, self.error = "Blocked", tariff.reason
            self._publish()
            return self.state()
        if self.recovery_required and not dry_run:
            self.status = "Recovery required"
            return self.state()
        if self.backoff_until and now < self.backoff_until and not dry_run:
            return self.state()
        ordinary_summer = tariff.season == "summer" and tariff.day_kind != "holiday"
        key = f"{tariff.season}-{'weekly' if ordinary_summer else tariff.day_kind}"
        if (
            not dry_run
            and self.status == "Applied and verified"
            and self.error is None
            and key == self.last_profile
            and self.last_verified
            and now - self.last_verified < VERIFY_INTERVAL
        ):
            self._publish()
            return self.state()
        attempted = False
        writes_before = self._write_attempts
        try:
            backend = self._backend()
            need_weekly = self.baseline is None or key == "summer-weekly"
            snapshot = await backend.snapshot(weekly=need_weekly)
            if snapshot["globals"].get(WEEKLY) and not _weekly_complete(snapshot["weekly"]):
                snapshot = await backend.snapshot(weekly=True)
            self._validate_clock(snapshot)
            _safe_baseline(snapshot["globals"])
            if self.baseline is None:
                if not snapshot["globals"][WEEKLY] or not _weekly_complete(snapshot["weekly"]):
                    raise ControlError(
                        "A complete active summer weekly baseline is required first"
                    )
                self.baseline = snapshot
                try:
                    await self._save()
                except ControlError:
                    self.baseline = None
                    raise
            elif snapshot["serial"] != self.baseline["serial"]:
                raise ControlError("The loaded inverter does not match the private baseline")
            if key == "summer-weekly":
                if snapshot["weekly"] != self.baseline["weekly"]:
                    raise ControlError(
                        "Native weekly tables changed; review before summer restoration"
                    )
                commands = self._baseline_commands()
                target_weekly = True
            else:
                plan = build_profile_plan(
                    now,
                    shared=self._shared(),
                    native_weekly_enabled=bool(snapshot["globals"][WEEKLY]),
                    weekly_backup_verified=_weekly_complete(self.baseline["weekly"]),
                    daily_plan_verified=True,
                    off_peak_power_kw=4,
                )
                if not plan.can_apply or plan.desired_profile is None:
                    raise ControlError("; ".join(plan.reasons))
                profile = plan.desired_profile
                commands = _profile_commands(profile)
                target_weekly = False
            for command in commands:
                command.inverse(snapshot["globals"])
            changes = [x for x in commands if not x.matches(snapshot["globals"])]
            mode = Command("function", WEEKLY, (WEEKLY,), (target_weekly,))
            if dry_run:
                return self._preview(
                    desired_profile=key,
                    changes=[x.record() for x in changes],
                    authority_change=not mode.matches(snapshot["globals"]),
                )
            if not changes and mode.matches(snapshot["globals"]):
                # Keep the last real undo journal useful after routine rechecks.
                self.post_write_failures, self.retry_exhausted = 0, False
                self.last_verified, self.last_profile = self._now(), key
                self.status, self.error, self.backoff_until = (
                    "Applied and verified",
                    None,
                    None,
                )
                await self._save()
                self._publish()
                return self.state()
            self.transaction = {
                "state": "writing",
                "snapshot": snapshot,
                "undo": [],
                "profile": key,
            }
            await self._save()
            for command in changes:
                attempted = True
                await self._journaled_write(
                    backend, command, command.inverse(snapshot["globals"])
                )
            readback = await backend.snapshot(weekly=False)
            self._validate_clock(readback)
            if any(not x.matches(readback["globals"]) for x in commands):
                raise ControlError(
                    "Daily profile readback does not match; authority was not switched"
                )
            if not mode.matches(readback["globals"]):
                attempted = True
                await self._journaled_write(backend, mode, mode.inverse(snapshot["globals"]))
            verified = await backend.snapshot(weekly=False)
            self._validate_clock(verified)
            if not mode.matches(verified["globals"]) or any(
                not x.matches(verified["globals"]) for x in commands
            ):
                raise ControlError("Final inverter profile verification failed")
            self.post_write_failures, self.retry_exhausted = 0, False
            self.transaction["state"] = "verified"
            self.transaction.pop("pending", None)
            self.last_verified, self.last_profile = self._now(), key
            self.status, self.error, self.backoff_until = "Applied and verified", None, None
            await self._save()
        except Exception as err:
            if dry_run:
                return self._preview(
                    str(err)
                    if isinstance(err, ControlError)
                    else f"Scheduling preview failed ({type(err).__name__})"
                )
            post_write_failure = self._write_attempts > writes_before
            rollback_failed = False
            if attempted:
                try:
                    await self._restore(backend)
                except Exception:
                    rollback_failed = True
                    self.enabled, self.recovery_required = False, True
                    with suppress(ControlError):
                        await self._save()
            if attempted:
                self.last_verified, self.last_profile = None, None
            self.status = (
                "Recovery required"
                if rollback_failed
                else "Error; prior settings restored"
                if attempted
                else "Blocked"
            )
            self.error = (
                str(err)
                if isinstance(err, ControlError)
                else f"Scheduling failed ({type(err).__name__})"
            )
            self.backoff_until = now + ERROR_BACKOFF
            if post_write_failure:
                self.post_write_failures += 1
                if self.post_write_failures >= MAX_POST_WRITE_FAILURES and not rollback_failed:
                    self.enabled, self.retry_exhausted = False, True
                    self.status = "Automatic retries stopped"
                try:
                    await self._save()
                except ControlError:
                    self.enabled, self.recovery_required = False, True
                    self.status = "Recovery required"
        self._publish()
        return self.state()

    def _baseline_commands(self) -> list[Command]:
        assert self.baseline is not None
        values = self.baseline["globals"]
        template = _profile_commands(
            InverterProfile(
                name="restore-summer",
                season="summer",
                day_kind="weekday",
                ac_windows=(ChargeWindow(TimeWindow("21:00", "05:00"), 2, 101),),
                pv_windows=(TimeWindow("09:00", "15:00"),),
                peak_windows=(),
            )
        )
        # Restore only fields owned by this controller; no grid codes, current
        # limits, reserve, calibration or unrelated protection parameters.
        for suffix in ("", "_2"):
            for key in (
                f"_12K_HOLD_GRID_PEAK_SHAVING_POWER{suffix}",
                f"_12K_HOLD_GRID_PEAK_SHAVING_SOC{suffix}",
            ):
                template.append(Command("number", key, (key,), (values[key],)))
        return [x.inverse(values) for x in template]

    async def async_shutdown(self) -> None:
        self._shutdown = True
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
        async with self._lock:
            pass
        managers = self.hass.data.get(f"{DOMAIN}_controls", {})
        managers.pop(self.entry.entry_id, None)
        if not managers:
            for service in (
                "apply_inverter_schedule",
                "set_inverter_schedule_enabled",
                "rollback_inverter_schedule",
            ):
                self.hass.services.async_remove(DOMAIN, service)


async def async_setup_energy_control(
    hass: HomeAssistant, entry: ConfigEntry, owner: Any
) -> EnergyControlManager:
    """Load the default-off master and register narrowly scoped services."""
    manager = EnergyControlManager(hass, entry, owner)
    await manager.async_load()
    hass.data.setdefault(f"{DOMAIN}_controls", {})[entry.entry_id] = manager

    async def apply(call: ServiceCall) -> dict[str, Any]:
        return await manager.async_apply(dry_run=call.data["dry_run"])

    async def enabled(call: ServiceCall) -> dict[str, Any]:
        return await manager.async_set_enabled(call.data["enabled"])

    async def rollback(_call: ServiceCall) -> dict[str, Any]:
        return await manager.async_rollback()

    for name, handler, schema in (
        (
            "apply_inverter_schedule",
            apply,
            vol.Schema({vol.Optional("dry_run", default=False): cv.boolean}),
        ),
        (
            "set_inverter_schedule_enabled",
            enabled,
            vol.Schema({vol.Required("enabled"): cv.boolean}),
        ),
        ("rollback_inverter_schedule", rollback, vol.Schema({})),
    ):
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=SupportsResponse.OPTIONAL
        )
    return manager


class _ControlEntity:
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: EnergyControlManager, key: str, name: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"whole_home_{key}"
        domain = "switch" if key == "automatic_inverter_schedule" else "sensor"
        self.entity_id = f"{domain}.home_energy_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "whole_home")},
            name="Home Energy",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.manager.signal, self.async_write_ha_state)
        )


class InverterStatusSensor(_ControlEntity, SensorEntity):
    @property
    def native_value(self) -> str:
        return self.manager.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.manager.state()


class SrpPeriodSensor(_ControlEntity, SensorEntity):
    @property
    def native_value(self) -> str:
        state = self.manager.state()
        if not state["shared_tariff_validated"]:
            return "Schedule unavailable or inconsistent"
        return f"{state['season'].title()} {'peak' if state['on_peak'] else 'off peak'}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.manager.state()


class InverterControlSwitch(_ControlEntity, SwitchEntity):
    @property
    def is_on(self) -> bool:
        return self.manager.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.manager.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_set_enabled(False)


def build_control_sensors(owner: Any) -> list[SensorEntity]:
    manager = getattr(owner, "energy_control", None)
    if not isinstance(manager, EnergyControlManager):
        return []
    return [
        InverterStatusSensor(manager, "inverter_schedule_status", "Inverter schedule status"),
        SrpPeriodSensor(manager, "srp_period", "SRP period"),
    ]


def build_control_switches(owner: Any) -> list[SwitchEntity]:
    manager = getattr(owner, "energy_control", None)
    if not isinstance(manager, EnergyControlManager):
        return []
    return [
        InverterControlSwitch(
            manager, "automatic_inverter_schedule", "Automatic inverter schedule"
        )
    ]
