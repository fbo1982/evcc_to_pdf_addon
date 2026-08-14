<p align="center">
  <img src="docs/images/hero.png" alt="EVCC to PDF – modulare Energieabrechnung" width="100%">
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-1.3.01-22c55e">
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-App-41BDF5">
  <img alt="EVCC" src="https://img.shields.io/badge/EVCC-compatible-00c853">
  <img alt="Homeoffice" src="https://img.shields.io/badge/Homeoffice-Energieabrechnung-1597ff">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-lightgrey">
</p>

# EVCC to PDF

**EVCC to PDF** ist ein modularer Energie-Abrechnungsbaukasten für Home Assistant. Eine Abrechnungsgruppe kann **EVCC-Ladevorgänge und Home-Assistant-Verbrauchssensoren gemeinsam** enthalten. Alle Verbraucher werden für denselben Zeitraum ausgewertet, mit demselben Gruppenstrompreis verrechnet und in **einer Abrechnung / einem PDF** zusammengeführt.

Typische Verbraucher sind Dienstwagen, Shelly-Energiezähler, einzelne Stromkreise, Server, 3D-Drucker oder eine Klimaanlage mit eigenem Energie-/Leistungssensor.

## Neu in v1.3.01

- keine getrennten Gruppentypen EVCC / Home Assistant mehr
- EVCC-Fahrzeuge und HA-Verbrauchssensoren können in derselben Gruppe kombiniert werden
- ein gemeinsamer Strompreis pro Abrechnungsgruppe
- BMF-/Destatis-Automatik kann für die komplette Gruppenabrechnung verwendet werden
- gemeinsame Gesamtsumme aus EVCC-Verbrauch + einbezogenen HA-Sensoren
- Fahrzeug-Zwischensummen bleiben erhalten
- HA-Verbraucher werden zusätzlich als eigene Positionen dargestellt
- Sensorliste zeigt nur **Energie- und Leistungssensoren**
- EVCC-eigene Home-Assistant-Sensoren werden automatisch ausgefiltert
- zusätzlicher Filter für **Alle / Energie / Leistung**
- bestehende v1.3.0-Gruppen werden automatisch migriert

## Beispiel: eine gemeinsame Homeoffice-Abrechnung

Eine einzige Gruppe **„Homeoffice-Abrechnung“** kann z. B. enthalten:

- EVCC: Dienstwagen / Ladevorgänge
- Shelly Phase 1
- Shelly Phase 2
- Shelly Phase 3
- Shelly Plug 3D-Drucker
- Shelly Server
- Energie- oder Leistungssensor der Klimaanlage

Alle enthaltenen Verbraucher werden über denselben Abrechnungszeitraum ermittelt. Am Ende entstehen eine gemeinsame kWh-Summe und ein gemeinsamer Rechnungsbetrag.

### Doppelzählung verhindern

Wenn beispielsweise „Phase 1“ den 3D-Drucker bereits enthält, kann der separate Shelly Plug des Druckers im PDF als Detail angezeigt werden, ohne erneut in die Gesamtsumme einzugehen. Dafür gibt es pro HA-Quelle die Option **„In Gruppensumme einrechnen“**.

## Verbrauchsermittlung

### EVCC

EVCC-Ladevorgänge werden wie bisher aus den Sessions gelesen und nach Fahrzeug untergliedert. Pro Fahrzeug werden Ladevorgänge und Zwischensummen ausgegeben.

### Home Assistant

Im Sensorpicker werden nur für die Abrechnung geeignete Verbrauchssensoren angeboten:

- **Energie:** Wh, kWh, MWh
- **Leistung:** W, kW, MW

EVCC-eigene HA-Entitäten werden aus dieser Liste entfernt, damit die gleichen Ladevorgänge nicht versehentlich zusätzlich über HA-Sensoren erfasst werden.

Energiezähler werden bevorzugt über Home-Assistant-Langzeitstatistiken ausgewertet. Leistungssensoren werden über den Zeitraum integriert und in kWh umgerechnet.

## Strompreis

Der Strompreis gehört zur **gesamten Abrechnungsgruppe** und gilt somit gleichermaßen für Fahrzeuge und HA-Verbraucher.

### Manuell

Ein Preis-Override kann in €/kWh eingetragen werden. Bleibt er leer, wird der Standard-Strompreis aus den Einstellungen verwendet.

Bei manueller Preiswahl erscheint im PDF nur der zugrunde gelegte Strompreis; die Zeile **„Preisermittlung“** entfällt.

### BMF-/Destatis-Automatik

Ist die Automatik aktiviert, wird der für das Abrechnungsjahr hinterlegte bzw. ermittelte Wert für die komplette Gruppe verwendet. Im PDF werden zusätzlich Preisermittlung und Grundlage ausgegeben.

> **Hinweis:** Das Projekt ist ein technisches Abrechnungswerkzeug und keine Steuer-, Rechts- oder Lohnabrechnungsberatung.

## Installation in Home Assistant

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https://github.com/fbo1982/evcc_to_pdf_addon.git)

Manuell:

1. **Einstellungen → Apps → App-Store** öffnen.
2. **Repositories** auswählen.
3. `https://github.com/fbo1982/evcc_to_pdf_addon.git` hinzufügen.
4. **EVCC to PDF** installieren und starten.
5. Weboberfläche öffnen.
6. EVCC und SMTP unter **Einstellungen** konfigurieren.
7. Unter **Gruppen** eine gemeinsame Abrechnungsgruppe anlegen.
8. EVCC-Fahrzeuge aktivieren/auswählen und über **HA-Entitäten aktualisieren** die gewünschten Verbrauchssensoren ergänzen.
9. Strompreis-Modus wählen und eine Vorschau erzeugen.

## PDF-Ausgabe

Das Standardtemplate kann in einer Abrechnung gleichzeitig darstellen:

- EVCC-Fahrzeuge mit Datum, Start, Ende, kWh und Kosten
- Fahrzeug-Zwischensummen
- Home-Assistant-Verbraucher mit Entity-ID, kWh, Kosten und Berechnungsmethode
- Information, ob eine HA-Position in die Gesamtsumme einfließt
- Gesamtverbrauch aller einbezogenen Verbraucher
- Gesamtkosten
- zugrunde gelegten Strompreis
- bei Automatik zusätzlich Preisermittlung und Grundlage

## Templates

Wichtige Template-Kontexte:

- `group_name`
- `group_type` (`mixed` ab v1.3.01)
- `has_evcc`, `has_ha`
- `vehicle_groups`, `sessions`
- `ha_sources`
- `evcc_total_energy`, `evcc_total_cost`
- `ha_total_energy`, `ha_total_cost`
- `total_energy_kwh`, `total_cost_eur`
- `electricity_price_eur_kwh`
- `price_mode`, `price_method_label`, `price_source_label`

Eine vollständige Übersicht steht in [`evcc_to_pdf/PLACEHOLDERS.md`](evcc_to_pdf/PLACEHOLDERS.md).

## Persistenz

Konfiguration, Gruppen und benutzerdefinierte Templates werden persistent im Home-Assistant-App-Konfigurationsbereich gespeichert. Schreibvorgänge erfolgen atomar mit Backups. Erzeugte PDFs werden unter `/share/evcc-pdfs` abgelegt.

## Branding

Das Homeoffice-/E-Mobility-Branding mit Schreibtisch, Wallbox, Fahrzeug und PDF bleibt Bestandteil der App:

- `evcc_to_pdf/icon.png`
- `evcc_to_pdf/logo.png`
- `docs/images/icon-512.png`
- `docs/images/logo-wide.png`
- `docs/images/hero.png`

## Changelog

Siehe [`CHANGELOG.md`](CHANGELOG.md).

## Lizenz

MIT License – siehe [`LICENSE`](LICENSE).
