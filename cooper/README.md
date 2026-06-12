# Cooper – Hunde-Tracker

Home Assistant Add-on zum Tracken von Cooper, unserem Dackelwelpen: Gassi-Log,
Fütterung & Gewicht, Tierarzt/Impfungen/Wurmkur und Training/Kommandos. Für
zwei Personen (Max & Franzi) auf dem Smartphone optimiert, läuft komplett über
Ingress.

## Installation

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store**
2. Oben rechts auf die drei Punkte → **Repositories**
3. Repository-URL hinzufügen: `https://github.com/fahrstuhl1/cooper-app`
4. Das Add-on **„Cooper”** erscheint im Store → installieren und starten
5. Cooper erscheint danach als eigener Eintrag in der Seitenleiste (Ingress)

## Optionen

| Option | Typ | Beschreibung | Standard |
| --- | --- | --- | --- |
| `dog_name` | `str` | Name des Hundes, wird in der UI angezeigt | `Cooper` |
| `birthdate` | `str` (`YYYY-MM-DD`) | Geburtsdatum, für Alter & Gewichtskurve | `2025-09-13` |
| `persons` | `list(str)` | Liste der erfassenden Personen | `["Max", "Franzi"]` |
| `daily_food_target_g` | `int` (50–2000) | Tagesziel Futtermenge in Gramm | `300` |
| `health_reminder_days` | `int` (1–180) | Vorlaufzeit für „Demnächst fällig” | `30` |
| `log_level` | `debug`/`info`/`warning`/`error` | Log-Level | `info` |

## Personen-Zuordnung

Sendet Home Assistant Ingress die Header `X-Remote-User-Name` bzw.
`X-Remote-User-Display-Name` und stimmt der Name mit einem Eintrag in
`persons` überein, wird dieser automatisch verwendet. Andernfalls (oder als
manuelle Übersteuerung) wählt man die aktive Person über die Chips oben in der
UI – die Auswahl wird im Browser (`localStorage`) gespeichert und bei jedem
Eintrag mitgesendet.

## Module

- **Gassi-Log**: Schnellerfassung in 2 Taps (Pipi/Häufchen/Beides/Nichts),
  nachträgliche Erfassung mit eigenem Zeitpunkt, Bearbeiten/Löschen. Dashboard
  zeigt Zeit seit letztem Gassi/Pipi/Häufchen und Anzahl heute.
- **Fütterung & Gewicht**: Fütterungs-Log mit Mengen-Vorschlägen, Tagesziel mit
  Fortschrittsbalken, Gewichtsverlauf als Liniendiagramm mit Alter in
  Wochen/Monaten auf der X-Achse.
- **Tierarzt/Impfungen/Wurmkur**: Ereignisse mit optionaler Fälligkeit
  (Datum oder Wiederholungsintervall in Wochen), Dashboard-Block „Demnächst
  fällig” mit Hervorhebung überfälliger Termine, Historie filterbar nach Typ.
- **Training & Kommandos**: Kommando-Status (`neu` → `in Arbeit` → `sitzt`)
  per Tap durchschalten, Trainings-Sessions mit geübten Kommandos, Dauer und
  Notiz.

## REST-Sensoren für Home Assistant (optional)

`GET /api/ha-sensors` liefert ein kompaktes JSON für REST-Sensoren, z. B.:

```yaml
sensor:
  - platform: rest
    resource: http://homeassistant.local:8123/api/hassio_ingress/<token>/api/ha-sensors
    name: Cooper Status
    value_template: "{{ value_json.minutes_since_last_walk }}"
    json_attributes:
      - minutes_since_last_pee
      - fed_today_g
      - next_due_health
```

Felder: `minutes_since_last_walk`, `minutes_since_last_pee`, `fed_today_g`,
`next_due_health` (Objekt mit `title`, `type`, `due_date` oder `null`).

## Datenhaltung

Alle Daten liegen in `/data/cooper.db` (SQLite, WAL-Modus). Das Schema wird
beim Start per `CREATE TABLE IF NOT EXISTS` angelegt – Add-on-Updates
erfordern keine Migration.

## Entwicklung / Smoke-Test

```bash
pip install -r requirements.txt
python3 smoke_test.py
```

Der Smoke-Test legt eine temporäre DB an, prüft alle Routen per
Flask-Testclient (Anlegen, Aggregation, Bearbeiten, Löschen, Personen-
Validierung) und beendet sich mit "Alle Smoke-Tests erfolgreich.".

## Screenshots

_Platzhalter – Screenshots des Dashboards und der Module folgen._

- `docs/screenshot-dashboard.png`
- `docs/screenshot-gassi.png`
- `docs/screenshot-futter.png`
- `docs/screenshot-gesundheit.png`
- `docs/screenshot-training.png`
