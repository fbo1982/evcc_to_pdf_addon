# EVCC to PDF – Dokumentation v1.3.01

## 1. Grundprinzip

Seit v1.3.01 gibt es keine getrennten EVCC- und Home-Assistant-Gruppentypen mehr. Eine **Abrechnungsgruppe** enthält beliebige Verbraucher aus beiden Quellen und erzeugt daraus eine gemeinsame Abrechnung.

Zu einer Gruppe gehören unter anderem:

- Empfänger
- gemeinsamer Abrechnungszeitraum
- gemeinsamer Strompreis
- optional EVCC-Ladevorgänge / Fahrzeuge
- beliebig viele Home-Assistant-Verbrauchssensoren
- Template und E-Mail-Einstellungen

## 2. EVCC-Verbraucher

Mit **„EVCC-Ladevorgänge in dieser Gruppe berücksichtigen“** wird EVCC für die Gruppe aktiviert. Danach können einzelne Fahrzeuge gewählt werden. Ohne Fahrzeugauswahl werden alle gefundenen Fahrzeuge berücksichtigt.

Im Report bleiben die Ladevorgänge nach Fahrzeug gegliedert und erhalten eine Zwischensumme je Fahrzeug.

## 3. Home-Assistant-Verbrauchssensoren

Nach **HA-Entitäten aktualisieren** zeigt der Picker ausschließlich geeignete Verbrauchssensoren:

- Energie-Sensoren: Wh / kWh / MWh
- Leistungs-Sensoren: W / kW / MW

EVCC-eigene Home-Assistant-Entitäten werden automatisch aus der Auswahl entfernt. Dadurch werden EVCC-Ladevorgänge nicht versehentlich ein zweites Mal als HA-Verbrauch erfasst.

Zusätzlich stehen im Picker folgende Filter zur Verfügung:

- Alle Verbrauchssensoren
- Energiezähler
- Leistungssensoren
- Freitextsuche nach Name oder Entity-ID

## 4. Berechnung von HA-Verbrauch

### Energiezähler

Für Energiezähler wird die Differenz bzw. Summe im gewählten Zeitraum ermittelt. Home-Assistant-Langzeitstatistiken werden bevorzugt verwendet; die Recorder-History dient als Fallback.

### Leistungssensoren

Leistungswerte werden über die Zeit integriert und in kWh umgerechnet.

Bereits in v1.3.0 konfigurierte Laufzeit-Quellen bleiben aus Kompatibilitätsgründen erhalten, werden aber nicht mehr im neuen Sensorpicker angeboten.

## 5. Doppelzählung

Jede HA-Quelle besitzt **„In Gruppensumme einrechnen“**.

Beispiel: Ein Shelly für Phase 1 enthält bereits den Stromverbrauch des 3D-Druckers. Ein zusätzlicher Shelly Plug am Drucker kann trotzdem als Detailposition erscheinen. Wird dessen Summierungsoption deaktiviert, bleibt die Gesamtsumme korrekt.

EVCC-Ladevorgänge werden immer in die Gruppensumme einbezogen, sofern EVCC für die Gruppe aktiviert ist.

## 6. Gemeinsamer Strompreis

Der Strompreis wird einmal pro Gruppe festgelegt und auf EVCC- und HA-Verbrauch gleichermaßen angewendet.

### Manuell

Der Gruppen-Override wird in €/kWh eingetragen. Ist er leer, wird der Standard-Strompreis aus den Einstellungen verwendet. Im PDF erscheint nur der zugrunde gelegte Strompreis.

### BMF-/Destatis-Automatik

Ist die Automatik aktiviert, wird der für das Abrechnungsjahr ermittelte Wert für die komplette Gruppe verwendet. Im PDF erscheinen zusätzlich Preisermittlung und Datengrundlage.

## 7. Gemeinsame PDF-Ausgabe

Das Standardtemplate zeigt nacheinander:

1. Fahrzeugbereiche mit Ladevorgängen und Fahrzeug-Zwischensummen
2. Home-Assistant-Verbraucher mit Entity-ID, Verbrauch, Kosten und Berechnungsmethode
3. gemeinsame Gesamtsumme
4. gemeinsamen Strompreis
5. bei Automatik Preisermittlung und Grundlage

Damit kann beispielsweise eine komplette Homeoffice-Abrechnung aus Dienstwagen, drei Phasen, Server, 3D-Drucker und Klimaanlage in einem Dokument erzeugt werden.

## 8. Migration von v1.3.0

Die Migration erfolgt automatisch:

- alte EVCC-Gruppen erhalten `include_evcc = true`
- alte Home-Assistant-Gruppen erhalten `include_evcc = false`
- alle Gruppen werden intern auf den gemeinsamen Typ `mixed` umgestellt
- vorhandene Fahrzeuge und HA-Quellen bleiben erhalten
- BMF-Preismodus wird nicht mehr aufgrund des alten Gruppentyps deaktiviert
- ein unverändertes v1.3.0-Standardtemplate wird automatisch auf das neue kombinierte Layout migriert
- individuell bearbeitete Templates werden nicht überschrieben

## 9. Persistenz

Einstellungen werden persistent unter `/config` gespeichert. Schreibvorgänge sind atomar und erzeugen Backups. Ein beschädigtes Settings-File führt nicht unmittelbar zu Werkseinstellungen, sondern löst zunächst die Wiederherstellung aus einem gültigen Backup aus.
