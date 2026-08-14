# EVCC to PDF v1.3.03

Modulare Energieabrechnung für **EVCC + Home Assistant**.

Eine Abrechnung kann beliebig viele frei benannte Home-Assistant-Sensorgruppen und zusätzlich einzelne EVCC-Fahrzeuge enthalten. Für alles gilt derselbe Zeitraum und Strompreis.

## Neu in v1.3.03

- persistente Konfiguration unter `/data/evcc_to_pdf`
- automatische Übernahme vorhandener v1.3.02-Konfiguration und gültiger Backups
- Gunicorn als produktiver Webserver
- aktueller Home-Assistant-App-Lifecycle (`startup: application`)
- bessere Fehlerprotokollierung bei HA-/EVCC-Aktualisierungen

## Abrechnungsmodell

- beliebig viele Sensor-Abrechnungsgruppen wie `HomeOffice`, `Server`, `Klimaanlage`
- beliebig viele Energie-/Leistungssensoren je Gruppe
- Sensorpicker mit Suche sowie Energie-/Leistungsfilter
- EVCC-Sensoren werden aus der HA-Auswahl entfernt
- Sensoren können gegen Doppelzählung aus der Gruppensumme ausgeschlossen werden
- PDF zeigt HA-Gruppen nur als **Gruppenname + Summe**
- Fahrzeuge bleiben einzeln mit EVCC-Ladevorgängen und Zwischensummen sichtbar
- ein gemeinsamer manueller oder automatischer Strompreis für die komplette Abrechnung
- Migration bestehender v1.3.01-Konfigurationen

Unter **Gruppen** eine Abrechnung öffnen, Fahrzeuge auswählen und anschließend die gewünschten Sensor-Abrechnungsgruppen anlegen. Über **HA-Entitäten aktualisieren** werden geeignete Verbrauchssensoren geladen.

Ausführliche Hinweise stehen in `DOCS.md`.
