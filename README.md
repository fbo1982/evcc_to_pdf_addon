<p align="center">
  <img src="docs/images/hero.png" alt="EVCC to PDF – modulare Energieabrechnung" width="100%">
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-1.3.0-22c55e">
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-App-41BDF5">
  <img alt="EVCC" src="https://img.shields.io/badge/EVCC-compatible-00c853">
  <img alt="Homeoffice" src="https://img.shields.io/badge/Homeoffice-Energieabrechnung-1597ff">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-lightgrey">
</p>

# EVCC to PDF

**EVCC to PDF** ist ab **v1.3.0** ein modularer Energie-Abrechnungsbaukasten für Home Assistant. Neben EVCC-Ladevorgängen können jetzt auch Home-Assistant-Entitäten wie Shelly-Energiezähler, Leistungs-Sensoren, Server, 3D-Drucker oder Klimaanlagen in frei definierbaren Gruppen ausgewertet werden.

Das Ziel: Energieverbrauch im Homeoffice oder beim Laden eines Dienstwagens nachvollziehbar über einen Zeitraum ermitteln, Kosten berechnen, als PDF dokumentieren und optional automatisch per E-Mail versenden.

## Highlights

- **EVCC-Gruppen** für Fahrzeuge und Ladevorgänge
- **Home-Assistant-Gruppen** für beliebige geeignete Energiequellen
- Mehrere Entitäten pro Gruppe, z. B. drei Phasen + 3D-Drucker + Server
- Gruppensumme aus den ausgewählten Quellen
- Einzelne Quellen können **nur als Detail angezeigt** und von der Summe ausgeschlossen werden – wichtig gegen Doppelzählungen
- Energie-Sensoren (`Wh`, `kWh`, `MWh`) werden als Zähler ausgewertet
- Leistungssensoren (`W`, `kW`, `MW`) werden über den Abrechnungszeitraum zu kWh integriert
- Climate-/Switch-Entitäten können optional über **Laufzeit × Nennleistung** geschätzt werden
- Home-Assistant-Langzeitstatistiken werden bevorzugt genutzt, mit History-Fallback
- Strompreis je Gruppe manuell; für EVCC zusätzlich **BMF-/Destatis-Strompreispauschale**
- Fahrzeugbasierte EVCC-Auswertung mit Zwischensummen
- PDF-Vorschau, PDF-Erstellung und automatischer E-Mail-Versand
- Monatlich, quartalsweise, halbjährlich oder jährlich
- HTML-Templates inklusive Editor
- Persistente, atomare Speicherung mit Backups und MQTT-Spiegel
- Neues Branding für **E-Mobilität + Homeoffice**

## Beispiel für modulare Gruppen

### Gruppe 1 – Homeoffice Stromkreise

- Shelly Phase 1
- Shelly Phase 2
- Shelly Phase 3
- Shelly Plug 3D-Drucker

Wenn der 3D-Drucker bereits in Phase 1 enthalten ist, kann der Plug trotzdem als Detailposition angezeigt werden. Die Option **„In Gruppensumme einrechnen“** wird dann für den Plug deaktiviert.

### Gruppe 2 – IT & Server

- Shelly / Energie-Sensor Server
- weitere IT-Verbraucher

### Gruppe 3 – Klimaanlage

Optimal ist ein eigener Energie- oder Leistungssensor der Klimaanlage. Falls nur eine `climate.*`-Entität vorhanden ist, kann alternativ die Laufzeit mit einer hinterlegten Nennleistung verrechnet werden. Diese Variante wird im Bericht ausdrücklich als **Schätzung** gekennzeichnet.

### Gruppe 4 – E-Fahrzeuge

- EVCC-Ladevorgänge
- Untergliederung nach Fahrzeugen
- optional BMF-/Destatis-Strompreispauschale

## Installation in Home Assistant

### Mit einem Klick

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https://github.com/fbo1982/evcc_to_pdf_addon.git)

### Manuell

1. **Einstellungen → Apps → App-Store** öffnen.
2. Oben rechts **Repositories** auswählen.
3. `https://github.com/fbo1982/evcc_to_pdf_addon.git` hinzufügen.
4. **EVCC to PDF** installieren und starten.
5. Optional **In Seitenleiste anzeigen** aktivieren.
6. Weboberfläche öffnen und die gewünschten Datenquellen und Gruppen konfigurieren.

## Schnellstart

1. Unter **Einstellungen** EVCC konfigurieren, wenn Fahrzeugabrechnungen genutzt werden sollen.
2. SMTP und Standard-Strompreis hinterlegen.
3. Unter **Gruppen** eine neue Abrechnungsgruppe anlegen.
4. Gruppentyp wählen: **EVCC** oder **Home Assistant**.
5. Bei Home Assistant zuerst **HA-Entitäten aktualisieren**.
6. Gewünschte Energie-/Leistungsquellen hinzufügen.
7. Prüfen, welche Quellen in die Gruppensumme einfließen dürfen.
8. Unter **Manuell** Vorschau und PDF für einen Testmonat erzeugen.
9. Danach optional den Scheduler aktivieren.

## Home-Assistant-Verbrauchsermittlung

EVCC to PDF nutzt den internen Home-Assistant-Core-API-Zugriff des Apps. Es ist kein separater Long-Lived Access Token erforderlich.

### Energiezähler

Für Sensoren mit Energieeinheit wie `kWh` oder `Wh` wird die Verbrauchsdifferenz des Abrechnungszeitraums ermittelt. Wenn Home Assistant Langzeitstatistiken für die Entität führt, werden diese bevorzugt genutzt. Damit sind auch Abrechnungszeiträume möglich, die über die normale Recorder-History hinausreichen.

### Leistungssensoren

Bei Sensoren in `W` oder `kW` wird die mittlere Leistung aus Home-Assistant-Statistiken über die Zeit integriert und daraus der Energieverbrauch in kWh berechnet.

### Laufzeit-Schätzung

Für `climate.*`, `switch.*`, `binary_sensor.*` und `input_boolean.*` kann als Fallback eine Nennleistung hinterlegt werden. Der Verbrauch wird dann aus aktiver Laufzeit × Nennleistung berechnet. Diese Methode ist eine Schätzung und kein gemessener Energieverbrauch.

## Doppelzählung verhindern

Ein wichtiger Teil der Gruppenlogik ist **„In Gruppensumme einrechnen“**. Beispiel:

- Phase 1 misst 20 kWh und enthält bereits den 3D-Drucker.
- Der 3D-Drucker-Plug misst davon 3 kWh.
- Werden beide summiert, entstünden fälschlich 23 kWh.

Deshalb kann der 3D-Drucker mit 3 kWh im Bericht sichtbar bleiben, aber aus der Gruppensumme ausgeschlossen werden. Die Gruppensumme bleibt korrekt bei 20 kWh.

## Strompreis

### Manuell

Der Gruppenpreis wird in €/kWh eingetragen. Bleibt der Gruppen-Override leer, wird der Standard-Strompreis aus **Einstellungen** verwendet.

Bei manueller Preiswahl erscheint im PDF nur:

**Zugrunde gelegter Strompreis: … €/kWh**

Eine Zeile „Preisermittlung“ wird nicht ausgegeben.

### BMF-/Destatis-Pauschale

Die automatische BMF-/Destatis-Option bleibt für **EVCC-Fahrzeuggruppen** verfügbar. Sie wird bewusst nicht auf allgemeine Homeoffice-/Home-Assistant-Gruppen übertragen.

> **Hinweis:** Das Projekt ist ein technisches Abrechnungswerkzeug und keine Steuer-, Rechts- oder Lohnabrechnungsberatung.

## PDF-Ausgabe

### EVCC-Gruppe

- Fahrzeug
- Datum, Start- und Endzeit
- geladene kWh
- Kosten je Ladevorgang
- Zwischensumme je Fahrzeug
- GesamtkWh und Gesamtkosten
- verwendeter Strompreis

### Home-Assistant-Gruppe

- Quellenname
- Entity-ID
- Verbrauch in kWh
- Kosten
- Berechnungsmethode
- Information, ob die Position in der Gruppensumme enthalten ist
- Gesamtverbrauch und Gesamtkosten der Gruppe

## Templates

Das Standardtemplate unterstützt jetzt beide Gruppentypen. Zusätzlich stehen unter anderem folgende Kontexte zur Verfügung:

- `group_name`
- `group_type`
- `ha_sources`
- `vehicle_groups`
- `sessions`
- `electricity_price_eur_kwh`
- `price_mode`
- `price_method_label`
- `price_source_label`
- `total_energy_kwh`
- `total_cost_eur`

Eine vollständige Übersicht liegt in [`evcc_to_pdf/PLACEHOLDERS.md`](evcc_to_pdf/PLACEHOLDERS.md).

## Datensicherheit und Persistenz

Konfiguration und benutzerdefinierte Templates werden persistent im Home-Assistant-App-Konfigurationsbereich gespeichert. Schreibvorgänge erfolgen atomar und vorhandene Einstellungen werden vor Änderungen gesichert. Ein kurzzeitig nicht verfügbarer MQTT-Broker darf die lokale Konfiguration nicht mit Werkseinstellungen überschreiben.

Erzeugte PDF-Dateien werden unter `/share/evcc-pdfs` abgelegt.

## Branding

v1.3.0 enthält das neue Homeoffice-/E-Mobility-Branding:

- `evcc_to_pdf/icon.png` – App-Icon
- `evcc_to_pdf/logo.png` – App-Store-Logo
- `docs/images/icon-512.png` – großes Icon
- `docs/images/logo-wide.png` – breites Logo
- `docs/images/hero.png` – vollständige Projektgrafik

## Changelog

Alle Änderungen findest du in [`CHANGELOG.md`](CHANGELOG.md).

## Repository

- Repository: `https://github.com/fbo1982/evcc_to_pdf_addon`
- Releases: `https://github.com/fbo1982/evcc_to_pdf_addon/releases`

## Lizenz

MIT License – siehe [`LICENSE`](LICENSE).
