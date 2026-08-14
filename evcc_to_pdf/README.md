# EVCC to PDF v1.3.01

Gemeinsame Energieabrechnung für **EVCC + Home Assistant**.

Eine Abrechnungsgruppe kann gleichzeitig EVCC-Fahrzeuge und Home-Assistant-Verbrauchssensoren enthalten. Verbrauch und Kosten werden für denselben Zeitraum berechnet und in einem gemeinsamen PDF zusammengeführt.

## Neu in v1.3.01

- Fahrzeuge und HA-Verbraucher in **einer Gruppe / einer Abrechnung**
- ein gemeinsamer Strompreis für alle Verbraucher der Gruppe
- BMF-/Destatis-Automatik gilt auf Wunsch für die komplette Gruppe
- Sensorpicker zeigt nur Energie- und Leistungssensoren
- EVCC-Sensoren aus Home Assistant werden automatisch ausgefiltert
- Filter nach Energie- oder Leistungssensoren
- Schutz vor Doppelzählung über **„In Gruppensumme einrechnen“**
- bestehende v1.3.0-Gruppen werden automatisch migriert

Unter **Gruppen** EVCC bei Bedarf aktivieren, Fahrzeuge auswählen und anschließend über **HA-Entitäten aktualisieren** zusätzliche Verbrauchssensoren wie Shellys, Server oder Klimaanlagen-Energiesensoren hinzufügen.

Ausführliche Hinweise stehen im Tab **Dokumentation** bzw. in `DOCS.md`.
