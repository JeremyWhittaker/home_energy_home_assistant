"""Config flow for Home Energy Monitor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow

from .const import (
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
)


def _schema(values: dict[str, Any] | None = None) -> vol.Schema:
    values = values or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_BATTERY_CAPACITY_KWH,
                default=values.get(CONF_BATTERY_CAPACITY_KWH, DEFAULT_BATTERY_CAPACITY_KWH),
            ): vol.All(vol.Coerce(float), vol.Range(min=5.0, max=200.0)),
            vol.Required(
                CONF_BATTERY_RESERVE_PERCENT,
                default=values.get(
                    CONF_BATTERY_RESERVE_PERCENT,
                    DEFAULT_BATTERY_RESERVE_PERCENT,
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=80.0)),
            vol.Required(
                CONF_PEAK_IMPORT_THRESHOLD_KW,
                default=values.get(
                    CONF_PEAK_IMPORT_THRESHOLD_KW,
                    DEFAULT_PEAK_IMPORT_THRESHOLD_KW,
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=30.0)),
            vol.Required(
                CONF_PLANNING_DISCHARGE_KW,
                default=values.get(
                    CONF_PLANNING_DISCHARGE_KW,
                    DEFAULT_PLANNING_DISCHARGE_KW,
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=20.0)),
            vol.Required(
                CONF_MIN_DISCHARGE_KW,
                default=values.get(CONF_MIN_DISCHARGE_KW, DEFAULT_MIN_DISCHARGE_KW),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=5.0)),
        }
    )


class HomeEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure the single whole-home model."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the local calculation entry."""
        await self.async_set_unique_id("whole_home")
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Home Energy", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema())

    @staticmethod
    def async_get_options_flow(config_entry: Any) -> OptionsFlow:
        """Return the options editor."""
        return HomeEnergyOptionsFlow()


class HomeEnergyOptionsFlow(OptionsFlow):
    """Edit forecasting and demand thresholds."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show or save options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        values = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(values))
