#!/usr/bin/with-contenv bashio
set -e

export EVCC_URL="$(bashio::config 'evcc_url')"
export EVCC_PASSWORD="$(bashio::config 'evcc_password')"
export GRID_PRICE="$(bashio::config 'grid_price')"
export SELECTED_VEHICLES="$(bashio::config 'selected_vehicles')"
export SMTP_SERVER="$(bashio::config 'smtp_server')"
export SMTP_PORT="$(bashio::config 'smtp_port')"
export SENDER_EMAIL="$(bashio::config 'sender_email')"
export SENDER_PASSWORD="$(bashio::config 'sender_password')"
export RECIPIENT_EMAIL="$(bashio::config 'recipient_email')"
export SENDER_NAME="$(bashio::config 'sender_name')"
export SENDER_STREET="$(bashio::config 'sender_street')"
export SENDER_CITY="$(bashio::config 'sender_city')"
export LOCALE="$(bashio::config 'locale')"

mkdir -p /share/evcc-pdfs
mkdir -p /app/output

cd /app
python3 generate_pdf_report.py

cp -f /app/output/*.pdf /share/evcc-pdfs/ 2>/dev/null || true
echo "Fertig. PDFs liegen unter /share/evcc-pdfs"
