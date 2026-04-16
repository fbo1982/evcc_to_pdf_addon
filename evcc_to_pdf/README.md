# EVCC to PDF v0.5.3

Komplettes Add-on-Repo für Home Assistant mit:
- Ingress-Weboberfläche
- EVCC Fahrzeugsynchronisation
- Gruppenverwaltung
- HTML-Templates
- PDF-Erzeugung
- manueller Testbericht / Versand
- Scheduler
- MQTT-Persistenz + lokaler Mirror
- optionaler Absender-Kopie pro Gruppe

## Speicherorte
- Lokaler Mirror: `/addon_config/evcc_to_pdf/settings.json`
- Templates Uploads / Berichte: `/share/evcc-pdfs`

## MQTT
Die statischen MQTT-Zugangsdaten liegen im Add-on-Konfigurationsbereich.
Die App speichert Inhalte unter:
- `<mqtt_base_topic>/config/global`
- `<mqtt_base_topic>/config/templates`
- `<mqtt_base_topic>/config/groups`

## Hinweise
- Secrets wie EVCC-/SMTP-Passwort werden in den UI-Daten mitgespeichert, wenn du sie dort eingibst.
- Das Default-Template kann nicht gelöscht werden.
