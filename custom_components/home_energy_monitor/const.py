"""Constants for Home Energy Monitor."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "home_energy_monitor"
PLATFORMS = (Platform.SENSOR, Platform.BINARY_SENSOR)

CONF_BATTERY_CAPACITY_KWH = "battery_capacity_kwh"
CONF_BATTERY_RESERVE_PERCENT = "battery_reserve_percent"
CONF_PEAK_IMPORT_THRESHOLD_KW = "peak_import_threshold_kw"
CONF_MIN_DISCHARGE_KW = "minimum_discharge_kw"
CONF_PLANNING_DISCHARGE_KW = "planning_discharge_kw"

DEFAULT_BATTERY_CAPACITY_KWH = 28.0
DEFAULT_BATTERY_RESERVE_PERCENT = 20.0
DEFAULT_PEAK_IMPORT_THRESHOLD_KW = 5.0
DEFAULT_MIN_DISCHARGE_KW = 0.3
DEFAULT_PLANNING_DISCHARGE_KW = 7.0

HELPER_BATTERY_CAPACITY = "input_number.home_energy_battery_capacity_kwh"
HELPER_BATTERY_RESERVE = "input_number.home_energy_battery_reserve_percent"
HELPER_PEAK_IMPORT_THRESHOLD = "input_number.home_energy_peak_import_threshold_kw"
HELPER_PLANNING_DISCHARGE = "input_number.home_energy_planning_discharge_kw"

PEAK_ON = "input_boolean.juicebox_srp_on_peak"
PEAK_SCHEDULE_VALID = "input_boolean.juicebox_srp_schedule_valid"
PEAK_HOLIDAY = "input_boolean.juicebox_srp_holiday"
PEAK_SUMMER_START_MONTH = "input_number.juicebox_srp_summer_start_month"
PEAK_SUMMER_END_MONTH = "input_number.juicebox_srp_summer_end_month"
PEAK_SUMMER_START = "input_datetime.juicebox_srp_summer_start"
PEAK_SUMMER_END = "input_datetime.juicebox_srp_summer_end"
PEAK_WINTER_1_START = "input_datetime.juicebox_srp_winter_window_1_start"
PEAK_WINTER_1_END = "input_datetime.juicebox_srp_winter_window_1_end"
PEAK_WINTER_2_START = "input_datetime.juicebox_srp_winter_window_2_start"
PEAK_WINTER_2_END = "input_datetime.juicebox_srp_winter_window_2_end"

UPDATE_INTERVAL = timedelta(minutes=1)
BATTERY_SMOOTHING_WINDOW = timedelta(minutes=15)
BATTERY_MINIMUM_SAMPLE_SPAN = timedelta(minutes=5)
RECONCILIATION_INTERVAL = timedelta(hours=4)

EG4_STALE_AFTER = timedelta(minutes=10)
ENPHASE_STALE_AFTER = timedelta(minutes=5)
TIGO_STALE_AFTER = timedelta(minutes=45)

CALCULATION_VERSION = "1.0"
MODEL_NAME = "EG4 CT + Enphase AC correction"

UNKNOWN_STATES = frozenset({"", "unknown", "unavailable", "none", "null"})
