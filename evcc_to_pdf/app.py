import atexit
import base64
import csv
import hashlib
import json
import logging
import math
import os
import re
import shutil
import smtplib
import ssl
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from email.message import EmailMessage
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import paho.mqtt.client as mqtt
import requests
import websocket
from flask import Flask, flash, redirect, render_template, request
from jinja2 import Template
from werkzeug.middleware.proxy_fix import ProxyFix
from weasyprint import HTML

APP_PORT = 8099
SETTINGS_DIR = Path(os.environ.get("EVCC_TO_PDF_SETTINGS_DIR", "/data/evcc_to_pdf"))
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
BACKUP_DIR = SETTINGS_DIR / "backups"
BMF_PRICE_CACHE_FILE = SETTINGS_DIR / "bmf_price_cache.json"
HA_ENTITY_CACHE_FILE = SETTINGS_DIR / "ha_entity_cache.json"
HA_API_BASE = os.environ.get("HA_API_BASE", "http://supervisor/core/api").rstrip("/")
HA_WS_URL = os.environ.get("HA_WS_URL", "ws://supervisor/core/websocket")
LEGACY_SETTINGS_FILES = [
    # v1.2.x / v1.3.0-v1.3.02: public app config was mounted to /config.
    Path("/config/settings.json"),
    # Transitional/experimental paths used by older project builds.
    Path("/app_config/settings.json"),
    Path("/addon_config/evcc_to_pdf/settings.json"),
    Path("/addon_config/settings.json"),
    Path("/data/settings.json"),
]
LEGACY_STORAGE_DIRS = [
    Path("/config"),
    Path("/app_config"),
    Path("/addon_config/evcc_to_pdf"),
    Path("/addon_config"),
    Path("/data"),
]
REPORT_DIR = Path("/share/evcc-pdfs")
OPTIONS_FILE = Path("/data/options.json")
DEFAULT_TEMPLATE_KEY = "default"
DEFAULT_TEMPLATE_LABEL = "Standard HTML"
_log_level_name = str(os.environ.get("LOG_LEVEL", "INFO")).upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOGGER = logging.getLogger("evcc_to_pdf")
DESTatis_TABLE_CODE = "61243-0001"
DESTatis_CSV_URL = "https://www-genesis.destatis.de/genesis-old/downloads/00/tables/61243-0001_00.csv"
LEGACY_DEFAULT_SOURCE_HASHES = {
    "5492eab4e4ea677da86d5c283c30f9ae1b4e70f3af677161232106487a6f9f01",
    "e845ab04ca5c28a3cc6b9fd568a1b0900bef17922e97605c81f8427390b64f56",
    "392553cc7cb6beb2b9f469c94c5d68e67ed2dfa68e06cd4e145333d9adf7e449",  # v1.3.0 Standardtemplate
    "0efd4abbbeff1094e32b5410784a0399c1aa6a9de048a09c5b147ee05a20f27b",  # v1.3.01 Standardtemplate
    "429f335f3ab897ee92a116f58ec76500750c82ecc115419b0ab6e7fa6de9c6f0",  # v1.3.04 Standardtemplate
}
BMF_RATE_CATALOG = {
    2026: {
        "billing_year": 2026,
        "source_year": 2025,
        "raw_eur_kwh": 0.3436,
        "rate_eur_kwh": 0.34,
        "source": "BMF/Destatis",
    },
}
APP_VERSION = "1.3.05"

DEFAULT_TEMPLATE_SOURCE_HTML = r"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <style>
    @page {
      size: A4;
      margin: 14mm 10mm 16mm 10mm;
      @bottom-center {
        content: "- Seite " counter(page) " / " counter(pages) " -";
        font-size: 9pt;
        color: #445;
      }
    }
    body { font-family: DejaVu Sans, Arial, sans-serif; font-size: 10pt; color: #111827; }
    .header { display: table; width: 100%; margin-bottom: 28px; }
    .col { display: table-cell; width: 50%; vertical-align: top; }
    .right { text-align: right; }
    .date-line { margin-top: 24px; margin-bottom: 30px; }
    .period { margin: 26px 0 8px; font-weight: bold; font-size: 11pt; }
    .group-title { margin: 0 0 20px; color: #164e8a; font-size: 13pt; }
    .section { margin: 0 0 22px; page-break-inside: avoid; }
    .section-title { margin: 12px 0 7px; font-size: 10.5pt; }
    table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 9.2pt; table-layout: fixed; }
    th, td { border: 1px solid #64748b; padding: 5px 6px; vertical-align: top; word-wrap: break-word; }
    th { background: #eef4fa; text-align: left; }
    .vehicle-total { margin: 7px 0 0; font-size: 9.4pt; }
    .summary { margin-top: 14px; padding: 12px; border: 1px solid #cbd5e1; background: #f8fbff; }
    .summary p { margin: 4px 0; }
    .summary .total-line { margin: 5px 0; padding: 6px 9px; font-size: 11.2pt; font-weight: 700; background: #eef6ff; border-left: 3px solid #2563eb; }
    .price-info { margin-top: 12px; padding-top: 8px; border-top: 1px solid #cbd5e1; }
    .bank { margin-top: 20px; }
    .closing { margin-top: 24px; }
    .signature { margin-top: 10px; }
    .notice { margin-top: 20px; font-size: 9pt; color: #475569; }
  </style>
</head>
<body>
  <div class="header">
    <div class="col">
      <strong>{{ recipient.company or recipient.name }}</strong><br>
      {{ recipient.name }}<br>
      {{ recipient.street }}<br>
      {{ recipient.zip }} {{ recipient.city }}
    </div>
    <div class="col right">
      <strong>{{ sender.name }}</strong><br>
      {{ sender.street }}<br>
      {{ sender.zip }} {{ sender.city }}
      <div class="date-line">{{ invoice_date }}</div>
    </div>
  </div>

  <div class="period">{{ billing_mode_label }} – {{ period_label }}</div>
  <div class="group-title">{{ group_name }}</div>

  {% if vehicle_groups %}
    {% for vehicle_group in vehicle_groups %}
    <div class="section">
      <div class="section-title"><strong>Fahrzeug: {{ vehicle_group.vehicle }}</strong></div>
      <table>
        <thead>
          <tr>
            <th>Datum</th>
            <th>Startzeit</th>
            <th>Endzeit</th>
            <th>Geladene kWh</th>
            <th>Kosten (€)</th>
          </tr>
        </thead>
        <tbody>
        {% for charge in vehicle_group.sessions %}
          <tr>
            <td>{{ charge.date }}</td>
            <td>{{ charge.start_time }}</td>
            <td>{{ charge.end_time }}</td>
            <td>{{ charge.energy_kwh_formatted }}</td>
            <td>{{ charge.cost_eur }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
      <p class="vehicle-total"><strong>Zwischensumme {{ vehicle_group.vehicle }}:</strong> {{ vehicle_group.total_energy_kwh }} · {{ vehicle_group.total_cost_eur }}</p>
    </div>
    {% endfor %}
  {% endif %}

  {% if billing_groups %}
  <div class="section">
    <div class="section-title"><strong>Weitere Abrechnungsgruppen</strong></div>
    <table>
      <thead>
        <tr>
          <th style="width:50%">Abrechnungsgruppe</th>
          <th style="width:25%">Verbrauch</th>
          <th style="width:25%">Kosten</th>
        </tr>
      </thead>
      <tbody>
      {% for item in billing_groups %}
        <tr>
          <td><strong>{{ item.name }}</strong></td>
          <td>{{ item.total_energy_kwh }}</td>
          <td>{{ item.total_cost_eur }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  <div class="summary">
    <p class="total-line"><strong>Gesamtverbrauch:</strong> {{ total_energy_kwh }}</p>
    <p class="total-line"><strong>Gesamtkosten:</strong> {{ total_cost_eur }}</p>
    <div class="price-info">
      <p><strong>Zugrunde gelegter Strompreis:</strong> {{ electricity_price_eur_kwh }}</p>
      {% if price_method_label %}<p><strong>Preisermittlung:</strong> {{ price_method_label }}</p>{% endif %}
      {% if price_source_label %}<p><strong>Grundlage:</strong> {{ price_source_label }}</p>{% endif %}
    </div>
  </div>

  <div class="bank">
    <p>Ich bitte um Begleichung der Kosten für den entsprechenden Zeitraum auf folgendes Konto:</p>
    <p>
      <strong>Empfänger:</strong> {{ bank.recipient }}<br>
      <strong>IBAN:</strong> {{ bank.iban }}<br>
      <strong>BIC:</strong> {{ bank.bic }}<br>
      {{ bank.institute }}
    </p>
  </div>

  <div class="closing">
    <p>Mit freundlichen Grüßen</p>
    <p class="signature">{{ sender.name }}</p>
    <p class="notice">Dieses Dokument wurde elektronisch erstellt und bedarf keiner Unterschrift.</p>
  </div>
</body>
</html>"""

DEFAULT_TEMPLATE_HTML = ""


EDITOR_DATA_PREFIX = "<!-- EVCC_EDITOR_DATA_BASE64:"


def build_default_editor_schema(raw_html=""):
    raw_html = str(raw_html or "").strip()
    blocks = [
        {"id": str(uuid.uuid4()), "type": "heading", "title": "Überschrift", "level": 1, "text": "Energieabrechnung"},
        {"id": str(uuid.uuid4()), "type": "text", "title": "Zeitraum", "text": "Zeitraum: {{ period_label }}"},
        {"id": str(uuid.uuid4()), "type": "summary", "title": "Kennzahlen", "energy_label": "Gesamtverbrauch", "cost_label": "Gesamtkosten"},
        {"id": str(uuid.uuid4()), "type": "table", "title": "Abrechnungspositionen", "heading": "Abrechnungspositionen", "show_cost": True},
        {"id": str(uuid.uuid4()), "type": "text", "title": "Hinweis", "text": "Dieses Dokument wurde elektronisch erstellt und bedarf keiner Unterschrift."},
    ]
    if raw_html:
        blocks = [{"id": str(uuid.uuid4()), "type": "html", "title": "Bestehendes HTML", "html": raw_html}]
    return {"version": 1, "page": {"title": "Energieabrechnung", "accent": "#22c55e"}, "blocks": blocks}


def extract_editor_schema(content):
    content = str(content or "")
    match = re.search(r"<!-- EVCC_EDITOR_DATA_BASE64:([A-Za-z0-9+/=]+) -->", content)
    if not match:
        return None
    try:
        raw = base64.b64decode(match.group(1)).decode("utf-8")
        schema = json.loads(raw)
        if isinstance(schema, dict):
            return schema
    except Exception:
        return None
    return None


def _editor_text_html(text):
    lines = [line.strip() for line in str(text or "").splitlines()]
    lines = [line for line in lines if line]
    return "<br>".join(lines)


def render_editor_template_html(schema):
    schema = schema if isinstance(schema, dict) else build_default_editor_schema()
    page = schema.get("page", {}) if isinstance(schema.get("page"), dict) else {}
    accent = str(page.get("accent") or "#22c55e")
    body_parts = []
    for block in schema.get("blocks", []):
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        title = str(block.get("title") or "")
        if block_type == "heading":
            level = int(block.get("level") or 1)
            level = min(3, max(1, level))
            body_parts.append(f'<section class="block"><h{level}>{block.get("text") or ""}</h{level}></section>')
        elif block_type == "text":
            body_parts.append(f'<section class="block"><p>{_editor_text_html(block.get("text"))}</p></section>')
        elif block_type == "summary":
            energy_label = block.get("energy_label") or "Gesamtverbrauch"
            cost_label = block.get("cost_label") or "Gesamtkosten"
            body_parts.append(f'''<section class="block">
<div class="summary-grid">
  <div class="metric-card">
    <div class="metric-label">{energy_label}</div>
    <div class="metric-value">{{{{ total_energy_kwh }}}}</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">{cost_label}</div>
    <div class="metric-value">{{{{ total_cost_eur }}}}</div>
  </div>
</div>
</section>''')
        elif block_type == "table":
            heading = block.get("heading") or title or "Abrechnungspositionen"
            cost_header = '<th>Kosten (€)</th>' if block.get("show_cost", True) else ''
            body_parts.append(f'''<section class="block">
<h3>{heading}</h3>
<table>
  <thead>
    <tr>
      <th>Typ</th>
      <th>Verbraucher</th>
      <th>Quelle / Zeitraum</th>
      <th>Verbrauch (kWh)</th>
      <th>Kosten (€)</th>
      <th>Summierung</th>
    </tr>
  </thead>
  <tbody>
    {{{{ rows_html|safe }}}}
  </tbody>
</table>
</section>''')
        elif block_type == "separator":
            body_parts.append('<section class="block"><hr></section>')
        elif block_type == "html":
            body_parts.append(f'<section class="block raw-html">{block.get("html") or ""}</section>')
    if not body_parts:
        body_parts.append('<section class="block"><p>Leeres Template</p></section>')

    html = f'''<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <style>
    @page {{
      size: A4;
      margin: 14mm 10mm 16mm 10mm;
      @bottom-center {{
        content: "- Seite " counter(page) " / " counter(pages) " -";
        font-size: 9pt;
        color: #445;
      }}
    }}
    body {{ font-family: DejaVu Sans, Arial, sans-serif; font-size: 10pt; color: #111827; }}
    h1, h2, h3 {{ margin: 0 0 10px; color: #0f172a; }}
    p {{ margin: 0; line-height: 1.5; }}
    .block {{ margin-bottom: 18px; }}
    .summary-grid {{ display: table; width: 100%; border-spacing: 8px 0; margin: 10px -8px 0; }}
    .metric-card {{ display: table-cell; width: 50%; padding: 14px; background: #eff6ff; border: 1px solid #dbeafe; border-radius: 12px; }}
    .metric-label {{ color: #475569; font-size: 9pt; margin-bottom: 6px; }}
    .metric-value {{ font-size: 18pt; font-weight: bold; color: {accent}; }}
    hr {{ border: 0; border-top: 1px solid #cbd5e1; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; table-layout: fixed; }}
    th, td {{ border: 1px solid #94a3b8; padding: 6px; vertical-align: top; word-break: break-word; }}
    th {{ background: #e2e8f0; text-align: left; }}
    .raw-html > *:first-child {{ margin-top: 0; }}
  </style>
</head>
<body>
{"".join(body_parts)}
</body>
</html>'''
    encoded = base64.b64encode(json.dumps(schema, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return f"{EDITOR_DATA_PREFIX}{encoded} -->\n" + html


def create_seed_template_entry():
    schema = build_default_editor_schema(DEFAULT_TEMPLATE_SOURCE_HTML)
    return {
        "key": DEFAULT_TEMPLATE_KEY,
        "label": DEFAULT_TEMPLATE_LABEL,
        "content": render_editor_template_html(schema),
    }


DEFAULT_TEMPLATE_HTML = create_seed_template_entry()["content"]

DEFAULT_SETTINGS = {
    "meta": {"version": APP_VERSION},
    "evcc": {"url": "", "password": ""},
    "sender": {"name": "", "street": "", "zip": "", "city": "", "email": ""},
    "smtp": {"host": "", "port": 587, "user": "", "password": "", "tls": True},
    "bank": {"recipient": "", "iban": "", "bic": "", "institute": ""},
    "scheduler": {"enabled": False, "day_of_month": 1, "time": "07:00", "last_run": "", "period_history": {}},
    "reporting": {
        "grid_price": 0.0,
        "default_billing_mode": "monthly",
        "default_email_body": "Bitte überweisen Sie den offenen Betrag auf das unten angegebene Konto.",
        "default_email_subject": "Energieabrechnung {{period_label}}",
    },
    "cached_assets": [],
    "groups": [],
    "templates": {
        DEFAULT_TEMPLATE_KEY: {
            "key": DEFAULT_TEMPLATE_KEY,
            "label": DEFAULT_TEMPLATE_LABEL,
            "content": DEFAULT_TEMPLATE_HTML,
        }
    },
    "default_template_key": DEFAULT_TEMPLATE_KEY,
}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "evcc-to-pdf-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

def ensure_dirs():
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

def _read_json_file(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:
        return None

def _atomic_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(value, indent=2, ensure_ascii=False)
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)

def load_addon_options():
    if not OPTIONS_FILE.exists():
        return {"mqtt_host": "core-mosquitto", "mqtt_port": 1883, "mqtt_user": "", "mqtt_password": "", "mqtt_base_topic": "/evcc2pdf"}
    try:
        return json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"mqtt_host": "core-mosquitto", "mqtt_port": 1883, "mqtt_user": "", "mqtt_password": "", "mqtt_base_topic": "/evcc2pdf"}

def deep_merge(base, override):
    if isinstance(base, dict) and isinstance(override, dict):
        merged = deepcopy(base)
        for key, value in override.items():
            merged[key] = deep_merge(merged[key], value) if key in merged else deepcopy(value)
        return merged
    return deepcopy(override)

def create_backup():
    ensure_dirs()
    if not SETTINGS_FILE.exists():
        return
    # Nur gültige Konfigurationen sichern. Eine beschädigte Datei darf kein gutes Backup verdrängen.
    if _read_json_file(SETTINGS_FILE) is None:
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_file = BACKUP_DIR / f"settings_{ts}.json"
    shutil.copy2(SETTINGS_FILE, backup_file)
    backups = sorted(BACKUP_DIR.glob("settings_*.json"), reverse=True)
    for old in backups[20:]:
        try:
            old.unlink()
        except Exception:
            pass

def _restore_latest_backup():
    ensure_dirs()
    for backup in sorted(BACKUP_DIR.glob("settings_*.json"), reverse=True):
        data = _read_json_file(backup)
        if data is not None:
            try:
                _atomic_write_json(SETTINGS_FILE, data)
                LOGGER.warning("Einstellungen aus Backup %s wiederhergestellt.", backup.name)
            except Exception:
                pass
            return data
    return None

def _copy_legacy_sidecars(source_dir):
    """Copy recoverable caches/backups from an older storage directory into /data.

    Existing persistent files always win. The old storage is never modified so an update
    can be rolled back without destroying the previous configuration.
    """
    source_dir = Path(source_dir)
    try:
        for filename, target in (
            ("bmf_price_cache.json", BMF_PRICE_CACHE_FILE),
            ("ha_entity_cache.json", HA_ENTITY_CACHE_FILE),
        ):
            source = source_dir / filename
            if source.exists() and not target.exists() and _read_json_file(source) is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                LOGGER.info("Legacy-Datei %s nach %s übernommen.", source, target)

        source_backup_dir = source_dir / "backups"
        if source_backup_dir.is_dir():
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            for source in sorted(source_backup_dir.glob("settings_*.json")):
                if _read_json_file(source) is None:
                    continue
                target = BACKUP_DIR / source.name
                if not target.exists():
                    shutil.copy2(source, target)
    except Exception as err:
        LOGGER.warning("Legacy-Nebenfiles aus %s konnten nicht vollständig migriert werden: %s", source_dir, err)


def _read_latest_valid_backup(backup_dir):
    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        return None, None
    for backup in sorted(backup_dir.glob("settings_*.json"), reverse=True):
        data = _read_json_file(backup)
        if data is not None:
            return data, backup
    return None, None


def _migrate_legacy_settings():
    """Recover settings from all previously used storage locations before defaults exist."""
    if SETTINGS_FILE.exists():
        return None

    ensure_dirs()
    checked = set()
    candidates = list(LEGACY_SETTINGS_FILES)
    for legacy_dir in LEGACY_STORAGE_DIRS:
        candidate = legacy_dir / "settings.json"
        if candidate not in candidates:
            candidates.append(candidate)

    for legacy in candidates:
        try:
            legacy = Path(legacy)
            key = str(legacy)
            if key in checked or legacy == SETTINGS_FILE:
                continue
            checked.add(key)
            if not legacy.exists():
                continue
            data = _read_json_file(legacy)
            source = legacy
            if data is None:
                data, backup = _read_latest_valid_backup(legacy.parent / "backups")
                if data is None:
                    LOGGER.warning("Legacy-Einstellungen in %s sind ungültig und es wurde kein gültiges Backup gefunden.", legacy)
                    continue
                source = backup
                LOGGER.warning("Ungültige Legacy-settings.json; verwende Backup %s.", backup)

            _atomic_write_json(SETTINGS_FILE, data)
            _copy_legacy_sidecars(legacy.parent)
            LOGGER.warning("Legacy-Einstellungen von %s nach %s migriert.", source, SETTINGS_FILE)
            return data
        except Exception as err:
            LOGGER.warning("Legacy-Migration von %s fehlgeschlagen: %s", legacy, err)

    # Auch wenn settings.json am alten Ort bereits fehlt, können Cache/Backups noch nützlich sein.
    for legacy_dir in LEGACY_STORAGE_DIRS:
        if Path(legacy_dir) != SETTINGS_DIR:
            _copy_legacy_sidecars(legacy_dir)
    return None

def load_local_settings():
    ensure_dirs()
    migrated = _migrate_legacy_settings()
    if migrated is not None:
        return migrated
    if SETTINGS_FILE.exists():
        data = _read_json_file(SETTINGS_FILE)
        if data is not None:
            return data
        LOGGER.error("settings.json ist beschädigt; versuche Wiederherstellung aus Backup.")
        restored = _restore_latest_backup()
        if restored is not None:
            return restored
        try:
            corrupt_copy = SETTINGS_DIR / f"settings_corrupt_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
            os.replace(SETTINGS_FILE, corrupt_copy)
            LOGGER.error("Beschädigte settings.json wurde zur Analyse nach %s verschoben.", corrupt_copy.name)
        except Exception:
            pass
        # Solange ein Legacy-Mount vorhanden ist, ist er die letzte Rettungsquelle vor
        # MQTT oder Werkseinstellungen. Das verhindert einen Reset bei gleichzeitig
        # beschädigter neuer settings.json und fehlendem neuen Backup.
        migrated = _migrate_legacy_settings()
        if migrated is not None:
            return migrated
    return None

def save_local_settings(settings, with_backup=True):
    ensure_dirs()
    if with_backup and SETTINGS_FILE.exists():
        create_backup()
    _atomic_write_json(SETTINGS_FILE, settings)

def mqtt_topics(base_topic):
    bt = base_topic.rstrip("/")
    return {"global": f"{bt}/config/global", "groups": f"{bt}/config/groups", "templates": f"{bt}/config/templates"}

def mqtt_load_payload(topic):
    options = load_addon_options()
    data = {"payload": None}
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if options.get("mqtt_user"):
            client.username_pw_set(options.get("mqtt_user", ""), options.get("mqtt_password", ""))
        client.connect(options.get("mqtt_host", "core-mosquitto"), int(options.get("mqtt_port", 1883)), 15)
        def on_message(client, userdata, msg):
            userdata["payload"] = msg.payload.decode("utf-8") if msg.payload else ""
        client.user_data_set(data)
        client.on_message = on_message
        client.subscribe(topic)
        client.loop_start()
        time.sleep(0.6)
        client.loop_stop()
        client.disconnect()
    except Exception:
        return None
    return data["payload"]

def mqtt_publish(topic, payload):
    options = load_addon_options()
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if options.get("mqtt_user"):
            client.username_pw_set(options.get("mqtt_user", ""), options.get("mqtt_password", ""))
        client.connect(options.get("mqtt_host", "core-mosquitto"), int(options.get("mqtt_port", 1883)), 15)
        info = client.publish(topic, payload=payload, qos=1, retain=True)
        client.loop_start()
        try:
            info.wait_for_publish(timeout=5)
        finally:
            client.loop_stop()
            client.disconnect()
        return True
    except Exception:
        return False

def _template_source_fingerprint(raw_html):
    normalized = "\n".join(line.rstrip() for line in str(raw_html or "").strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def _is_unmodified_legacy_default_template(entry):
    if not isinstance(entry, dict):
        return False
    schema = extract_editor_schema(entry.get("content", ""))
    if not isinstance(schema, dict):
        return False
    blocks = schema.get("blocks", [])
    if not isinstance(blocks, list) or len(blocks) != 1:
        return False
    block = blocks[0]
    if not isinstance(block, dict) or block.get("type") != "html":
        return False
    return _template_source_fingerprint(block.get("html", "")) in LEGACY_DEFAULT_SOURCE_HASHES

def normalize_template_dict(templates):
    out = {}
    if not isinstance(templates, dict):
        templates = {}
    for key, value in templates.items():
        if not isinstance(value, dict):
            continue
        tpl_key = str(value.get("key") or key).strip()
        if not tpl_key:
            continue
        out[tpl_key] = {
            "key": tpl_key,
            "label": str(value.get("label") or tpl_key).strip(),
            "content": str(value.get("content") or "").strip(),
        }
    if not out:
        seed = create_seed_template_entry()
        out[seed["key"]] = seed
    elif DEFAULT_TEMPLATE_KEY in out and _is_unmodified_legacy_default_template(out[DEFAULT_TEMPLATE_KEY]):
        # Nur bekannte, unveränderte ausgelieferte Standardtemplates migrieren.
        # Sobald ein Nutzer das Template editiert hat, bleibt es unangetastet.
        out[DEFAULT_TEMPLATE_KEY] = create_seed_template_entry()
    return out

def normalize_ha_source(source):
    base = {
        "entity_id": "",
        "label": "",
        "mode": "auto",
        "include_in_total": True,
        "nominal_power_w": 0.0,
        "unit": "",
        "device_class": "",
        "state_class": "",
        "domain": "",
    }
    merged = deep_merge(base, source or {})
    merged["entity_id"] = str(merged.get("entity_id") or "").strip()
    merged["label"] = str(merged.get("label") or merged["entity_id"]).strip()
    merged["mode"] = str(merged.get("mode") or "auto").strip().lower()
    if merged["mode"] not in {"auto", "energy", "power", "runtime"}:
        merged["mode"] = "auto"
    merged["include_in_total"] = bool(merged.get("include_in_total", True))
    merged["nominal_power_w"] = max(0.0, parse_float(merged.get("nominal_power_w"), 0.0))
    for key in ("unit", "device_class", "state_class", "domain"):
        merged[key] = str(merged.get(key) or "").strip()
    return merged


def normalize_billing_group(item):
    base = {
        "id": str(uuid.uuid4()),
        "name": "",
        "ha_sources": [],
    }
    merged = deep_merge(base, item or {})
    merged["id"] = str(merged.get("id") or uuid.uuid4())
    merged["name"] = str(merged.get("name") or "Abrechnungsgruppe").strip() or "Abrechnungsgruppe"
    if not isinstance(merged.get("ha_sources"), list):
        merged["ha_sources"] = []
    merged["ha_sources"] = [
        normalize_ha_source(src)
        for src in merged["ha_sources"]
        if isinstance(src, dict) and str(src.get("entity_id") or "").strip()
    ]
    return merged


def normalize_group(group):
    base = {
        "id": str(uuid.uuid4()),
        "active": True,
        "name": "",
        "group_type": "mixed",  # Legacy-/Template-Kompatibilität.
        "include_evcc": True,
        "group_icon": "auto",
        "recipient_name": "",
        "recipient_company": "",
        "recipient_email": "",
        "recipient_street": "",
        "recipient_zip": "",
        "recipient_city": "",
        "vehicles": [],
        "billing_groups": [],
        "ha_sources": [],  # Legacy-/Template-Alias; wird aus billing_groups abgeleitet.
        "grid_price_override": "",
        "grid_price_mode": "manual",
        "sender_mode": "default",
        "custom_sender": {"name": "", "email": "", "street": "", "zip": "", "city": ""},
        "html_mode": "default",
        "selected_template_key": DEFAULT_TEMPLATE_KEY,
        "email_body_mode": "default",
        "custom_email_body": "",
        "email_subject_mode": "default",
        "custom_email_subject": "",
        "billing_mode_mode": "default",
        "custom_billing_mode": "monthly",
        "send_day": 1,
        "sender_copy_enabled": False,
        "bank_mode": "default",
        "custom_bank": {"recipient": "", "iban": "", "bic": "", "institute": ""},
    }
    source_group = group or {}
    legacy_group_type = str(source_group.get("group_type") or "").strip().lower()
    merged = deep_merge(base, source_group)

    if "include_evcc" not in source_group:
        merged["include_evcc"] = legacy_group_type != "homeassistant"
    else:
        merged["include_evcc"] = bool(source_group.get("include_evcc"))
    merged["group_type"] = "mixed"

    if not isinstance(merged.get("vehicles"), list):
        merged["vehicles"] = []
    merged["vehicles"] = [str(v) for v in merged["vehicles"] if str(v).strip()]

    # v1.3.02: HA-Sensoren liegen in beliebig vielen benannten Abrechnungsgruppen.
    # v1.3.01 hatte noch eine flache ha_sources-Liste. Diese wird einmalig verlustfrei
    # in eine Abrechnungsgruppe migriert. Der Alias ha_sources bleibt für eigene Templates erhalten.
    source_billing_groups = source_group.get("billing_groups")
    billing_groups = []
    if isinstance(source_billing_groups, list):
        billing_groups = [normalize_billing_group(item) for item in source_billing_groups if isinstance(item, dict)]
    else:
        legacy_sources = source_group.get("ha_sources", [])
        if isinstance(legacy_sources, list) and legacy_sources:
            billing_groups = [normalize_billing_group({
                "name": str(source_group.get("name") or "Home Assistant").strip() or "Home Assistant",
                "ha_sources": legacy_sources,
            })]
    merged["billing_groups"] = billing_groups
    merged["ha_sources"] = [deepcopy(src) for item in billing_groups for src in item.get("ha_sources", [])]

    if str(merged.get("grid_price_mode") or "manual").lower() not in {"manual", "bmf"}:
        merged["grid_price_mode"] = "manual"
    return merged

def normalize_settings(raw):
    settings = deep_merge(DEFAULT_SETTINGS, raw or {})
    settings["meta"] = settings.get("meta", {})
    settings["meta"]["version"] = APP_VERSION
    settings["templates"] = normalize_template_dict(settings.get("templates", {}))
    if settings.get("default_template_key") not in settings["templates"]:
        settings["default_template_key"] = next(iter(settings["templates"]), DEFAULT_TEMPLATE_KEY)
    assets = settings.get("cached_assets", [])
    if not isinstance(assets, list):
        assets = []
    settings["cached_assets"] = [str(v) for v in assets if str(v).strip()]
    settings["groups"] = [normalize_group(g) for g in settings.get("groups", [])]
    return settings

def settings_from_mqtt():
    options = load_addon_options()
    topics = mqtt_topics(options.get("mqtt_base_topic", "/evcc2pdf"))
    mqtt_global = mqtt_load_payload(topics["global"])
    mqtt_groups = mqtt_load_payload(topics["groups"])
    mqtt_templates = mqtt_load_payload(topics["templates"])
    if not (mqtt_global or mqtt_groups or mqtt_templates):
        return None
    combined = deepcopy(DEFAULT_SETTINGS)
    try:
        if mqtt_global:
            combined = deep_merge(combined, json.loads(mqtt_global))
    except Exception:
        pass
    try:
        if mqtt_groups:
            combined["groups"] = json.loads(mqtt_groups)
    except Exception:
        pass
    try:
        if mqtt_templates:
            combined["templates"] = json.loads(mqtt_templates)
    except Exception:
        pass
    return normalize_settings(combined)

def sync_settings_to_mqtt(settings):
    options = load_addon_options()
    topics = mqtt_topics(options.get("mqtt_base_topic", "/evcc2pdf"))
    payload = deepcopy(settings)
    groups_payload = payload.pop("groups", [])
    templates_payload = payload.pop("templates", {})
    mqtt_publish(topics["global"], json.dumps(payload, ensure_ascii=False))
    mqtt_publish(topics["groups"], json.dumps(groups_payload, ensure_ascii=False))
    mqtt_publish(topics["templates"], json.dumps(templates_payload, ensure_ascii=False))

def load_settings():
    ensure_dirs()
    local_raw = load_local_settings()
    if local_raw is not None:
        return normalize_settings(local_raw)
    mqtt_settings = settings_from_mqtt()
    if mqtt_settings is not None:
        save_local_settings(mqtt_settings, with_backup=False)
        return mqtt_settings
    settings = normalize_settings(DEFAULT_SETTINGS)
    # Auf einem frischen System lokal anlegen, aber niemals ungeprüfte Defaults in retained MQTT
    # publizieren. So kann ein kurzzeitig nicht erreichbarer Broker keine vorhandene Konfiguration
    # mit Werkseinstellungen überschreiben.
    if not SETTINGS_FILE.exists():
        save_local_settings(settings, with_backup=False)
    return settings

def save_settings(settings):
    normalized = normalize_settings(settings)
    save_local_settings(normalized, with_backup=True)
    try:
        sync_settings_to_mqtt(normalized)
    except Exception:
        pass

def parse_bool(value): return str(value).lower() in {"1","true","on","yes"}
def parse_float(value, fallback=0.0):
    try: return float(str(value).strip().replace(",", "."))
    except Exception: return fallback
def parse_int(value, fallback=0):
    try: return int(str(value).strip())
    except Exception: return fallback

def extract_name(value):
    if isinstance(value, dict):
        for key in ("title","name","id","uid"):
            if value.get(key): return str(value.get(key))
        return json.dumps(value, ensure_ascii=False)
    return str(value)

def evcc_session(settings):
    session = requests.Session()
    base_url = str(settings["evcc"].get("url","")).rstrip("/")
    password = str(settings["evcc"].get("password",""))
    if not base_url: raise ValueError("EVCC-URL ist leer.")
    if password:
        response = session.post(f"{base_url}/api/auth/login", json={"password": password}, timeout=15)
        response.raise_for_status()
    return session

def fetch_sessions(settings):
    base_url = str(settings["evcc"].get("url","")).rstrip("/")
    session = evcc_session(settings)
    response = session.get(f"{base_url}/api/sessions", timeout=30)
    response.raise_for_status()
    data = response.json()
    result = data["result"] if isinstance(data, dict) and "result" in data else data
    if not isinstance(result, list): raise ValueError("Unerwartete Antwort von EVCC bei /api/sessions")
    return result

def fetch_available_assets(settings):
    assets = set()
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    session = evcc_session(settings)

    def add_vehicle_entries(vehicle_container):
        if isinstance(vehicle_container, dict):
            for key, entry in vehicle_container.items():
                # In vielen EVCC-Versionen ist der Schlüssel nur die interne db-ID (z.B. db:13),
                # der lesbare Fahrzeugname steckt im title-Feld.
                if isinstance(entry, dict):
                    name = (
                        entry.get("title")
                        or entry.get("name")
                        or entry.get("vehicle")
                        or entry.get("id")
                        or ""
                    )
                    name = str(name).strip()
                    if name:
                        assets.add(name)

                    # Fallback: nur dann Key übernehmen, wenn er nicht wie eine interne EVCC-ID aussieht.
                    key_name = str(key).strip()
                    if key_name and not key_name.startswith("db:"):
                        assets.add(key_name)
                else:
                    key_name = str(key).strip()
                    if key_name and not key_name.startswith("db:"):
                        assets.add(key_name)

                    value_name = str(entry).strip()
                    if value_name:
                        assets.add(value_name)

        elif isinstance(vehicle_container, list):
            for entry in vehicle_container:
                if isinstance(entry, dict):
                    name = (
                        entry.get("title")
                        or entry.get("name")
                        or entry.get("vehicle")
                        or entry.get("id")
                        or ""
                    )
                else:
                    name = str(entry)

                name = str(name).strip()
                if name:
                    assets.add(name)

    # 1) Alle in EVCC eingetragenen Fahrzeuge aus /api/state
    try:
        state_response = session.get(f"{base_url}/api/state", timeout=15)
        state_response.raise_for_status()
        state_data = state_response.json()

        # EVCC kann vehicles je nach Version entweder direkt auf Top-Level
        # oder unter result.vehicles liefern.
        add_vehicle_entries(state_data.get("vehicles", []))
        result = state_data.get("result", {})
        if isinstance(result, dict):
            add_vehicle_entries(result.get("vehicles", []))
    except Exception:
        pass

    # 2) Zusätzlich alles aus Sessions ergänzen
    try:
        sessions = fetch_sessions(settings)
        for s in sessions:
            value = s.get("vehicle")
            if value:
                if isinstance(value, dict):
                    name = (
                        value.get("title")
                        or value.get("name")
                        or value.get("vehicle")
                        or value.get("id")
                        or ""
                    )
                else:
                    name = str(value)

                name = str(name).strip()
                if name:
                    assets.add(name)
    except Exception:
        pass

    return sorted(assets, key=lambda x: x.lower())


def _ha_token():
    token = str(os.environ.get("SUPERVISOR_TOKEN", "")).strip()
    if not token:
        raise ValueError("Home-Assistant-Zugriff ist nicht verfügbar (SUPERVISOR_TOKEN fehlt).")
    return token


def _ha_headers():
    return {"Authorization": f"Bearer {_ha_token()}", "Content-Type": "application/json"}


def ha_rest_get(path, params=None, timeout=30):
    response = requests.get(f"{HA_API_BASE}/{str(path).lstrip('/')}", headers=_ha_headers(), params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_ha_timezone():
    try:
        cfg = ha_rest_get("config", timeout=10)
        name = str(cfg.get("time_zone") or "UTC")
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _as_ha_utc_iso(value):
    tz = get_ha_timezone()
    if value.tzinfo is None:
        value = value.replace(tzinfo=tz)
    return value.astimezone(ZoneInfo("UTC")).isoformat()


def _ha_source_kind(entity):
    attrs = entity.get("attributes", {}) if isinstance(entity, dict) else {}
    entity_id = str(entity.get("entity_id") or "") if isinstance(entity, dict) else ""
    domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
    device_class = str(attrs.get("device_class") or "").lower()
    unit = str(attrs.get("unit_of_measurement") or "").strip()
    unit_l = unit.lower().replace(" ", "")
    if device_class == "energy" or unit_l in {"wh", "kwh", "mwh"}:
        return "energy"
    if device_class == "power" or unit_l in {"w", "kw", "mw"}:
        return "power"
    if domain in {"climate", "switch", "binary_sensor", "input_boolean"}:
        return "runtime"
    return "unsupported"


def _ha_entity_registry_platforms():
    """Liefert entity_id -> Integrationsplattform, soweit Home Assistant sie bereitstellt."""
    try:
        rows = ha_ws_call({"type": "config/entity_registry/list"}, timeout=20)
    except Exception as err:
        LOGGER.info("HA Entity Registry konnte für den Sensorfilter nicht gelesen werden: %s", err)
        return {}
    platforms = {}
    for row in rows if isinstance(rows, list) else []:
        entity_id = str(row.get("entity_id") or "").strip()
        if entity_id:
            platforms[entity_id] = str(row.get("platform") or "").strip().lower()
    return platforms


def _is_evcc_ha_entity(entity_id, label, platform=""):
    # Primär über die Entity Registry filtern. Der Namens-Fallback greift auch bei älteren HA-Versionen.
    if str(platform or "").lower() == "evcc":
        return True
    entity_l = str(entity_id or "").lower()
    label_l = str(label or "").lower()
    return "evcc" in entity_l or label_l.startswith("evcc ") or label_l.startswith("evcc-")


def fetch_ha_entities():
    states = ha_rest_get("states", timeout=30)
    platforms = _ha_entity_registry_platforms()
    candidates = []
    for item in states if isinstance(states, list) else []:
        entity_id = str(item.get("entity_id") or "").strip()
        if not entity_id:
            continue
        attrs = item.get("attributes", {}) if isinstance(item.get("attributes"), dict) else {}
        label = str(attrs.get("friendly_name") or entity_id)
        kind = _ha_source_kind(item)
        domain = entity_id.split(".", 1)[0] if "." in entity_id else ""

        # Im HA-Auswahldialog werden ausschließlich echte Verbrauchssensoren angeboten:
        # Energiezähler (Wh/kWh/MWh) oder Leistungssensoren (W/kW/MW).
        # Climate-/Switch-/Runtime-Entitäten und alle EVCC-eigenen HA-Sensoren bleiben draußen.
        if domain != "sensor" or kind not in {"energy", "power"}:
            continue
        platform = platforms.get(entity_id, "")
        if _is_evcc_ha_entity(entity_id, label, platform):
            continue

        candidates.append({
            "entity_id": entity_id,
            "label": label,
            "kind": kind,
            "unit": str(attrs.get("unit_of_measurement") or ""),
            "device_class": str(attrs.get("device_class") or ""),
            "state_class": str(attrs.get("state_class") or ""),
            "domain": domain,
            "platform": platform,
            "state": str(item.get("state") or ""),
        })
    candidates.sort(key=lambda x: (x["kind"], x["label"].lower(), x["entity_id"].lower()))
    _atomic_write_json(HA_ENTITY_CACHE_FILE, {"updated_at": datetime.now().isoformat(), "entities": candidates})
    return candidates


def load_ha_entity_cache():
    data = _read_json_file(HA_ENTITY_CACHE_FILE)
    if not isinstance(data, dict):
        return {"updated_at": "", "entities": []}
    entities = data.get("entities") if isinstance(data.get("entities"), list) else []
    # Auch einen noch aus v1.3.0 vorhandenen Cache sofort bereinigen.
    filtered = []
    for item in entities:
        if not isinstance(item, dict):
            continue
        entity_id = str(item.get("entity_id") or "")
        label = str(item.get("label") or entity_id)
        kind = str(item.get("kind") or "")
        domain = str(item.get("domain") or (entity_id.split(".", 1)[0] if "." in entity_id else ""))
        platform = str(item.get("platform") or "")
        if domain == "sensor" and kind in {"energy", "power"} and not _is_evcc_ha_entity(entity_id, label, platform):
            filtered.append(item)
    return {"updated_at": str(data.get("updated_at") or ""), "entities": filtered}


def ha_ws_call(command, timeout=35):
    token = _ha_token()
    ws = websocket.create_connection(HA_WS_URL, timeout=timeout)
    try:
        hello = json.loads(ws.recv())
        if hello.get("type") == "auth_required":
            ws.send(json.dumps({"type": "auth", "access_token": token}))
            auth = json.loads(ws.recv())
            if auth.get("type") != "auth_ok":
                raise ValueError(f"Home-Assistant-WebSocket-Authentifizierung fehlgeschlagen: {auth.get('message', auth.get('type'))}")
        command = dict(command)
        command.setdefault("id", 1)
        ws.send(json.dumps(command))
        while True:
            message = json.loads(ws.recv())
            if message.get("type") == "result" and message.get("id") == command["id"]:
                if not message.get("success"):
                    raise ValueError(str(message.get("error") or "Home-Assistant-WebSocket-Aufruf fehlgeschlagen"))
                return message.get("result")
    finally:
        try:
            ws.close()
        except Exception:
            pass


def fetch_ha_statistics(entity_id, start, end, types, period="hour"):
    command = {
        "id": 1,
        "type": "recorder/statistics_during_period",
        "start_time": _as_ha_utc_iso(start),
        "end_time": _as_ha_utc_iso(end),
        "statistic_ids": [entity_id],
        "period": period,
        "types": list(types),
    }
    result = ha_ws_call(command)
    if not isinstance(result, dict):
        return []
    rows = result.get(entity_id, [])
    return rows if isinstance(rows, list) else []


def fetch_ha_history(entity_id, start, end, include_attributes=False):
    params = {
        "filter_entity_id": entity_id,
        "end_time": _as_ha_utc_iso(end),
    }
    if not include_attributes:
        params["minimal_response"] = "true"
        params["no_attributes"] = "true"
    result = ha_rest_get(f"history/period/{_as_ha_utc_iso(start)}", params=params, timeout=45)
    if not isinstance(result, list) or not result:
        return []
    return result[0] if isinstance(result[0], list) else []


def _unit_energy_factor_to_kwh(unit):
    unit = str(unit or "").strip().lower()
    return {"wh": 0.001, "kwh": 1.0, "mwh": 1000.0}.get(unit, 1.0)


def _unit_power_factor_to_kw(unit):
    unit = str(unit or "").strip().lower()
    return {"w": 0.001, "kw": 1.0, "mw": 1000.0}.get(unit, 0.001)


def _parse_iso_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _energy_from_statistics(entity_id, start, end, unit):
    # Eine Stunde vor Periodenstart liefert den Basis-Summenwert exakt am Monats-/Quartalsbeginn.
    rows = fetch_ha_statistics(entity_id, start - timedelta(hours=1), end, ["sum", "state"], period="hour")
    usable = [r for r in rows if isinstance(r, dict) and (r.get("sum") is not None or r.get("state") is not None)]
    if not usable:
        return None
    start_ms = int(start.replace(tzinfo=get_ha_timezone()).astimezone(ZoneInfo("UTC")).timestamp() * 1000) if start.tzinfo is None else int(start.timestamp()*1000)
    end_ms = int(end.replace(tzinfo=get_ha_timezone()).astimezone(ZoneInfo("UTC")).timestamp() * 1000) if end.tzinfo is None else int(end.timestamp()*1000)
    def val(row):
        return row.get("sum") if row.get("sum") is not None else row.get("state")
    base_candidates = [r for r in usable if int(r.get("end") or r.get("start") or 0) <= start_ms]
    end_candidates = [r for r in usable if int(r.get("end") or r.get("start") or 0) <= end_ms]
    if not end_candidates:
        return None
    base = base_candidates[-1] if base_candidates else usable[0]
    finish = end_candidates[-1]
    try:
        delta = float(val(finish)) - float(val(base))
    except Exception:
        return None
    if delta < -1e-6:
        return None
    return max(0.0, delta) * _unit_energy_factor_to_kwh(unit)


def _power_from_statistics(entity_id, start, end, unit):
    rows = fetch_ha_statistics(entity_id, start, end, ["mean"], period="hour")
    if not rows:
        return None
    tz = get_ha_timezone()
    start_ms = int(start.replace(tzinfo=tz).astimezone(ZoneInfo("UTC")).timestamp() * 1000) if start.tzinfo is None else int(start.timestamp()*1000)
    end_ms = int(end.replace(tzinfo=tz).astimezone(ZoneInfo("UTC")).timestamp() * 1000) if end.tzinfo is None else int(end.timestamp()*1000)
    total_kwh = 0.0
    used = False
    factor = _unit_power_factor_to_kw(unit)
    for row in rows:
        if not isinstance(row, dict) or row.get("mean") is None:
            continue
        rs = int(row.get("start") or 0)
        re_ = int(row.get("end") or 0)
        overlap_ms = max(0, min(re_, end_ms) - max(rs, start_ms))
        if overlap_ms <= 0:
            continue
        total_kwh += float(row["mean"]) * factor * (overlap_ms / 3600000.0)
        used = True
    return total_kwh if used else None


def _energy_from_history(entity_id, start, end, unit):
    rows = fetch_ha_history(entity_id, start, end, include_attributes=False)
    values = []
    for row in rows:
        try:
            values.append(float(str(row.get("state")).replace(",", ".")))
        except Exception:
            continue
    if len(values) < 2:
        return None
    total = 0.0
    previous = values[0]
    for current in values[1:]:
        diff = current - previous
        if diff >= 0:
            total += diff
        else:
            # total_increasing-Sensoren können nach Reset wieder bei 0 beginnen.
            total += max(0.0, current)
        previous = current
    return total * _unit_energy_factor_to_kwh(unit)


def _power_from_history(entity_id, start, end, unit):
    rows = fetch_ha_history(entity_id, start, end, include_attributes=False)
    if not rows:
        return None
    tz = get_ha_timezone()
    start_a = start.replace(tzinfo=tz) if start.tzinfo is None else start
    end_a = end.replace(tzinfo=tz) if end.tzinfo is None else end
    points = []
    for row in rows:
        dt = _parse_iso_dt(row.get("last_changed") or row.get("last_updated"))
        try:
            value = float(str(row.get("state")).replace(",", "."))
        except Exception:
            continue
        if dt is not None:
            points.append((dt, value))
    if not points:
        return None
    points.sort(key=lambda x: x[0])
    factor = _unit_power_factor_to_kw(unit)
    total = 0.0
    for idx, (dt, value) in enumerate(points):
        nxt = points[idx + 1][0] if idx + 1 < len(points) else end_a
        seg_start = max(dt, start_a)
        seg_end = min(nxt, end_a)
        if seg_end > seg_start:
            total += value * factor * ((seg_end - seg_start).total_seconds() / 3600.0)
    return max(0.0, total)


def _runtime_energy_from_history(entity_id, start, end, nominal_power_w):
    if nominal_power_w <= 0:
        raise ValueError("Für Laufzeit-Entitäten muss eine Nennleistung in Watt angegeben werden.")
    rows = fetch_ha_history(entity_id, start, end, include_attributes=True)
    if not rows:
        return None
    tz = get_ha_timezone()
    start_a = start.replace(tzinfo=tz) if start.tzinfo is None else start
    end_a = end.replace(tzinfo=tz) if end.tzinfo is None else end
    points = []
    for row in rows:
        dt = _parse_iso_dt(row.get("last_changed") or row.get("last_updated"))
        if dt is None:
            continue
        attrs = row.get("attributes", {}) if isinstance(row.get("attributes"), dict) else {}
        hvac_action = str(attrs.get("hvac_action") or "").lower()
        state = str(row.get("state") or "").lower()
        if hvac_action:
            active = hvac_action not in {"off", "idle", "unavailable", "unknown"}
        else:
            active = state not in {"off", "idle", "unavailable", "unknown", "none", "0"}
        points.append((dt, active))
    if not points:
        return None
    points.sort(key=lambda x: x[0])
    active_seconds = 0.0
    for idx, (dt, active) in enumerate(points):
        nxt = points[idx + 1][0] if idx + 1 < len(points) else end_a
        seg_start = max(dt, start_a)
        seg_end = min(nxt, end_a)
        if active and seg_end > seg_start:
            active_seconds += (seg_end - seg_start).total_seconds()
    return (active_seconds / 3600.0) * (float(nominal_power_w) / 1000.0)


def calculate_ha_source_consumption(source, start, end):
    entity_id = str(source.get("entity_id") or "").strip()
    if not entity_id:
        raise ValueError("Leere Home-Assistant-Entität in der Gruppe.")
    try:
        current = ha_rest_get(f"states/{entity_id}", timeout=15)
    except Exception as err:
        raise ValueError(f"{entity_id}: Entität konnte nicht gelesen werden ({err})") from err
    attrs = current.get("attributes", {}) if isinstance(current, dict) else {}
    unit = str(attrs.get("unit_of_measurement") or source.get("unit") or "")
    detected = _ha_source_kind(current)
    mode = str(source.get("mode") or "auto").lower()
    if mode == "auto":
        mode = detected
    if mode == "energy":
        energy = None
        try:
            energy = _energy_from_statistics(entity_id, start, end, unit)
        except Exception as err:
            LOGGER.info("Long-Term-Statistik für %s nicht verfügbar: %s", entity_id, err)
        if energy is None:
            energy = _energy_from_history(entity_id, start, end, unit)
        if energy is None:
            raise ValueError(f"{entity_id}: Energieverbrauch konnte weder aus Langzeitstatistik noch Historie ermittelt werden.")
        return energy, "Energiezähler (Home Assistant)", unit
    if mode == "power":
        energy = None
        try:
            energy = _power_from_statistics(entity_id, start, end, unit)
        except Exception as err:
            LOGGER.info("Leistungsstatistik für %s nicht verfügbar: %s", entity_id, err)
        if energy is None:
            energy = _power_from_history(entity_id, start, end, unit)
        if energy is None:
            raise ValueError(f"{entity_id}: Leistung konnte nicht über den Zeitraum integriert werden.")
        return energy, "Leistung über Zeitraum integriert", unit
    if mode == "runtime":
        energy = _runtime_energy_from_history(entity_id, start, end, parse_float(source.get("nominal_power_w"), 0.0))
        if energy is None:
            raise ValueError(f"{entity_id}: Laufzeit konnte nicht ermittelt werden.")
        return energy, "Laufzeit × Nennleistung (Schätzung)", "W"
    raise ValueError(f"{entity_id}: Entität ist kein Energie-/Leistungssensor. Für climate/switch bitte Modus Laufzeit und Nennleistung verwenden.")


def get_ingress_path():
    return request.headers.get("X-Ingress-Path", "").rstrip("/")

@app.context_processor
def inject_common():
    settings = load_settings()
    return {"settings": settings, "ingress_path": get_ingress_path(), "app_version": APP_VERSION}

def find_group(settings, group_id):
    for group in settings["groups"]:
        if group.get("id") == group_id:
            return group
    return None

def schedule_months_for_mode(mode):
    if mode == "monthly":
        return set(range(1, 13))
    if mode == "quarterly":
        return {1, 4, 7, 10}
    if mode == "halfyearly":
        return {1, 7}
    if mode == "yearly":
        return {1}
    return set(range(1, 13))

def build_period_key(start, end, mode):
    return f"{mode}:{start.strftime('%Y%m%d')}:{end.strftime('%Y%m%d')}"

def scheduler_due_for_group(now, settings, group):
    scheduler_cfg = settings.get("scheduler", {})
    send_day = int(group.get("send_day") or scheduler_cfg.get("day_of_month", 1) or 1)
    send_day = max(1, min(28, send_day))
    mode = effective_billing_mode(settings, group)
    if now.month not in schedule_months_for_mode(mode):
        return False, None
    if now.day != send_day:
        return False, None
    period_start, period_end = period_for_mode(now, mode)
    period_key = build_period_key(period_start, period_end, mode)
    history = scheduler_cfg.get("period_history", {})
    if not isinstance(history, dict):
        history = {}
    if history.get(group.get("id")) == period_key:
        return False, period_key
    return True, period_key

def period_for_mode(reference_date, mode):
    ref = reference_date.replace(day=1)
    if mode == "monthly":
        end = ref - timedelta(days=1)
        start = end.replace(day=1)
        return start, end
    if mode == "quarterly":
        current_quarter = (ref.month - 1)//3 + 1
        end_quarter = current_quarter - 1
        year = ref.year
        if end_quarter == 0:
            end_quarter = 4
            year -= 1
        start_month = (end_quarter - 1) * 3 + 1
        start = datetime(year, start_month, 1)
        end = datetime(year, 12, 31) if start_month == 10 else datetime(year, start_month + 3, 1) - timedelta(days=1)
        return start, end
    if mode == "halfyearly":
        if ref.month <= 6:
            year = ref.year - 1
            return datetime(year, 7, 1), datetime(year, 12, 31)
        return datetime(ref.year, 1, 1), datetime(ref.year, 6, 30)
    if mode == "yearly":
        year = ref.year - 1
        return datetime(year, 1, 1), datetime(year, 12, 31)
    return period_for_mode(reference_date, "monthly")

def billing_mode_label(mode):
    return {"monthly":"Monatliche Abrechnung","quarterly":"Quartalsabrechnung","halfyearly":"Halbjährliche Abrechnung","yearly":"Jährliche Abrechnung"}.get(mode,"Abrechnung")

def period_label(start, end):
    return f"{start.strftime('%d.%m.%Y')} bis {end.strftime('%d.%m.%Y')}"

def effective_sender(settings, group): return group.get("custom_sender", {}) if group.get("sender_mode") == "custom" else settings.get("sender", {})
def effective_bank(settings, group): return group.get("custom_bank", {}) if group.get("bank_mode") == "custom" else settings.get("bank", {})
def effective_email_body(settings, group): return group.get("custom_email_body", "") if group.get("email_body_mode") == "custom" else settings.get("reporting", {}).get("default_email_body", "")

def build_period_context(summary):
    return {
        "period_label": period_label(summary["period_start"], summary["period_end"]),
        "period_start": summary["period_start"].strftime("%d.%m.%Y"),
        "period_end": summary["period_end"].strftime("%d.%m.%Y"),
        "period_month": summary["period_start"].strftime("%m.%Y"),
        "period_year": summary["period_start"].strftime("%Y"),
        "billing_mode_label": billing_mode_label(summary["billing_mode"]),
    }

def render_shortcuts(text, summary=None):
    text = str(text or "")
    if not summary:
        return text
    ctx = build_period_context(summary)
    for key, value in ctx.items():
        text = text.replace(f"{{{{{key}}}}}", str(value))
    return text

def effective_email_subject(settings, group, summary=None):
    base_subject = group.get("custom_email_subject", "").strip() if group.get("email_subject_mode") == "custom" else settings.get("reporting", {}).get("default_email_subject", "").strip()
    if not base_subject:
        base_subject = "Energieabrechnung {{period_label}}"
    return render_shortcuts(base_subject, summary)

def effective_billing_mode(settings, group): return group.get("custom_billing_mode", "monthly") if group.get("billing_mode_mode") == "custom" else settings.get("reporting", {}).get("default_billing_mode", "monthly")
def effective_template_key(settings, group):
    if group.get("html_mode") == "custom":
        key = group.get("selected_template_key") or settings.get("default_template_key", DEFAULT_TEMPLATE_KEY)
        if key in settings["templates"]: return key
    return settings.get("default_template_key", DEFAULT_TEMPLATE_KEY)

def grid_price_for_group(settings, group, billing_year=None):
    if billing_year is not None:
        return price_info_for_group(settings, group, billing_year)["price_eur_kwh"]
    override = str(group.get("grid_price_override", "")).strip()
    return parse_float(override, parse_float(settings["reporting"].get("grid_price"), 0.0)) if override else parse_float(settings["reporting"].get("grid_price"), 0.0)

def format_de_number(value, decimals=2):
    try:
        return f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"{0:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip().lower()


def _parse_destatis_number(value):
    raw = str(value or "").strip().replace(" ", "")
    if not raw or raw in {"-", ".", "...", "/"}:
        return None
    raw = raw.replace(".", "").replace(",", ".") if "," in raw else raw
    try:
        number = float(raw)
    except Exception:
        return None
    # GENESIS liefert die Tabelle üblicherweise in EUR/kWh (z. B. 0,3436).
    # Falls eine Quelle Cent/kWh liefert, normalisieren wir auf EUR/kWh.
    if number > 2:
        number /= 100.0
    if 0 < number < 2:
        return number
    return None


def _extract_destatis_rate_from_csv(csv_text, source_year):
    rows = list(csv.reader(StringIO(csv_text), delimiter=";"))
    target_class = "5 000 bis unter 15 000"
    target_price = "durchschnittspreise inkl"

    # Flat-File-CSV: Spalten über ihre Überschriften erkennen.
    for header_index, row in enumerate(rows[:40]):
        normalized = [_normalize_text(c) for c in row]
        joined = " | ".join(normalized)
        if "halbjahr" not in joined or "jahresverbrauch" not in joined:
            continue
        def find_col(*needles):
            for idx, cell in enumerate(normalized):
                if all(n in cell for n in needles):
                    return idx
            return None
        year_col = find_col("jahr")
        half_col = find_col("halbjahr")
        class_col = find_col("jahresverbrauch")
        price_col = find_col("preisart")
        value_col = find_col("wert")
        if value_col is None:
            value_col = len(row) - 1
        if class_col is None or half_col is None:
            continue
        for data_row in rows[header_index + 1:]:
            cells = [_normalize_text(c) for c in data_row]
            if len(cells) <= max(class_col, half_col, value_col):
                continue
            full = " | ".join(cells)
            if str(source_year) not in full:
                continue
            if "1. halbjahr" not in cells[half_col] and "1 . halbjahr" not in cells[half_col]:
                continue
            if target_class not in cells[class_col]:
                continue
            if price_col is not None and price_col < len(cells) and target_price not in cells[price_col]:
                continue
            value = _parse_destatis_number(data_row[value_col])
            if value is not None:
                return value

    # Klassische GENESIS-Pivottabelle: Zielzeile finden und Spaltenkontext aus den
    # darüberliegenden Kopfzeilen zusammensetzen.
    for row_index, row in enumerate(rows):
        normalized = [_normalize_text(c) for c in row]
        if not any(target_class in cell for cell in normalized):
            continue
        preceding_rows = rows[max(0, row_index - 16):row_index]
        global_context = " | ".join(_normalize_text(c) for r in preceding_rows for c in r)
        if target_price not in global_context:
            # Manche Exporte wiederholen die Preisart rechts neben der Klasse.
            if target_price not in " | ".join(normalized):
                continue
        for col_index, cell in enumerate(row):
            value = _parse_destatis_number(cell)
            if value is None:
                continue
            column_context_parts = []
            for prev in preceding_rows:
                if col_index < len(prev):
                    column_context_parts.append(_normalize_text(prev[col_index]))
                if prev:
                    column_context_parts.append(_normalize_text(prev[0]))
            column_context = " | ".join(column_context_parts)
            if str(source_year) in column_context and ("1. halbjahr" in column_context or "1 . halbjahr" in column_context):
                return value
    return None


def load_bmf_rate_cache():
    data = _read_json_file(BMF_PRICE_CACHE_FILE)
    return data if isinstance(data, dict) else {}


def save_bmf_rate_cache(cache):
    try:
        _atomic_write_json(BMF_PRICE_CACHE_FILE, cache)
    except Exception as err:
        LOGGER.warning("BMF-Preis-Cache konnte nicht gespeichert werden: %s", err)


def _rate_info_from_raw(billing_year, raw_eur_kwh, source="Destatis"):
    rate = math.floor(float(raw_eur_kwh) * 100 + 1e-9) / 100.0
    return {
        "billing_year": int(billing_year),
        "source_year": int(billing_year) - 1,
        "raw_eur_kwh": float(raw_eur_kwh),
        "rate_eur_kwh": rate,
        "source": source,
    }


def fetch_bmf_rate_from_destatis(billing_year):
    billing_year = int(billing_year)
    source_year = billing_year - 1
    response = requests.get(DESTatis_CSV_URL, timeout=20, headers={"User-Agent": f"EVCC-to-PDF/{APP_VERSION}"})
    response.raise_for_status()
    content = response.content
    decoded = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            decoded = content.decode(encoding)
            break
        except Exception:
            continue
    if decoded is None:
        raise ValueError("Destatis-CSV konnte nicht dekodiert werden.")
    raw = _extract_destatis_rate_from_csv(decoded, source_year)
    if raw is None:
        raise ValueError(f"Destatis-Wert für 1. Halbjahr {source_year} konnte nicht ermittelt werden.")
    return _rate_info_from_raw(billing_year, raw, source="Destatis")


def resolve_bmf_rate(billing_year):
    billing_year = int(billing_year)
    if billing_year < 2026 or billing_year > 2030:
        raise ValueError("Die BMF-Strompreispauschale ist nach aktueller Regelung für 2026 bis 2030 vorgesehen.")

    catalog = BMF_RATE_CATALOG.get(billing_year)
    if catalog:
        return deepcopy(catalog)

    cache = load_bmf_rate_cache()
    cached = cache.get(str(billing_year))
    if isinstance(cached, dict) and parse_float(cached.get("rate_eur_kwh"), 0) > 0:
        return cached

    try:
        info = fetch_bmf_rate_from_destatis(billing_year)
        cache[str(billing_year)] = info
        save_bmf_rate_cache(cache)
        return info
    except Exception as err:
        raise ValueError(
            f"BMF-Strompreispauschale für {billing_year} konnte noch nicht automatisch ermittelt werden: {err}"
        ) from err


def price_info_for_group(settings, group, billing_year):
    mode = str(group.get("grid_price_mode", "manual") or "manual").strip().lower()
    if mode == "bmf":
        info = resolve_bmf_rate(billing_year)
        price = float(info["rate_eur_kwh"])
        source_year = int(info["source_year"])
        return {
            "mode": "bmf",
            "price_eur_kwh": price,
            "price_eur_kwh_formatted": format_de_number(price, 2),
            "price_eur_kwh_label": f"{format_de_number(price, 2)} €/kWh",
            "price_method_label": f"BMF-Strompreispauschale {billing_year} (Jahrespauschale)",
            "price_source_label": (
                f"Destatis, Statistik {DESTatis_TABLE_CODE}, 1. Halbjahr {source_year} "
                f"(BMF-Basis für das Kalenderjahr {billing_year})"
            ),
            "price_source_year": source_year,
            "price_raw_eur_kwh": float(info.get("raw_eur_kwh", price)),
        }

    override = str(group.get("grid_price_override", "")).strip()
    default_price = parse_float(settings.get("reporting", {}).get("grid_price"), 0.0)
    price = parse_float(override, default_price) if override else default_price
    return {
        "mode": "manual",
        "price_eur_kwh": price,
        "price_eur_kwh_formatted": format_de_number(price, 4 if round(price, 2) != price else 2),
        "price_eur_kwh_label": f"{format_de_number(price, 4 if round(price, 2) != price else 2)} €/kWh",
        # Gewünscht: Bei manueller Preiswahl keine Zeile „Preisermittlung“ ausgeben.
        "price_method_label": "",
        "price_source_label": "",
        "price_source_year": None,
        "price_raw_eur_kwh": price,
    }


def _resolve_report_period(settings, group, mode=None, manual_year=None, manual_month=None):
    if manual_year and manual_month:
        start = datetime(int(manual_year), int(manual_month), 1)
        next_period_start = datetime(int(manual_year) + 1, 1, 1) if int(manual_month) == 12 else datetime(int(manual_year), int(manual_month) + 1, 1)
        end = next_period_start - timedelta(days=1)
        return start, end, next_period_start, "monthly"
    mode = mode or effective_billing_mode(settings, group)
    start, end = period_for_mode(datetime.today(), mode)
    return start, end, end + timedelta(days=1), mode


def generate_evcc_summary(settings, group, mode=None, manual_year=None, manual_month=None):
    sessions = fetch_sessions(settings)
    df = pd.DataFrame(sessions)
    if df.empty:
        raise ValueError("Keine Sessions gefunden.")
    if "created" not in df.columns or "chargedEnergy" not in df.columns:
        raise ValueError("EVCC Sessions enthalten nicht die benötigten Felder.")

    def normalize_vehicle_name(value):
        if isinstance(value, dict):
            name = value.get("title") or value.get("name") or value.get("vehicle") or value.get("id") or ""
            return str(name).strip()
        return str(value or "").strip()

    def parse_local_datetime(value):
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return pd.NaT
        try:
            if getattr(ts, "tzinfo", None) is not None:
                return ts.tz_convert(None)
        except Exception:
            pass
        try:
            if getattr(ts, "tzinfo", None) is not None:
                return ts.tz_localize(None)
        except Exception:
            pass
        return ts

    df["created"] = df["created"].apply(parse_local_datetime)
    df = df.dropna(subset=["created"])
    df["vehicle_display"] = df["vehicle"].apply(normalize_vehicle_name) if "vehicle" in df.columns else ""
    start, end, next_period_start, mode = _resolve_report_period(settings, group, mode, manual_year, manual_month)
    selected = {str(v).strip() for v in group.get("vehicles", []) if str(v).strip()}
    if selected:
        df = df[df["vehicle_display"].isin(selected)]
    df = df[(df["created"] >= start) & (df["created"] < next_period_start)]
    if df.empty:
        raise ValueError("Keine Ladevorgänge für den gewählten Zeitraum gefunden.")
    df["chargedEnergy"] = pd.to_numeric(df["chargedEnergy"], errors="coerce").fillna(0)
    price_info = price_info_for_group(settings, group, start.year)
    df["price"] = (df["chargedEnergy"] * price_info["price_eur_kwh"]).round(2)
    end_col = next((c for c in ("finished", "updated", "end") if c in df.columns), None)
    if end_col:
        df[end_col] = df[end_col].apply(parse_local_datetime)
    else:
        df["__end"] = df["created"]
        end_col = "__end"
    df = df.sort_values("created", ascending=True)
    rows_html, session_rows = [], []
    for _, row in df.iterrows():
        dt = row["created"]
        enddt = row[end_col] if pd.notna(row[end_col]) else row["created"]
        energy = float(row.get("chargedEnergy", 0) or 0)
        price = float(row.get("price", 0) or 0)
        vehicle = str(row.get("vehicle_display", ""))
        row_data = {
            "date": dt.strftime('%d.%m.%Y'), "start_time": dt.strftime('%H:%M'), "end_time": enddt.strftime('%H:%M'),
            "vehicle": vehicle, "energy_kwh": energy, "energy_kwh_formatted": format_de_number(energy),
            "cost": price, "cost_formatted": format_de_number(price), "cost_eur": f"{format_de_number(price)} €",
        }
        session_rows.append(row_data)
        rows_html.append(f"<tr><td>{row_data['date']}</td><td>{row_data['start_time']}</td><td>{row_data['end_time']}</td><td>{vehicle}</td><td>{row_data['energy_kwh_formatted']}</td><td>{row_data['cost_eur']}</td></tr>")
    vehicle_groups, grouped = [], {}
    for item in session_rows:
        grouped.setdefault(item.get("vehicle") or "Ohne Fahrzeugzuordnung", []).append(item)
    for vehicle_name, items in grouped.items():
        vehicle_energy = sum(float(item.get("energy_kwh", 0) or 0) for item in items)
        vehicle_cost = sum(float(item.get("cost", 0) or 0) for item in items)
        vehicle_groups.append({"vehicle": vehicle_name, "sessions": items, "total_energy": vehicle_energy, "total_cost": vehicle_cost,
                               "total_energy_kwh": f"{format_de_number(vehicle_energy)} kWh", "total_cost_eur": f"{format_de_number(vehicle_cost)} €"})
    total_energy = float(df['chargedEnergy'].sum())
    total_cost = float(df['price'].sum())
    return {
        "group_type": "evcc", "rows_html": "\n".join(rows_html), "sessions": session_rows, "vehicle_groups": vehicle_groups, "ha_sources": [],
        "total_energy": total_energy, "total_cost": total_cost, "total_energy_kwh": f"{format_de_number(total_energy)} kWh",
        "total_cost_eur": f"{format_de_number(total_cost)} €", "total_energy_formatted": format_de_number(total_energy),
        "total_cost_formatted": format_de_number(total_cost), "period_start": start, "period_end": end,
        "period_start_str": start.strftime('%d.%m.%Y'), "period_end_str": end.strftime('%d.%m.%Y'), "billing_mode": mode, **price_info,
    }


def generate_ha_summary(settings, group, mode=None, manual_year=None, manual_month=None):
    start, end, next_period_start, mode = _resolve_report_period(settings, group, mode, manual_year, manual_month)
    configured_groups = group.get("billing_groups", [])
    if not configured_groups:
        raise ValueError("In dieser Abrechnung sind noch keine Home-Assistant-Abrechnungsgruppen konfiguriert.")
    price_info = price_info_for_group(settings, group, start.year)
    price = float(price_info["price_eur_kwh"])
    billing_group_rows = []
    flat_sources = []
    total_energy = 0.0

    for billing_group in configured_groups:
        sources = billing_group.get("ha_sources", [])
        if not sources:
            # Leere Gruppen bleiben in der Konfiguration erhalten, erscheinen aber nicht im PDF.
            continue
        group_energy = 0.0
        source_rows = []
        for source in sources:
            try:
                energy, method, unit = calculate_ha_source_consumption(source, start, next_period_start)
            except Exception as err:
                if bool(source.get("include_in_total", True)):
                    raise ValueError(f"Quelle {source.get('label') or source.get('entity_id')}: {err}") from err
                energy, method, unit = 0.0, f"Nicht verfügbar: {err}", str(source.get("unit") or "")
            include = bool(source.get("include_in_total", True))
            cost = round(float(energy) * price, 2)
            if include:
                group_energy += float(energy)
            row = {
                "entity_id": source.get("entity_id", ""),
                "label": source.get("label") or source.get("entity_id", ""),
                "mode": source.get("mode", "auto"),
                "unit": unit,
                "include_in_total": include,
                "energy_kwh": float(energy),
                "energy_kwh_formatted": format_de_number(energy),
                "cost": cost,
                "cost_formatted": format_de_number(cost),
                "calculation_method": method,
                "billing_group_id": billing_group.get("id", ""),
                "billing_group_name": billing_group.get("name", ""),
            }
            source_rows.append(row)
            flat_sources.append(row)

        group_cost = round(group_energy * price, 2)
        total_energy += group_energy
        billing_group_rows.append({
            "id": billing_group.get("id", ""),
            "name": billing_group.get("name") or "Abrechnungsgruppe",
            "sources": source_rows,
            "source_count": len(source_rows),
            "included_source_count": sum(1 for item in source_rows if item.get("include_in_total")),
            "total_energy": group_energy,
            "total_cost": group_cost,
            "total_energy_formatted": format_de_number(group_energy),
            "total_cost_formatted": format_de_number(group_cost),
            "total_energy_kwh": f"{format_de_number(group_energy)} kWh",
            "total_cost_eur": f"{format_de_number(group_cost)} €",
        })

    # Die HA-Teilsumme entspricht exakt der Summe der im PDF sichtbaren Gruppensummen.
    total_cost = round(sum(float(item.get("total_cost", 0) or 0) for item in billing_group_rows), 2)
    return {
        "group_type": "homeassistant",
        "rows_html": "".join(
            f"<tr><td>Abrechnungsgruppe</td><td>{item['name']}</td><td></td>"
            f"<td>{item['total_energy_formatted']}</td><td>{item['total_cost_eur']}</td><td>enthalten</td></tr>"
            for item in billing_group_rows
        ),
        "sessions": [],
        "vehicle_groups": [],
        "ha_sources": flat_sources,
        "billing_groups": billing_group_rows,
        "total_energy": total_energy,
        "total_cost": total_cost,
        "total_energy_kwh": f"{format_de_number(total_energy)} kWh",
        "total_cost_eur": f"{format_de_number(total_cost)} €",
        "total_energy_formatted": format_de_number(total_energy),
        "total_cost_formatted": format_de_number(total_cost),
        "period_start": start,
        "period_end": end,
        "period_start_str": start.strftime('%d.%m.%Y'),
        "period_end_str": end.strftime('%d.%m.%Y'),
        "billing_mode": mode,
        **price_info,
    }

def _blank_component_summary(settings, group, mode=None, manual_year=None, manual_month=None):
    start, end, _next_period_start, resolved_mode = _resolve_report_period(settings, group, mode, manual_year, manual_month)
    price_info = price_info_for_group(settings, group, start.year)
    return {
        "rows_html": "", "sessions": [], "vehicle_groups": [], "ha_sources": [], "billing_groups": [],
        "total_energy": 0.0, "total_cost": 0.0,
        "period_start": start, "period_end": end, "billing_mode": resolved_mode, **price_info,
    }


def generate_combined_summary(settings, group, mode=None, manual_year=None, manual_month=None):
    """Eine Abrechnungsgruppe kann EVCC-Ladevorgänge und HA-Verbrauchssensoren gemeinsam enthalten."""
    include_evcc = bool(group.get("include_evcc", True))
    ha_configured = any(item.get("ha_sources") for item in group.get("billing_groups", []))
    if not include_evcc and not ha_configured:
        raise ValueError("In dieser Abrechnungsgruppe sind noch keine Verbraucher konfiguriert.")

    evcc = _blank_component_summary(settings, group, mode, manual_year, manual_month)
    evcc_notice = ""
    if include_evcc:
        try:
            evcc = generate_evcc_summary(settings, group, mode=mode, manual_year=manual_year, manual_month=manual_month)
        except ValueError as err:
            text = str(err)
            if text in {"Keine Sessions gefunden.", "Keine Ladevorgänge für den gewählten Zeitraum gefunden."}:
                evcc_notice = text
            else:
                raise

    ha = _blank_component_summary(settings, group, mode, manual_year, manual_month)
    if ha_configured:
        ha = generate_ha_summary(settings, group, mode=mode, manual_year=manual_year, manual_month=manual_month)

    start = evcc.get("period_start") or ha.get("period_start")
    end = evcc.get("period_end") or ha.get("period_end")
    billing_mode = evcc.get("billing_mode") or ha.get("billing_mode")
    price_info = price_info_for_group(settings, group, start.year)
    price = float(price_info["price_eur_kwh"])

    total_energy = float(evcc.get("total_energy", 0) or 0) + float(ha.get("total_energy", 0) or 0)
    # Gesamtbetrag aus den sichtbaren Teilsummen bilden, damit PDF-Zeilen und Endsumme centgenau übereinstimmen.
    total_cost = round(float(evcc.get("total_cost", 0) or 0) + float(ha.get("total_cost", 0) or 0), 2)

    # Einheitliche Tabellenzeilen für den Template-Editor / {{ rows_html }}.
    combined_rows = []
    for charge in evcc.get("sessions", []):
        combined_rows.append(
            f"<tr><td>Fahrzeug</td><td>{charge.get('vehicle','')}</td>"
            f"<td>{charge.get('date','')} {charge.get('start_time','')}-{charge.get('end_time','')}</td>"
            f"<td>{charge.get('energy_kwh_formatted','')}</td><td>{charge.get('cost_eur','')}</td><td>enthalten</td></tr>"
        )
    for item in ha.get("billing_groups", []):
        combined_rows.append(
            f"<tr><td>Abrechnungsgruppe</td><td>{item.get('name','')}</td><td></td>"
            f"<td>{item.get('total_energy_formatted','')}</td><td>{item.get('total_cost_eur','')}</td><td>enthalten</td></tr>"
        )

    return {
        "group_type": "mixed",
        "has_evcc": include_evcc,
        "has_ha": ha_configured,
        "evcc_notice": evcc_notice,
        "rows_html": "".join(combined_rows),
        "sessions": evcc.get("sessions", []),
        "vehicle_groups": evcc.get("vehicle_groups", []),
        "ha_sources": ha.get("ha_sources", []),
        "billing_groups": ha.get("billing_groups", []),
        "evcc_total_energy": float(evcc.get("total_energy", 0) or 0),
        "evcc_total_cost": float(evcc.get("total_cost", 0) or 0),
        "ha_total_energy": float(ha.get("total_energy", 0) or 0),
        "ha_total_cost": float(ha.get("total_cost", 0) or 0),
        "total_energy": total_energy,
        "total_cost": total_cost,
        "total_energy_kwh": f"{format_de_number(total_energy)} kWh",
        "total_cost_eur": f"{format_de_number(total_cost)} €",
        "total_energy_formatted": format_de_number(total_energy),
        "total_cost_formatted": format_de_number(total_cost),
        "period_start": start,
        "period_end": end,
        "period_start_str": start.strftime('%d.%m.%Y'),
        "period_end_str": end.strftime('%d.%m.%Y'),
        "billing_mode": billing_mode,
        **price_info,
    }


def generate_rows_and_summary(settings, group, mode=None, manual_year=None, manual_month=None):
    return generate_combined_summary(settings, group, mode=mode, manual_year=manual_year, manual_month=manual_month)


def render_html(settings, group, mode=None, manual_year=None, manual_month=None):
    summary = generate_rows_and_summary(settings, group, mode=mode, manual_year=manual_year, manual_month=manual_month)
    sender = effective_sender(settings, group)
    recipient = {"name": group.get("recipient_name",""), "company": group.get("recipient_company",""), "email": group.get("recipient_email",""), "street": group.get("recipient_street",""), "zip": group.get("recipient_zip",""), "city": group.get("recipient_city","")}
    bank = effective_bank(settings, group)
    email_body = render_shortcuts(effective_email_body(settings, group), summary)
    tpl_key = effective_template_key(settings, group)
    tpl = settings["templates"][tpl_key]["content"]
    billing_label = billing_mode_label(summary["billing_mode"])
    period_lbl = period_label(summary["period_start"], summary["period_end"])
    context = {
        "sender": sender,
        "recipient": recipient,
        "bank": bank,
        "invoice_date": datetime.today().strftime("%d.%m.%Y"),
        "billing_mode_label": billing_label,
        "period_label": period_lbl,
        "period_start": summary["period_start_str"],
        "period_end": summary["period_end_str"],
        "rows_html": summary["rows_html"],
        "sessions": summary["sessions"],
        "vehicle_groups": summary["vehicle_groups"],
        "ha_sources": summary.get("ha_sources", []),
        "billing_groups": summary.get("billing_groups", []),
        "sensor_groups": summary.get("billing_groups", []),
        "has_evcc": summary.get("has_evcc", False),
        "has_ha": summary.get("has_ha", False),
        "evcc_total_energy": format_de_number(summary.get("evcc_total_energy", 0)),
        "evcc_total_cost": format_de_number(summary.get("evcc_total_cost", 0)),
        "ha_total_energy": format_de_number(summary.get("ha_total_energy", 0)),
        "ha_total_cost": format_de_number(summary.get("ha_total_cost", 0)),
        "group_name": group.get("name", ""),
        "group_type": summary.get("group_type", group.get("group_type", "evcc")),
        "total_energy_kwh": summary["total_energy_kwh"],
        "total_cost_eur": summary["total_cost_eur"],
        "total_energy": summary["total_energy_formatted"],
        "total_cost": summary["total_cost_formatted"],
        "electricity_price": summary["price_eur_kwh_formatted"],
        "electricity_price_eur_kwh": summary["price_eur_kwh_label"],
        "price_mode": summary["mode"],
        "price_method_label": summary["price_method_label"],
        "price_source_label": summary["price_source_label"],
        "price_source_year": summary["price_source_year"],
        "email_body": email_body,
        "sender_name": sender.get("name", ""),
        "sender_street": sender.get("street", ""),
        "sender_zip": sender.get("zip", ""),
        "sender_city": sender.get("city", ""),
        "sender_email": sender.get("email", ""),
        "recipient_name": recipient.get("name", ""),
        "recipient_company": recipient.get("company", ""),
        "recipient_street": recipient.get("street", ""),
        "recipient_zip": recipient.get("zip", ""),
        "recipient_city": recipient.get("city", ""),
        "recipient_email": recipient.get("email", ""),
        "bank_recipient": bank.get("recipient", ""),
        "bank_iban": bank.get("iban", ""),
        "bank_bic": bank.get("bic", ""),
        "bank_institute": bank.get("institute", ""),
        "template_key": tpl_key,
        "template_label": settings["templates"][tpl_key].get("label", tpl_key),
    }
    html = Template(tpl).render(**context)
    return html, summary

def generate_pdf(settings, group, mode=None, manual_year=None, manual_month=None):
    ensure_dirs()
    html, summary = render_html(settings, group, mode=mode, manual_year=manual_year, manual_month=manual_month)
    safe_group = re.sub(r"[^A-Za-z0-9_-]+","_", group["name"]).strip("_") or "gruppe"
    filename = f"energie_abrechnung_{safe_group}_{summary['period_start'].strftime('%Y%m%d')}_{summary['period_end'].strftime('%Y%m%d')}.pdf"
    out = REPORT_DIR / filename
    HTML(string=html).write_pdf(str(out))
    return out, summary

def send_email_with_attachment(settings, group, pdf_path, summary):
    smtp_cfg = settings.get("smtp", {})
    host = smtp_cfg.get("host", "").strip()
    if not host:
        raise ValueError("SMTP Host fehlt.")
    port = int(smtp_cfg.get("port", 587))
    sender = effective_sender(settings, group)
    sender_email = sender.get("email", "").strip() or smtp_cfg.get("user", "").strip()
    recipient_email = group.get("recipient_email", "").strip()
    if not sender_email or not recipient_email:
        raise ValueError("Absender- oder Empfänger-E-Mail fehlt.")

    copy_email = sender.get("email", "").strip() or settings.get("sender", {}).get("email", "").strip() or sender_email
    copy_enabled = bool(group.get("sender_copy_enabled")) and bool(copy_email)
    subject = effective_email_subject(settings, group, summary)
    body = render_shortcuts(effective_email_body(settings, group), summary) or "Anbei die Abrechnung als PDF."
    pdf_bytes = pdf_path.read_bytes()

    def build_message(target_email, include_copy_header=False):
        msg = EmailMessage()
        msg["From"] = sender_email
        msg["To"] = target_email
        if include_copy_header and copy_enabled and copy_email != target_email:
            msg["Cc"] = copy_email
        msg["Subject"] = subject
        msg.set_content(body)
        msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_path.name)
        return msg

    user = smtp_cfg.get("user", "").strip()
    password = smtp_cfg.get("password", "")

    def send_via_server(server):
        main_msg = build_message(recipient_email, include_copy_header=False)
        server.send_message(main_msg, to_addrs=[recipient_email])

        if copy_enabled and copy_email:
            copy_msg = build_message(copy_email, include_copy_header=False)
            server.send_message(copy_msg, to_addrs=[copy_email])

    if bool(smtp_cfg.get("tls", True)):
        with smtplib.SMTP(host, port) as server:
            server.starttls(context=ssl.create_default_context())
            if user:
                server.login(user, password)
            send_via_server(server)
    else:
        with smtplib.SMTP(host, port) as server:
            if user:
                server.login(user, password)
            send_via_server(server)

_BACKGROUND_STOP_EVENT = threading.Event()
_BACKGROUND_LOCK = threading.Lock()
_SCHEDULER_THREAD = None


def scheduler_loop():
    LOGGER.info("Scheduler gestartet.")
    while not _BACKGROUND_STOP_EVENT.is_set():
        try:
            settings = load_settings()
            if settings.get("scheduler", {}).get("enabled"):
                now = datetime.now()
                hhmm = settings["scheduler"].get("time", "07:00")
                default_day = int(settings["scheduler"].get("day_of_month", 1))
                current_tag = now.strftime("%Y-%m-%d")
                if now.strftime("%H:%M") >= hhmm and settings["scheduler"].get("last_run") != current_tag:
                    sent = False
                    for group in settings.get("groups", []):
                        if not group.get("active"):
                            continue
                        send_day = int(group.get("send_day", default_day) or default_day)
                        if now.day != send_day:
                            continue
                        try:
                            pdf_path, summary = generate_pdf(settings, group)
                            send_email_with_attachment(settings, group, pdf_path, summary)
                            sent = True
                        except Exception as err:
                            LOGGER.exception("Automatische Abrechnung für Gruppe %s fehlgeschlagen: %s", group.get("name") or group.get("id"), err)
                    if sent:
                        settings["scheduler"]["last_run"] = current_tag
                        save_settings(settings)
        except Exception as err:
            LOGGER.exception("Scheduler-Durchlauf fehlgeschlagen: %s", err)
        _BACKGROUND_STOP_EVENT.wait(60)
    LOGGER.info("Scheduler beendet.")


def start_background_services():
    """Start background services exactly once per WSGI worker."""
    global _SCHEDULER_THREAD
    ensure_dirs()
    with _BACKGROUND_LOCK:
        if _SCHEDULER_THREAD is not None and _SCHEDULER_THREAD.is_alive():
            return
        _BACKGROUND_STOP_EVENT.clear()
        _SCHEDULER_THREAD = threading.Thread(
            target=scheduler_loop,
            name="evcc-to-pdf-scheduler",
            daemon=True,
        )
        _SCHEDULER_THREAD.start()


def stop_background_services():
    _BACKGROUND_STOP_EVENT.set()


atexit.register(stop_background_services)

@app.route("/")
def dashboard():
    settings = load_settings()
    return render_template("dashboard.html", settings=settings)

@app.route("/settings", methods=["GET","POST"])
def settings_page():
    settings = load_settings()
    if request.method == "POST":
        settings["evcc"]["url"] = request.form.get("evcc_url","").strip()
        settings["evcc"]["password"] = request.form.get("evcc_password","").strip()
        settings["sender"]["name"] = request.form.get("sender_name","").strip()
        settings["sender"]["street"] = request.form.get("sender_street","").strip()
        settings["sender"]["zip"] = request.form.get("sender_zip","").strip()
        settings["sender"]["city"] = request.form.get("sender_city","").strip()
        settings["sender"]["email"] = request.form.get("sender_email","").strip()
        settings["bank"]["recipient"] = request.form.get("bank_recipient","").strip()
        settings["bank"]["iban"] = request.form.get("bank_iban","").strip()
        settings["bank"]["bic"] = request.form.get("bank_bic","").strip()
        settings["bank"]["institute"] = request.form.get("bank_institute","").strip()
        settings["smtp"]["host"] = request.form.get("smtp_host","").strip()
        settings["smtp"]["port"] = parse_int(request.form.get("smtp_port","587"),587)
        settings["smtp"]["user"] = request.form.get("smtp_user","").strip()
        settings["smtp"]["password"] = request.form.get("smtp_password","").strip()
        settings["smtp"]["tls"] = parse_bool(request.form.get("smtp_tls"))
        settings["scheduler"]["enabled"] = parse_bool(request.form.get("scheduler_enabled"))
        settings["scheduler"]["day_of_month"] = max(1, min(28, parse_int(request.form.get("scheduler_day_of_month","1"),1)))
        settings["scheduler"]["time"] = request.form.get("scheduler_time","07:00").strip() or "07:00"
        settings["reporting"]["grid_price"] = parse_float(request.form.get("grid_price","0"),0.0)
        settings["reporting"]["default_billing_mode"] = request.form.get("default_billing_mode","monthly").strip()
        settings["reporting"]["default_email_body"] = request.form.get("default_email_body","").strip()
        settings["reporting"]["default_email_subject"] = request.form.get("default_email_subject","").strip()
        save_settings(settings)
        flash("Einstellungen gespeichert.", "success")
        return redirect(f"{get_ingress_path()}/settings")
    return render_template("settings.html", settings=settings)

@app.route("/refresh_assets", methods=["POST"])
def refresh_assets():
    settings = load_settings()
    try:
        settings["cached_assets"] = fetch_available_assets(settings)
        save_settings(settings)
        (REPORT_DIR / "available_assets.txt").write_text("\n".join(settings["cached_assets"]), encoding="utf-8")
        LOGGER.info("EVCC-Assets aktualisiert: %s Einträge.", len(settings["cached_assets"]))
        flash(f"{len(settings['cached_assets'])} Einträge geladen.", "success")
    except Exception as err:
        LOGGER.exception("EVCC-Assets konnten nicht aktualisiert werden: %s", err)
        flash(f"Einträge konnten nicht geladen werden: {err}", "error")
    return redirect(f"{get_ingress_path()}/groups")

@app.route("/refresh_ha_entities", methods=["POST"])
def refresh_ha_entities_route():
    try:
        entities = fetch_ha_entities()
        LOGGER.info("Home-Assistant-Entitäten aktualisiert: %s geeignete Verbrauchssensoren.", len(entities))
        flash(f"Home-Assistant-Entitäten aktualisiert: {len(entities)} geeignete Quellen gefunden.", "success")
    except Exception as err:
        LOGGER.exception("Home-Assistant-Entitäten konnten nicht geladen werden: %s", err)
        flash(f"Home-Assistant-Entitäten konnten nicht geladen werden: {err}", "error")
    return redirect(f"{get_ingress_path()}/groups")


@app.route("/groups", methods=["GET","POST"])
def groups_page():
    settings = load_settings()
    edit_group = None
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        if action == "delete":
            group_id = request.form.get("group_id","").strip()
            settings["groups"] = [g for g in settings["groups"] if g.get("id") != group_id]
            save_settings(settings)
            flash("Gruppe gelöscht.", "success")
            return redirect(f"{get_ingress_path()}/groups")

        group_id = request.form.get("group_id","").strip() or str(uuid.uuid4())
        group = find_group(settings, group_id) or {"id": group_id}
        group["id"] = group_id
        group["active"] = parse_bool(request.form.get("active"))
        group["name"] = request.form.get("name","").strip()
        group["recipient_name"] = request.form.get("recipient_name","").strip()
        group["recipient_company"] = request.form.get("recipient_company","").strip()
        group["recipient_email"] = request.form.get("recipient_email","").strip()
        group["recipient_street"] = request.form.get("recipient_street","").strip()
        group["recipient_zip"] = request.form.get("recipient_zip","").strip()
        group["recipient_city"] = request.form.get("recipient_city","").strip()
        group["group_type"] = "mixed"
        group["include_evcc"] = parse_bool(request.form.get("include_evcc"))
        group["group_icon"] = request.form.get("group_icon", "auto").strip().lower()
        group["vehicles"] = [v for v in request.form.getlist("vehicles") if v.strip()]
        try:
            raw_billing_groups = json.loads(request.form.get("billing_groups_json", "[]") or "[]")
        except Exception:
            raw_billing_groups = []
        group["billing_groups"] = [normalize_billing_group(item) for item in raw_billing_groups if isinstance(item, dict)]
        group["ha_sources"] = [deepcopy(src) for item in group["billing_groups"] for src in item.get("ha_sources", [])]
        group["grid_price_override"] = request.form.get("grid_price_override","").strip()
        group["grid_price_mode"] = "bmf" if parse_bool(request.form.get("grid_price_bmf")) else "manual"
        group["sender_mode"] = request.form.get("sender_mode","default").strip()
        group["custom_sender"] = {
            "name": request.form.get("custom_sender_name","").strip(),
            "email": request.form.get("custom_sender_email","").strip(),
            "street": request.form.get("custom_sender_street","").strip(),
            "zip": request.form.get("custom_sender_zip","").strip(),
            "city": request.form.get("custom_sender_city","").strip(),
        }
        group["html_mode"] = request.form.get("html_mode","default").strip()
        group["selected_template_key"] = request.form.get("selected_template_key",DEFAULT_TEMPLATE_KEY).strip()
        group["email_body_mode"] = request.form.get("email_body_mode","default").strip()
        group["custom_email_body"] = request.form.get("custom_email_body","").strip()
        group["email_subject_mode"] = request.form.get("email_subject_mode","default").strip()
        group["custom_email_subject"] = request.form.get("custom_email_subject","").strip()
        group["billing_mode_mode"] = request.form.get("billing_mode_mode","default").strip()
        group["custom_billing_mode"] = request.form.get("custom_billing_mode","monthly").strip()
        group["send_day"] = max(1, min(28, parse_int(request.form.get("send_day","1"),1)))
        group["sender_copy_enabled"] = parse_bool(request.form.get("sender_copy_enabled"))
        group["bank_mode"] = request.form.get("bank_mode","default").strip()
        group["custom_bank"] = {
            "recipient": request.form.get("custom_bank_recipient","").strip(),
            "iban": request.form.get("custom_bank_iban","").strip(),
            "bic": request.form.get("custom_bank_bic","").strip(),
            "institute": request.form.get("custom_bank_institute","").strip(),
        }
        existing = find_group(settings, group_id)
        if existing:
            existing.update(normalize_group(group))
            flash("Gruppe aktualisiert.", "success")
        else:
            settings["groups"].append(normalize_group(group))
            flash("Gruppe angelegt.", "success")
        save_settings(settings)
        return redirect(f"{get_ingress_path()}/groups")

    edit_id = request.args.get("edit","").strip()
    if edit_id:
        edit_group = find_group(settings, edit_id)
    try:
        current_bmf = resolve_bmf_rate(datetime.today().year)
    except Exception:
        current_bmf = None
    ha_cache = load_ha_entity_cache()
    return render_template("groups.html", settings=settings, edit_group=edit_group, current_bmf=current_bmf,
                           ha_entities=ha_cache.get("entities", []), ha_entities_updated=ha_cache.get("updated_at", ""))



@app.route("/templates/editor", methods=["GET", "POST"])
def template_editor_page():
    settings = load_settings()
    key = request.values.get("key", "").strip()
    edit_template = settings["templates"].get(key) if key else None
    if request.method == "POST":
        key = request.form.get("key", "").strip()
        label = request.form.get("label", "").strip()
        schema_raw = request.form.get("editor_schema", "").strip()
        if not key or not label:
            flash("Key und Bezeichnung sind erforderlich.", "error")
            return redirect(f"{get_ingress_path()}/templates/editor" + (f"?key={key}" if key else ""))
        try:
            schema = json.loads(schema_raw) if schema_raw else build_default_editor_schema()
        except Exception:
            flash("Editor-Daten konnten nicht verarbeitet werden.", "error")
            return redirect(f"{get_ingress_path()}/templates/editor" + (f"?key={key}" if key else ""))
        settings["templates"][key] = {"key": key, "label": label, "content": render_editor_template_html(schema)}
        save_settings(settings)
        flash("Template aus dem Editor gespeichert.", "success")
        return redirect(f"{get_ingress_path()}/templates?edit={key}")

    schema = extract_editor_schema(edit_template.get("content", "") if edit_template else "")
    if not schema:
        schema = build_default_editor_schema(edit_template.get("content", "") if edit_template else "")
    return render_template("template_editor.html", settings=settings, edit_template=edit_template, editor_schema=schema, editor_key=key)

@app.route("/templates", methods=["GET","POST"])
def templates_page():
    settings = load_settings()
    edit_key = request.args.get("edit","").strip()
    edit_template = settings["templates"].get(edit_key)
    if request.method == "POST":
        action = request.form.get("form_action","save").strip()
        key = request.form.get("key","").strip()
        if action == "set_default":
            key = request.form.get("key","").strip()
            if key in settings["templates"]:
                settings["default_template_key"] = key
                save_settings(settings)
                flash("Default-Template gesetzt.", "success")
            return redirect(f"{get_ingress_path()}/templates")
        if action == "delete":
            key = request.form.get("key","").strip()
            if key == settings.get("default_template_key"):
                flash("Das aktuelle Default-Template kann nicht gelöscht werden.", "error")
            elif key in settings["templates"]:
                del settings["templates"][key]
                save_settings(settings)
                flash("Template gelöscht.", "success")
            return redirect(f"{get_ingress_path()}/templates")
        label = request.form.get("label","").strip()
        content = request.form.get("content","").strip()
        upload = request.files.get("template_file")
        if upload and upload.filename:
            content = upload.read().decode("utf-8", errors="ignore")
        if not key or not label or not content:
            flash("Key, Bezeichnung und Inhalt sind erforderlich.", "error")
            return redirect(f"{get_ingress_path()}/templates")
        settings["templates"][key] = {"key": key, "label": label, "content": content}
        save_settings(settings)
        flash("Template gespeichert.", "success")
        return redirect(f"{get_ingress_path()}/templates")
    return render_template("templates_page.html", settings=settings, edit_template=edit_template)

@app.route("/report", methods=["GET","POST"])
def report_page():
    settings = load_settings()
    generated_file = None
    preview_html = None

    today = datetime.today()
    selected_mode = "manual"
    selected_year = str(today.year)
    selected_month = f"{today.month:02d}"
    selected_group_id = settings["groups"][0]["id"] if settings.get("groups") else ""

    if request.method == "POST":
        selected_group_id = request.form.get("group_id","").strip()
        action = request.form.get("action","pdf")
        selected_mode = request.form.get("mode","manual").strip() or "manual"
        selected_year = request.form.get("year","").strip() or str(today.year)
        selected_month = request.form.get("month","").strip() or f"{today.month:02d}"
        group = find_group(settings, selected_group_id)
        if not group:
            flash("Gruppe nicht gefunden.", "error")
            return redirect(f"{get_ingress_path()}/report")
        try:
            manual_year = selected_year if selected_mode == "manual" else None
            manual_month = selected_month if selected_mode == "manual" else None
            if action == "preview":
                preview_html, _ = render_html(settings, group, manual_year=manual_year, manual_month=manual_month)
            else:
                pdf_path, summary = generate_pdf(settings, group, manual_year=manual_year, manual_month=manual_month)
                generated_file = pdf_path
                flash(f"PDF erzeugt: {pdf_path.name}", "success")
                if action == "send":
                    send_email_with_attachment(settings, group, pdf_path, summary)
                    flash("E-Mail versendet.", "success")
        except Exception as err:
            flash(f"Bericht konnte nicht verarbeitet werden: {err}", "error")

    current_year = today.year
    years = list(range(current_year - 3, current_year + 2))
    months = list(range(1,13))
    return render_template(
        "report.html",
        settings=settings,
        years=years,
        months=months,
        generated_file=generated_file,
        preview_html=preview_html,
        selected_mode=selected_mode,
        selected_year=selected_year,
        selected_month=selected_month,
        selected_group_id=selected_group_id,
    )

if __name__ == "__main__":
    # Entwicklungs-Fallback. Produktiv wird die App über Gunicorn (wsgi.py) gestartet.
    start_background_services()
    app.run(host="0.0.0.0", port=APP_PORT)