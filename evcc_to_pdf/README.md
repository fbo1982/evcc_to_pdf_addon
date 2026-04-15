# EVCC to PDF

Schritt 1: Ingress-Weboberfläche für EVCC-Abrechnung.

## Funktionen in Version 0.3.2
- Eigene Oberfläche in Home Assistant
- EVCC-Verbindung speichern
- Fahrzeuge aus EVCC laden
- Fahrzeuggruppen mit Empfängern verwalten
- Sender- und SMTP-Daten speichern
- Scheduler-Konfiguration speichern
- Testbericht als TXT erzeugen
- Bericht für Vormonat oder manuell gewählten Monat/Jahr erzeugen

## Fixes in 0.3.2
- Ingress-Navigation korrigiert
- Statische Dateien/CSS über Ingress korrigiert
- Robusteres Handling von gespeicherten Einstellungen

## Noch nicht in Schritt 1
- PDF-Erzeugung
- echter Mailversand
- echter laufender Scheduler

## Speicherorte
- Einstellungen: `/addon_config/evcc_to_pdf/settings.json`
- Testberichte: `/share/evcc-pdfs`
