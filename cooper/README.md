# Cooper – Tier-Gesundheitstracker

Home Assistant Add-on zum Tracken der Gesundheit deiner Haustiere: Gewicht,
Impfungen, Wurmkur, Tierarzt-Termine und Fütterung. Unterstützt **mehrere
Tiere gleichzeitig** (Hund + Katzen + weitere). Vollständig touch-optimiert
für iOS und Android – läuft komplett über Ingress, keine externe Datenbank nötig.

## Installation

1. **Einstellungen → Add-ons → Add-on Store** → drei Punkte oben rechts → **Repositories**
2. Repository-URL hinzufügen: `https://github.com/fahrstuhl1/cooper-app`
3. **Cooper** erscheint im Store → installieren und starten
4. Cooper erscheint als eigener Eintrag in der Seitenleiste

## Optionen

| Option | Typ | Beschreibung | Standard |
| --- | --- | --- | --- |
| `animals` | `list` | Liste der Tiere (Name, Tierart, Geburtsdatum) | Cooper + 2 Katzen |
| `health_reminder_days` | `int` (1–180) | Vorlaufzeit für „Demnächst fällig" | `30` |
| `notification_service` | `str` | HA Notify-Dienst für Erinnerungen | `notify` |
| `notify_hour` | `int` (0–23) | Stunde der täglichen Erinnerung | `8` |
| `timezone` | `str` | Zeitzone für Datumsberechnungen | `Europe/Berlin` |
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
health_reminder_days: 30
notification_service: notify
notify_hour: 8
timezone: "Europe/Berlin"
```

Unterstützte Tierarten: `dog`, `cat`, `rabbit`, `bird`, `reptile`, `other`

## Module

- **Start-Dashboard**: Tier-Übersicht (alle Tiere als Kacheln oder Einzelansicht),
  Gewichtstrend, fällige Gesundheitstermine, Vorrats-Erinnerungen auf einen Blick
- **Gesundheit**: Impfungen, Wurmkur, Parasitenschutz, Tierarzt-Termine –
  mit optionaler Fälligkeit und Wiederholungsintervall (z. B. alle 4 Wochen);
  filterbar nach Typ; überfällige Einträge hervorgehoben;
  **Linkswisch** zum schnellen Löschen
- **Futter & Gewicht**: Gewichtsverlauf pro Tier mit Trendanzeige; Futtermittel-Vorräte
  mit automatischer Kauf-Erinnerung, Fortschrittsbalken und Auffüll-Dialog;
  stückbasierte Einheiten (Dosen, Stück) und Gramm-Einheiten unterstützt;
  **Linkswisch** zum schnellen Löschen
- **Tiere verwalten**: Über das ☰-Menü – anlegen, bearbeiten, löschen

## Touch-Gesten

| Geste | Aktion |
| --- | --- |
| Wischen links/rechts | Zwischen Tabs wechseln (Start → Gesundheit → Futter) |
| Runterziehen (Seitenanfang) | Aktiven Tab aktualisieren (Pull-to-refresh) |
| Linkswisch auf Eintrag | Löschen-Button anzeigen; weiter wischen → direkt löschen |
| Modal herunterziehen | Modal schließen (Drag-to-dismiss) |

## REST-Sensor für Home Assistant (optional)

```yaml
sensor:
  - platform: rest
    resource: http://homeassistant.local:8123/api/hassio_ingress/<token>/api/ha-sensors
    name: Cooper Status
    value_template: "{{ value_json.next_due_health.due_date | default('') }}"
    json_attributes:
      - next_due_health
```

Felder: `next_due_health` (Objekt mit `title`, `type`, `due_date` oder `null`).

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
