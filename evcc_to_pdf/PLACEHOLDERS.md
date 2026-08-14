# Platzhalter für HTML-Templates

## Gruppe
- `{{ group_name }}` – Name der Abrechnungsgruppe
- `{{ group_type }}` – `evcc` oder `homeassistant`

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
- `{{ period_start }}`
- `{{ period_end }}`

## EVCC
- `{{ sessions }}` – Liste aller Ladevorgänge
- `{{ vehicle_groups }}` – nach Fahrzeug gruppierte Ladevorgänge inklusive Zwischensummen

## Home Assistant
- `{{ ha_sources }}` – Liste der ausgewerteten Quellen

Jeder Eintrag in `ha_sources` enthält unter anderem:
- `entity_id`
- `label`
- `energy_kwh`
- `energy_kwh_formatted`
- `cost`
- `cost_formatted`
- `include_in_total`
- `calculation_method`
- `mode`
- `unit`

## Gemeinsame Tabellen
- `{{ rows_html|safe }}` – gerenderte Tabellenzeilen des gewählten Gruppentyps

## Summen
- `{{ total_energy_kwh }}` – formatiert inklusive `kWh`
- `{{ total_cost_eur }}` – formatiert inklusive `€`
- `{{ total_energy }}` – nur Zahlenformat
- `{{ total_cost }}` – nur Zahlenformat

## Strompreis
- `{{ electricity_price }}` – Preis als Zahl im deutschen Format
- `{{ electricity_price_eur_kwh }}` – Preis inklusive `€/kWh`
- `{{ price_mode }}` – `manual` oder `bmf`
- `{{ price_method_label }}` – nur bei Automatik, z. B. `BMF-Strompreispauschale 2026`
- `{{ price_source_label }}` – nur bei Automatik
- `{{ price_source_year }}` – Bezugsjahr der Destatis-Daten

Bei manueller Preiswahl sind `price_method_label` und `price_source_label` leer. Dadurch entfällt die Zeile „Preisermittlung“ vollständig.

## Bank
- `{{ bank.recipient }}`
- `{{ bank.iban }}`
- `{{ bank.bic }}`
- `{{ bank.institute }}`

## Mailtext
- `{{ email_body }}`
