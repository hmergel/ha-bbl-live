"""Sensoren für BBL Live."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Game
from .const import GAME_STATES
from .coordinator import BBLConfigEntry, BBLData
from .entity import BBLEntity


def _game_list(games: list[Game]) -> list[dict[str, Any]]:
    return [
        {
            "datum": g.start.isoformat() if g.start else None,
            "gegner": g.opponent_name,
            "heimspiel": g.is_home,
            "ort": g.venue_name,
            "ergebnis": g.score_text,
            "ausgang": g.outcome,
            "wettbewerb": g.competition,
        }
        for g in games
    ]


def _status_attrs(d: BBLData) -> dict[str, Any]:
    g = d.current_game
    if g is None:
        return {}
    return {**g.base_attributes(), "punktestand": g.score_text, **g.score_attributes()}


def _live_attrs(d: BBLData) -> dict[str, Any]:
    g = d.current_game
    if g is None:
        return {}
    return {**g.score_attributes(), "gegner": g.opponent_name, "heimspiel": g.is_home}


def _last_attrs(d: BBLData) -> dict[str, Any]:
    g = d.last_game
    if g is None:
        return {}
    return {
        **g.base_attributes(),
        "ausgang": g.outcome,
        **g.score_attributes(),
        "letzte_spiele": _game_list(d.recent),
    }


def _next_attrs(d: BBLData) -> dict[str, Any]:
    g = d.next_game
    if g is None:
        return {}
    return {**g.base_attributes(), "kommende_spiele": _game_list(d.upcoming)}


def _standing_attrs(d: BBLData) -> dict[str, Any]:
    s = d.standing or {}
    return {
        "spiele": s.get("totalGames"),
        "siege": s.get("totalVictories"),
        "niederlagen": s.get("totalLosses"),
        "korbdifferenz": s.get("totalGoalDifference"),
        "serie": s.get("streak"),
        "serie_anzahl": s.get("streakCount"),
        "letzte_10": s.get("last10Outcomes"),
    }


@dataclass(frozen=True, kw_only=True)
class BBLSensorDescription(SensorEntityDescription):
    value_fn: Callable[[BBLData], Any]
    attrs_fn: Callable[[BBLData], dict[str, Any]] = lambda _: {}
    picture_fn: Callable[[BBLData], str | None] = lambda _: None


SENSORS: tuple[BBLSensorDescription, ...] = (
    BBLSensorDescription(
        key="game_status",
        translation_key="game_status",
        icon="mdi:basketball",
        device_class=SensorDeviceClass.ENUM,
        options=GAME_STATES,
        value_fn=lambda d: d.game_state,
        attrs_fn=_status_attrs,
        picture_fn=lambda d: d.current_game.opponent_logo if d.current_game else None,
    ),
    BBLSensorDescription(
        key="live_score",
        translation_key="live_score",
        icon="mdi:scoreboard",
        value_fn=lambda d: d.current_game.score_text if d.current_game else None,
        attrs_fn=_live_attrs,
    ),
    BBLSensorDescription(
        key="last_result",
        translation_key="last_result",
        icon="mdi:trophy-outline",
        value_fn=lambda d: d.last_game.score_text if d.last_game else None,
        attrs_fn=_last_attrs,
        picture_fn=lambda d: d.last_game.opponent_logo if d.last_game else None,
    ),
    BBLSensorDescription(
        key="next_game",
        translation_key="next_game",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.next_game.start if d.next_game else None,
        attrs_fn=_next_attrs,
    ),
    BBLSensorDescription(
        key="next_opponent",
        translation_key="next_opponent",
        icon="mdi:account-group",
        value_fn=lambda d: d.next_game.opponent_name if d.next_game else None,
        attrs_fn=lambda d: d.next_game.base_attributes() if d.next_game else {},
        picture_fn=lambda d: d.next_game.opponent_logo if d.next_game else None,
    ),
    BBLSensorDescription(
        key="next_venue",
        translation_key="next_venue",
        icon="mdi:stadium",
        value_fn=lambda d: d.next_game.venue_name if d.next_game else None,
        attrs_fn=lambda d: (
            {
                "adresse": d.next_game.venue_address,
                "heimspiel": d.next_game.is_home,
            }
            if d.next_game
            else {}
        ),
    ),
    BBLSensorDescription(
        key="table_rank",
        translation_key="table_rank",
        icon="mdi:format-list-numbered",
        value_fn=lambda d: (d.standing or {}).get("rank"),
        attrs_fn=_standing_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BBLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(BBLSensor(coordinator, desc) for desc in SENSORS)


class BBLSensor(BBLEntity, SensorEntity):
    """Ein BBL-Sensor."""

    entity_description: BBLSensorDescription

    def __init__(self, coordinator, description: BBLSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.entity_description.attrs_fn(self.coordinator.data)

    @property
    def entity_picture(self) -> str | None:
        return self.entity_description.picture_fn(self.coordinator.data)
