
import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from flask import Flask, flash, redirect, render_template, request
from paho.mqtt import publish, subscribe

APP_PORT = 8099
APP_DIR = Path("/addon_config/evcc_to_pdf")
FALLBACK_UI_FILE = APP_DIR / "ui_fallback.json"
SECRETS_FILE = APP_DIR / "secrets.json"
REPORT_DIR = Path("/share/evcc-pdfs")
OPTIONS_FILE = Path("/data/options.json")

DEFAULT_HTML = (
    "<html><body>"
    "<h1>{{ group.name }}</h1>"
    "<p>{{ recipient.recipient_company }}</p>"
    "<p>{{ period_label }}</p>"
    "<p>{{ summary.total_price }} EUR</p>"
    "</body></html>"
)

DEFAULT_UI = {
    "evcc": {
        "url": "",
    },
    "sender": {
        "name": "",
        "street": "",
        "zip": "",
        "city": "",
        "email": "",
    },
    "smtp": {
        "host": "",
        "port": 587,
        "user": "",
        "tls": True,
    },
    "scheduler": {
        "enabled": False,
        "day_of_month": 1,
        "time": "07:00",
    },
    "reporting": {
        "grid_price": 0.0,
        "billing_mode_default": "monthly",
        "default_template_id": "default",
        "default_email_body": "Hallo,\n\nanbei die Abrechnung.\n\nViele Grüße",
    },
    "cached_vehicles": [],
    "groups": [],
    "templates": {
        "default": {
            "id": "default",
            "label": "Standard HTML",
            "content": DEFAULT_HTML,
        }
    },
}

DEFAULT_SECRETS = {
    "evcc_password": "",
    "smtp_password": "",
}


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "evcc-to-pdf-secret")


def ensure_dirs() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def read_addon_options() -> dict:
    defaults = {
        "mqtt_host": "core-mosquitto",
        "mqtt_port": 1883,
        "mqtt_user": "",
        "mqtt_password": "",
        "mqtt_base_topic": "/evcc2pdf",
    }
    if OPTIONS_FILE.exists():
        try:
            with OPTIONS_FILE.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
                defaults.update(loaded)
        except Exception:
            pass
    return defaults


def mqtt_base_topic() -> str:
    base = str(read_addon_options().get("mqtt_base_topic", "/evcc2pdf")).strip() or "/evcc2pdf"
    return base.rstrip("/")


def topic_ui() -> str:
    return f"{mqtt_base_topic()}/config/ui"


def mqtt_auth():
    opts = read_addon_options()
    user = str(opts.get("mqtt_user", "") or "")
    password = str(opts.get("mqtt_password", "") or "")
    if user:
        return {"username": user, "password": password}
    return None


def mqtt_connection_kwargs() -> dict:
    opts = read_addon_options()
    return {
        "hostname": str(opts.get("mqtt_host", "core-mosquitto")),
        "port": int(opts.get("mqtt_port", 1883)),
        "auth": mqtt_auth(),
    }


def load_local_fallback() -> dict:
    ensure_dirs()
    if not FALLBACK_UI_FILE.exists():
        return deepcopy(DEFAULT_UI)
    try:
        with FALLBACK_UI_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return deepcopy(DEFAULT_UI)


def save_local_fallback(data: dict) -> None:
    ensure_dirs()
    with FALLBACK_UI_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_local_secrets() -> dict:
    ensure_dirs()
    if not SECRETS_FILE.exists():
        save_local_secrets(deepcopy(DEFAULT_SECRETS))
        return deepcopy(DEFAULT_SECRETS)
    try:
        with SECRETS_FILE.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
            merged = deepcopy(DEFAULT_SECRETS)
            merged.update(loaded)
            return merged
    except Exception:
        return deepcopy(DEFAULT_SECRETS)


def save_local_secrets(data: dict) -> None:
    ensure_dirs()
    with SECRETS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def deep_merge(base: dict, incoming: dict) -> dict:
    result = deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def normalize_template_id(value: str) -> str:
    value = (value or "").strip().lower()
    value = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return value.strip("_") or str(uuid.uuid4())


def parse_bool(value) -> bool:
    return str(value).lower() in {"1", "true", "on", "yes"}


def get_previous_month() -> tuple[int, int]:
    first = datetime.today().replace(day=1)
    prev = first - timedelta(days=1)
    return prev.year, prev.month


def extract_name(item) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("title", "name", "vehicle", "idTag", "uid", "displayName", "label"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def is_card_name(name: str) -> bool:
    lowered = name.lower()
    return "ladekarte" in lowered or "gästeladen" in lowered or "guest" in lowered


def normalize_vehicle_entry(item) -> dict:
    name = extract_name(item)
    if not name:
        return {"name": "", "kind": "vehicle"}
    return {"name": name, "kind": "card" if is_card_name(name) else "vehicle"}


def collect_named_entries(obj) -> list[dict]:
    results = []
    if isinstance(obj, list):
        for entry in obj:
            norm = normalize_vehicle_entry(entry)
            if norm["name"]:
                results.append(norm)
    elif isinstance(obj, dict):
        for key in ("title", "name", "vehicle", "idTag", "uid", "displayName", "label"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                results.append(normalize_vehicle_entry(value))
                break
        for value in obj.values():
            if isinstance(value, (dict, list)):
                results.extend(collect_named_entries(value))
    return results


def normalize_ui_data(data: dict) -> dict:
    merged = deep_merge(DEFAULT_UI, data or {})

    merged["cached_vehicles"] = [normalize_vehicle_entry(v) for v in merged.get("cached_vehicles", [])]
    merged["cached_vehicles"] = [v for v in merged["cached_vehicles"] if v.get("name")]

    reporting = deep_merge(DEFAULT_UI["reporting"], merged.get("reporting", {}) or {})
    if reporting.get("billing_mode_default") not in {"monthly", "quarterly", "halfyearly", "yearly"}:
        reporting["billing_mode_default"] = "monthly"
    reporting["default_template_id"] = normalize_template_id(str(reporting.get("default_template_id") or "default"))
    reporting["default_email_body"] = str(reporting.get("default_email_body") or "")
    merged["reporting"] = reporting

    templates = {}
    raw_templates = merged.get("templates", {}) or {}
    items = raw_templates.values() if isinstance(raw_templates, dict) else raw_templates
    for tpl in items:
        if not isinstance(tpl, dict):
            continue
        tpl_id = normalize_template_id(str(tpl.get("id") or tpl.get("label") or "template"))
        templates[tpl_id] = {
            "id": tpl_id,
            "label": str(tpl.get("label") or tpl_id),
            "content": str(tpl.get("content") or ""),
        }
    if "default" not in templates:
        templates["default"] = deepcopy(DEFAULT_UI["templates"]["default"])
    if merged["reporting"]["default_template_id"] not in templates:
        merged["reporting"]["default_template_id"] = "default"
    merged["templates"] = templates

    groups = []
    for g in merged.get("groups", []):
        if not isinstance(g, dict):
            continue

        vehicles = []
        for v in g.get("vehicles", []) or []:
            name = extract_name(v)
            if name:
                vehicles.append(name)

        sender_mode = str(g.get("sender_mode", "default") or "default")
        if sender_mode not in {"default", "custom"}:
            sender_mode = "default"

        html_mode = str(g.get("html_mode", "default") or "default")
        if html_mode not in {"default", "custom"}:
            html_mode = "default"

        email_mode = str(g.get("email_mode", "default") or "default")
        if email_mode not in {"default", "custom"}:
            email_mode = "default"

        billing_mode_scope = str(g.get("billing_mode_scope", "default") or "default")
        if billing_mode_scope not in {"default", "custom"}:
            billing_mode_scope = "default"

        billing_mode_custom = str(g.get("billing_mode_custom", "") or "")
        if billing_mode_custom not in {"monthly", "quarterly", "halfyearly", "yearly"}:
            billing_mode_custom = merged["reporting"]["billing_mode_default"]

        template_id = normalize_template_id(str(g.get("template_id") or "default"))
        if template_id not in merged["templates"]:
            template_id = merged["reporting"]["default_template_id"]

        groups.append({
            "id": str(g.get("id") or uuid.uuid4()),
            "name": str(g.get("name") or ""),
            "recipient_name": str(g.get("recipient_name") or ""),
            "recipient_company": str(g.get("recipient_company") or ""),
            "recipient_email": str(g.get("recipient_email") or ""),
            "recipient_street": str(g.get("recipient_street") or ""),
            "recipient_zip": str(g.get("recipient_zip") or ""),
            "recipient_city": str(g.get("recipient_city") or ""),
            "vehicles": vehicles,
            "grid_price_override": str(g.get("grid_price_override") or ""),
            "sender_mode": sender_mode,
            "custom_sender": {
                "name": str((g.get("custom_sender") or {}).get("name") or ""),
                "email": str((g.get("custom_sender") or {}).get("email") or ""),
                "street": str((g.get("custom_sender") or {}).get("street") or ""),
                "zip": str((g.get("custom_sender") or {}).get("zip") or ""),
                "city": str((g.get("custom_sender") or {}).get("city") or ""),
            },
            "html_mode": html_mode,
            "template_id": template_id,
            "email_mode": email_mode,
            "custom_email_body": str(g.get("custom_email_body") or ""),
            "billing_mode_scope": billing_mode_scope,
            "billing_mode_custom": billing_mode_custom,
        })
    merged["groups"] = groups
    return merged


def load_ui_data() -> dict:
    ensure_dirs()
    data = normalize_ui_data(load_local_fallback())
    try:
        msg = subscribe.simple(topic_ui(), retained=True, timeout=2, **mqtt_connection_kwargs())
        if msg and getattr(msg, "payload", None):
            payload = msg.payload.decode("utf-8")
            if payload:
                mqtt_data = json.loads(payload)
                data = normalize_ui_data(deep_merge(data, mqtt_data))
    except Exception:
        pass
    return data


def save_ui_data(data: dict) -> None:
    data = normalize_ui_data(data)
    save_local_fallback(data)
    try:
        publish.single(
            topic_ui(),
            payload=json.dumps(data, ensure_ascii=False),
            retain=True,
            qos=1,
            **mqtt_connection_kwargs(),
        )
    except Exception:
        pass


def evcc_session(ui: dict) -> requests.Session:
    session = requests.Session()
    base_url = str(ui["evcc"].get("url", "")).rstrip("/")
    secrets = load_local_secrets()
    password = str(secrets.get("evcc_password", "") or "")
    if not base_url:
        raise ValueError("EVCC-URL ist leer.")
    if password:
        login_url = f"{base_url}/api/auth/login"
        response = session.post(login_url, json={"password": password}, timeout=15)
        response.raise_for_status()
    return session


def fetch_sessions(ui: dict) -> list[dict]:
    base_url = str(ui["evcc"].get("url", "")).rstrip("/")
    session = evcc_session(ui)
    response = session.get(f"{base_url}/api/sessions", timeout=30)
    response.raise_for_status()
    data = response.json()
    result = data.get("result") if isinstance(data, dict) else data
    if not isinstance(result, list):
        raise ValueError("Unerwartete Antwort von EVCC bei /api/sessions")
    return result


def fetch_available_vehicles(ui: dict) -> list[dict]:
    base_url = str(ui["evcc"].get("url", "")).rstrip("/")
    session = evcc_session(ui)
    collected = []

    response = session.get(f"{base_url}/api/state", timeout=20)
    response.raise_for_status()
    state = response.json()
    if isinstance(state, dict):
        state_result = state.get("result", state)
        collected.extend(collect_named_entries(state_result.get("vehicles", []) if isinstance(state_result, dict) else []))

    try:
        for item in fetch_sessions(ui):
            vehicle = item.get("vehicle")
            if vehicle:
                collected.append(normalize_vehicle_entry(vehicle))
    except Exception:
        pass

    dedup = {}
    for entry in collected:
        if entry.get("name"):
            dedup[entry["name"]] = entry
    return sorted(dedup.values(), key=lambda x: x["name"].lower())


def split_cached_vehicles(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    vehicles = [v for v in entries if v.get("kind") != "card"]
    cards = [v for v in entries if v.get("kind") == "card"]
    return vehicles, cards


def find_group(ui: dict, group_id: str):
    for group in ui.get("groups", []):
        if group.get("id") == group_id:
            return group
    return None


def effective_sender(ui: dict, group: dict) -> dict:
    if group.get("sender_mode") == "custom":
        return group.get("custom_sender", {}) or {}
    return ui.get("sender", {}) or {}


def effective_template(ui: dict, group: dict) -> dict:
    templates = ui.get("templates", {})
    if group.get("html_mode") == "custom":
        tid = str(group.get("template_id") or ui["reporting"]["default_template_id"])
        return templates.get(tid) or templates.get(ui["reporting"]["default_template_id"]) or templates.get("default") or {}
    tid = ui["reporting"]["default_template_id"]
    return templates.get(tid) or templates.get("default") or {}


def effective_email_body(ui: dict, group: dict) -> str:
    if group.get("email_mode") == "custom":
        return str(group.get("custom_email_body") or "")
    return str(ui.get("reporting", {}).get("default_email_body") or "")


def effective_billing_mode(ui: dict, group: dict) -> str:
    if group.get("billing_mode_scope") == "custom":
        mode = str(group.get("billing_mode_custom") or "")
    else:
        mode = str(ui.get("reporting", {}).get("billing_mode_default") or "monthly")
    if mode not in {"monthly", "quarterly", "halfyearly", "yearly"}:
        mode = "monthly"
    return mode


def period_for_mode(mode: str, year: int, month: int) -> tuple[pd.Timestamp, pd.Timestamp, str]:
    if mode == "monthly":
        start = pd.Timestamp(year=year, month=month, day=1)
        end = start + pd.offsets.MonthBegin(1)
        label = f"{year:04d}-{month:02d}"
    elif mode == "quarterly":
        q_start_month = ((month - 1) // 3) * 3 + 1
        start = pd.Timestamp(year=year, month=q_start_month, day=1)
        end = start + pd.offsets.MonthBegin(3)
        q = ((q_start_month - 1) // 3) + 1
        label = f"{year:04d} Q{q}"
    elif mode == "halfyearly":
        h_start_month = 1 if month <= 6 else 7
        start = pd.Timestamp(year=year, month=h_start_month, day=1)
        end = start + pd.offsets.MonthBegin(6)
        h = 1 if h_start_month == 1 else 2
        label = f"{year:04d} H{h}"
    else:
        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year + 1, month=1, day=1)
        label = f"{year:04d}"
    return start, end, label


def build_report_dataframe(ui: dict, group: dict, year: int, month: int):
    sessions = fetch_sessions(ui)
    df = pd.DataFrame(sessions)
    if df.empty:
        raise ValueError("Keine Sessions gefunden.")
    if "created" not in df.columns:
        raise ValueError("Spalte 'created' fehlt.")
    if "chargedEnergy" not in df.columns:
        raise ValueError("Spalte 'chargedEnergy' fehlt.")

    mode = effective_billing_mode(ui, group)
    start, end, period_label = period_for_mode(mode, year, month)

    df["created"] = pd.to_datetime(df["created"], errors="coerce", utc=True).dt.tz_localize(None)
    df = df.dropna(subset=["created"])
    df = df[(df["created"] >= start) & (df["created"] < end)]

    if "vehicle" in df.columns and group.get("vehicles"):
        df["vehicle"] = df["vehicle"].fillna("").astype(str)
        df = df[df["vehicle"].isin(group["vehicles"])]

    if df.empty:
        raise ValueError("Keine Sessions für Auswahl gefunden.")

    df["chargedEnergy"] = pd.to_numeric(df["chargedEnergy"], errors="coerce").fillna(0)

    raw_override = str(group.get("grid_price_override", "")).strip().replace(",", ".")
    if raw_override:
        try:
            grid_price = float(raw_override)
        except ValueError:
            grid_price = float(ui["reporting"].get("grid_price", 0) or 0)
    else:
        grid_price = float(ui["reporting"].get("grid_price", 0) or 0)

    df["price"] = (df["chargedEnergy"] * grid_price).round(2)
    df = df.sort_values("created", ascending=True)
    return df, grid_price, mode, period_label


def write_txt_report(ui: dict, group: dict, year: int, month: int) -> Path:
    df, grid_price, mode, period_label = build_report_dataframe(ui, group, year, month)
    sender = effective_sender(ui, group)
    template = effective_template(ui, group)
    email_body = effective_email_body(ui, group)
    output_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in group["name"]).strip("_") or "gruppe"
    output_file = REPORT_DIR / f"evcc_report_{period_label.replace(' ', '_')}_{output_name}.txt"

    lines = [
        "EVCC Abrechnung",
        "================",
        "",
        f"Gruppe: {group['name']}",
        f"Empfänger: {group.get('recipient_name', '')}",
        f"Firma: {group.get('recipient_company', '')}",
        f"E-Mail: {group.get('recipient_email', '')}",
        "",
        f"Absender-Modus: {'Gruppenbezogen' if group.get('sender_mode') == 'custom' else 'Standard'}",
        f"Absender: {sender.get('name', '')}",
        f"HTML: {template.get('label', 'Standard HTML')}",
        f"E-Mail-Text-Modus: {'Custom' if group.get('email_mode') == 'custom' else 'Standard'}",
        f"Abrechnungsmodus: {mode}",
        f"Periode: {period_label}",
        "",
        "E-Mail-Inhalt:",
        email_body,
        "",
        f"Fahrzeuge: {', '.join(group.get('vehicles', [])) if group.get('vehicles') else 'Alle'}",
        f"Netzstrompreis: {grid_price:.2f} €/kWh",
        "",
        "Chronologische Ladeliste:",
        "",
    ]
    for _, row in df.iterrows():
        created_str = row["created"].strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"{created_str} | {row.get('vehicle','')} | {float(row.get('chargedEnergy',0)):.2f} kWh | {float(row.get('price',0)):.2f} €"
        )

    lines.extend([
        "",
        f"Anzahl Ladevorgänge: {len(df)}",
        f"Gesamtenergie: {float(df['chargedEnergy'].sum()):.2f} kWh",
        f"Gesamtbetrag: {float(df['price'].sum()):.2f} €",
    ])
    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


@app.context_processor
def inject_common():
    ui = load_ui_data()
    ingress_path = request.headers.get("X-Ingress-Path", "").rstrip("/")
    vehicles, cards = split_cached_vehicles(ui.get("cached_vehicles", []))
    return {
        "ui": ui,
        "ingress_path": ingress_path,
        "vehicle_count": len(vehicles),
        "card_count": len(cards),
        "group_count": len(ui.get("groups", [])),
    }


@app.get("/")
def dashboard():
    ui = load_ui_data()
    vehicles, cards = split_cached_vehicles(ui.get("cached_vehicles", []))
    return render_template("dashboard.html", ui=ui, vehicles=vehicles, cards=cards)


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    ui = load_ui_data()
    secrets = load_local_secrets()

    if request.method == "POST":
        ui["evcc"]["url"] = request.form.get("evcc_url", "").strip()
        secrets["evcc_password"] = request.form.get("evcc_password", "").strip()

        ui["sender"]["name"] = request.form.get("sender_name", "").strip()
        ui["sender"]["street"] = request.form.get("sender_street", "").strip()
        ui["sender"]["zip"] = request.form.get("sender_zip", "").strip()
        ui["sender"]["city"] = request.form.get("sender_city", "").strip()
        ui["sender"]["email"] = request.form.get("sender_email", "").strip()

        ui["smtp"]["host"] = request.form.get("smtp_host", "").strip()
        try:
            ui["smtp"]["port"] = int(request.form.get("smtp_port", "587").strip())
        except ValueError:
            ui["smtp"]["port"] = 587
        ui["smtp"]["user"] = request.form.get("smtp_user", "").strip()
        secrets["smtp_password"] = request.form.get("smtp_password", "").strip()
        ui["smtp"]["tls"] = parse_bool(request.form.get("smtp_tls"))

        raw_grid = request.form.get("grid_price", "0").strip().replace(",", ".")
        try:
            ui["reporting"]["grid_price"] = float(raw_grid)
        except ValueError:
            ui["reporting"]["grid_price"] = 0.0

        ui["reporting"]["default_template_id"] = normalize_template_id(request.form.get("default_template_id", "default"))
        if ui["reporting"]["default_template_id"] not in ui["templates"]:
            ui["reporting"]["default_template_id"] = "default"
        ui["reporting"]["default_email_body"] = request.form.get("default_email_body", "")
        billing_mode_default = request.form.get("billing_mode_default", "monthly").strip()
        if billing_mode_default not in {"monthly", "quarterly", "halfyearly", "yearly"}:
            billing_mode_default = "monthly"
        ui["reporting"]["billing_mode_default"] = billing_mode_default

        ui["scheduler"]["enabled"] = parse_bool(request.form.get("scheduler_enabled"))
        try:
            ui["scheduler"]["day_of_month"] = int(request.form.get("scheduler_day_of_month", "1").strip())
        except ValueError:
            ui["scheduler"]["day_of_month"] = 1
        ui["scheduler"]["time"] = request.form.get("scheduler_time", "07:00").strip() or "07:00"

        save_ui_data(ui)
        save_local_secrets(secrets)
        flash("Einstellungen gespeichert.", "success")
        return redirect(f"{request.headers.get('X-Ingress-Path','')}/settings")

    addon_opts = read_addon_options()
    return render_template("settings.html", ui=ui, addon_opts=addon_opts, secrets=secrets)


@app.post("/refresh_vehicles")
def refresh_vehicles():
    ui = load_ui_data()
    try:
        ui["cached_vehicles"] = fetch_available_vehicles(ui)
        save_ui_data(ui)
        cache_file = REPORT_DIR / "available_vehicles.txt"
        lines = [v["name"] for v in ui["cached_vehicles"] if v.get("name")]
        cache_file.write_text("\n".join(lines), encoding="utf-8")
        flash(f"{len(ui['cached_vehicles'])} Fahrzeuge/Ladekarten geladen.", "success")
    except Exception as err:
        flash(f"Fahrzeuge konnten nicht geladen werden: {err}", "error")
    return redirect(f"{request.headers.get('X-Ingress-Path','')}/groups")


@app.route("/groups", methods=["GET", "POST"])
def groups_page():
    ui = load_ui_data()

    if request.method == "POST":
        action = request.form.get("form_action", "").strip()
        if action == "delete":
            gid = request.form.get("group_id", "").strip()
            ui["groups"] = [g for g in ui["groups"] if g.get("id") != gid]
            save_ui_data(ui)
            flash("Gruppe gelöscht.", "success")
            return redirect(f"{request.headers.get('X-Ingress-Path','')}/groups")

        gid = request.form.get("group_id", "").strip() or str(uuid.uuid4())
        sender_mode = request.form.get("sender_mode", "default").strip()
        if sender_mode not in {"default", "custom"}:
            sender_mode = "default"

        html_mode = request.form.get("html_mode", "default").strip()
        if html_mode not in {"default", "custom"}:
            html_mode = "default"

        email_mode = request.form.get("email_mode", "default").strip()
        if email_mode not in {"default", "custom"}:
            email_mode = "default"

        billing_mode_scope = request.form.get("billing_mode_scope", "default").strip()
        if billing_mode_scope not in {"default", "custom"}:
            billing_mode_scope = "default"

        billing_mode_custom = request.form.get("billing_mode_custom", ui["reporting"]["billing_mode_default"]).strip()
        if billing_mode_custom not in {"monthly", "quarterly", "halfyearly", "yearly"}:
            billing_mode_custom = ui["reporting"]["billing_mode_default"]

        template_id = normalize_template_id(request.form.get("template_id", ui["reporting"]["default_template_id"]))
        if template_id not in ui["templates"]:
            template_id = ui["reporting"]["default_template_id"]

        group_data = {
            "id": gid,
            "name": request.form.get("name", "").strip(),
            "recipient_name": request.form.get("recipient_name", "").strip(),
            "recipient_company": request.form.get("recipient_company", "").strip(),
            "recipient_email": request.form.get("recipient_email", "").strip(),
            "recipient_street": request.form.get("recipient_street", "").strip(),
            "recipient_zip": request.form.get("recipient_zip", "").strip(),
            "recipient_city": request.form.get("recipient_city", "").strip(),
            "vehicles": [v.strip() for v in request.form.getlist("vehicles") if v.strip()],
            "grid_price_override": request.form.get("grid_price_override", "").strip(),
            "sender_mode": sender_mode,
            "custom_sender": {
                "name": request.form.get("custom_sender_name", "").strip(),
                "email": request.form.get("custom_sender_email", "").strip(),
                "street": request.form.get("custom_sender_street", "").strip(),
                "zip": request.form.get("custom_sender_zip", "").strip(),
                "city": request.form.get("custom_sender_city", "").strip(),
            },
            "html_mode": html_mode,
            "template_id": template_id,
            "email_mode": email_mode,
            "custom_email_body": request.form.get("custom_email_body", ""),
            "billing_mode_scope": billing_mode_scope,
            "billing_mode_custom": billing_mode_custom,
        }

        if not group_data["name"]:
            flash("Gruppenname fehlt.", "error")
            return redirect(f"{request.headers.get('X-Ingress-Path','')}/groups")

        existing = find_group(ui, gid)
        if existing:
            existing.update(group_data)
            flash("Gruppe aktualisiert.", "success")
        else:
            ui["groups"].append(group_data)
            flash("Gruppe angelegt.", "success")

        save_ui_data(ui)
        return redirect(f"{request.headers.get('X-Ingress-Path','')}/groups")

    edit_id = request.args.get("edit", "").strip()
    edit_group = find_group(ui, edit_id) if edit_id else None
    vehicles, cards = split_cached_vehicles(ui.get("cached_vehicles", []))
    return render_template("groups.html", ui=ui, edit_group=edit_group, vehicles=vehicles, cards=cards)


@app.route("/templates", methods=["GET", "POST"])
def templates_page():
    ui = load_ui_data()
    if request.method == "POST":
        action = request.form.get("form_action", "").strip()
        if action == "delete":
            tid = request.form.get("template_id", "").strip()
            if tid != "default":
                ui["templates"].pop(tid, None)
                for group in ui.get("groups", []):
                    if group.get("template_id") == tid:
                        group["template_id"] = ui["reporting"]["default_template_id"]
                if ui["reporting"]["default_template_id"] == tid:
                    ui["reporting"]["default_template_id"] = "default"
                save_ui_data(ui)
                flash("Template gelöscht.", "success")
            return redirect(f"{request.headers.get('X-Ingress-Path','')}/templates")

        tid = request.form.get("template_id", "").strip() or request.form.get("template_label", "")
        tid = normalize_template_id(tid)
        label = request.form.get("template_label", "").strip() or tid
        content = request.form.get("template_content", "").strip()
        set_default = parse_bool(request.form.get("template_default"))

        ui["templates"][tid] = {"id": tid, "label": label, "content": content}
        if set_default:
            ui["reporting"]["default_template_id"] = tid
        save_ui_data(ui)
        flash("Template gespeichert.", "success")
        return redirect(f"{request.headers.get('X-Ingress-Path','')}/templates")

    edit_id = request.args.get("edit", "").strip()
    edit_template = ui.get("templates", {}).get(edit_id)
    return render_template("templates.html", ui=ui, edit_template=edit_template)


@app.route("/report", methods=["GET", "POST"])
def report_page():
    ui = load_ui_data()
    generated_file = None

    if request.method == "POST":
        gid = request.form.get("group_id", "").strip()
        mode = request.form.get("mode", "previous_month").strip()
        if mode == "manual":
            try:
                year = int(request.form.get("year", "").strip())
                month = int(request.form.get("month", "").strip())
            except ValueError:
                flash("Jahr oder Monat ungültig.", "error")
                return redirect(f"{request.headers.get('X-Ingress-Path','')}/report")
        else:
            year, month = get_previous_month()

        group = find_group(ui, gid)
        if not group:
            flash("Gruppe nicht gefunden.", "error")
            return redirect(f"{request.headers.get('X-Ingress-Path','')}/report")

        try:
            generated_file = write_txt_report(ui, group, year, month)
            flash(f"Bericht erzeugt: {generated_file}", "success")
        except Exception as err:
            flash(f"Bericht konnte nicht erzeugt werden: {err}", "error")

    current_year = datetime.today().year
    return render_template(
        "report.html",
        ui=ui,
        years=list(range(current_year - 3, current_year + 2)),
        months=list(range(1, 13)),
        generated_file=generated_file,
    )


if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=APP_PORT)
