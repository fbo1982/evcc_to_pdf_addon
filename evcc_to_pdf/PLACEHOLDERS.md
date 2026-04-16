# Platzhalter für HTML-Templates

## Kopfbereich
- `{{ recipient.name }}`
- `{{ recipient.company }}`
- `{{ recipient.street }}`
- `{{ recipient.zip }}`
- `{{ recipient.city }}`
- `{{ recipient.email }}`

- `{{ sender.name }}`
- `{{ sender.street }}`
- `{{ sender.zip }}`
- `{{ sender.city }}`
- `{{ sender.email }}`

- `{{ invoice_date }}`
- `{{ billing_mode_label }}`
- `{{ period_label }}`

## Tabelle
- `{{ rows_html|safe }}`

Jede Zeile enthält:
- Datum
- Startzeit
- Endzeit
- Fahrzeug
- geladene kWh
- Kosten

## Summen
- `{{ total_energy_kwh }}`
- `{{ total_cost_eur }}`

## Bankverbindung
- `{{ bank.recipient }}`
- `{{ bank.iban }}`
- `{{ bank.bic }}`
- `{{ bank.institute }}`

## Abschluss
- `{{ email_body }}`
