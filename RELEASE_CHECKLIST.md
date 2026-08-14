# EVCC to PDF – Release-Checkliste

Diese Regeln sollen bei allen weiteren Änderungen am Projekt beibehalten werden.

## Daten & Update-Sicherheit

- Bestehende Benutzerdaten niemals stillschweigend auf Werkseinstellungen zurücksetzen.
- Persistente Konfiguration ausschließlich im dafür vorgesehenen Home-Assistant-App-Konfigurationsbereich speichern.
- Einstellungen atomar schreiben und gültige Backups erhalten.
- Neue Datenstrukturen mit einer rückwärtskompatiblen Migration versehen.
- Migrationen müssen Empfänger, Preise, Fahrzeuge, Sensoren, Maildaten und individuelle Einstellungen erhalten.

## Templates

- Mitgeliefertes Standardtemplate verhält sich wie ein normales Benutzer-Template.
- Nur ein nachweislich unverändertes ausgeliefertes Standardtemplate darf automatisch auf eine neue Version migriert werden.
- Individuell bearbeitete Templates niemals automatisch überschreiben.
- Neue Reportdaten als Template-Kontext dokumentieren.

## Abrechnungslogik

- Eine Abrechnung hat einen gemeinsamen Zeitraum und Strompreis.
- Beliebig viele HA-Sensor-Abrechnungsgruppen sind zulässig.
- Beliebig viele geeignete Verbrauchssensoren je Sensorgruppe sind zulässig.
- Sensorgruppen werden im Standard-PDF nur als Gruppenname + Summe ausgegeben.
- EVCC-Fahrzeuge bleiben im Standard-PDF einzeln und transparent mit Ladevorgängen und Fahrzeug-Zwischensummen sichtbar.
- Schutz vor Doppelzählung (`include_in_total`) erhalten.
- HA-Picker auf Energie-/Leistungssensoren begrenzen und EVCC-eigene HA-Sensoren ausblenden.
- Manueller Preis: keine Zeile „Preisermittlung“ im Standard-PDF.
- Preisautomatik: Preisermittlung und Grundlage im Standard-PDF ausgeben.

## Release

- `APP_VERSION` aktualisieren.
- `config.yaml` aktualisieren.
- README, App-README, DOCS und CHANGELOG aktualisieren.
- Versionsbadge aktualisieren.
- Python-Syntax prüfen.
- Jinja-Templates parsen.
- JavaScript-Syntax prüfen.
- YAML prüfen.
- Migration der Vorgängerversion testen.
- Summen-/Preislogik testen.
- Standard-PDF-Kontext prüfen: HA-Sensordetails verborgen, Fahrzeuge detailliert.
- ZIP erstellen und mit `unzip -t` prüfen.
