"""Konstanten für die BBL-Live-Integration."""

from datetime import timedelta

DOMAIN = "bbl_live"

CONF_TEAM_ID = "team_id"
CONF_TEAM_NAME = "team_name"

BASE_URL = "https://www.easycredit-bbl.de"

# Abfrage-Intervalle
INTERVAL_LIVE = timedelta(seconds=30)  # Spiel läuft
INTERVAL_PREGAME = timedelta(minutes=1)  # Kurz vor Spielbeginn / Spiel sollte laufen
INTERVAL_SOON = timedelta(minutes=5)  # Nächstes Spiel in den nächsten Stunden
INTERVAL_IDLE = timedelta(minutes=30)  # Sonst

# Zeitfenster, in dem ein Spiel als "aktuelles Spiel" gilt
PREGAME_WINDOW = timedelta(minutes=30)
MAX_GAME_DURATION = timedelta(hours=4)
SOON_WINDOW = timedelta(hours=3)
# So lange bleibt der Status nach Spielende auf "beendet"
FINISHED_HOLD = timedelta(hours=3)

# Spielzustände (Zustand der Status-Entität)
STATE_NO_GAME = "kein_spiel"
STATE_SCHEDULED = "geplant"
STATE_PREGAME = "vor_spiel"
STATE_LIVE = "live"
STATE_FINISHED = "beendet"
STATE_POSTPONED = "verschoben"
STATE_CANCELLED = "abgesagt"

GAME_STATES = [
    STATE_NO_GAME,
    STATE_PREGAME,
    STATE_LIVE,
    STATE_FINISHED,
    STATE_POSTPONED,
    STATE_CANCELLED,
]
