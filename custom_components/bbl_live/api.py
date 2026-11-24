"""Datenzugriff auf die öffentlichen Seiten der easyCredit BBL.

Die Website easycredit-bbl.de ist eine Next.js-Anwendung. Jede Seite liefert
ihre Daten als JSON im <script id="__NEXT_DATA__">-Block mit. Diese Daten
werden hier gelesen und in einfache Dictionaries umgewandelt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import re
from typing import Any

import aiohttp

from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    STATE_CANCELLED,
    STATE_FINISHED,
    STATE_LIVE,
    STATE_POSTPONED,
    STATE_SCHEDULED,
)

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
    re.DOTALL,
)

_HEADERS = {
    "User-Agent": "HomeAssistant-BBL-Live/1.0",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "de-DE,de;q=0.9",
}

_FINAL_STATUSES = {"OFFICIAL", "FINAL", "FINISHED", "ENDED", "POST", "COMPLETE"}
# Explizite "noch nicht begonnen"-Status der BBL (z. B. "PRE" kurz vor Spielbeginn)
_PRE_STATUSES = {"PRE", "PREGAME", "PRE_GAME", "SCHEDULED", "NOT_STARTED"}
# gameProgress-Werte, die noch keinen Spielbeginn bedeuten
_PRE_PROGRESS = {"", "0", "PRE", "PREGAME", "PRE_GAME", "SCHEDULED", "NOT_STARTED"}
_POSTPONED_STATUSES = {"POSTPONED", "DELAYED"}
_CANCELLED_STATUSES = {"CANCELLED", "CANCELED", "ABANDONED"}


class BBLApiError(Exception):
    """Fehler beim Abrufen oder Auswerten der BBL-Daten."""


@dataclass
class Game:
    """Ein Spiel aus Sicht der gewählten Mannschaft."""

    id: str
    competition: str | None
    stage: str | None
    match_day: int | None
    status_raw: str
    progress_raw: str | None
    state: str
    start: datetime | None
    is_home: bool
    home_name: str
    home_tlc: str | None
    home_logo: str | None
    guest_name: str
    guest_tlc: str | None
    guest_logo: str | None
    home_score: int | None
    guest_score: int | None
    period: str | None
    game_clock: str | None
    quarters: list[dict[str, Any]] = field(default_factory=list)
    venue_name: str | None = None
    venue_address: str | None = None
    spectators: int | None = None
    tv: list[str] = field(default_factory=list)

    @property
    def opponent_name(self) -> str:
        return self.guest_name if self.is_home else self.home_name

    @property
    def opponent_logo(self) -> str | None:
        return self.guest_logo if self.is_home else self.home_logo

    @property
    def own_score(self) -> int | None:
        return self.home_score if self.is_home else self.guest_score

    @property
    def opponent_score(self) -> int | None:
        return self.guest_score if self.is_home else self.home_score

    @property
    def has_score(self) -> bool:
        return self.home_score is not None and self.guest_score is not None

    @property
    def score_text(self) -> str | None:
        """Punktestand im Format Heim:Gast."""
        if not self.has_score:
            return None
        return f"{self.home_score}:{self.guest_score}"

    @property
    def outcome(self) -> str | None:
        """Sieg/Niederlage aus Sicht der eigenen Mannschaft."""
        if not self.has_score or self.own_score == self.opponent_score:
            return None
        return "Sieg" if self.own_score > self.opponent_score else "Niederlage"

    @property
    def url(self) -> str:
        return f"{BASE_URL}/spiele/{self.id}"

    def base_attributes(self) -> dict[str, Any]:
        """Gemeinsame Attribute für alle Entitäten."""
        return {
            "spiel_id": self.id,
            "gegner": self.opponent_name,
            "heimspiel": self.is_home,
            "heim": self.home_name,
            "gast": self.guest_name,
            "beginn": self.start.isoformat() if self.start else None,
            "ort": self.venue_name,
            "adresse": self.venue_address,
            "wettbewerb": self.competition,
            "spieltag": self.match_day,
            "tv": ", ".join(self.tv) if self.tv else None,
            "gegner_logo": self.opponent_logo,
            "link": self.url,
        }

    def score_attributes(self) -> dict[str, Any]:
        """Attribute rund um den Punktestand."""
        lead = None
        if self.has_score:
            lead = self.own_score - self.opponent_score
        return {
            "punkte_heim": self.home_score,
            "punkte_gast": self.guest_score,
            "punkte_eigene": self.own_score,
            "punkte_gegner": self.opponent_score,
            "differenz": lead,
            "viertel": self.period,
            "spieluhr": self.game_clock,
            "viertel_ergebnisse": self.quarters,
            "zuschauer": self.spectators,
            "status_roh": self.status_raw,
            "fortschritt_roh": self.progress_raw,
        }


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_quarters(result: dict[str, Any]) -> list[dict[str, Any]]:
    quarters: list[dict[str, Any]] = []
    for i in range(1, 5):
        home = _to_int(result.get(f"homeTeamQ{i}Score"))
        guest = _to_int(result.get(f"guestTeamQ{i}Score"))
        if home is None and guest is None:
            continue
        quarters.append({"abschnitt": f"Q{i}", "heim": home, "gast": guest})
    for i in range(1, 10):
        home = _to_int(result.get(f"homeTeamOT{i}Score")) or 0
        guest = _to_int(result.get(f"guestTeamOT{i}Score")) or 0
        if home or guest:
            quarters.append({"abschnitt": f"OT{i}", "heim": home, "gast": guest})
    return quarters


def _determine_state(status: str, progress: str | None, has_score: bool) -> str:
    status = status.strip().upper()
    progress_u = str(progress or "").strip().upper()
    if status in _FINAL_STATUSES or progress_u == "E":
        return STATE_FINISHED
    if status in _CANCELLED_STATUSES:
        return STATE_CANCELLED
    if status in _POSTPONED_STATUSES:
        return STATE_POSTPONED
    if not has_score:
        # Bei explizitem Vor-Spiel-Status (z. B. "PRE") ist das Spiel noch nicht
        # gestartet, auch wenn gameProgress bereits einen Wert liefert.
        if status in _PRE_STATUSES:
            return STATE_SCHEDULED
        if not status and progress_u in _PRE_PROGRESS:
            return STATE_SCHEDULED
    # Alles andere (z. B. LIVE, IN_PROGRESS, gameProgress "Q2") gilt als laufend
    return STATE_LIVE


def parse_game(raw: dict[str, Any], team_id: str) -> Game:
    """Wandelt ein Spiel-Objekt der BBL in ein Game um."""
    home = raw.get("homeTeam") or {}
    guest = raw.get("guestTeam") or {}
    result = raw.get("result") or {}
    venue = raw.get("venue") or {}

    home_score = _to_int(result.get("homeTeamFinalScore"))
    guest_score = _to_int(result.get("guestTeamFinalScore"))
    status = str(raw.get("status") or "")
    progress = raw.get("gameProgress")
    has_score = home_score is not None and guest_score is not None

    # Vor Spielbeginn liefert die BBL teils 0:0 – das ist kein echter Spielstand
    state = _determine_state(
        status, progress, has_score and (home_score or guest_score) > 0
    )
    if state == STATE_SCHEDULED:
        home_score = guest_score = None
        has_score = False

    start = None
    if raw.get("scheduledTime"):
        start = dt_util.parse_datetime(str(raw["scheduledTime"]))

    tv = [
        ch.get("name")
        for ch in (raw.get("tvChannel") or [])
        if isinstance(ch, dict) and ch.get("name")
    ]

    home_id = str(home.get("teamId") or home.get("seasonTeamId") or "")

    return Game(
        id=str(raw.get("id")),
        competition=raw.get("competition"),
        stage=raw.get("stage"),
        match_day=_to_int(raw.get("matchDay")),
        status_raw=status,
        progress_raw=progress,
        state=state,
        start=start,
        is_home=home_id == str(team_id),
        home_name=home.get("name") or "?",
        home_tlc=home.get("tlc"),
        home_logo=home.get("logoUrl"),
        guest_name=guest.get("name") or "?",
        guest_tlc=guest.get("tlc"),
        guest_logo=guest.get("logoUrl"),
        home_score=home_score,
        guest_score=guest_score,
        period=result.get("latestPeriod"),
        game_clock=raw.get("gameTime"),
        quarters=_build_quarters(result) if has_score else [],
        venue_name=venue.get("name"),
        venue_address=venue.get("address"),
        spectators=_to_int(result.get("spectators")),
        tv=tv,
    )


class BBLApi:
    """Liest Daten von easycredit-bbl.de."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _page_props(self, path: str) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        try:
            async with self._session.get(
                url, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    raise BBLApiError(f"HTTP {resp.status} für {url}")
                html = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BBLApiError(f"Verbindungsfehler für {url}: {err}") from err

        match = _NEXT_DATA_RE.search(html)
        if not match:
            raise BBLApiError(f"Keine Spieldaten in {url} gefunden")
        try:
            data = json.loads(match.group(1))
            return data["props"]["pageProps"]
        except (ValueError, KeyError, TypeError) as err:
            raise BBLApiError(f"Ungültige Daten in {url}: {err}") from err

    async def get_teams(self) -> dict[str, str]:
        """Alle Mannschaften der aktuellen Saison: {team_id: name}."""
        props = await self._page_props("/saison/teams")
        teams = props.get("teamNavigatorData") or []
        result = {
            str(t["id"]): t.get("nameFull") or t.get("nameShort") or str(t["id"])
            for t in teams
            if t.get("id")
        }
        if not result:
            raise BBLApiError("Keine Mannschaften gefunden")
        return dict(sorted(result.items(), key=lambda kv: kv[1].lower()))

    async def get_team(self, team_id: str) -> dict[str, Any]:
        """Teamseite: letzte Spiele, kommende Spiele, Tabellenplatz."""
        props = await self._page_props(f"/teams/{team_id}")
        played = (props.get("games") or {}).get("items") or []
        scheduled = (props.get("scheduledGames") or {}).get("items") or []
        season_team = props.get("seasonTeam") or {}
        team = props.get("team") or {}
        return {
            "name": team.get("nameFull") or season_team.get("name"),
            "logo": props.get("seasonLogoUrl") or team.get("logoUrl"),
            "games": [parse_game(g, team_id) for g in played + scheduled],
            "standing": season_team.get("mainRoundStanding") or {},
        }

    async def get_game(self, game_id: str, team_id: str) -> Game:
        """Spielseite mit aktuellem (Live-)Stand."""
        props = await self._page_props(f"/spiele/{game_id}")
        raw = props.get("initialGameData")
        if not raw:
            raise BBLApiError(f"Spiel {game_id} nicht gefunden")
        return parse_game(raw, team_id)
