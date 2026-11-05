"""User control for the seasonal inverter schedule."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .energy_control import build_control_switches


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Expose the persisted automatic-control master."""
    async_add_entities(build_control_switches(hass.data[DOMAIN][entry.entry_id]))
