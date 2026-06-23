# Changelog

## 2.5.0 – 2026-06-22

### Neu
- **Stückbasierte Einheiten**: Futter-Produkte können jetzt in Dosen oder Stück erfasst werden (z.B. Nassfutter); Packungsgröße, Tagesration und Vorrat werden in der gewählten Einheit angezeigt
- **Gesundheits-Dashboard global**: Nur noch eine Ansicht für alle Tiere; Tier-Badge bei jedem Eintrag; Tier-Auswahl direkt im Erstell-/Bearbeiten-Formular
- **Futter-Dashboard global**: Vorräte immer für alle Tiere gruppiert angezeigt; Gewichts-Übersicht kompakt (eine Kachel pro Tier) im „Alle"-Modus
- **Tier-Zuweisung editierbar**: Produkte können nachträglich einem anderen Tier oder auf „Geteilt" umgestellt werden (Dropdown statt Checkbox)
- **Gewicht aus Alle-Modus**: Neue Kacheln mit „+ Gewicht"-Button pro Tier ermöglichen Gewichtseingabe direkt aus der Gesamtübersicht

### Geändert
- Futter-Dashboard zeigt immer alle Produkte (global), nicht gefiltert nach ausgewähltem Tier
- Gesundheits-Dashboard zeigt immer alle Einträge (global), Tier-Filter entfernt
- Vorrats-Karte zeigt jetzt Tage und Vorrat in einer Zeile

---

## 2.4.0 – 2026-06-22

### Neu
- **Hamburger-Menü**: ☰-Button ersetzt 🔔 im Header; Tier-Verwaltung und Benachrichtigungs-Test ins Menü verschoben; Bottom-Nav auf 3 Tabs reduziert (Start | Gesundheit | Futter)
- **Gesundheits-Filter: Zeilenumbruch**: Filterchips brechen jetzt in neue Zeilen um statt horizontal zu scrollen
- **Futter-Tab ohne Sub-Tabs**: Gewicht und Vorräte auf einer scrollbaren Seite, kein Tab-Wechsel nötig; Vorräte immer sichtbar
- **„Alle"-Modus**: Neuer „Alle"-Chip im Tier-Selector; Start-Tab zeigt 2-Spalten-Grid mit Übersichtskarten; Gesundheits-Tab zeigt alle Tiere mit Tier-Badge; Futter-Tab gruppiert Vorräte nach Tier
- **Klickbare Hero-Statistiken**: Gewichts-Kachel navigiert direkt zum Futter-Tab, Termin-Kachel zum Gesundheits-Tab
- **Geteiltes Futter**: Produkte können als „Für alle Tiere (geteilt)" markiert werden (animal_id = NULL); 👥-Badge zeigt geteilte Produkte; Abfragen inkludieren automatisch geteilte Produkte
- **Zeitzone konfigurierbar**: Neue Option `timezone` in config.yaml (Standard: Europe/Berlin); wird in server.py und notifier.py aus der Config gelesen

---

## 2.3.0 – 2026-06-22

### Neu
- **Untere Navigation**: Tab-Leiste nach unten verschoben (mobile-first, mit Safe-Area-Support); aktiver Tab mit Indikator-Strich
- **Gradients Hero-Karte**: Start-Tab zeigt Tier-Karte mit lila Gradient, Avatar und Gewichts-Trend-Anzeige
- **Gewichts-Trend**: Differenz zur vorherigen Messung direkt neben aktuellem Gewicht (↑ / ↓ / →)
- **Gewichtskurve mit Flächenfüllung**: SVG-Chart mit Gradient-Fläche unter der Linie und Datumsbeschriftungen
- **„Erledigt"-Button**: Gesundheitseinträge mit Fälligkeitsdatum können direkt als erledigt markiert werden; bei Wiederholungen wird der nächste Termin automatisch berechnet
- **Tage-Countdown auf Gesundheitseinträgen**: Zeigt „Heute fällig", „Morgen fällig", „In X Tagen" oder „X Tage überfällig" statt rohen Datumsangaben
- **Benachrichtigungs-Test**: 🔔-Button in der Kopfzeile sendet sofort eine Test-Benachrichtigung
- **Deutsche Tierartnamen**: Hund / Katze / Kaninchen / Vogel / Reptil / Sonstiges statt englischer Bezeichnungen
- **Tab-Einblend-Animation**: Tabs blenden beim Wechsel sanft ein

---

## 2.2.0 – 2026-06-22

### Neu
- **HA-Benachrichtigungen**: Tägliche Push-Notifications über den Home Assistant Benachrichtigungs-Dienst (konfigurierbar: Service-Name und Uhrzeit)
- **Test-Button**: Benachrichtigung direkt aus dem Start-Tab testen (Button „🔔 Benachrichtigung testen")
- **Touch-Gesten**: Wischen nach links/rechts wechselt zwischen den Haupt-Tabs (Start → Gesundheit → Futter → Tiere) sowie zwischen Gewicht- und Vorräte-Sub-Tab im Futter-Bereich
- **Neue Konfigurations-Optionen**: `notification_service` (HA Notify-Dienst, Standard: `notify`) und `notify_hour` (Stunde der täglichen Erinnerung, Standard: 8)

---

## 2.1.0 – 2026-06-22

### Neu
- **Futter-Vorräte**: Beliebig viele Futtermittel pro Tier anlegen (Name, Packungsgröße, Tagesration, aktueller Vorrat)
- **Kauf-Erinnerung**: Automatische Berechnung des Leerstand-Datums; Warnung wenn Vorrat für weniger als X Tage reicht (Standard: 10 Tage)
- **Vorräte-Tab**: Sub-Tab im Futter-Bereich mit Vorrats-Karten, Fortschrittsbalken und Auffüll-Dialog
- **Dashboard-Erinnerungen**: Futter-Produkte mit geringem Vorrat werden direkt im Start-Dashboard angezeigt

### Entfernt
- **Fütterungs-Protokoll**: Einzel-Fütterungen werden nicht mehr geloggt
- **Benutzer-Auswahl**: Kein Personen-Tracking mehr (Max, Franzi entfernt); `persons`- und `daily_food_target_g`-Optionen entfernt

---

## 2.0.1 – 2026-06-22

### Bugfix
- HA Ingress: API-Pfade sind jetzt relativ (`api/meta` statt `/api/meta`), damit Requests korrekt durch den Ingress-Tunnel gehen und nicht mit 404 scheitern

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
