# EVCC to PDF

Version 0.4.5

## Highlights
- MQTT als primärer Konfigurationsspeicher mit lokalem Mirror
- Update-sichere Einstellungen: lokale Datei in `/addon_config/evcc_to_pdf/settings.json`
- Migration bestehender lokaler Daten nach MQTT, wenn MQTT noch leer ist
- Gruppen mit Standard-/Custom-Absender, HTML und E-Mail-Inhalt
- Abrechnungsmodi: monatlich, quartal, halbjährlich, jährlich
- HTML-Templates anlegen, hochladen, als Default markieren und löschen
- Fahrzeuge aus EVCC `/api/state` plus Sessions ergänzen


0.4.5
- robustere Trennung von Fahrzeugen und Ladekarten
- gruppenbezogene Felder klappen nur bei Auswahl von "custom" auf
- HTML-Auswahl zeigt Default-Template und hinterlegte Templates
