# Cooper – Tier-Gesundheitstracker

Home Assistant Add-on zum Tracken der Gesundheit deiner Haustiere: Gewicht,
Impfungen, Wurmkur, Tierarzt-Termine und Fütterung. Unterstützt **mehrere
Tiere gleichzeitig** (Hund + Katzen + weitere). Für Smartphone optimiert,
läuft komplett über Ingress – keine externe Datenbank nötig.

## Installation

1. **Einstellungen → Add-ons → Add-on Store** → drei Punkte oben rechts → **Repositories**
2. Repository-URL hinzufügen: `https://github.com/fahrstuhl1/cooper-app`
3. **Cooper** erscheint im Store → installieren und starten
4. Cooper erscheint als eigener Eintrag in der Seitenleiste

## Optionen

| Option | Typ | Beschreibung | Standard |
| --- | --- | --- | --- |
| `animals` | `list` | Liste der Tiere (Name, Tierart, Geburtsdatum) | Cooper + 2 Katzen |
| `persons` | `list(str)` | Erfassende Personen | `["Max", "Franzi"]` |
| `daily_food_target_g` | `int` (50–2000) | Tagesziel Futtermenge in Gramm | `300` |
| `health_reminder_days` | `int` (1–180) | Vorlaufzeit für „Demnächst fällig" | `30` |
| `log_level` | `debug`/`info`/`warning`/`error` | Log-Level | `info` |

### Beispiel-Konfiguration

```yaml
animals:
  - name: "Cooper"
    species: "dog"
    birthdate: "2025-09-13"
  - name: "Luna"
    species: "cat"
    birthdate: "2023-05-01"
  - name: "Mochi"
    species: "cat"
    birthdate: ""
persons:
  - "Max"
  - "Franzi"
daily_food_target_g: 300
health_reminder_days: 30
```

Unterstützte Tierarten: `dog`, `cat`, `rabbit`, `bird`, `reptile`, `other`

## Module

- **Start-Dashboard**: Tier-Steckbrief (Alter, Gewicht, heutige Futtermenge),
  Fortschrittsbalken, fällige Gesundheitstermine auf einen Blick
- **Gesundheit**: Impfungen, Wurmkur, Parasitenschutz, Tierarzt-Termine –
  mit optionaler Fälligkeit und Wiederholungsintervall (z. B. alle 4 Wochen),
  Filterbar nach Typ, überfällige Einträge werden hervorgehoben
- **Futter & Gewicht**: Fütterungs-Log mit Mengen-Vorschlägen und Tagesziel,
  Gewichtsverlauf als SVG-Liniendiagramm
- **Tiere**: Tiere direkt in der App verwalten – anlegen, bearbeiten, löschen

## Personen-Zuordnung

Sendet Home Assistant Ingress die Header `X-Remote-User-Name` bzw.
`X-Remote-User-Display-Name` und stimmt der Name mit einem Eintrag in
`persons` überein, wird dieser automatisch verwendet. Andernfalls wählt man
die aktive Person über die Chips in der UI – die Auswahl wird im Browser
(`localStorage`) gespeichert.

## REST-Sensor für Home Assistant (optional)

```yaml
sensor:
  - platform: rest
    resource: http://homeassistant.local:8123/api/hassio_ingress/<token>/api/ha-sensors
    name: Cooper Status
    value_template: "{{ value_json.fed_today_g }}"
    json_attributes:
      - fed_today_g
      - next_due_health
```

Felder: `fed_today_g` (Gramm heute gefüttert),
`next_due_health` (Objekt mit `title`, `type`, `due_date` oder `null`).

## Datenhaltung

Alle Daten liegen in `/data/cooper.db` (SQLite, WAL-Modus). Das Schema wird
beim Start automatisch angelegt und migriert – kein manueller Eingriff nötig.

Beim Update von v1.x auf v2.0 werden vorhandene Einträge automatisch dem
ersten Tier zugeordnet.

## Entwicklung / Smoke-Test

```bash
pip install -r requirements.txt
python3 smoke_test.py
```
