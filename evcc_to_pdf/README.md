# EVCC to PDF

Version 0.4.0

## Neu in 0.4.0
- MQTT-Konfiguration im statischen Add-on-Konfigurationsbereich
- UI-Daten werden primär in MQTT gespeichert
- Fallback-Dateien unter `/addon_config/evcc_to_pdf`
- Gruppen können Standard-Absender oder gruppenbezogenen Absender nutzen
- Bei gruppenbezogenem Absender: Standard-HTML oder eigenes HTML-Template auswählbar
- Template-Verwaltung in eigener UI-Seite
- Fahrzeuge und Ladekarten werden getrennt dargestellt

## Speicherorte
- UI-Fallback: `/addon_config/evcc_to_pdf/ui_fallback.json`
- Secrets lokal: `/addon_config/evcc_to_pdf/secrets.json`
- Testberichte: `/share/evcc-pdfs`

## MQTT Topics
- `<base>/config/ui`
- `<base>/config/templates`
