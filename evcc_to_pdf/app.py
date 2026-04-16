
import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import paho.mqtt.client as mqtt
import requests
from flask import Flask, flash, redirect, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix


APP_PORT = 8099
SETTINGS_DIR = Path("/addon_config/evcc_to_pdf")
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
REPORT_DIR = Path("/share/evcc-pdfs")
OPTIONS_FILE = Path("/data/options.json")


DEFAULT_SETTINGS = {
    "evcc": {
        "url": "",
        "password": "",
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
        "password": "",
        "tls": True,
    },
    "scheduler": {
        "enabled": False,
        "day_of_month": 1,
        "time": "07:00",
    },
    "reporting": {
        "grid_price": 0.0,
        "billing_mode": "monthly",
        "default_email_body": "",
        "default_template_key": "default",
    },
    "cached_assets": {
        "vehicles": [],
        "cards": [],
    },
    "groups": [],
    "templates": {
        "default": {
            "label": "Standard HTML",
            "content": "<html><body><h1>EVCC Abrechnung</h1><p>{{ group_name }}</p><p>{{ period_label }}</p>{{ positions_table }}</body></html>"
        }
    },
}


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "evcc-to-pdf-dev-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


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


def merge_unique(*lists) -> list[str]:
    out = []
    seen = set()
    for values in lists:
        for item in values or []:
            name = extract_name(item)
            if name and name not in seen:
                seen.add(name)
                out.append(name)
    return out


def normalize_group(group: dict) -> dict:
    merged_assets = merge_unique(group.get("assets", []), group.get("vehicles", []), group.get("cards", []))

    # Migration alt -> neu: HTML-Modus + Template-Key auf eine gemeinsame Auswahl abbilden
    template_choice = str(group.get("template_choice", "")).strip()
    if not template_choice:
        if str(group.get("html_mode", "default") or "default") == "custom":
            template_choice = str(group.get("custom_template_key", "")).strip() or "default"
        else:
            template_choice = "default"

    normalized = {
        "id": str(group.get("id") or uuid.uuid4()),
        "name": str(group.get("name", "")).strip(),
        "recipient_name": str(group.get("recipient_name", "")).strip(),
        "recipient_company": str(group.get("recipient_company", "")).strip(),
        "recipient_email": str(group.get("recipient_email", "")).strip(),
        "recipient_street": str(group.get("recipient_street", "")).strip(),
        "recipient_zip": str(group.get("recipient_zip", "")).strip(),
        "recipient_city": str(group.get("recipient_city", "")).strip(),
        "assets": merged_assets,
        "vehicles": merged_assets,
        "cards": [],
        "grid_price_override": str(group.get("grid_price_override", "")).strip(),
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
        "custom_email_body": str(group.get("custom_email_body", "")).strip(),
        "billing_mode_source": str(group.get("billing_mode_source", "default") or "default"),
        "custom_billing_mode": str(group.get("custom_billing_mode", "monthly") or "monthly"),
        "custom_send_day": int(group.get("custom_send_day", 1) or 1),
    }
    return normalized


def normalize_settings(loaded: dict | None) -> dict:
    settings = deepcopy(DEFAULT_SETTINGS)
    loaded = loaded or {}

    for section in ("evcc", "sender", "smtp", "scheduler", "reporting"):
        if isinstance(loaded.get(section), dict):
            settings[section].update(loaded[section])

    # backward compatibility: some older versions may have top-level grid price
    if "grid_price" in loaded and not settings["reporting"].get("grid_price"):
        try:
            settings["reporting"]["grid_price"] = float(loaded.get("grid_price", 0))
        except Exception:
            settings["reporting"]["grid_price"] = 0.0

    cached_assets = loaded.get("cached_assets", {})
    if isinstance(cached_assets, dict):
        settings["cached_assets"]["vehicles"] = normalize_assets(cached_assets.get("vehicles", []))
        settings["cached_assets"]["cards"] = normalize_assets(cached_assets.get("cards", []))
    else:
        # migration from old cached_vehicles list
        settings["cached_assets"]["vehicles"] = normalize_assets(loaded.get("cached_vehicles", []))

    raw_groups = loaded.get("groups", [])
    if isinstance(raw_groups, list):
        settings["groups"] = [normalize_group(g) for g in raw_groups if isinstance(g, dict)]

    raw_templates = loaded.get("templates", {})
    if isinstance(raw_templates, dict):
        templates = {}
        for key, value in raw_templates.items():
            if isinstance(value, dict):
                label = str(value.get("label", key)).strip() or key
                content = str(value.get("content", "") or "")
                templates[str(key)] = {"label": label, "content": content}
            elif isinstance(value, str):
                templates[str(key)] = {"label": str(key), "content": value}
        if templates:
            settings["templates"] = templates

    if settings["reporting"]["default_template_key"] not in settings["templates"]:
        settings["reporting"]["default_template_key"] = next(iter(settings["templates"].keys()))

    return settings


def save_local_settings(settings: dict) -> None:
    ensure_dirs()
    with SETTINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


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
    import time
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
    ensure_dirs()
    local = normalize_settings(local_raw_settings())
    try:
        remote_raw = mqtt_fetch_settings()
    except Exception:
        remote_raw = None

    if remote_raw:
        remote = normalize_settings(remote_raw)
        # keep local mirror updated
        save_local_settings(remote)
        return remote

    # MQTT empty/unavailable: use local mirror and seed MQTT if possible
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


def parse_bool(value: str | None) -> bool:
    return str(value).lower() in {"1", "true", "on", "yes"}


def get_previous_month() -> tuple[int, int]:
    today = datetime.today().replace(day=1)
    last_day_previous_month = today - timedelta(days=1)
    return last_day_previous_month.year, last_day_previous_month.month


def evcc_session(settings: dict) -> requests.Session:
    session = requests.Session()
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    password = str(settings["evcc"].get("password", ""))

    if not base_url:
        raise ValueError("EVCC-URL ist leer.")

    if password:
        login_url = f"{base_url}/api/auth/login"
        response = session.post(login_url, json={"password": password}, timeout=15)
        response.raise_for_status()
    return session


def fetch_sessions(settings: dict) -> list[dict]:
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    session = evcc_session(settings)
    response = session.get(f"{base_url}/api/sessions", timeout=30)
    response.raise_for_status()
    data = response.json()
    result = data["result"] if isinstance(data, dict) and "result" in data else data
    if not isinstance(result, list):
        raise ValueError("Unerwartete Antwort von EVCC bei /api/sessions")
    return result


def fetch_state(settings: dict) -> dict:
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    session = evcc_session(settings)
    response = session.get(f"{base_url}/api/state", timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["result"] if isinstance(data, dict) and "result" in data else data


def fetch_available_assets(settings: dict) -> tuple[list[str], list[str]]:
    vehicles = set()
    cards = set()

    state = fetch_state(settings)

    state_vehicle_names = set()
    raw_vehicles = state.get("vehicles", [])
    if isinstance(raw_vehicles, dict):
        raw_vehicles = list(raw_vehicles.values())
    for item in raw_vehicles:
        name = extract_name(item)
        if name:
            state_vehicle_names.add(name)
            vehicles.add(name)

    # Karten/Tags direkt aus state lesen
    for key in ("tags", "cards", "rfid", "tokens"):
        raw_cards = state.get(key, [])
        if isinstance(raw_cards, dict):
            raw_cards = list(raw_cards.values())
        if isinstance(raw_cards, list):
            for item in raw_cards:
                name = extract_name(item)
                if name:
                    cards.add(name)

    # Session-Werte ergänzen. Alles, was kein bekanntes EVCC-Fahrzeug ist,
    # behandeln wir standardmäßig als Ladekarte/Tag.
    try:
        sessions = fetch_sessions(settings)
        for s in sessions:
            name = extract_name(s.get("vehicle"))
            if not name:
                continue
            lowered = name.lower()
            if name in state_vehicle_names:
                vehicles.add(name)
            elif any(token in lowered for token in ("ladekarte", "karte", "guest", "gäste", "gaeste", "rfid", "token")):
                cards.add(name)
            else:
                cards.add(name)
    except Exception:
        pass

    # Überschneidungen bereinigen: State-Fahrzeuge haben Vorrang als Fahrzeug.
    cards = {c for c in cards if c not in state_vehicle_names}

    return sorted(vehicles, key=lambda x: x.lower()), sorted(cards, key=lambda x: x.lower())


def write_assets_cache(settings: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    vehicles = settings["cached_assets"]["vehicles"]
    cards = settings["cached_assets"]["cards"]
    (REPORT_DIR / "available_vehicles.txt").write_text("\n".join(vehicles), encoding="utf-8")
    (REPORT_DIR / "available_cards.txt").write_text("\n".join(cards), encoding="utf-8")


def billing_mode_label(value: str) -> str:
    return {
        "monthly": "Monatlich",
        "quarterly": "Quartal",
        "semiannual": "Halbjährlich",
        "annual": "Jährlich",
    }.get(value, value)


def report_rows_for_group(settings: dict, group: dict, year: int, month: int):
    sessions = fetch_sessions(settings)
    df = pd.DataFrame(sessions)
    if df.empty:
        raise ValueError("Keine Sessions gefunden.")
    if "created" not in df.columns:
        raise ValueError("Spalte 'created' fehlt.")
    if "chargedEnergy" not in df.columns:
        raise ValueError("Spalte 'chargedEnergy' fehlt.")

    df["created"] = pd.to_datetime(df["created"], errors="coerce", utc=True).dt.tz_localize(None)
    df = df.dropna(subset=["created"])

    billing_mode = group["custom_billing_mode"] if group.get("billing_mode_source") == "custom" else settings["reporting"]["billing_mode"]

    if billing_mode == "monthly":
        start = datetime(year, month, 1)
        end = datetime(year + (month // 12), ((month % 12) + 1), 1)
    elif billing_mode == "quarterly":
        qstart = ((month - 1) // 3) * 3 + 1
        start = datetime(year, qstart, 1)
        em = qstart + 3
        ey = year + (1 if em > 12 else 0)
        em = ((em - 1) % 12) + 1
        end = datetime(ey, em, 1)
    elif billing_mode == "semiannual":
        sstart = 1 if month <= 6 else 7
        start = datetime(year, sstart, 1)
        em = sstart + 6
        ey = year + (1 if em > 12 else 0)
        em = ((em - 1) % 12) + 1
        end = datetime(ey, em, 1)
    else:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)

    df = df[(df["created"] >= start) & (df["created"] < end)]

    selected = set(group.get("vehicles", []) + group.get("cards", []))
    if "vehicle" in df.columns and selected:
        df["vehicle"] = df["vehicle"].fillna("").astype(str)
        df = df[df["vehicle"].isin(selected)]

    if df.empty:
        raise ValueError("Keine Sessions für die Auswahl gefunden.")

    df["chargedEnergy"] = pd.to_numeric(df["chargedEnergy"], errors="coerce").fillna(0)
    price = group.get("grid_price_override", "")
    try:
        grid_price = float(str(price).replace(",", ".")) if str(price).strip() else float(settings["reporting"]["grid_price"])
    except Exception:
        grid_price = float(settings["reporting"]["grid_price"])

    df["price"] = (df["chargedEnergy"] * grid_price).round(2)
    df = df.sort_values("created", ascending=True)

    summary = {
        "group_name": group["name"],
        "period_label": f"{billing_mode_label(billing_mode)} {start.strftime('%Y-%m-%d')} bis {(end - timedelta(days=1)).strftime('%Y-%m-%d')}",
        "grid_price": grid_price,
        "total_energy": round(float(df["chargedEnergy"].sum()), 2),
        "total_price": round(float(df["price"].sum()), 2),
    }
    return df, summary


def write_txt_report(settings: dict, group: dict, year: int, month: int) -> Path:
    df, summary = report_rows_for_group(settings, group, year, month)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_group = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in group["name"]).strip("_") or "gruppe"
    output_file = REPORT_DIR / f"evcc_report_{safe_group}.txt"

    lines = [
        "EVCC Abrechnung",
        "================",
        f"Gruppe: {summary['group_name']}",
        f"Zeitraum: {summary['period_label']}",
        f"Netzstrompreis: {summary['grid_price']:.2f} €/kWh",
        "",
    ]
    for _, row in df.iterrows():
        lines.append(f"{row['created'].strftime('%Y-%m-%d %H:%M')} | {row.get('vehicle','')} | {float(row.get('chargedEnergy',0)):.2f} kWh | {float(row.get('price',0)):.2f} €")
    lines.extend(["", f"Gesamtenergie: {summary['total_energy']:.2f} kWh", f"Gesamtbetrag: {summary['total_price']:.2f} €"])
    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def find_group(settings: dict, group_id: str) -> dict | None:
    for group in settings["groups"]:
        if group.get("id") == group_id:
            return group
    return None


@app.context_processor
def inject_common():
    settings = load_settings()
    return {
        "settings": settings,
        "ingress_path": ingress_path(),
        "all_assets": merge_unique(settings.get("cached_assets", {}).get("vehicles", []), settings.get("cached_assets", {}).get("cards", [])),
    }


@app.route("/")
def dashboard():
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
            settings["smtp"]["port"] = int(request.form.get("smtp_port", "587"))
        except Exception:
            settings["smtp"]["port"] = 587
        settings["smtp"]["user"] = request.form.get("smtp_user", "").strip()
        settings["smtp"]["password"] = request.form.get("smtp_password", "").strip()
        settings["smtp"]["tls"] = parse_bool(request.form.get("smtp_tls"))

        settings["scheduler"]["enabled"] = parse_bool(request.form.get("scheduler_enabled"))
        try:
            settings["scheduler"]["day_of_month"] = int(request.form.get("scheduler_day_of_month", "1"))
        except Exception:
            settings["scheduler"]["day_of_month"] = 1
        settings["scheduler"]["time"] = request.form.get("scheduler_time", "07:00").strip() or "07:00"

        try:
            settings["reporting"]["grid_price"] = float(request.form.get("grid_price", "0").replace(",", "."))
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
        vehicles, cards = fetch_available_assets(settings)
        settings["cached_assets"]["vehicles"] = vehicles
        settings["cached_assets"]["cards"] = cards
        save_settings(settings)
        write_assets_cache(settings)
        flash(f"{len(vehicles)} Fahrzeuge und {len(cards)} Ladekarten geladen.", "success")
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

        group_id = request.form.get("group_id", "").strip() or str(uuid.uuid4())
        group_data = {
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
        }
        group_data = normalize_group(group_data)
        existing = find_group(settings, group_id)
        if existing:
            existing.update(group_data)
            flash("Gruppe aktualisiert.", "success")
        else:
            settings["groups"].append(group_data)
            flash("Gruppe angelegt.", "success")
        save_settings(settings)
        return redirect(f"{ingress_path()}/groups")

    edit_group_id = request.args.get("edit", "").strip()
    edit_group = find_group(settings, edit_group_id) if edit_group_id else None
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

            existing = settings["templates"].get(original_key) if original_key else None
            if action == "update" and original_key and original_key != key and original_key in settings["templates"]:
                del settings["templates"][original_key]
                if settings["reporting"]["default_template_key"] == original_key:
                    settings["reporting"]["default_template_key"] = key
            settings["templates"][key] = {
                "label": label or key,
                "content": content if content else (existing or {}).get("content", "")
            }
            save_settings(settings)
            flash("Template gespeichert.", "success")
            return redirect(f"{ingress_path()}/templates")

    edit_key = request.args.get("edit", "").strip()
    edit_template = settings["templates"].get(edit_key) if edit_key else None
    return render_template("templates.html", title="Templates", edit_key=edit_key, edit_template=edit_template)


@app.route("/report", methods=["GET", "POST"])
def report_page():
    settings = load_settings()
    generated_file = None
    if request.method == "POST":
        group = find_group(settings, request.form.get("group_id", "").strip())
        if not group:
            flash("Gruppe nicht gefunden.", "error")
            return redirect(f"{ingress_path()}/report")
        mode = request.form.get("mode", "previous_month")
        if mode == "manual":
            year = int(request.form.get("year"))
            month = int(request.form.get("month"))
        else:
            year, month = get_previous_month()
        try:
            generated_file = write_txt_report(settings, group, year, month)
            flash(f"Bericht erzeugt: {generated_file}", "success")
        except Exception as err:
            flash(f"Bericht konnte nicht erzeugt werden: {err}", "error")
    current_year = datetime.today().year
    years = list(range(current_year - 3, current_year + 2))
    months = list(range(1, 13))
    return render_template("report.html", title="Testbericht", years=years, months=months, generated_file=generated_file)


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=APP_PORT)
