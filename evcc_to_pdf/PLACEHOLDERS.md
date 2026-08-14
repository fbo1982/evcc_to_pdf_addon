# Template-Platzhalter – v1.3.01

## Gruppe und Zeitraum

- `{{ group_name }}` – Name der Abrechnungsgruppe
- `{{ group_type }}` – ab v1.3.01 normalerweise `mixed`
- `{{ has_evcc }}` – EVCC ist für die Gruppe aktiviert
- `{{ has_ha }}` – mindestens eine HA-Quelle ist konfiguriert
- `{{ period_label }}` – lesbarer Abrechnungszeitraum
- `{{ period_start }}` / `{{ period_end }}`
- `{{ billing_mode_label }}`

## Fahrzeuge / EVCC

- `{{ sessions }}` – alle EVCC-Ladevorgänge im Zeitraum
- `{{ vehicle_groups }}` – Ladevorgänge nach Fahrzeug gruppiert
- `{{ evcc_total_energy }}` – EVCC-Teilsumme kWh, formatiert
- `{{ evcc_total_cost }}` – EVCC-Teilsumme Kosten, formatiert

Ein Element aus `vehicle_groups` enthält u. a.:

- `vehicle`
- `sessions`
- `total_energy_kwh`
- `total_cost_eur`

## Home Assistant

- `{{ ha_sources }}` – ausgewertete HA-Verbrauchssensoren
- `{{ ha_total_energy }}` – einbezogene HA-Teilsumme kWh, formatiert
- `{{ ha_total_cost }}` – einbezogene HA-Teilsumme Kosten, formatiert

Ein Element aus `ha_sources` enthält u. a.:

- `entity_id`
- `label`
- `energy_kwh`
- `energy_kwh_formatted`
- `cost`
- `cost_formatted`
- `include_in_total`
- `calculation_method`

## Gemeinsame Summen

- `{{ total_energy_kwh }}` – Gesamtverbrauch EVCC + einbezogene HA-Quellen
- `{{ total_cost_eur }}` – Gesamtkosten
- `{{ total_energy }}` – formatierter Zahlenwert ohne Einheit
- `{{ total_cost }}` – formatierter Zahlenwert ohne Einheit
- `{{ rows_html|safe }}` – kombinierte Tabellenzeilen für EVCC und HA

## Strompreis

- `{{ electricity_price }}` – formatierter Zahlenwert
- `{{ electricity_price_eur_kwh }}` – inklusive Einheit
- `{{ price_mode }}` – `manual` oder `bmf`
- `{{ price_method_label }}` – bei manuell leer
- `{{ price_source_label }}` – bei manuell leer
- `{{ price_source_year }}`

## Absender / Empfänger / Bank

- `{{ sender }}` / `{{ recipient }}` / `{{ bank }}`
- `{{ sender_name }}`, `{{ sender_street }}`, `{{ sender_zip }}`, `{{ sender_city }}`, `{{ sender_email }}`
- `{{ recipient_name }}`, `{{ recipient_company }}`, `{{ recipient_street }}`, `{{ recipient_zip }}`, `{{ recipient_city }}`, `{{ recipient_email }}`
- `{{ bank_recipient }}`, `{{ bank_iban }}`, `{{ bank_bic }}`, `{{ bank_institute }}`
