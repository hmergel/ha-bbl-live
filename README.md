# BBL Live – Basketball Bundesliga für Home Assistant

<a href="https://buymeacoffee.com/hmergel" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50"></a>

Eigene Integration (Custom Component) für Home Assistant. Sie zeigt für deine Lieblingsmannschaft der easyCredit BBL Folgendes an:

- **Letztes Ergebnis** mit Gegner, Sieg/Niederlage und Viertel-Ergebnissen
- **Live-Punktestand** während des Spiels (Abfrage alle 30 Sekunden)
- **Spielstatus** des aktuellen Spiels: `Kein Spiel`, `Vor dem Spiel`, `Live`, `Beendet`, `Verschoben` oder `Abgesagt`
- **Nächstes Spiel** mit Datum/Uhrzeit, Gegner, Ort (Halle und Adresse), Heim/Auswärts und TV-Sender
- Zusätzlich: **Tabellenplatz** und der Binärsensor **Spiel läuft**

Die Daten stammen von den öffentlichen Seiten auf [easycredit-bbl.de](https://www.easycredit-bbl.de). Einen API-Schlüssel brauchst du nicht.

## Installation

Benötigt Home Assistant 2025.3 oder neuer.

### Manuell (ohne Update-Funktion)
1. Kopiere den Ordner `custom_components/bbl_live` nach `<HA-Konfiguration>/custom_components/bbl_live`, also zum Beispiel `/config/custom_components/bbl_live`.
2. Starte Home Assistant neu.
3. Gehe zu **Einstellungen → Geräte & Dienste → Integration hinzufügen**, suche nach **BBL Live** und wähle deine Mannschaft.

### Über HACS (empfohlen, mit Update-Funktion)
1. Öffne in HACS oben rechts das Menü **⋮ → Benutzerdefinierte Repositories**.
2. Trage `https://github.com/hmergel/ha-bbl-live` ein und wähle als Typ **Integration**.
3. Suche in HACS nach **BBL Live** und klicke auf **Herunterladen**. Starte danach Home Assistant neu.

Sobald es eine neue Version gibt, zeigt Home Assistant unter **Einstellungen → Updates** ein Update an.

## Entitäten

Beispiel für ALBA BERLIN. Die Entitäts-IDs leiten sich aus dem Mannschaftsnamen ab.

| Entität | Zustand | Wichtige Attribute |
|---|---|---|
| `sensor.alba_berlin_spielstatus` | `kein_spiel` / `vor_spiel` / `live` / `beendet` / … | `gegner`, `punktestand`, `viertel`, `spieluhr`, `ort`, `beginn` |
| `sensor.alba_berlin_live_punktestand` | `78:72` (Heim:Gast) | `punkte_eigene`, `punkte_gegner`, `differenz`, `viertel`, `viertel_ergebnisse` |
| `sensor.alba_berlin_letztes_ergebnis` | `95:77` (Heim:Gast) | `gegner`, `ausgang` (Sieg/Niederlage), `heimspiel`, `ort`, `letzte_spiele` |
| `sensor.alba_berlin_nachstes_spiel` | Zeitstempel | `gegner`, `heimspiel`, `ort`, `adresse`, `tv`, `kommende_spiele` |
| `sensor.alba_berlin_nachster_gegner` | Name des Gegners (mit Logo) | wie oben |
| `sensor.alba_berlin_nachster_spielort` | Name der Halle | `adresse`, `heimspiel` |
| `sensor.alba_berlin_tabellenplatz` | z. B. `8` | `siege`, `niederlagen`, `korbdifferenz`, `serie` |
| `binary_sensor.alba_berlin_spiel_lauft` | an/aus | `gegner`, `punktestand`, `viertel` |

### Abfrage-Intervall
| Situation | Intervall |
|---|---|
| Spiel läuft | 30 s |
| 30 Minuten vor Spielbeginn | 1 min |
| Nächstes Spiel beginnt in weniger als 3 Stunden | 5 min |
| Sonst | 30 min |

Nach dem Abpfiff bleibt der Status noch etwa 3 Stunden auf `Beendet`. Danach wechselt er auf `Kein Spiel`.

## Dashboard-Beispiel (Markdown-Karte)

```yaml
type: markdown
content: >
  {% set s = 'sensor.alba_berlin_spielstatus' %}
  {% if is_state(s, 'live') %}
  ## 🔴 LIVE: {{ state_attr(s,'heim') }} {{ state_attr(s,'punktestand') }} {{ state_attr(s,'gast') }}
  {{ state_attr(s,'viertel') }}
  {% endif %}
  **Letztes Spiel:** {{ state_attr('sensor.alba_berlin_letztes_ergebnis','heim') }} –
  {{ state_attr('sensor.alba_berlin_letztes_ergebnis','gast') }}
  **{{ states('sensor.alba_berlin_letztes_ergebnis') }}**
  ({{ state_attr('sensor.alba_berlin_letztes_ergebnis','ausgang') }})

  **Nächstes Spiel:** {{ as_timestamp(states('sensor.alba_berlin_nachstes_spiel')) | timestamp_custom('%a %d.%m. %H:%M') }}
  gegen {{ states('sensor.alba_berlin_nachster_gegner') }}
  in {{ states('sensor.alba_berlin_nachster_spielort') }}
```

## Automations-Beispiel: Benachrichtigung bei Spielende

```yaml
automation:
  - alias: BBL Spielende
    trigger:
      - platform: state
        entity_id: sensor.alba_berlin_spielstatus
        to: beendet
    action:
      - service: notify.notify
        data:
          message: >
            Endstand gegen {{ state_attr('sensor.alba_berlin_spielstatus','gegner') }}:
            {{ state_attr('sensor.alba_berlin_spielstatus','punktestand') }}
```

## Hinweise
- Die Integration liest die Daten, die die BBL-Website in ihre Seiten einbettet. Wenn die BBL ihre Website umbaut, kann eine Anpassung nötig werden. Die Integration meldet dann `UpdateFailed` im Log.
- Wie schnell der Live-Punktestand aktualisiert wird, hängt davon ab, wie oft die BBL-Website ihre Seiten aktualisiert.
- Die Rohwerte `status_roh` und `fortschritt_roh` stehen als Attribute zur Verfügung. Damit lässt sich prüfen, welche Statuswerte die BBL während eines Spiels liefert.

## Unterstützung
Wenn dir die Integration gefällt, freue ich mich über einen Kaffee ☕

<a href="https://buymeacoffee.com/hmergel" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50"></a>
