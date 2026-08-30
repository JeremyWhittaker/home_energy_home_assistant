"""Platform import and setup regression tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from custom_components.home_energy_monitor import binary_sensor, sensor
from custom_components.home_energy_monitor.const import DOMAIN


async def test_sensor_and_binary_sensor_platforms_import_and_add_entities() -> None:
    """Both forwarded platforms must import and construct every entity."""
    coordinator = Mock()
    entry = SimpleNamespace(entry_id="platform-test")
    hass = SimpleNamespace(data={DOMAIN: {entry.entry_id: coordinator}})

    sensors: list[object] = []
    binary_sensors: list[object] = []
    await sensor.async_setup_entry(hass, entry, lambda entities: sensors.extend(entities))
    await binary_sensor.async_setup_entry(
        hass,
        entry,
        lambda entities: binary_sensors.extend(entities),
    )

    assert len(sensors) == len(sensor.SENSORS) == 29
    assert len(binary_sensors) == len(binary_sensor.BINARY_SENSORS) == 9
