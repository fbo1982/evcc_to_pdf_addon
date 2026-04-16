import json
import os
import smtplib
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
from weasyprint import HTML
from werkzeug.middleware.proxy_fix import ProxyFix

APP_PORT = 8099
SETTINGS_DIR = Path("/addon_config/evcc_to_pdf")
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
RUNTIME_STATE_FILE = SETTINGS_DIR / "runtime_state.json"
REPORT_DIR = Path("/share/evcc-pdfs")
OPTIONS_FILE = Path("/data/options.json")

DEFAULT_SETTINGS = {
    "evcc": {"url": "", "password": ""},
    "sender": {"name": "", "street": "", "zip": "", "city": "", "email": ""},
    "smtp": {"host": "", "port": 587, "user": "", "password": "", "tls": True},
    "scheduler": {"enabled": False, "day_of_month": 1, "time": "07:00"},
    "reporting": {
        "grid_price": 0.0,
        "billing_mode": "monthly",
        "default_email_body": "",
        "default_template_key": "default",
    },
    "cached_assets": {"assets": []},
    "groups": [],
    "templates": {
        "default": {
            "label": "Standard HTML",
            "content": """<!doctype html>
<html lang=\"de\">
<head>
<meta charset=\"utf-8\">
<style>
body { font-family: Arial, sans-serif; font-size: 12px; color: #222; }
h1,h2,h3 { margin: 0 0 8px 0; }
.section { margin-bottom: 18px; }
.meta-table td { padding: 2px 10px 2px 0; vertical-align: top; }
table.positions { width: 100%; border-collapse: collapse; margin-top: 12px; }
table.positions th, table.positions td { border: 1px solid #ccc; padding: 6px; text-align: left; }
table.positions th { background: #f2f2f2; }
.summary { margin-top: 12px; }
.small { color: #666; font-size: 10px; }
</style>
</head>
<body>
  <div class=\"section\">
    <h1>EVCC Abrechnung</h1>
    <div class=\"small\">Erstellt am {{ generated_at }}</div>
  </div>

  <div class=\"section\">
    <table class=\"meta-table\">
      <tr><td><strong>Gruppe</strong></td><td>{{ group_name }}</td></tr>
      <tr><td><strong>Zeitraum</strong></td><td>{{ period_label }}</td></tr>
      <tr><td><strong>Empfänger</strong></td><td>{{ recipient_company }}{% if recipient_name %} / {{ recipient_name }}{% endif %}</td></tr>
      <tr><td><strong>Absender</strong></td><td>{{ sender_name }}</td></tr>
      <tr><td><strong>Assets</strong></td><td>{{ assets_label }}</td></tr>
    </table>
  </div>

  <div class=\"section\">
    {{ positions_table | safe }}
  </div>

  <div class=\"section summary\">
    <p><strong>Gesamtenergie:</strong> {{ total_energy }} kWh</p>
    <p><strong>Gesamtbetrag:</strong> {{ total_price }} €</p>
  </div>
</body>
</html>"""
        }
    },
}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "evcc-to-pdf-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
scheduler_started = False


def ensure_dirs() -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_addon_options() -> dict:
    if not OPTIONS_FILE.exists():
        return {
            "mqtt_host": "core-mosquitto",
            "mqtt_port": 1883,
            "mqtt_user": "",
            "mqtt_password": "",
            "mqtt_base_topic": "/evcc2pdf",
        }
    with OPTIONS_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "mqtt_host": str(data.get("mqtt_host", "core-mosquitto")),
        "mqtt_port": int(data.get("mqtt_port", 1883) or 1883),
        "mqtt_user": str(data.get("mqtt_user", "")),
        "mqtt_password": str(data.get("mqtt_password", "")),
        "mqtt_base_topic": str(data.get("mqtt_base_topic", "/evcc2pdf") or "/evcc2pdf"),
    }


def mqtt_topic(name: str) -> str:
    base = load_addon_options()["mqtt_base_topic"].rstrip("/")
    return f"{base}/{name.lstrip('/')}"


def local_raw_settings() -> dict | None:
    ensure_dirs()
    if SETTINGS_FILE.exists():
        with SETTINGS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def local_runtime_state() -> dict:
    ensure_dirs()
    if RUNTIME_STATE_FILE.exists():
        try:
            return json.loads(RUNTIME_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_auto_send": {}}


def save_runtime_state(state: dict) -> None:
    ensure_dirs()
    RUNTIME_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def extract_name(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("title", "name", "vehicle", "label", "id"):
            if key in value and value[key]:
                return str(value[key]).strip()
        return ""
    if value is None:
        return ""
    return str(value).strip()


def normalize_assets(items) -> list[str]:
    out = []
    seen = set()
    for item in items or []:
        name = extract_name(item)
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def parse_bool(value) -> bool:
    return str(value).lower() in {"1", "true", "on", "yes"}


def normalize_group(group: dict) -> dict:
    template_choice = str(group.get("template_choice", "default") or "default").strip() or "default"
    return {
        "id": str(group.get("id") or uuid.uuid4()),
        "name": str(group.get("name", "")).strip(),
        "recipient_name": str(group.get("recipient_name", "")).strip(),
        "recipient_company": str(group.get("recipient_company", "")).strip(),
        "recipient_email": str(group.get("recipient_email", "")).strip(),
        "recipient_street": str(group.get("recipient_street", "")).strip(),
        "recipient_zip": str(group.get("recipient_zip", "")).strip(),
        "recipient_city": str(group.get("recipient_city", "")).strip(),
        "assets": normalize_assets(group.get("assets", [])),
        "grid_price_override": str(group.get("grid_price_override", "")).strip(),
        "active": bool(group.get("active", False)),
        "sender_mode": str(group.get("sender_mode", "default") or "default"),
        "custom_sender": {
            "name": str(group.get("custom_sender", {}).get("name", "")).strip(),
            "street": str(group.get("custom_sender", {}).get("street", "")).strip(),
            "zip": str(group.get("custom_sender", {}).get("zip", "")).strip(),
            "city": str(group.get("custom_sender", {}).get("city", "")).strip(),
            "email": str(group.get("custom_sender", {}).get("email", "")).strip(),
        },
        "template_choice": template_choice,
        "email_body_mode": str(group.get("email_body_mode", "default") or "default"),
        "custom_email_body": str(group.get("custom_email_body", "") or ""),
        "billing_mode_source": str(group.get("billing_mode_source", "default") or "default"),
        "custom_billing_mode": str(group.get("custom_billing_mode", "monthly") or "monthly"),
        "custom_send_day": int(group.get("custom_send_day", 1) or 1),
    }


def normalize_settings(loaded: dict | None) -> dict:
    settings = deepcopy(DEFAULT_SETTINGS)
    loaded = loaded or {}
    for section in ("evcc", "sender", "smtp", "scheduler", "reporting"):
        if isinstance(loaded.get(section), dict):
            settings[section].update(loaded[section])
    settings["cached_assets"]["assets"] = normalize_assets((loaded.get("cached_assets") or {}).get("assets", loaded.get("cached_assets", {}).get("vehicles", loaded.get("cached_vehicles", []))))
    raw_groups = loaded.get("groups", [])
    if isinstance(raw_groups, list):
        settings["groups"] = [normalize_group(g) for g in raw_groups if isinstance(g, dict)]
    raw_templates = loaded.get("templates", {})
    if isinstance(raw_templates, dict):
        templates = {}
        for key, value in raw_templates.items():
            if isinstance(value, dict):
                templates[str(key)] = {
                    "label": str(value.get("label", key)).strip() or str(key),
                    "content": str(value.get("content", "") or ""),
                }
            elif isinstance(value, str):
                templates[str(key)] = {"label": str(key), "content": value}
        if templates:
            settings["templates"] = templates
    if settings["reporting"]["default_template_key"] not in settings["templates"]:
        settings["reporting"]["default_template_key"] = next(iter(settings["templates"].keys()))
    return settings


def save_local_settings(settings: dict) -> None:
    ensure_dirs()
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def mqtt_fetch_settings() -> dict | None:
    opts = load_addon_options()
    payload_holder = {"payload": None}

    def on_connect(client, userdata, flags, reason_code, properties=None):
        client.subscribe(mqtt_topic("config/settings"))

    def on_message(client, userdata, msg):
        try:
            payload_holder["payload"] = msg.payload.decode("utf-8")
        except Exception:
            payload_holder["payload"] = None
        client.disconnect()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if opts["mqtt_user"]:
        client.username_pw_set(opts["mqtt_user"], opts["mqtt_password"])
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(opts["mqtt_host"], opts["mqtt_port"], 10)
    client.loop_start()
    timeout = time.time() + 2.0
    while time.time() < timeout and payload_holder["payload"] is None:
        time.sleep(0.05)
    client.loop_stop()
    if payload_holder["payload"]:
        try:
            return json.loads(payload_holder["payload"])
        except json.JSONDecodeError:
            return None
    return None


def mqtt_publish_settings(settings: dict) -> None:
    opts = load_addon_options()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if opts["mqtt_user"]:
        client.username_pw_set(opts["mqtt_user"], opts["mqtt_password"])
    client.connect(opts["mqtt_host"], opts["mqtt_port"], 10)
    client.publish(mqtt_topic("config/settings"), json.dumps(settings, ensure_ascii=False), qos=1, retain=True)
    client.disconnect()


def load_settings() -> dict:
    local = normalize_settings(local_raw_settings())
    try:
        remote_raw = mqtt_fetch_settings()
    except Exception:
        remote_raw = None
    if remote_raw:
        remote = normalize_settings(remote_raw)
        save_local_settings(remote)
        return remote
    save_local_settings(local)
    try:
        mqtt_publish_settings(local)
    except Exception:
        pass
    return local


def save_settings(settings: dict) -> None:
    normalized = normalize_settings(settings)
    save_local_settings(normalized)
    try:
        mqtt_publish_settings(normalized)
    except Exception:
        pass


def ingress_path() -> str:
    return request.headers.get("X-Ingress-Path", "").rstrip("/")


def evcc_session(settings: dict) -> requests.Session:
    session = requests.Session()
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    password = str(settings["evcc"].get("password", ""))
    if not base_url:
        raise ValueError("EVCC-URL ist leer.")
    if password:
        response = session.post(f"{base_url}/api/auth/login", json={"password": password}, timeout=15)
        response.raise_for_status()
    return session


def fetch_sessions(settings: dict) -> list[dict]:
    session = evcc_session(settings)
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    response = session.get(f"{base_url}/api/sessions", timeout=30)
    response.raise_for_status()
    data = response.json()
    result = data["result"] if isinstance(data, dict) and "result" in data else data
    if not isinstance(result, list):
        raise ValueError("Unerwartete Antwort von EVCC bei /api/sessions")
    return result


def fetch_state(settings: dict) -> dict:
    session = evcc_session(settings)
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    response = session.get(f"{base_url}/api/state", timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["result"] if isinstance(data, dict) and "result" in data else data


def fetch_available_assets(settings: dict) -> list[str]:
    assets = []
    seen = set()
    state = fetch_state(settings)
    raw_vehicles = state.get("vehicles", [])
    if isinstance(raw_vehicles, dict):
        raw_vehicles = list(raw_vehicles.values())
    for item in raw_vehicles:
        name = extract_name(item)
        if name and name not in seen:
            seen.add(name)
            assets.append(name)
    for key in ("tags", "cards", "rfid", "tokens"):
        raw_cards = state.get(key, [])
        if isinstance(raw_cards, dict):
            raw_cards = list(raw_cards.values())
        if isinstance(raw_cards, list):
            for item in raw_cards:
                name = extract_name(item)
                if name and name not in seen:
                    seen.add(name)
                    assets.append(name)
    try:
        for s in fetch_sessions(settings):
            name = extract_name(s.get("vehicle"))
            if name and name not in seen:
                seen.add(name)
                assets.append(name)
    except Exception:
        pass
    return sorted(assets, key=lambda x: x.lower())


def write_assets_cache(settings: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    assets = settings["cached_assets"].get("assets", [])
    (REPORT_DIR / "available_assets.txt").write_text("\n".join(assets), encoding="utf-8")


def billing_mode_label(value: str) -> str:
    return {
        "monthly": "Monatlich",
        "quarterly": "Quartal",
        "semiannual": "Halbjährlich",
        "annual": "Jährlich",
    }.get(value, value)


def last_completed_period(billing_mode: str, ref: datetime | None = None) -> tuple[datetime, datetime, str]:
    ref = ref or datetime.now()
    if billing_mode == "monthly":
        first_this_month = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_this_month
        start = (first_this_month - timedelta(days=1)).replace(day=1)
        stamp = start.strftime("%Y-%m")
    elif billing_mode == "quarterly":
        current_q_start_month = ((ref.month - 1) // 3) * 3 + 1
        current_q_start = datetime(ref.year, current_q_start_month, 1)
        end = current_q_start
        prev_end = current_q_start - timedelta(days=1)
        start_month = ((prev_end.month - 1) // 3) * 3 + 1
        start = datetime(prev_end.year, start_month, 1)
        stamp = f"{start.year}-Q{((start.month - 1)//3)+1}"
    elif billing_mode == "semiannual":
        current_h_start_month = 1 if ref.month <= 6 else 7
        current_h_start = datetime(ref.year, current_h_start_month, 1)
        end = current_h_start
        prev_end = current_h_start - timedelta(days=1)
        start_month = 1 if prev_end.month <= 6 else 7
        start = datetime(prev_end.year, start_month, 1)
        stamp = f"{start.year}-H{'1' if start.month == 1 else '2'}"
    else:
        end = datetime(ref.year, 1, 1)
        start = datetime(ref.year - 1, 1, 1)
        stamp = f"{start.year}"
    return start, end, stamp


def manual_period(billing_mode: str, year: int, month: int) -> tuple[datetime, datetime, str]:
    if billing_mode == "monthly":
        start = datetime(year, month, 1)
        end = datetime(year + (month // 12), ((month % 12) + 1), 1)
        stamp = start.strftime("%Y-%m")
    elif billing_mode == "quarterly":
        qstart = ((month - 1) // 3) * 3 + 1
        start = datetime(year, qstart, 1)
        em = qstart + 3
        ey = year + (1 if em > 12 else 0)
        em = ((em - 1) % 12) + 1
        end = datetime(ey, em, 1)
        stamp = f"{start.year}-Q{((start.month - 1)//3)+1}"
    elif billing_mode == "semiannual":
        sstart = 1 if month <= 6 else 7
        start = datetime(year, sstart, 1)
        em = sstart + 6
        ey = year + (1 if em > 12 else 0)
        em = ((em - 1) % 12) + 1
        end = datetime(ey, em, 1)
        stamp = f"{start.year}-H{'1' if start.month == 1 else '2'}"
    else:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        stamp = f"{year}"
    return start, end, stamp


def get_group_billing_mode(settings: dict, group: dict) -> str:
    return group.get("custom_billing_mode") if group.get("billing_mode_source") == "custom" else settings["reporting"]["billing_mode"]


def get_group_send_day(settings: dict, group: dict) -> int:
    return int(group.get("custom_send_day", 1) or 1) if group.get("billing_mode_source") == "custom" else int(settings["scheduler"].get("day_of_month", 1) or 1)


def get_grid_price(settings: dict, group: dict) -> float:
    price = group.get("grid_price_override", "")
    try:
        return float(str(price).replace(",", ".")) if str(price).strip() else float(settings["reporting"]["grid_price"])
    except Exception:
        return float(settings["reporting"]["grid_price"])


def get_sender(settings: dict, group: dict) -> dict:
    if group.get("sender_mode") == "custom":
        return group.get("custom_sender", {})
    return settings.get("sender", {})


def get_email_body(settings: dict, group: dict, summary: dict) -> str:
    raw = group.get("custom_email_body", "") if group.get("email_body_mode") == "custom" else settings["reporting"].get("default_email_body", "")
    if not raw.strip():
        raw = "Hallo,\n\nim Anhang befindet sich die EVCC-Abrechnung für {{ period_label }}.\n\nViele Grüße\n{{ sender_name }}"
    return Template(raw).render(**summary)


def get_template_key(settings: dict, group: dict) -> str:
    choice = str(group.get("template_choice", "default") or "default")
    if choice == "default":
        return settings["reporting"]["default_template_key"]
    if choice not in settings["templates"]:
        return settings["reporting"]["default_template_key"]
    return choice


def format_period_label(start: datetime, end: datetime, billing_mode: str) -> str:
    return f"{billing_mode_label(billing_mode)} {start.strftime('%d.%m.%Y')} bis {(end - timedelta(days=1)).strftime('%d.%m.%Y')}"


def build_positions_table(df: pd.DataFrame) -> str:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            f"<tr><td>{row['created'].strftime('%d.%m.%Y %H:%M')}</td><td>{row.get('vehicle','')}</td><td>{float(row.get('chargedEnergy',0)):.2f}</td><td>{float(row.get('price',0)):.2f}</td></tr>"
        )
    return (
        "<table class='positions'><thead><tr><th>Datum</th><th>Asset</th><th>Energie (kWh)</th><th>Preis (€)</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def collect_report_data(settings: dict, group: dict, start: datetime, end: datetime, period_stamp: str):
    sessions = fetch_sessions(settings)
    df = pd.DataFrame(sessions)
    if df.empty:
        raise ValueError("Keine Sessions gefunden.")
    if "created" not in df.columns or "chargedEnergy" not in df.columns:
        raise ValueError("EVCC-Sessions enthalten nicht die erwarteten Felder.")
    df["created"] = pd.to_datetime(df["created"], errors="coerce", utc=True).dt.tz_localize(None)
    df = df.dropna(subset=["created"])
    df = df[(df["created"] >= start) & (df["created"] < end)]
    selected = set(group.get("assets", []))
    if "vehicle" in df.columns and selected:
        df["vehicle"] = df["vehicle"].fillna("").astype(str)
        df = df[df["vehicle"].isin(selected)]
    if df.empty:
        raise ValueError("Keine Sessions für die Auswahl gefunden.")
    df["chargedEnergy"] = pd.to_numeric(df["chargedEnergy"], errors="coerce").fillna(0)
    grid_price = get_grid_price(settings, group)
    df["price"] = (df["chargedEnergy"] * grid_price).round(2)
    df = df.sort_values("created", ascending=True)
    billing_mode = get_group_billing_mode(settings, group)
    sender = get_sender(settings, group)
    summary = {
        "group_name": group["name"],
        "recipient_name": group.get("recipient_name", ""),
        "recipient_company": group.get("recipient_company", ""),
        "recipient_email": group.get("recipient_email", ""),
        "sender_name": sender.get("name", ""),
        "sender_email": sender.get("email", ""),
        "period_label": format_period_label(start, end, billing_mode),
        "period_stamp": period_stamp,
        "assets_label": ", ".join(group.get("assets", [])),
        "grid_price": f"{grid_price:.2f}",
        "total_energy": f"{float(df['chargedEnergy'].sum()):.2f}",
        "total_price": f"{float(df['price'].sum()):.2f}",
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "positions_table": build_positions_table(df),
    }
    return df, summary


def create_report_files(settings: dict, group: dict, start: datetime, end: datetime, period_stamp: str):
    df, summary = collect_report_data(settings, group, start, end, period_stamp)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_group = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in group["name"]).strip("_") or "gruppe"
    base_name = f"evcc_{safe_group}_{period_stamp}"
    txt_file = REPORT_DIR / f"{base_name}.txt"
    pdf_file = REPORT_DIR / f"{base_name}.pdf"

    txt_lines = [
        "EVCC Abrechnung",
        "================",
        f"Gruppe: {summary['group_name']}",
        f"Zeitraum: {summary['period_label']}",
        f"Netzstrompreis: {summary['grid_price']} €/kWh",
        "",
    ]
    for _, row in df.iterrows():
        txt_lines.append(f"{row['created'].strftime('%Y-%m-%d %H:%M')} | {row.get('vehicle','')} | {float(row.get('chargedEnergy',0)):.2f} kWh | {float(row.get('price',0)):.2f} €")
    txt_lines.extend(["", f"Gesamtenergie: {summary['total_energy']} kWh", f"Gesamtbetrag: {summary['total_price']} €"])
    txt_file.write_text("\n".join(txt_lines), encoding="utf-8")

    template_key = get_template_key(settings, group)
    template_html = settings["templates"][template_key]["content"]
    rendered_html = Template(template_html).render(**summary)
    HTML(string=rendered_html).write_pdf(str(pdf_file))

    return txt_file, pdf_file, summary


def send_report_email(settings: dict, group: dict, pdf_file: Path, summary: dict):
    smtp = settings["smtp"]
    if not smtp.get("host") or not group.get("recipient_email"):
        raise ValueError("SMTP oder Empfänger-E-Mail nicht vollständig konfiguriert.")
    sender = get_sender(settings, group)
    body = get_email_body(settings, group, summary)
    msg = EmailMessage()
    msg["Subject"] = f"EVCC Abrechnung - {summary['period_label']} - {group['name']}"
    msg["From"] = sender.get("email") or smtp.get("user")
    msg["To"] = group["recipient_email"]
    msg.set_content(body)
    msg.add_attachment(pdf_file.read_bytes(), maintype="application", subtype="pdf", filename=pdf_file.name)
    server = smtplib.SMTP(smtp["host"], int(smtp.get("port", 587)), timeout=30)
    try:
        server.ehlo()
        if smtp.get("tls"):
            server.starttls()
            server.ehlo()
        if smtp.get("user"):
            server.login(smtp["user"], smtp.get("password", ""))
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def auto_send_group(settings: dict, group: dict):
    billing_mode = get_group_billing_mode(settings, group)
    start, end, stamp = last_completed_period(billing_mode)
    _, pdf_file, summary = create_report_files(settings, group, start, end, stamp)
    send_report_email(settings, group, pdf_file, summary)
    state = local_runtime_state()
    state.setdefault("last_auto_send", {})[group["id"]] = stamp
    save_runtime_state(state)


def scheduler_loop():
    while True:
        try:
            settings = load_settings()
            if settings["scheduler"].get("enabled"):
                now = datetime.now()
                try:
                    target_h, target_m = [int(x) for x in str(settings["scheduler"].get("time", "07:00")).split(":", 1)]
                except Exception:
                    target_h, target_m = 7, 0
                state = local_runtime_state()
                for group in settings.get("groups", []):
                    if not group.get("active"):
                        continue
                    send_day = get_group_send_day(settings, group)
                    if now.day != send_day:
                        continue
                    if (now.hour, now.minute) < (target_h, target_m):
                        continue
                    billing_mode = get_group_billing_mode(settings, group)
                    _, _, stamp = last_completed_period(billing_mode, now)
                    if state.setdefault("last_auto_send", {}).get(group["id"]) == stamp:
                        continue
                    try:
                        auto_send_group(settings, group)
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(60)


def start_scheduler_once():
    global scheduler_started
    if scheduler_started:
        return
    scheduler_started = True
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()


@app.context_processor
def inject_common():
    settings = load_settings()
    return {
        "settings": settings,
        "ingress_path": ingress_path(),
        "all_assets": settings.get("cached_assets", {}).get("assets", []),
    }


@app.route("/")
def dashboard():
    start_scheduler_once()
    return render_template("dashboard.html", title="Dashboard")


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    settings = load_settings()
    if request.method == "POST":
        settings["evcc"]["url"] = request.form.get("evcc_url", "").strip()
        settings["evcc"]["password"] = request.form.get("evcc_password", "").strip()
        settings["sender"]["name"] = request.form.get("sender_name", "").strip()
        settings["sender"]["street"] = request.form.get("sender_street", "").strip()
        settings["sender"]["zip"] = request.form.get("sender_zip", "").strip()
        settings["sender"]["city"] = request.form.get("sender_city", "").strip()
        settings["sender"]["email"] = request.form.get("sender_email", "").strip()
        settings["smtp"]["host"] = request.form.get("smtp_host", "").strip()
        try:
            settings["smtp"]["port"] = int(request.form.get("smtp_port", "587") or 587)
        except Exception:
            settings["smtp"]["port"] = 587
        settings["smtp"]["user"] = request.form.get("smtp_user", "").strip()
        settings["smtp"]["password"] = request.form.get("smtp_password", "").strip()
        settings["smtp"]["tls"] = parse_bool(request.form.get("smtp_tls"))
        settings["scheduler"]["enabled"] = parse_bool(request.form.get("scheduler_enabled"))
        try:
            settings["scheduler"]["day_of_month"] = int(request.form.get("scheduler_day_of_month", "1") or 1)
        except Exception:
            settings["scheduler"]["day_of_month"] = 1
        settings["scheduler"]["time"] = request.form.get("scheduler_time", "07:00").strip() or "07:00"
        try:
            settings["reporting"]["grid_price"] = float(str(request.form.get("grid_price", "0")).replace(",", "."))
        except Exception:
            settings["reporting"]["grid_price"] = 0.0
        settings["reporting"]["billing_mode"] = request.form.get("billing_mode", "monthly").strip() or "monthly"
        settings["reporting"]["default_email_body"] = request.form.get("default_email_body", "")
        settings["reporting"]["default_template_key"] = request.form.get("default_template_key", settings["reporting"]["default_template_key"])
        save_settings(settings)
        flash("Einstellungen gespeichert.", "success")
        return redirect(f"{ingress_path()}/settings")
    return render_template("settings.html", title="Einstellungen")


@app.route("/refresh_vehicles", methods=["POST"])
def refresh_vehicles():
    settings = load_settings()
    try:
        assets = fetch_available_assets(settings)
        settings["cached_assets"]["assets"] = assets
        save_settings(settings)
        write_assets_cache(settings)
        flash(f"{len(assets)} Assets geladen.", "success")
    except Exception as err:
        flash(f"Fahrzeuge konnten nicht geladen werden: {err}", "error")
    return redirect(f"{ingress_path()}/groups")


@app.route("/groups", methods=["GET", "POST"])
def groups_page():
    settings = load_settings()
    if request.method == "POST":
        form_action = request.form.get("form_action", "").strip()
        if form_action == "delete":
            group_id = request.form.get("group_id", "").strip()
            settings["groups"] = [g for g in settings["groups"] if g.get("id") != group_id]
            save_settings(settings)
            flash("Gruppe gelöscht.", "success")
            return redirect(f"{ingress_path()}/groups")
        if form_action == "toggle_active":
            group_id = request.form.get("group_id", "").strip()
            grp = next((g for g in settings["groups"] if g.get("id") == group_id), None)
            if grp:
                grp["active"] = parse_bool(request.form.get("active"))
                save_settings(settings)
                flash("Status gespeichert.", "success")
            return redirect(f"{ingress_path()}/groups")

        group_id = request.form.get("group_id", "").strip() or str(uuid.uuid4())
        group_data = normalize_group({
            "id": group_id,
            "name": request.form.get("name", "").strip(),
            "recipient_name": request.form.get("recipient_name", "").strip(),
            "recipient_company": request.form.get("recipient_company", "").strip(),
            "recipient_email": request.form.get("recipient_email", "").strip(),
            "recipient_street": request.form.get("recipient_street", "").strip(),
            "recipient_zip": request.form.get("recipient_zip", "").strip(),
            "recipient_city": request.form.get("recipient_city", "").strip(),
            "assets": request.form.getlist("assets"),
            "grid_price_override": request.form.get("grid_price_override", "").strip(),
            "active": parse_bool(request.form.get("active")),
            "sender_mode": request.form.get("sender_mode", "default").strip(),
            "custom_sender": {
                "name": request.form.get("custom_sender_name", "").strip(),
                "street": request.form.get("custom_sender_street", "").strip(),
                "zip": request.form.get("custom_sender_zip", "").strip(),
                "city": request.form.get("custom_sender_city", "").strip(),
                "email": request.form.get("custom_sender_email", "").strip(),
            },
            "template_choice": request.form.get("template_choice", "default").strip() or "default",
            "email_body_mode": request.form.get("email_body_mode", "default").strip(),
            "custom_email_body": request.form.get("custom_email_body", ""),
            "billing_mode_source": request.form.get("billing_mode_source", "default").strip(),
            "custom_billing_mode": request.form.get("custom_billing_mode", "monthly").strip(),
            "custom_send_day": request.form.get("custom_send_day", "1").strip(),
        })
        existing = next((g for g in settings["groups"] if g.get("id") == group_id), None)
        if existing:
            existing.update(group_data)
            flash("Gruppe aktualisiert.", "success")
        else:
            settings["groups"].append(group_data)
            flash("Gruppe angelegt.", "success")
        save_settings(settings)
        return redirect(f"{ingress_path()}/groups")

    edit_group_id = request.args.get("edit", "").strip()
    edit_group = next((g for g in settings["groups"] if g.get("id") == edit_group_id), None)
    return render_template("groups.html", title="Gruppen", edit_group=edit_group)


@app.route("/templates", methods=["GET", "POST"])
def templates_page():
    settings = load_settings()
    if request.method == "POST":
        action = request.form.get("action", "").strip()
        if action == "delete":
            key = request.form.get("template_key", "").strip()
            if settings["reporting"]["default_template_key"] == key:
                flash("Das aktuell gesetzte Default-Template kann nicht gelöscht werden.", "error")
            elif key in settings["templates"]:
                del settings["templates"][key]
                save_settings(settings)
                flash("Template gelöscht.", "success")
            return redirect(f"{ingress_path()}/templates")
        if action == "set_default":
            key = request.form.get("template_key", "").strip()
            if key in settings["templates"]:
                settings["reporting"]["default_template_key"] = key
                save_settings(settings)
                flash("Default-Template gesetzt.", "success")
            return redirect(f"{ingress_path()}/templates")
        if action in {"create", "update"}:
            original_key = request.form.get("original_template_key", "").strip()
            key = request.form.get("template_key", "").strip()
            label = request.form.get("template_label", "").strip()
            content = request.form.get("template_content", "")
            uploaded = request.files.get("template_file")
            if uploaded and uploaded.filename:
                content = uploaded.read().decode("utf-8", errors="replace")
                if not key:
                    key = Path(uploaded.filename).stem.lower().replace(" ", "_")
                if not label:
                    label = uploaded.filename
            if not key:
                flash("Template-Key fehlt.", "error")
                return redirect(f"{ingress_path()}/templates")
            if action == "update" and original_key and original_key != key and original_key in settings["templates"]:
                old = settings["templates"].pop(original_key)
                if settings["reporting"]["default_template_key"] == original_key:
                    settings["reporting"]["default_template_key"] = key
                if not content:
                    content = old.get("content", "")
                if not label:
                    label = old.get("label", key)
            old_existing = settings["templates"].get(key, {})
            settings["templates"][key] = {
                "label": label or old_existing.get("label", key),
                "content": content if content else old_existing.get("content", ""),
            }
            save_settings(settings)
            flash("Template gespeichert.", "success")
            return redirect(f"{ingress_path()}/templates")
    edit_key = request.args.get("edit", "").strip()
    edit_template = settings["templates"].get(edit_key) if edit_key else None
    return render_template("templates.html", title="HTML Templates", edit_key=edit_key, edit_template=edit_template)


@app.route("/report", methods=["GET", "POST"])
def report_page():
    settings = load_settings()
    generated_file = None
    generated_pdf = None
    if request.method == "POST":
        group = next((g for g in settings["groups"] if g.get("id") == request.form.get("group_id", "").strip()), None)
        if not group:
            flash("Gruppe nicht gefunden.", "error")
            return redirect(f"{ingress_path()}/report")
        billing_mode = get_group_billing_mode(settings, group)
        mode = request.form.get("mode", "previous_period")
        if mode == "manual":
            year = int(request.form.get("year") or datetime.now().year)
            month = int(request.form.get("month") or datetime.now().month)
            start, end, stamp = manual_period(billing_mode, year, month)
        else:
            start, end, stamp = last_completed_period(billing_mode)
        try:
            txt_file, pdf_file, summary = create_report_files(settings, group, start, end, stamp)
            generated_file = txt_file
            generated_pdf = pdf_file
            if request.form.get("action") == "send":
                send_report_email(settings, group, pdf_file, summary)
                flash(f"PDF erzeugt und E-Mail versendet: {pdf_file.name}", "success")
            else:
                flash(f"PDF erzeugt: {pdf_file.name}", "success")
        except Exception as err:
            flash(f"Bericht konnte nicht erzeugt werden: {err}", "error")
    current_year = datetime.today().year
    years = list(range(current_year - 3, current_year + 2))
    months = list(range(1, 13))
    return render_template("report.html", title="Testbericht", years=years, months=months, generated_file=generated_file, generated_pdf=generated_pdf)


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    ensure_dirs()
    start_scheduler_once()
    app.run(host="0.0.0.0", port=APP_PORT)
