# Changelog

## 2.0.0 – 2026-06-22

### Neu
- **Multi-Tier-Unterstützung**: Beliebig viele Tiere (Hunde, Katzen, Kaninchen, Vögel, Reptilien …) in einer Instanz verwalten
- **Tier-Auswahl**: Scrollbare Chip-Leiste in der UI – alle Daten (Futter, Gewicht, Gesundheit) werden tierspezifisch gespeichert und angezeigt
- **Tierarten-Icons**: Automatische Emoji-Icons je Tierart (🐕 🐱 🐇 🐦 🦎 🐾)
- **Tiere-Tab**: Tiere direkt in der App anlegen, umbenennen und löschen (Tierart, Geburtsdatum)
- **Altersanzeige**: Alter jedes Tieres wird automatisch aus dem Geburtsdatum berechnet und angezeigt
- **Neue Konfigurationsstruktur**: Option `animals` (Liste) ersetzt `dog_name` und `birthdate`

### Geändert
- **Start-Tab** zeigt Tier-Steckbrief (Name, Art, Alter, Gewicht, heutige Futtermenge, fällige Termine)
- **Gewichtskurve**: SVG-Liniendiagramm direkt in der App, keine externe Bibliothek nötig
- **Gesundheits-Tab**: Typ-Filterchips, Überfällig/Demnächst fällig-Markierungen, Bearbeiten-Modal
- **Futter-Tab**: Unter-Tabs Fütterung | Gewicht, Tagesziel aus aktuellem Dashboard-API-Aufruf
- `/api/meta` liefert jetzt die Tierliste statt `dog_name`/`birthdate`
- `/api/dashboard`, `/api/feedings`, `/api/weights`, `/api/health` akzeptieren `animal_id`-Parameter
- `panel_icon` auf `mdi:paw` geändert

### Entfernt
- **Gassi-Log** (Walks) vollständig entfernt – Routen, DB-Tabelle, UI
- **Training & Kommandos** (Commands, Sessions) vollständig entfernt
- `dog_name` und `birthdate` als separate Konfigurationsoptionen entfernt
- HA-Sensor-Felder `minutes_since_last_walk` und `minutes_since_last_pee` entfernt

### Migration bestehender Daten
Beim ersten Start mit v2.0.0 werden vorhandene Fütterungs-, Gewichts- und Gesundheits-Einträge automatisch dem ersten Tier zugeordnet (Cooper). Manuelle Migration ist nicht nötig.

---

## 1.0.0 – 2025-10-01

- Erstveröffentlichung: Gassi-Log, Fütterung & Gewicht, Gesundheitsereignisse, Training & Kommandos für einen Hund
