# EVCC to PDF

Schritt 1: Ingress-Weboberfläche für EVCC-Abrechnung.

## Funktionen in Version 0.3.3
- Eigene Oberfläche in Home Assistant
- EVCC-Verbindung speichern
- Fahrzeuge aus EVCC laden
- Fahrzeuggruppen mit Empfängern verwalten
- Sender- und SMTP-Daten speichern
- Scheduler-Konfiguration speichern
- Testbericht als TXT erzeugen
- Bericht für Vormonat oder manuell gewählten Monat/Jahr erzeugen

## Fixes in 0.3.3
- Ingress-Navigation korrigiert
- Static/CSS-Pfade korrigiert

## Noch nicht in Schritt 1
- PDF-Erzeugung
- echter Mailversand
- echter laufender Scheduler

## Speicherorte
- Einstellungen: `/addon_config/evcc_to_pdf/settings.json`
- Testberichte: `/share/evcc-pdfs`
