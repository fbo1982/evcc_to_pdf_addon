# EVCC to PDF for Home Assistant OS

Dieses Add-on baut auf dem Projekt `MaizeShark/evcc-to-PDF` auf und ergänzt:

- Preisberechnung über festen Netzstrompreis
- Filter auf ausgewählte Fahrzeuge
- gemeinsame Abrechnung
- chronologisch sortierte Liste der einzelnen Ladevorgänge
- Zusammenfassung im PDF

## Ausgabe
Die PDFs werden nach `/share/evcc-pdfs` kopiert.

## Konfiguration
- `evcc_url`: URL zu deiner EVCC-Instanz
- `evcc_password`: optionales EVCC-Passwort
- `grid_price`: fixer Netzstrompreis in Euro pro kWh
- `selected_vehicles`: kommagetrennte Fahrzeugnamen, z. B. `Tesla Model Y,VW ID.4`
- SMTP-Felder: optional für den Mailversand
