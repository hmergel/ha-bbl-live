"""DataUpdateCoordinator für BBL Live."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import BBLApi, BBLApiError, Game
from .const import (
    CONF_TEAM_ID,
    DOMAIN,
    FINISHED_HOLD,
    INTERVAL_IDLE,
    INTERVAL_LIVE,
    INTERVAL_PREGAME,
    INTERVAL_SOON,
    MAX_GAME_DURATION,
    PREGAME_WINDOW,
    SOON_WINDOW,
    STATE_FINISHED,
    STATE_LIVE,
    STATE_NO_GAME,
    STATE_PREGAME,
    STATE_SCHEDULED,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class BBLData:
    """Aufbereitete Daten für die Entitäten."""

    team_name: str | None
    team_logo: str | None
    game_state: str
    current_game: Game | None
    last_game: Game | None
    next_game: Game | None
    upcoming: list[Game] = field(default_factory=list)
    recent: list[Game] = field(default_factory=list)
    standing: dict[str, Any] = field(default_factory=dict)


type BBLConfigEntry = ConfigEntry["BBLCoordinator"]


class BBLCoordinator(DataUpdateCoordinator[BBLData]):
    """Holt die Daten der Lieblingsmannschaft und passt das Intervall an."""

    config_entry: BBLConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BBLConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.data[CONF_TEAM_ID]}",
            update_interval=INTERVAL_IDLE,
        )
        self.team_id: str = str(entry.data[CONF_TEAM_ID])
        self.api = BBLApi(async_get_clientsession(hass))
        self._tracked_game: Game | None = None

    async def _async_update_data(self) -> BBLData:
        try:
            team = await self.api.get_team(self.team_id)
        except BBLApiError as err:
            raise UpdateFailed(str(err)) from err

        now = dt_util.utcnow()
        games: dict[str, Game] = {g.id: g for g in team["games"]}
        all_games = sorted(
            games.values(), key=lambda g: g.start or datetime.max.replace(tzinfo=now.tzinfo)
        )

        current = self._find_current(all_games, now)

        # Falls die Teamseite ein laufendes Spiel weder bei "gespielt" noch
        # bei "geplant" führt, das zuletzt bekannte nächste Spiel weiter verfolgen.
        if current is None and self._tracked_game is not None:
            tracked = self._tracked_game
            if (
                tracked.start
                and tracked.start - PREGAME_WINDOW <= now <= tracked.start + MAX_GAME_DURATION
                and not (tracked.id in games and games[tracked.id].state == STATE_FINISHED)
            ):
                current = tracked

        # Für das aktuelle Spiel die Spielseite abrufen (genauerer Live-Stand)
        if current is not None:
            try:
                current = await self.api.get_game(current.id, self.team_id)
                games[current.id] = current
            except BBLApiError as err:
                _LOGGER.debug("Live-Daten für Spiel %s nicht abrufbar: %s", current.id, err)

        finished = sorted(
            (g for g in games.values() if g.state == STATE_FINISHED and g.start),
            key=lambda g: g.start,
            reverse=True,
        )
        upcoming = sorted(
            (
                g
                for g in games.values()
                if g.state == STATE_SCHEDULED
                and g.start
                and g.start > now
            ),
            key=lambda g: g.start,
        )

        last_game = finished[0] if finished else None
        next_game = upcoming[0] if upcoming else None

        # Zustand des aktuellen Spiels bestimmen
        if current is not None:
            if current.state == STATE_SCHEDULED:
                state = STATE_PREGAME
            else:
                state = current.state
        elif (
            last_game is not None
            and last_game.start
            and now - last_game.start < MAX_GAME_DURATION + FINISHED_HOLD
        ):
            # Kürzlich beendetes Spiel noch eine Weile anzeigen
            current = last_game
            state = STATE_FINISHED
        else:
            state = STATE_NO_GAME

        # Spiel merken, das als nächstes (oder gerade) verfolgt werden soll
        if current is not None and state in (STATE_PREGAME, STATE_LIVE):
            self._tracked_game = current
        elif next_game is not None:
            self._tracked_game = next_game
        else:
            self._tracked_game = None

        self._adjust_interval(state, next_game, now)

        return BBLData(
            team_name=team["name"],
            team_logo=team["logo"],
            game_state=state,
            current_game=current,
            last_game=last_game,
            next_game=next_game,
            upcoming=upcoming,
            recent=finished,
            standing=team["standing"],
        )

    @staticmethod
    def _find_current(games: list[Game], now: datetime) -> Game | None:
        """Spiel, das gerade läuft oder gleich beginnt."""
        for game in games:
            if game.state == STATE_LIVE:
                return game
        for game in games:
            if game.state != STATE_SCHEDULED or game.start is None:
                continue
            if game.start - PREGAME_WINDOW <= now <= game.start + MAX_GAME_DURATION:
                return game
        return None

    def _adjust_interval(self, state: str, next_game: Game | None, now: datetime) -> None:
        if state == STATE_LIVE:
            interval = INTERVAL_LIVE
        elif state == STATE_PREGAME:
            interval = INTERVAL_PREGAME
        elif next_game and next_game.start and next_game.start - now <= SOON_WINDOW:
            interval = INTERVAL_SOON
        else:
            interval = INTERVAL_IDLE
        if interval != self.update_interval:
            _LOGGER.debug("Abfrageintervall %s -> %s (Status %s)", self.update_interval, interval, state)
            self.update_interval = interval
