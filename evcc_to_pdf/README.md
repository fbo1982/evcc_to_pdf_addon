# EVCC to PDF

Version 0.4.2

## Highlights
- MQTT als primärer Konfigurationsspeicher mit lokalem Mirror
- Update-sichere Einstellungen: lokale Datei in `/addon_config/evcc_to_pdf/settings.json`
- Migration bestehender lokaler Daten nach MQTT, wenn MQTT noch leer ist
- Gruppen mit Standard-/Custom-Absender, HTML und E-Mail-Inhalt
- Abrechnungsmodi: monatlich, quartal, halbjährlich, jährlich
- HTML-Templates anlegen, hochladen, als Default markieren und löschen
- Fahrzeuge aus EVCC `/api/state` plus Sessions ergänzen
