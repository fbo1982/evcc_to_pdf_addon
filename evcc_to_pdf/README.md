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


## Neu in 0.4.1
- Abrechnungsmodus Standard/Gruppe: monatlich, quartal, halbjährlich, jährlich
- Standard-E-Mail-Inhalt global, optional gruppenbezogen
- Standard-HTML-Template global, optional gruppenbezogen
- Templates können gelöscht und als Standard markiert werden
