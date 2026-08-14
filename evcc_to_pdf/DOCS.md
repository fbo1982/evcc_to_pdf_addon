# EVCC to PDF – Dokumentation v1.3.0

## 1. Konzept

Eine **Abrechnungsgruppe** ist eine eigenständige Einheit mit Empfänger, Strompreis, Zeitraum, Template und Datenquellen. Es gibt zwei Gruppentypen:

1. **EVCC** – Ladevorgänge und Fahrzeuge
2. **Home Assistant** – Energie-, Leistungs- oder Laufzeit-Entitäten

Damit lassen sich beispielsweise E-Fahrzeuge, Homeoffice-Stromkreise, Server und Klimaanlagen unabhängig voneinander abrechnen.

## 2. Einstellungen

### EVCC

Für EVCC-Gruppen die Basis-URL und bei Bedarf das EVCC-Passwort eintragen.

### Standard-Strompreis

Der Standard-Strompreis in €/kWh wird verwendet, wenn eine Gruppe keinen eigenen Preis-Override besitzt.

### SMTP

Für den automatischen Versand SMTP-Host, Port, Benutzer und Passwort hinterlegen. TLS kann aktiviert werden.

### Scheduler

Der Scheduler erzeugt und versendet aktive Gruppen automatisch nach deren Abrechnungsmodus und Versandtag.

## 3. EVCC-Gruppen

Beim Gruppentyp **EVCC** werden die EVCC-Fahrzeuge angezeigt. Nach **EVCC aktualisieren** können einzelne Fahrzeuge ausgewählt werden. Ohne Auswahl werden alle passenden Ladevorgänge verwendet.

Die Standardausgabe untergliedert den Bericht nach Fahrzeugen und erzeugt pro Fahrzeug eine Zwischensumme.

### BMF-/Destatis-Preis

Nur EVCC-Gruppen können die automatische BMF-/Destatis-Strompreispauschale verwenden. Bei manueller Preiswahl wird im Bericht ausschließlich der verwendete Strompreis ausgegeben; „Preisermittlung“ und „Grundlage“ bleiben leer.

## 4. Home-Assistant-Gruppen

### Entitäten laden

Unter **Gruppen → HA-Entitäten aktualisieren** liest die App geeignete Entitäten direkt aus Home Assistant. Dafür nutzt das App den internen Core-API-Zugriff und `SUPERVISOR_TOKEN`; ein eigener Long-Lived Access Token ist nicht erforderlich.

Angeboten werden:

- Energie-Sensoren in `Wh`, `kWh`, `MWh`
- Leistungssensoren in `W`, `kW`, `MW`
- `climate.*`, `switch.*`, `binary_sensor.*`, `input_boolean.*` für die optionale Laufzeit-Schätzung

### Quelle hinzufügen

Eine Quelle enthält:

- Anzeigename
- Entity-ID
- Auswertungsmodus
- optionale Nennleistung
- Option **In Gruppensumme einrechnen**

### Automatische Auswertung

**Auto** erkennt den Typ anhand der aktuellen Home-Assistant-Entität.

#### Energiezähler

Energiezähler werden über die Differenz des Abrechnungszeitraums ausgewertet. Langzeitstatistiken werden bevorzugt. Falls keine Statistik verfügbar ist, versucht die App die Recorder-History zu verwenden.

#### Leistungssensor

Leistungswerte werden über den Zeitraum integriert und in kWh umgerechnet. Auch hier werden Home-Assistant-Statistiken bevorzugt.

#### Laufzeit × Nennleistung

Für Entitäten ohne gemessene Energie oder Leistung kann eine Nennleistung in Watt hinterlegt werden. Die aktive Laufzeit wird mit dieser Leistung multipliziert. Diese Methode ist eine **Schätzung** und wird im PDF entsprechend gekennzeichnet.

Für Klimaanlagen ist ein echter Energie- oder Leistungssensor vorzuziehen.

## 5. Doppelzählungen

Beispiel:

- `sensor.shelly_phase_1_energy` misst den gesamten Stromkreis.
- `sensor.3d_drucker_energy` ist Bestandteil dieses Stromkreises.

Wenn beide Quellen addiert werden, wird der Drucker doppelt gezählt. Deshalb kann der Drucker in der Gruppe sichtbar bleiben, während **In Gruppensumme einrechnen** deaktiviert wird.

Die Detailposition erhält weiterhin ihren eigenen Verbrauch und rechnerischen Kostenanteil, beeinflusst aber die Gruppensumme nicht.

## 6. Strompreis für Home-Assistant-Gruppen

Home-Assistant-Gruppen verwenden einen manuellen Gruppenpreis. Bleibt der Override leer, wird der Standard-Strompreis aus den Einstellungen verwendet.

Die BMF-/Destatis-Automatik ist bewusst EVCC-Gruppen vorbehalten.

## 7. Berichte

Unter **Manuell** Gruppe, Jahr und Monat auswählen. Möglich sind:

- HTML-Vorschau
- PDF erzeugen
- PDF erzeugen und per E-Mail senden

### Home-Assistant-PDF

Je Quelle werden ausgegeben:

- Name
- Entity-ID
- Verbrauch
- Kosten
- Berechnungsmethode
- Summierungsstatus

Danach folgen Gesamtverbrauch, Gesamtkosten und Strompreis der Gruppe.

## 8. Langzeitstatistiken und History

Für Abrechnungen ist eine kontinuierliche Datenbasis wichtig. Die App verwendet für geeignete Sensoren bevorzugt Home Assistants Recorder-Langzeitstatistiken. Dadurch ist die Auswertung nicht ausschließlich von der normalen History-Aufbewahrungsdauer abhängig.

Wenn eine Entität keine geeigneten Statistiken liefert, wird auf die History zurückgegriffen. Fehlt für eine Quelle die erforderliche Datenbasis und die Quelle ist Teil der Gruppensumme, wird die Abrechnung mit einer verständlichen Fehlermeldung abgebrochen, statt stillschweigend einen falschen Wert zu verwenden.

## 9. Templates

Das Standardtemplate unterstützt EVCC- und Home-Assistant-Gruppen. Eigene Templates können weiterhin verwendet werden.

Zusätzliche Variablen in v1.3.0:

- `group_name`
- `group_type`
- `ha_sources`

Details stehen in `PLACEHOLDERS.md`.

## 10. Speicherung und Backups

Die Konfiguration wird persistent unter dem von Home Assistant bereitgestellten App-Konfigurationsbereich gespeichert. Schreibvorgänge sind atomar, vor Änderungen werden Backups erstellt und beschädigte Konfigurationen werden nicht kommentarlos durch Werkseinstellungen ersetzt.

## 11. PDF-Ablage

PDFs werden unter `/share/evcc-pdfs` gespeichert.

## 12. Hinweis

EVCC to PDF ist ein technisches Abrechnungswerkzeug und keine Steuer-, Rechts- oder Lohnabrechnungsberatung. Bei Laufzeit × Nennleistung handelt es sich ausdrücklich um eine Verbrauchsschätzung.
