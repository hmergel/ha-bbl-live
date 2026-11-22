"""Binärsensor: Läuft gerade ein Spiel?"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATE_LIVE
from .coordinator import BBLConfigEntry
from .entity import BBLEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BBLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([BBLGameRunning(entry.runtime_data)])


class BBLGameRunning(BBLEntity, BinarySensorEntity):
    """An, solange das Spiel der Mannschaft läuft."""

    _attr_translation_key = "game_running"
    _attr_icon = "mdi:basketball-hoop"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "game_running")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.game_state == STATE_LIVE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        g = self.coordinator.data.current_game
        if g is None or not self.is_on:
            return {}
        return {
            "gegner": g.opponent_name,
            "punktestand": g.score_text,
            "viertel": g.period,
        }
