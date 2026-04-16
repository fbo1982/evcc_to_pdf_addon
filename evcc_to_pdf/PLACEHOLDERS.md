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

## Tabelle
- `{{ rows_html|safe }}`

## Summen
- `{{ total_energy_kwh }}`
- `{{ total_cost_eur }}`

## Bank
- `{{ bank.recipient }}`
- `{{ bank.iban }}`
- `{{ bank.bic }}`
- `{{ bank.institute }}`

## Mailtext
- `{{ email_body }}`
