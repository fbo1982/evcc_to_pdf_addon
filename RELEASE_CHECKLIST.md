# EVCC to PDF – Release-Checkliste

Diese Regeln sollen bei allen weiteren Änderungen am Projekt beibehalten werden.

## Daten & Update-Sicherheit

- Bestehende Benutzerdaten niemals stillschweigend auf Werkseinstellungen zurücksetzen.
- Persistente Laufzeitdaten ausschließlich unter `/data/evcc_to_pdf` speichern; `/config`/`app_config` nur als Legacy-/Benutzerdatei-Mount verwenden.
- Einstellungen atomar schreiben und gültige Backups unter `/data/evcc_to_pdf/backups` erhalten.
- Neue Datenstrukturen oder Speicherpfade mit einer rückwärtskompatiblen Migration versehen; Defaults erst erzeugen, wenn kein gültiger aktueller oder Legacy-Datensatz/Backup existiert.
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
- produktiven WSGI-Start und genau einen Scheduler-Prozess prüfen.
- Home-Assistant-App-Lifecycle (`startup`, `init`, Mount-Typen) auf aktuelle Supervisor-Warnungen prüfen.
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

## Sensorgruppen-Oberfläche
- Innerhalb einer Abrechnung dürfen beliebig viele Sensorgruppen existieren.
- Im Editor wird **immer nur eine Sensorgruppe gleichzeitig** angezeigt und bearbeitet.
- Die aktive Sensorgruppe wird über ein Dropdown gewählt.
- Sensoren werden ohne zusätzliche Zielgruppen-Auswahl automatisch der aktiven Gruppe zugeordnet.
- Andere Gruppen dürfen beim Bearbeiten der aktiven Gruppe nicht als parallele Karten eingeblendet werden.
- Fahrzeuge bleiben außerhalb der Sensorgruppen und werden im PDF weiterhin einzeln transparent ausgewiesen.

## Strompreispauschale / PDF-Transparenz

- BMF-Strompreispauschale immer als **Jahrespauschale** behandeln: für das gesamte Kalenderjahr gilt das 1. Halbjahr des Vorjahres; kein unterjähriger Wechsel auf neuere Halbjahreswerte.
- Im Standard-PDF den gemeinsamen Strompreis nur einmal zentral im Summenblock ausweisen; Sensor-Abrechnungsgruppen zeigen nur Gruppenname, Verbrauch und Kosten.
- Gesamtverbrauch und Gesamtkosten im Standard-PDF visuell hervorheben, ohne den restlichen Preisnachweis zu überladen.
- Fahrzeuge bleiben weiterhin einzeln mit ihren Ladevorgängen und Fahrzeug-Zwischensummen transparent sichtbar.
