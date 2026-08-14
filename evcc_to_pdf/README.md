# EVCC to PDF v1.3.04

Modulare Energieabrechnung für **EVCC + Home Assistant**.

Eine Abrechnung kann beliebig viele frei benannte Home-Assistant-Sensorgruppen und zusätzlich einzelne EVCC-Fahrzeuge enthalten. Für alles gilt derselbe Zeitraum und Strompreis.

## Neu in v1.3.04

- Sensorgruppen werden über ein zentrales Dropdown ausgewählt
- es wird immer nur die aktuell gewählte Sensorgruppe mit ihren Sensoren angezeigt
- Gruppenname kann direkt in der ausgewählten Gruppe bearbeitet werden
- neue Sensoren landen automatisch in der aktiven Gruppe
- Sortieren und Löschen beziehen sich ebenfalls nur auf die ausgewählte Gruppe
- bestehende v1.3.03-Konfigurationen bleiben unverändert kompatibel

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

Unter **Gruppen** eine Abrechnung öffnen, Fahrzeuge auswählen und anschließend über **+ Neue Sensorgruppe** die gewünschten Gruppen anlegen. Die zu bearbeitende Gruppe wird im Dropdown ausgewählt; darunter sind nur deren Sensoren sichtbar. Über **HA-Entitäten aktualisieren** werden geeignete Verbrauchssensoren geladen.

Ausführliche Hinweise stehen in `DOCS.md`.
