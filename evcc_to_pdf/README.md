# EVCC to PDF

Schritt 1: Ingress-Weboberfläche für EVCC-Abrechnung.

## Funktionen in Version 0.3.5
- Eigene Oberfläche in Home Assistant
- EVCC-Verbindung speichern
- Fahrzeuge aus EVCC laden
- Fahrzeuggruppen mit Empfängern verwalten
- Sender- und SMTP-Daten speichern
- Scheduler-Konfiguration speichern
- Testbericht als TXT erzeugen
- Bericht für Vormonat oder manuell gewählten Monat/Jahr erzeugen

## Speicherorte
- Einstellungen: `/addon_config/evcc_to_pdf/settings.json`
- Testberichte: `/share/evcc-pdfs`


## Neu in 0.3.5
- Vollständige Fahrzeugliste aus EVCC `/api/state`
- Zusätzliche Erkennung und getrennte Anzeige von Ladekarten
