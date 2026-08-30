"""Config-flow tests."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_monitor.const import DOMAIN


async def test_user_flow_creates_single_entry(hass) -> None:
    """The no-credential local model accepts commissioned defaults."""
    initial = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert initial["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        initial["flow_id"],
        {
            "battery_capacity_kwh": 28.0,
            "battery_reserve_percent": 20.0,
            "peak_import_threshold_kw": 5.0,
            "planning_discharge_kw": 7.0,
            "minimum_discharge_kw": 0.3,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Energy"


async def test_duplicate_flow_aborts(hass) -> None:
    """Only one physical-property model may exist."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="whole_home", data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
