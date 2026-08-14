# EVCC to PDF – Dokumentation v1.3.02

## 1. Grundprinzip

Eine **Abrechnung** enthält die gemeinsamen Rahmenbedingungen: Empfänger, Zeitraum, Strompreis, Versand, ausgewählte Fahrzeuge und beliebig viele Sensor-Abrechnungsgruppen.

Eine **Sensor-Abrechnungsgruppe** ist ein frei benannter Container für Home-Assistant-Verbrauchssensoren, z. B.:

- HomeOffice → Shelly L1, L2, L3, 3D-Drucker
- Server → Shelly Server, Shelly Router
- Klimaanlage → Energie-/Leistungssensor Klima

Die Anzahl der Gruppen und Sensoren ist nicht fest begrenzt.

## 2. Fahrzeuge

EVCC-Fahrzeuge gehören direkt zur Abrechnung und werden nicht in Sensorgruppen versteckt. Im Standard-PDF bleibt jedes Fahrzeug einzeln sichtbar. Dazu werden die Ladevorgänge des Zeitraums und eine Fahrzeug-Zwischensumme ausgegeben.

Ist EVCC aktiviert und kein einzelnes Fahrzeug gewählt, werden alle gefundenen EVCC-Fahrzeuge berücksichtigt.

## 3. Sensor-Abrechnungsgruppen

Über **+ Abrechnungsgruppe** können beliebig viele Gruppen angelegt und frei benannt werden. Die Pfeile ändern die Reihenfolge; diese Reihenfolge wird auch für die Standard-PDF-Ausgabe verwendet.

Der Sensorpicker arbeitet mit einer Zielgruppe. Nach Auswahl der Zielgruppe kann der gewünschte Sensor gesucht, gefiltert und hinzugefügt werden.

Ein Sensor wird über die Oberfläche nur einmal zugeordnet, damit derselbe Messwert nicht versehentlich in mehreren Gruppen doppelt summiert wird.

## 4. Sensorfilter

Nach **HA-Entitäten aktualisieren** werden nur geeignete Verbrauchssensoren angeboten:

- Energie: Wh / kWh / MWh
- Leistung: W / kW / MW

Zusätzlich gibt es:

- Freitextsuche nach Name/Entity-ID
- Filter Alle / Energie / Leistung
- automatisches Ausblenden EVCC-eigener HA-Sensoren

Bereits aus älteren Versionen vorhandene Laufzeitquellen bleiben kompatibel, werden aber nicht neu über den Picker angeboten.

## 5. Verbrauchsermittlung

### Energiezähler

Für Energiezähler wird der Verbrauch im gewählten Zeitraum ermittelt. Home-Assistant-Langzeitstatistiken werden bevorzugt verwendet; Recorder-History dient als Fallback.

### Leistungssensoren

Leistungswerte werden über die Zeit integriert und in kWh umgerechnet.

## 6. Doppelzählung

Jeder Sensor besitzt **In Gruppensumme einrechnen**.

Beispiel: Shelly L1 enthält bereits den 3D-Drucker. Ein zusätzlicher Drucker-Shelly kann konfiguriert bleiben, aber von der Gruppensumme ausgeschlossen werden. Dadurch wird der Verbrauch nicht doppelt berechnet.

## 7. Strompreis

Der Strompreis liegt auf Ebene der kompletten Abrechnung und gilt für alle Sensorgruppen und Fahrzeuge.

### Manuell

Ein Preis-Override wird in €/kWh eingetragen. Ohne Override gilt der Standardpreis aus den Einstellungen. Im PDF erscheint bei manueller Preiswahl keine zusätzliche Zeile „Preisermittlung“.

### BMF-/Destatis-Automatik

Bei aktivierter Automatik wird der für das Abrechnungsjahr ermittelte Wert für die komplette Abrechnung verwendet. Das Standard-PDF zeigt zusätzlich Preisermittlung und Grundlage.

## 8. PDF-Darstellung

Das Standard-PDF trennt Transparenz und technische Details bewusst:

- Fahrzeuge: einzeln mit Ladevorgängen und Fahrzeug-Zwischensumme
- Sensor-Abrechnungsgruppen: nur Gruppenname, Gruppenverbrauch und Gruppenbetrag
- keine einzelnen HA-Entity-IDs im Standard-PDF
- gemeinsame Gesamtsumme und gemeinsamer Strompreis

Damit kann der Arbeitgeber die Abrechnung nachvollziehen, ohne die interne Home-Assistant-/Shelly-Struktur offenzulegen.

## 9. Migration von v1.3.01

Die flache `ha_sources`-Liste einer bestehenden v1.3.01-Abrechnung wird automatisch in eine Sensor-Abrechnungsgruppe überführt. Fahrzeuge, Preis, Empfänger- und Versanddaten bleiben erhalten.

Das unveränderte v1.3.01-Standardtemplate wird auf die neue Gruppensummen-Darstellung aktualisiert. Ein vom Nutzer bearbeitetes Template bleibt unverändert.

## 10. Persistenz

Einstellungen werden persistent unter `/config` gespeichert, atomar geschrieben und gesichert. Bei beschädigter Hauptdatei wird zuerst versucht, ein gültiges Backup wiederherzustellen.

## 11. Release-Checkliste

Die für Folgeversionen verbindlichen Projektregeln stehen zusätzlich in der Root-Datei `RELEASE_CHECKLIST.md`.
