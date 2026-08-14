# EVCC to PDF – Dokumentation v1.3.05

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

Über **+ Neue Sensorgruppe** können beliebig viele Gruppen angelegt und frei benannt werden. Oben im Bereich **Sensorgruppen** wählt ein Dropdown die aktuell zu bearbeitende Gruppe aus. Es wird immer nur diese eine Gruppe mit ihrem Namen und ihren zugeordneten Sensoren angezeigt; die übrigen Gruppen bleiben ausgeblendet, bis sie im Dropdown gewählt werden.

Die Pfeile neben dem Dropdown ändern die Reihenfolge der aktuell ausgewählten Gruppe. Diese Reihenfolge wird auch für die Standard-PDF-Ausgabe verwendet. **Gruppe löschen** betrifft ausschließlich die aktive Gruppe.

Der Sensorpicker arbeitet automatisch mit der im Dropdown ausgewählten Gruppe. Eine zusätzliche Zielgruppen-Auswahl ist nicht mehr nötig. Nach Auswahl der Gruppe kann der gewünschte Sensor gesucht, gefiltert und hinzugefügt werden.

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

Die BMF-Strompreispauschale ist eine **Jahrespauschale**. Für das gesamte Kalenderjahr wird nach der BMF-Regel der von Destatis veröffentlichte Gesamtstrompreis aus dem **1. Halbjahr des Vorjahres** für private Haushalte mit 5.000 bis unter 15.000 kWh Jahresverbrauch verwendet und auf volle Cent abgerundet. Der Wert wird nicht im laufenden Jahr halbjährlich angepasst.

Für das Kalenderjahr **2026** ist daher das **1. Halbjahr 2025** die maßgebliche Datengrundlage. Der Destatis-Wert von 34,36 ct/kWh ergibt nach Abrundung die BMF-Strompreispauschale von **0,34 €/kWh** für das gesamte Kalenderjahr 2026. Für 2027 ist entsprechend das 1. Halbjahr 2026 maßgeblich.

**Hinweis zum Anwendungsbereich:** Die konkrete BMF-Strompreispauschale ist steuerlich für selbst getragene Stromkosten beim häuslichen Laden betrieblicher Elektro-/Hybridelektrofahrzeuge geregelt. Wenn derselbe Wert in EVCC to PDF auf zusätzliche Home-Assistant-Abrechnungsgruppen angewendet wird, dient er dort als einheitlicher Rechenpreis; die BMF-Regel selbst ist keine allgemeine Homeoffice-Strompauschale.

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

Einstellungen werden ab v1.3.03 im Home-Assistant-App-Datenbereich unter `/data/evcc_to_pdf` gespeichert. Dazu gehören:

- `settings.json`
- `backups/settings_*.json`
- `bmf_price_cache.json`
- `ha_entity_cache.json`

Beim ersten Start nach einem Update wird vor dem Anlegen von Werkseinstellungen nach älteren Konfigurationen gesucht. v1.3.02 und ältere Installationen mit `/config/settings.json` werden automatisch übernommen. Ist die alte Hauptdatei beschädigt, wird zusätzlich nach einem gültigen Backup gesucht. Alte Dateien werden bei der Migration nicht gelöscht.

Der seit v1.3.03 verwendete `app_config`-Mount bleibt auch in v1.3.05 read-only unter `/config` eingebunden, damit diese Migration zuverlässig durchgeführt werden kann. Neue Laufzeitdaten werden ausschließlich unter `/data/evcc_to_pdf` geschrieben.

## 11. Webserver & App-Lifecycle

Die Weboberfläche wird produktiv über Gunicorn mit einem Worker und vier Threads ausgeliefert. Dadurch läuft der interne Scheduler genau einmal, während mehrere Webanfragen parallel verarbeitet werden können. Die App startet als `application`, also nach Home Assistant, und verwendet wieder den Standard-Init des Supervisors.

Fehler beim Laden von Home-Assistant-Verbrauchssensoren oder EVCC-Assets werden zusätzlich im App-Log protokolliert.

## 12. Release-Checkliste

Die für Folgeversionen verbindlichen Projektregeln stehen zusätzlich in der Root-Datei `RELEASE_CHECKLIST.md`.
