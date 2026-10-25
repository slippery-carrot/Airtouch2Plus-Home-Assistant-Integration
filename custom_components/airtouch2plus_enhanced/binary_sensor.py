"""TCP connectivity diagnostic for the AirTouch controller."""
from __future__ import annotations

from airtouch2.at2plus import At2PlusClient
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Expose the TCP socket state as a diagnostic binary sensor."""
    client: At2PlusClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AirTouchConnectionSensor(client)])


class AirTouchConnectionSensor(BinarySensorEntity):
    """Whether the library believes its controller TCP connection is open."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "TCP connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, client: At2PlusClient) -> None:
        self._client = client
        self._ac_id = next(iter(client.aircons_by_id))
        self._attr_unique_id = f"at2plus_ac_{self._ac_id}_tcp_connection"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, f"at2plus_ac_{self._ac_id}")})

    @property
    def is_on(self) -> bool:
        return self._client.connected

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        """Keep short disconnects visible even after a quick reconnection."""
        last = self._client.last_tcp_disconnect
        return {
            "disconnect_count": self._client.tcp_disconnect_count,
            "last_disconnected": last.isoformat() if last else None,
        }

    async def async_added_to_hass(self) -> None:
        # Changes are pushed immediately rather than waiting for a HA poll.
        self.async_on_remove(
            self._client.add_connection_callback(self.async_write_ha_state)
        )
