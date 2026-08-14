# EVCC to PDF v1.3.05

Modulare Energieabrechnung für **EVCC + Home Assistant**.

Eine Abrechnung kann beliebig viele frei benannte Home-Assistant-Sensorgruppen und zusätzlich einzelne EVCC-Fahrzeuge enthalten. Für alles gilt derselbe Zeitraum und Strompreis.

## Neu in v1.3.05

- **Weitere Abrechnungsgruppen** zeigt im PDF nur noch Gruppenname, Verbrauch und Kosten
- Gesamtverbrauch und Gesamtkosten sind im Summenblock besser hervorgehoben
- der gemeinsame Strompreis steht weiterhin einmal zentral im Summenblock
- die BMF-/Destatis-Grundlage wird als Jahrespauschale klarer erklärt
- 2026 bleibt bei 0,34 €/kWh auf Basis von Destatis 61243-0001, 1. Halbjahr 2025
- unveränderte Standardtemplates aus v1.3.04 werden aktualisiert; eigene Template-Anpassungen bleiben erhalten

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
