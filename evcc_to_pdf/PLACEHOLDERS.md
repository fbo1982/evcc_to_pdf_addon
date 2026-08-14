# Platzhalter für HTML-Templates

## Empfänger
- `{{ recipient.name }}`
- `{{ recipient.company }}`
- `{{ recipient.street }}`
- `{{ recipient.zip }}`
- `{{ recipient.city }}`
- `{{ recipient.email }}`

## Absender
- `{{ sender.name }}`
- `{{ sender.street }}`
- `{{ sender.zip }}`
- `{{ sender.city }}`
- `{{ sender.email }}`

## Zeit / Abrechnung
- `{{ invoice_date }}`
- `{{ billing_mode_label }}`
- `{{ period_label }}`

## Tabellen / Fahrzeuge
- `{{ rows_html|safe }}` – klassische chronologische Tabellenzeilen
- `{{ sessions }}` – Liste aller Ladevorgänge
- `{{ vehicle_groups }}` – nach Fahrzeug gruppierte Ladevorgänge inklusive Zwischensummen

## Summen
- `{{ total_energy_kwh }}`
- `{{ total_cost_eur }}`

## Strompreis
- `{{ electricity_price }}` – Preis als Zahl im deutschen Format
- `{{ electricity_price_eur_kwh }}` – Preis inklusive `€/kWh`
- `{{ price_mode }}` – `manual` oder `bmf`
- `{{ price_method_label }}` – nur bei Automatik, z. B. `BMF-Strompreispauschale 2026`
- `{{ price_source_label }}` – nur bei Automatik, z. B. `Destatis, Statistik 61243-0001, 1. Halbjahr 2025`
- `{{ price_source_year }}` – Bezugsjahr der Destatis-Daten

Bei manueller Preiswahl sind `price_method_label` und `price_source_label` leer. Dadurch kann die Zeile „Preisermittlung“ im Template vollständig entfallen.

## Bank
- `{{ bank.recipient }}`
- `{{ bank.iban }}`
- `{{ bank.bic }}`
- `{{ bank.institute }}`

## Mailtext
- `{{ email_body }}`
