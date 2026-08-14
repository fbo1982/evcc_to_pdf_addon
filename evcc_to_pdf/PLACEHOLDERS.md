# Template-Platzhalter – v1.3.03

## Abrechnung / Zeitraum

- `{{ group_name }}` – Name der kompletten Abrechnung
- `{{ group_type }}` – Kompatibilitätswert `mixed`
- `{{ has_evcc }}` – EVCC ist aktiviert
- `{{ has_ha }}` – mindestens eine Sensor-Abrechnungsgruppe mit Sensoren ist konfiguriert
- `{{ period_label }}` – lesbarer Abrechnungszeitraum
- `{{ period_start }}` / `{{ period_end }}`
- `{{ billing_mode_label }}`

## Fahrzeuge / EVCC

- `{{ sessions }}` – alle EVCC-Ladevorgänge im Zeitraum
- `{{ vehicle_groups }}` – Ladevorgänge nach Fahrzeug gruppiert
- `{{ evcc_total_energy }}` – EVCC-Teilsumme kWh
- `{{ evcc_total_cost }}` – EVCC-Teilsumme Kosten

Ein Element aus `vehicle_groups` enthält u. a.:

- `vehicle`
- `sessions`
- `total_energy_kwh`
- `total_cost_eur`

## Sensor-Abrechnungsgruppen

- `{{ billing_groups }}` – ausgewertete, benannte HA-Sensorgruppen
- `{{ sensor_groups }}` – Alias für `billing_groups`
- `{{ ha_total_energy }}` – Summe aller einbezogenen Sensorgruppen
- `{{ ha_total_cost }}` – Kosten aller einbezogenen Sensorgruppen

Ein Element aus `billing_groups` enthält u. a.:

- `id`
- `name`
- `sources` – technische Sensorliste; im Standard-PDF bewusst nicht ausgegeben
- `source_count`
- `included_source_count`
- `total_energy`
- `total_cost`
- `total_energy_kwh`
- `total_cost_eur`

## Sensor-Kompatibilität

- `{{ ha_sources }}` – flache Liste aller ausgewerteten HA-Sensoren für bestehende eigene Templates

Ein Element aus `ha_sources` enthält u. a.:

- `entity_id`
- `label`
- `energy_kwh`
- `energy_kwh_formatted`
- `cost`
- `cost_formatted`
- `include_in_total`
- `calculation_method`
- `billing_group_id`
- `billing_group_name`

## Gemeinsame Summen

- `{{ total_energy_kwh }}` – Gesamtverbrauch Fahrzeuge + Sensorgruppen
- `{{ total_cost_eur }}` – Gesamtkosten
- `{{ total_energy }}` – formatierter Zahlenwert ohne Einheit
- `{{ total_cost }}` – formatierter Zahlenwert ohne Einheit
- `{{ rows_html|safe }}` – kombinierte Tabellenzeilen; HA wird ab v1.3.02 als Gruppensumme ausgegeben

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
