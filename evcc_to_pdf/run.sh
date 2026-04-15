#!/usr/bin/with-contenv bashio

export EVCC_URL="$(bashio::config 'evcc_url')"
export EVCC_PASSWORD="$(bashio::config 'evcc_password')"
export GRID_PRICE="$(bashio::config 'grid_price')"
export SELECTED_VEHICLES="$(bashio::config 'selected_vehicles')"

mkdir -p /share/evcc-pdfs
mkdir -p /app/output

cd /app
python3 generate_pdf_report.py
