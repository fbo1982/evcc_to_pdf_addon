<p align="center">
  <img src="docs/images/hero.png" alt="EVCC to PDF – modulare Energieabrechnung" width="100%">
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-1.3.02-22c55e">
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-App-41BDF5">
  <img alt="EVCC" src="https://img.shields.io/badge/EVCC-compatible-00c853">
  <img alt="Homeoffice" src="https://img.shields.io/badge/Homeoffice-Energieabrechnung-1597ff">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-lightgrey">
</p>

# EVCC to PDF

**EVCC to PDF** erstellt gemeinsame Energieabrechnungen aus EVCC-Ladevorgängen und Home-Assistant-Verbrauchssensoren. Sensoren können in **beliebig vielen frei benannten Abrechnungsgruppen** zusammengefasst werden. Fahrzeuge bleiben dagegen bewusst einzeln und transparent sichtbar.

Beispiel für eine einzige Abrechnung:

- **HomeOffice** → Shelly L1 + Shelly L2 + Shelly L3 + Shelly 3D-Drucker
- **Server** → Shelly Server + Shelly Router
- **Klimaanlage** → Energie-/Leistungssensor der Klimaanlage
- **Fahrzeuge** → BMW iX1, Silence S04 usw. mit einzelnen EVCC-Ladevorgängen

Alle Positionen verwenden denselben Abrechnungszeitraum und denselben Strompreis. In der PDF werden die Home-Assistant-Sensoren **nicht einzeln offengelegt**: Dort erscheinen nur die Namen und Summen ihrer Abrechnungsgruppen. Fahrzeuge werden weiterhin einzeln mit Ladevorgängen und Fahrzeug-Zwischensummen aufgelistet.

## Neu in v1.3.02

- beliebig viele benannte **Sensor-Abrechnungsgruppen** innerhalb einer Abrechnung
- beliebig viele HA-Verbrauchssensoren je Gruppe
- Gruppen können frei benannt, gelöscht und in der PDF-Reihenfolge verschoben werden
- Sensorpicker mit Suche und Filter **Alle / Energie / Leistung**
- EVCC-eigene Home-Assistant-Sensoren werden aus dem Picker ausgefiltert
- ein Sensor kann über die UI nur einer Sensorgruppe zugeordnet werden
- Schalter **„In Gruppensumme einrechnen“** bleibt zum Schutz vor Doppelzählungen erhalten
- PDF zeigt für HA nur **Gruppenname + Gruppenverbrauch + Gruppenbetrag**
- Fahrzeuge bleiben detailliert und einzeln sichtbar
- gemeinsamer manueller oder BMF-/Destatis-Strompreis für die komplette Abrechnung
- automatische Migration der flachen HA-Sensorliste aus v1.3.01
- unverändertes v1.3.01-Standardtemplate wird auf die neue Gruppenausgabe migriert; eigene Template-Anpassungen bleiben unangetastet

## Datenmodell

Die Konfiguration ist ab v1.3.02 bewusst in zwei Ebenen getrennt:

**Abrechnung**

- Empfänger, Absender, Bankdaten
- Zeitraum und Versand
- gemeinsamer Strompreis
- ausgewählte EVCC-Fahrzeuge
- beliebig viele Sensor-Abrechnungsgruppen

**Sensor-Abrechnungsgruppe**

- frei wählbarer Gruppenname
- beliebig viele Home-Assistant-Verbrauchssensoren
- Gruppensumme in kWh und Euro

Fahrzeuge werden nicht in den Sensorgruppen versteckt. Sie bleiben als eigenständige, nachvollziehbare Positionen der Abrechnung erhalten.

## Sensorfilter

Im HA-Picker werden nur für die Verbrauchsermittlung geeignete Sensoren angeboten:

- **Energie:** Wh, kWh, MWh
- **Leistung:** W, kW, MW

EVCC-eigene HA-Entitäten werden automatisch entfernt, damit Ladevorgänge nicht versehentlich doppelt erfasst werden. Energiezähler werden bevorzugt aus Home-Assistant-Langzeitstatistiken ermittelt; Leistungssensoren werden über den Abrechnungszeitraum zu kWh integriert.

## Doppelzählung vermeiden

Wenn beispielsweise `Shelly L1` bereits den 3D-Drucker enthält und zusätzlich ein eigener Shelly Plug am Drucker existiert, kann der Detail-Sensor in derselben Gruppe hinterlegt, aber mit **„In Gruppensumme einrechnen“ = aus** markiert werden.

Der Sensor bleibt damit konfiguriert, beeinflusst aber weder Gruppen- noch Gesamtsumme.

## Strompreis

Der Strompreis gilt **einmal pro Abrechnung** für alle Sensorgruppen und Fahrzeuge.

### Manuell

Ein Preis-Override kann in €/kWh eingetragen werden. Bleibt er leer, wird der Standard-Strompreis aus den Einstellungen verwendet. Bei manueller Preiswahl zeigt die PDF nur:

> Zugrunde gelegter Strompreis: … €/kWh

Eine zusätzliche Zeile „Preisermittlung“ wird nicht ausgegeben.

### BMF-/Destatis-Automatik

Ist die Automatik aktiviert, verwendet die Abrechnung den für das Abrechnungsjahr ermittelten Wert. In der PDF werden zusätzlich Preisermittlung und Datengrundlage angezeigt.

> **Hinweis:** Das Projekt ist ein technisches Abrechnungswerkzeug und keine Steuer-, Rechts- oder Lohnabrechnungsberatung.

## PDF-Ausgabe

Das Standardtemplate zeigt:

1. jedes EVCC-Fahrzeug einzeln
2. darunter dessen einzelne Ladevorgänge
3. Fahrzeug-Zwischensumme
4. anschließend die benannten Sensor-Abrechnungsgruppen nur als Summenpositionen
5. Gesamtverbrauch und Gesamtkosten
6. zugrunde gelegten Strompreis
7. bei Preisautomatik zusätzlich Preisermittlung und Grundlage

Die einzelnen Shelly-/HA-Entity-IDs werden im Standard-PDF nicht offengelegt.

## Installation in Home Assistant

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https://github.com/fbo1982/evcc_to_pdf_addon.git)

Manuell:

1. **Einstellungen → Apps → App-Store** öffnen.
2. **Repositories** auswählen.
3. `https://github.com/fbo1982/evcc_to_pdf_addon.git` hinzufügen.
4. **EVCC to PDF** installieren und starten.
5. EVCC und SMTP unter **Einstellungen** konfigurieren.
6. Unter **Gruppen** eine Abrechnung anlegen.
7. Gewünschte EVCC-Fahrzeuge auswählen.
8. **HA-Entitäten aktualisieren**.
9. Beliebig viele Sensor-Abrechnungsgruppen anlegen, z. B. `HomeOffice`, `Server`, `Klimaanlage`.
10. Verbrauchssensoren den Gruppen zuweisen.
11. Strompreis-Modus wählen und Vorschau/PDF erzeugen.

## Templates

Wichtige Template-Kontexte:

- `group_name` – Name der kompletten Abrechnung
- `vehicle_groups` – Fahrzeuge mit Ladevorgängen und Zwischensummen
- `billing_groups` – ausgewertete Sensor-Abrechnungsgruppen
- `sensor_groups` – Alias für `billing_groups`
- `ha_sources` – flache Sensorliste für Rückwärtskompatibilität eigener Templates
- `total_energy_kwh`, `total_cost_eur`
- `electricity_price_eur_kwh`
- `price_mode`, `price_method_label`, `price_source_label`

Eine vollständige Übersicht steht in [`evcc_to_pdf/PLACEHOLDERS.md`](evcc_to_pdf/PLACEHOLDERS.md).

## Persistenz & Update-Sicherheit

Konfiguration, Gruppen und benutzerdefinierte Templates werden persistent im Home-Assistant-App-Konfigurationsbereich gespeichert. Schreibvorgänge erfolgen atomar mit Backups. Bestehende Datenstrukturen werden versionsübergreifend migriert, ohne benutzerdefinierte Templates pauschal zu überschreiben.

Erzeugte PDFs werden unter `/share/evcc-pdfs` abgelegt.

## Release-Regeln

Die beim Projekt vereinbarten Schritte für Folgeversionen sind zusätzlich in [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) dokumentiert. Dazu gehören insbesondere Persistenz, Migration, Template-Schutz, Versionierung, Changelog und Paketprüfung.

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
