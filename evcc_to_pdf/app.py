import json
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
from pathlib import Path

import pandas as pd
import paho.mqtt.client as mqtt
import requests
from flask import Flask, flash, redirect, render_template, request
from jinja2 import Template
from werkzeug.middleware.proxy_fix import ProxyFix
from weasyprint import HTML

APP_PORT = 8099
SETTINGS_DIR = Path("/addon_config/evcc_to_pdf")
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
BACKUP_DIR = SETTINGS_DIR / "backups"
REPORT_DIR = Path("/share/evcc-pdfs")
OPTIONS_FILE = Path("/data/options.json")
DEFAULT_TEMPLATE_KEY = "default"
DEFAULT_TEMPLATE_LABEL = "Standard HTML"
APP_VERSION = "0.5.5"

DEFAULT_TEMPLATE_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <style>
    @page { size: A4; margin: 18mm 14mm 18mm 14mm; }
    body { font-family: DejaVu Sans, Arial, sans-serif; font-size: 11pt; color: #111; }
    .header { display: table; width: 100%; margin-bottom: 30px; }
    .col { display: table-cell; width: 50%; vertical-align: top; }
    .right { text-align: right; }
    .period { margin: 18px 0 14px; font-weight: bold; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 10.5pt; }
    th, td { border: 1px solid #666; padding: 6px 7px; vertical-align: top; }
    th { background: #efefef; text-align: left; }
    .summary { margin-top: 16px; }
    .summary p { margin: 5px 0; }
    .bank { margin-top: 24px; }
    .footer { margin-top: 28px; }
  </style>
</head>
<body>
  <div class="header">
    <div class="col">
      <strong>{{ recipient.company or recipient.name }}</strong><br>
      {{ recipient.name }}<br>
      {{ recipient.street }}<br>
      {{ recipient.zip }} {{ recipient.city }}<br>
      {{ recipient.email }}
    </div>
    <div class="col right">
      <strong>{{ sender.name }}</strong><br>
      {{ sender.street }}<br>
      {{ sender.zip }} {{ sender.city }}<br>
      {{ sender.email }}<br><br>
      {{ invoice_date }}
    </div>
  </div>

  <div class="period">{{ billing_mode_label }} – {{ period_label }}</div>

  <table>
    <thead>
      <tr>
        <th>Datum</th>
        <th>Startzeit</th>
        <th>Endzeit</th>
        <th>Fahrzeug</th>
        <th>Geladene kWh</th>
        <th>Kosten (€)</th>
      </tr>
    </thead>
    <tbody>
      {{ rows_html|safe }}
    </tbody>
  </table>

  <div class="summary">
    <p><strong>Gesamt geladene kWh:</strong> {{ total_energy_kwh }}</p>
    <p><strong>Gesamtkosten:</strong> {{ total_cost_eur }}</p>
  </div>

  <div class="bank">
    <p>Ich bitte um Begleichung der Kosten für den entsprechenden Zeitraum auf folgendes Konto:</p>
    <p>
      {{ bank.recipient }}<br>
      IBAN: {{ bank.iban }}<br>
      BIC: {{ bank.bic }}<br>
      {{ bank.institute }}
    </p>
  </div>

  <div class="footer">
    <p>{{ email_body|replace('\n', '<br>')|safe }}</p>
    <p>Mit freundlichen Grüßen</p>
    <p>{{ sender.name }}</p>
  </div>
</body>
</html>"""

DEFAULT_SETTINGS = {
    "meta": {"version": APP_VERSION},
    "evcc": {"url": "", "password": ""},
    "sender": {"name": "", "street": "", "zip": "", "city": "", "email": ""},
    "smtp": {"host": "", "port": 587, "user": "", "password": "", "tls": True},
    "bank": {"recipient": "", "iban": "", "bic": "", "institute": ""},
    "scheduler": {"enabled": False, "day_of_month": 1, "time": "07:00", "last_run": ""},
    "reporting": {
        "grid_price": 0.0,
        "default_billing_mode": "monthly",
        "default_email_body": "Bitte überweisen Sie den offenen Betrag auf das unten angegebene Konto.",
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
    if SETTINGS_FILE.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"settings_{ts}.json"
        shutil.copy2(SETTINGS_FILE, backup_file)
        backups = sorted(BACKUP_DIR.glob("settings_*.json"), reverse=True)
        for old in backups[10:]:
            try:
                old.unlink()
            except Exception:
                pass

def load_local_settings():
    ensure_dirs()
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None

def save_local_settings(settings, with_backup=True):
    ensure_dirs()
    if with_backup and SETTINGS_FILE.exists():
        create_backup()
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

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
        client.publish(topic, payload=payload, qos=1, retain=True)
        client.disconnect()
        return True
    except Exception:
        return False

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
        out[tpl_key] = {"key": tpl_key, "label": str(value.get("label") or tpl_key).strip(), "content": str(value.get("content") or "").strip()}
    if DEFAULT_TEMPLATE_KEY not in out:
        out[DEFAULT_TEMPLATE_KEY] = {"key": DEFAULT_TEMPLATE_KEY, "label": DEFAULT_TEMPLATE_LABEL, "content": DEFAULT_TEMPLATE_HTML}
    if not out[DEFAULT_TEMPLATE_KEY]["content"].strip():
        out[DEFAULT_TEMPLATE_KEY]["content"] = DEFAULT_TEMPLATE_HTML
    return out

def normalize_group(group):
    base = {
        "id": str(uuid.uuid4()),
        "active": True,
        "name": "",
        "recipient_name": "",
        "recipient_company": "",
        "recipient_email": "",
        "recipient_street": "",
        "recipient_zip": "",
        "recipient_city": "",
        "vehicles": [],
        "grid_price_override": "",
        "sender_mode": "default",
        "custom_sender": {"name": "", "email": "", "street": "", "zip": "", "city": ""},
        "html_mode": "default",
        "selected_template_key": DEFAULT_TEMPLATE_KEY,
        "email_body_mode": "default",
        "custom_email_body": "",
        "billing_mode_mode": "default",
        "custom_billing_mode": "monthly",
        "send_day": 1,
        "sender_copy_enabled": False,
        "bank_mode": "default",
        "custom_bank": {"recipient": "", "iban": "", "bic": "", "institute": ""},
    }
    merged = deep_merge(base, group or {})
    if not isinstance(merged.get("vehicles"), list):
        merged["vehicles"] = []
    merged["vehicles"] = [str(v) for v in merged["vehicles"] if str(v).strip()]
    return merged

def normalize_settings(raw):
    settings = deep_merge(DEFAULT_SETTINGS, raw or {})
    settings["meta"] = settings.get("meta", {})
    settings["meta"]["version"] = APP_VERSION
    settings["templates"] = normalize_template_dict(settings.get("templates", {}))
    if settings.get("default_template_key") not in settings["templates"]:
        settings["default_template_key"] = DEFAULT_TEMPLATE_KEY
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
    if local_raw:
        return normalize_settings(local_raw)
    mqtt_settings = settings_from_mqtt()
    if mqtt_settings:
        save_local_settings(mqtt_settings, with_backup=False)
        return mqtt_settings
    settings = normalize_settings(DEFAULT_SETTINGS)
    save_local_settings(settings, with_backup=False)
    try:
        sync_settings_to_mqtt(settings)
    except Exception:
        pass
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

    # 1) Alle in EVCC eingetragenen Fahrzeuge aus /api/state
    try:
        state_response = session.get(f"{base_url}/api/state", timeout=15)
        state_response.raise_for_status()
        state_data = state_response.json()
        result = state_data.get("result", {})

        state_vehicles = result.get("vehicles", [])
        if isinstance(state_vehicles, dict):
            state_vehicles = list(state_vehicles.values())

        for entry in state_vehicles:
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

def get_ingress_path():
    return request.headers.get("X-Ingress-Path", "").rstrip("/")

@app.context_processor
def inject_common():
    settings = load_settings()
    return {"settings": settings, "ingress_path": get_ingress_path()}

def find_group(settings, group_id):
    for group in settings["groups"]:
        if group.get("id") == group_id:
            return group
    return None

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
def effective_billing_mode(settings, group): return group.get("custom_billing_mode", "monthly") if group.get("billing_mode_mode") == "custom" else settings.get("reporting", {}).get("default_billing_mode", "monthly")
def effective_template_key(settings, group):
    if group.get("html_mode") == "custom":
        key = group.get("selected_template_key") or settings.get("default_template_key", DEFAULT_TEMPLATE_KEY)
        if key in settings["templates"]: return key
    return settings.get("default_template_key", DEFAULT_TEMPLATE_KEY)

def grid_price_for_group(settings, group):
    override = str(group.get("grid_price_override","")).strip()
    return parse_float(override, parse_float(settings["reporting"].get("grid_price"), 0.0)) if override else parse_float(settings["reporting"].get("grid_price"), 0.0)

def generate_rows_and_summary(settings, group, mode=None, manual_year=None, manual_month=None):
    sessions = fetch_sessions(settings)
    df = pd.DataFrame(sessions)
    if df.empty: raise ValueError("Keine Sessions gefunden.")
    if "created" not in df.columns or "chargedEnergy" not in df.columns: raise ValueError("EVCC Sessions enthalten nicht die benötigten Felder.")
    df["created"] = pd.to_datetime(df["created"], errors="coerce", utc=True).dt.tz_localize(None)
    df = df.dropna(subset=["created"])

    if manual_year and manual_month:
        start = datetime(int(manual_year), int(manual_month), 1)
        end = datetime(int(manual_year), 12, 31) if int(manual_month) == 12 else datetime(int(manual_year), int(manual_month)+1, 1) - timedelta(days=1)
        mode = "monthly"
    else:
        mode = mode or effective_billing_mode(settings, group)
        start, end = period_for_mode(datetime.today(), mode)

    selected = set([str(v) for v in group.get("vehicles", [])])
    if selected and "vehicle" in df.columns:
        df["vehicle"] = df["vehicle"].fillna("").astype(str)
        df = df[df["vehicle"].isin(selected)]

    df = df[(df["created"] >= start) & (df["created"] <= end + timedelta(days=1) - timedelta(seconds=1))]
    if df.empty: raise ValueError("Keine Ladevorgänge für den gewählten Zeitraum gefunden.")

    df["chargedEnergy"] = pd.to_numeric(df["chargedEnergy"], errors="coerce").fillna(0)
    df["price"] = (df["chargedEnergy"] * grid_price_for_group(settings, group)).round(2)

    end_col = next((c for c in ("finished","updated","end") if c in df.columns), None)
    if end_col:
        df[end_col] = pd.to_datetime(df[end_col], errors="coerce", utc=True).dt.tz_localize(None)
    else:
        df["__end"] = df["created"]
        end_col = "__end"
    df = df.sort_values("created", ascending=True)

    rows_html = []
    for _, row in df.iterrows():
        dt = row["created"]
        enddt = row[end_col] if pd.notna(row[end_col]) else row["created"]
        rows_html.append(f"<tr><td>{dt.strftime('%d.%m.%Y')}</td><td>{dt.strftime('%H:%M')}</td><td>{enddt.strftime('%H:%M')}</td><td>{str(row.get('vehicle',''))}</td><td>{float(row.get('chargedEnergy',0)):.2f}</td><td>{float(row.get('price',0)):.2f}</td></tr>")

    return {
        "rows_html": "\n".join(rows_html),
        "total_energy_kwh": f"{df['chargedEnergy'].sum():.2f} kWh",
        "total_cost_eur": f"{df['price'].sum():.2f} €",
        "period_start": start,
        "period_end": end,
        "billing_mode": mode,
    }

def render_html(settings, group, mode=None, manual_year=None, manual_month=None):
    summary = generate_rows_and_summary(settings, group, mode=mode, manual_year=manual_year, manual_month=manual_month)
    sender = effective_sender(settings, group)
    recipient = {"name": group.get("recipient_name",""), "company": group.get("recipient_company",""), "email": group.get("recipient_email",""), "street": group.get("recipient_street",""), "zip": group.get("recipient_zip",""), "city": group.get("recipient_city","")}
    bank = effective_bank(settings, group)
    email_body = effective_email_body(settings, group)
    tpl = settings["templates"][effective_template_key(settings, group)]["content"]
    html = Template(tpl).render(
        sender=sender, recipient=recipient, bank=bank,
        invoice_date=datetime.today().strftime("%d.%m.%Y"),
        billing_mode_label=billing_mode_label(summary["billing_mode"]),
        period_label=period_label(summary["period_start"], summary["period_end"]),
        rows_html=summary["rows_html"],
        total_energy_kwh=summary["total_energy_kwh"],
        total_cost_eur=summary["total_cost_eur"],
        email_body=email_body,
    )
    return html, summary

def generate_pdf(settings, group, mode=None, manual_year=None, manual_month=None):
    ensure_dirs()
    html, summary = render_html(settings, group, mode=mode, manual_year=manual_year, manual_month=manual_month)
    safe_group = re.sub(r"[^A-Za-z0-9_-]+","_", group["name"]).strip("_") or "gruppe"
    filename = f"evcc_abrechnung_{safe_group}_{summary['period_start'].strftime('%Y%m%d')}_{summary['period_end'].strftime('%Y%m%d')}.pdf"
    out = REPORT_DIR / filename
    HTML(string=html).write_pdf(str(out))
    return out, summary

def send_email_with_attachment(settings, group, pdf_path, summary):
    smtp_cfg = settings.get("smtp", {})
    host = smtp_cfg.get("host","").strip()
    if not host: raise ValueError("SMTP Host fehlt.")
    port = int(smtp_cfg.get("port",587))
    sender = effective_sender(settings, group)
    sender_email = sender.get("email","").strip() or smtp_cfg.get("user","").strip()
    recipient_email = group.get("recipient_email","").strip()
    if not sender_email or not recipient_email: raise ValueError("Absender- oder Empfänger-E-Mail fehlt.")

    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    if group.get("sender_copy_enabled") and sender_email:
        msg["Cc"] = sender_email
    msg["Subject"] = f"EVCC Abrechnung – {group.get('name','')} – {period_label(summary['period_start'], summary['period_end'])}"
    msg.set_content(effective_email_body(settings, group) or "Anbei die Abrechnung als PDF.")
    msg.add_attachment(pdf_path.read_bytes(), maintype="application", subtype="pdf", filename=pdf_path.name)

    user = smtp_cfg.get("user","").strip()
    password = smtp_cfg.get("password","")
    if bool(smtp_cfg.get("tls", True)):
        with smtplib.SMTP(host, port) as server:
            server.starttls(context=ssl.create_default_context())
            if user: server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as server:
            if user: server.login(user, password)
            server.send_message(msg)

def scheduler_loop():
    while True:
        try:
            settings = load_settings()
            if settings.get("scheduler", {}).get("enabled"):
                now = datetime.now()
                hhmm = settings["scheduler"].get("time","07:00")
                default_day = int(settings["scheduler"].get("day_of_month",1))
                current_tag = now.strftime("%Y-%m-%d")
                if now.strftime("%H:%M") >= hhmm and settings["scheduler"].get("last_run") != current_tag:
                    sent = False
                    for group in settings.get("groups", []):
                        if not group.get("active"): continue
                        send_day = int(group.get("send_day", default_day) or default_day)
                        if now.day != send_day: continue
                        try:
                            pdf_path, summary = generate_pdf(settings, group)
                            send_email_with_attachment(settings, group, pdf_path, summary)
                            sent = True
                        except Exception:
                            pass
                    if sent:
                        settings["scheduler"]["last_run"] = current_tag
                        save_settings(settings)
        except Exception:
            pass
        time.sleep(60)

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
        flash(f"{len(settings['cached_assets'])} Einträge geladen.", "success")
    except Exception as err:
        flash(f"Einträge konnten nicht geladen werden: {err}", "error")
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
        group["vehicles"] = [v for v in request.form.getlist("vehicles") if v.strip()]
        group["grid_price_override"] = request.form.get("grid_price_override","").strip()
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
    return render_template("groups.html", settings=settings, edit_group=edit_group)

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
    if request.method == "POST":
        group_id = request.form.get("group_id","").strip()
        action = request.form.get("action","pdf")
        mode = request.form.get("mode","auto").strip()
        manual_year = request.form.get("year","").strip() or None
        manual_month = request.form.get("month","").strip() or None
        group = find_group(settings, group_id)
        if not group:
            flash("Gruppe nicht gefunden.", "error")
            return redirect(f"{get_ingress_path()}/report")
        try:
            if action == "preview":
                preview_html, _ = render_html(settings, group, manual_year=manual_year if mode == "manual" else None, manual_month=manual_month if mode == "manual" else None)
            else:
                pdf_path, summary = generate_pdf(settings, group, manual_year=manual_year if mode == "manual" else None, manual_month=manual_month if mode == "manual" else None)
                generated_file = pdf_path
                flash(f"PDF erzeugt: {pdf_path.name}", "success")
                if action == "send":
                    send_email_with_attachment(settings, group, pdf_path, summary)
                    flash("E-Mail versendet.", "success")
        except Exception as err:
            flash(f"Bericht konnte nicht verarbeitet werden: {err}", "error")
    current_year = datetime.today().year
    years = list(range(current_year - 3, current_year + 2))
    months = list(range(1,13))
    return render_template("report.html", settings=settings, years=years, months=months, generated_file=generated_file, preview_html=preview_html)

if __name__ == "__main__":
    ensure_dirs()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=APP_PORT)
