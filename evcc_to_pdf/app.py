import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from flask import Flask, flash, redirect, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

APP_PORT = 8099
SETTINGS_DIR = Path("/addon_config/evcc_to_pdf")
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
REPORT_DIR = Path("/share/evcc-pdfs")

DEFAULT_SETTINGS = {
    "evcc": {"url": "", "password": ""},
    "sender": {"name": "", "street": "", "zip": "", "city": "", "email": ""},
    "smtp": {"host": "", "port": 587, "user": "", "password": "", "tls": True},
    "scheduler": {"enabled": False, "day_of_month": 1, "time": "07:00"},
    "reporting": {"grid_price": 0.0},
    "cached_vehicles": [],
    "groups": [],
}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "evcc-to-pdf-dev-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


def ensure_dirs() -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def deep_merge(defaults: dict, loaded: dict) -> dict:
    merged = deepcopy(defaults)
    for k, v in loaded.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def extract_name(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("title", "name", "vehicle", "id", "uid"):
            if key in value and value[key]:
                return str(value[key]).strip()
        return ""
    return str(value).strip()


def normalize_vehicle_entry(value: Any) -> dict | None:
    if value is None:
        return None
    if isinstance(value, str):
        name = value.strip()
        if not name:
            return None
        entry_type = "card" if "ladekarte" in name.lower() or "gast" in name.lower() else "vehicle"
        return {"name": name, "type": entry_type}
    if isinstance(value, dict):
        name = extract_name(value)
        if not name:
            return None
        entry_type = str(value.get("type") or value.get("entry_type") or "").strip().lower()
        if entry_type not in {"vehicle", "card"}:
            entry_type = "card" if "ladekarte" in name.lower() or "gast" in name.lower() else "vehicle"
        return {"name": name, "type": entry_type}
    return normalize_vehicle_entry(str(value))


def normalize_vehicle_list(items: Any) -> list[dict]:
    result: list[dict] = []
    seen = set()
    if not isinstance(items, list):
        return result
    for item in items:
        normalized = normalize_vehicle_entry(item)
        if not normalized:
            continue
        key = (normalized["name"], normalized["type"])
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return sorted(result, key=lambda x: (x["type"], x["name"].lower()))


def normalize_group(group: dict) -> dict:
    normalized = {
        "id": str(group.get("id") or uuid.uuid4()),
        "name": str(group.get("name", "")).strip(),
        "recipient_name": str(group.get("recipient_name", "")).strip(),
        "recipient_company": str(group.get("recipient_company", "")).strip(),
        "recipient_email": str(group.get("recipient_email", "")).strip(),
        "recipient_street": str(group.get("recipient_street", "")).strip(),
        "recipient_zip": str(group.get("recipient_zip", "")).strip(),
        "recipient_city": str(group.get("recipient_city", "")).strip(),
        "grid_price_override": str(group.get("grid_price_override", "")).strip(),
        "vehicles": [],
    }
    raw_vehicles = group.get("vehicles", [])
    names = []
    for item in raw_vehicles if isinstance(raw_vehicles, list) else []:
        name = extract_name(item)
        if name:
            names.append(name)
    normalized["vehicles"] = sorted(set(names), key=str.lower)
    return normalized


def migrate_settings(loaded: dict) -> dict:
    settings = deep_merge(DEFAULT_SETTINGS, loaded if isinstance(loaded, dict) else {})
    settings["cached_vehicles"] = normalize_vehicle_list(settings.get("cached_vehicles", []))
    settings["groups"] = [normalize_group(g) for g in settings.get("groups", []) if isinstance(g, dict)]
    if "grid_price" in settings and not settings["reporting"].get("grid_price"):
        try:
            settings["reporting"]["grid_price"] = float(settings.get("grid_price") or 0)
        except Exception:
            settings["reporting"]["grid_price"] = 0.0
    return settings


def load_settings() -> dict:
    ensure_dirs()
    if not SETTINGS_FILE.exists():
        settings = deepcopy(DEFAULT_SETTINGS)
        save_settings(settings)
        return settings

    try:
        loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        loaded = {}
    settings = migrate_settings(loaded)
    return settings


def save_settings(settings: dict) -> None:
    ensure_dirs()
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_bool(value: str | None) -> bool:
    return str(value).lower() in {"1", "true", "on", "yes"}


def get_previous_month() -> tuple[int, int]:
    today = datetime.today().replace(day=1)
    previous = today - timedelta(days=1)
    return previous.year, previous.month


def evcc_session(settings: dict) -> requests.Session:
    session = requests.Session()
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    password = str(settings["evcc"].get("password", "")).strip()

    if not base_url:
        raise ValueError("EVCC-URL ist leer.")

    if password:
        login_url = f"{base_url}/api/auth/login"
        resp = session.post(login_url, json={"password": password}, timeout=15)
        resp.raise_for_status()

    return session


def fetch_sessions(settings: dict) -> list[dict]:
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    sess = evcc_session(settings)
    resp = sess.get(f"{base_url}/api/sessions", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "result" in data:
        data = data["result"]
    if not isinstance(data, list):
        raise ValueError("Unerwartete Antwort von /api/sessions")
    return data


def fetch_state(settings: dict) -> dict:
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    sess = evcc_session(settings)
    resp = sess.get(f"{base_url}/api/state", timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "result" in data and isinstance(data["result"], dict):
        return data["result"]
    if isinstance(data, dict):
        return data
    raise ValueError("Unerwartete Antwort von /api/state")


def fetch_available_vehicles(settings: dict) -> list[dict]:
    entries: list[dict] = []

    try:
        state = fetch_state(settings)
    except Exception:
        state = {}

    # vehicles may be list or dict depending on EVCC version/config
    vehicles_obj = state.get("vehicles", [])
    if isinstance(vehicles_obj, dict):
        iterable = vehicles_obj.values()
    else:
        iterable = vehicles_obj if isinstance(vehicles_obj, list) else []

    for item in iterable:
        name = extract_name(item)
        if name:
            entries.append({"name": name, "type": "card" if "ladekarte" in name.lower() or "gast" in name.lower() else "vehicle"})

    # Some setups expose loadpoint vehicle names or identifiers
    loadpoints = state.get("loadpoints", [])
    if isinstance(loadpoints, list):
        for lp in loadpoints:
            if not isinstance(lp, dict):
                continue
            for key in ("vehicleName", "vehicleTitle", "vehicle", "card", "tag"):
                name = extract_name(lp.get(key))
                if name:
                    entries.append({"name": name, "type": "card" if "ladekarte" in name.lower() or "gast" in name.lower() else "vehicle"})

    # Sessions as fallback/additional source
    try:
        sessions = fetch_sessions(settings)
    except Exception:
        sessions = []

    for item in sessions:
        if not isinstance(item, dict):
            continue
        name = extract_name(item.get("vehicle"))
        if name:
            entries.append({"name": name, "type": "card" if "ladekarte" in name.lower() or "gast" in name.lower() else "vehicle"})

    return normalize_vehicle_list(entries)


def grid_price_for_group(settings: dict, group: dict) -> float:
    raw = str(group.get("grid_price_override", "")).strip().replace(",", ".")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return float(settings.get("reporting", {}).get("grid_price", 0) or 0)


def find_group(settings: dict, group_id: str) -> dict | None:
    for group in settings.get("groups", []):
        if group.get("id") == group_id:
            return group
    return None


def write_txt_report(settings: dict, group: dict, year: int, month: int) -> Path:
    sessions = fetch_sessions(settings)
    df = pd.DataFrame(sessions)

    if df.empty:
        raise ValueError("Keine Sessions gefunden.")

    if "created" not in df.columns:
        raise ValueError("Spalte 'created' fehlt in den Sessions.")

    df["created"] = pd.to_datetime(df["created"], errors="coerce", utc=True).dt.tz_localize(None)
    df = df.dropna(subset=["created"])

    df = df[(df["created"].dt.year == year) & (df["created"].dt.month == month)]

    if "vehicle" in df.columns and group.get("vehicles"):
        wanted = set(group["vehicles"])
        df["vehicle"] = df["vehicle"].fillna("").astype(str)
        df = df[df["vehicle"].isin(wanted)]

    if df.empty:
        raise ValueError("Keine Sessions für diese Auswahl gefunden.")

    if "chargedEnergy" not in df.columns:
        raise ValueError("Spalte 'chargedEnergy' fehlt in den Sessions.")

    df["chargedEnergy"] = pd.to_numeric(df["chargedEnergy"], errors="coerce").fillna(0)
    price = grid_price_for_group(settings, group)
    df["price"] = (df["chargedEnergy"] * price).round(2)
    df = df.sort_values("created", ascending=True)

    safe_group = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in (group.get("name") or "gruppe")).strip("_")
    output_file = REPORT_DIR / f"evcc_report_{year:04d}-{month:02d}_{safe_group}.txt"

    lines = [
        "EVCC Abrechnung",
        "================",
        "",
        f"Gruppe: {group.get('name', '')}",
        f"Empfänger: {group.get('recipient_name', '')}",
        f"Firma: {group.get('recipient_company', '')}",
        f"E-Mail: {group.get('recipient_email', '')}",
        "",
        f"Monat: {year:04d}-{month:02d}",
        f"Fahrzeuge: {', '.join(group.get('vehicles', [])) if group.get('vehicles') else 'Alle'}",
        f"Netzstrompreis: {price:.2f} €/kWh",
        "",
        "Chronologische Ladeliste:",
        "",
    ]

    for _, row in df.iterrows():
        created_str = row["created"].strftime("%Y-%m-%d %H:%M")
        vehicle = str(row.get("vehicle", ""))
        energy = float(row.get("chargedEnergy", 0))
        total = float(row.get("price", 0))
        lines.append(f"{created_str} | {vehicle} | {energy:.2f} kWh | {total:.2f} €")

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
    settings = load_settings()
    ingress_path = request.headers.get("X-Ingress-Path", "").rstrip("/")
    return {
        "settings": settings,
        "ingress_path": ingress_path,
    }


@app.route("/")
def dashboard():
    settings = load_settings()
    return render_template("dashboard.html", settings=settings)


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
            settings["smtp"]["port"] = int(request.form.get("smtp_port", "587").strip())
        except ValueError:
            settings["smtp"]["port"] = 587
        settings["smtp"]["user"] = request.form.get("smtp_user", "").strip()
        settings["smtp"]["password"] = request.form.get("smtp_password", "").strip()
        settings["smtp"]["tls"] = parse_bool(request.form.get("smtp_tls"))

        settings["scheduler"]["enabled"] = parse_bool(request.form.get("scheduler_enabled"))
        try:
            settings["scheduler"]["day_of_month"] = int(request.form.get("scheduler_day_of_month", "1").strip())
        except ValueError:
            settings["scheduler"]["day_of_month"] = 1
        settings["scheduler"]["time"] = request.form.get("scheduler_time", "07:00").strip() or "07:00"

        raw_grid_price = request.form.get("grid_price", "0").strip().replace(",", ".")
        try:
            settings["reporting"]["grid_price"] = float(raw_grid_price)
        except ValueError:
            settings["reporting"]["grid_price"] = 0.0

        save_settings(settings)
        flash("Einstellungen gespeichert.", "success")
        return redirect(f"{request.headers.get('X-Ingress-Path', '').rstrip('/')}/settings")

    return render_template("settings.html", settings=settings)


@app.route("/refresh_vehicles", methods=["POST"])
def refresh_vehicles():
    settings = load_settings()
    try:
        vehicles = fetch_available_vehicles(settings)
        settings["cached_vehicles"] = vehicles
        save_settings(settings)

        cache_file = REPORT_DIR / "available_vehicles.txt"
        lines = [f"{'🚗' if x['type'] == 'vehicle' else '💳'} {x['name']}" for x in vehicles]
        cache_file.write_text("\n".join(lines), encoding="utf-8")

        flash(f"{len(vehicles)} Fahrzeuge/Ladekarten geladen.", "success")
    except Exception as err:
        flash(f"Fahrzeuge konnten nicht geladen werden: {err}", "error")
    return redirect(f"{request.headers.get('X-Ingress-Path', '').rstrip('/')}/groups")


@app.route("/groups", methods=["GET", "POST"])
def groups_page():
    settings = load_settings()

    if request.method == "POST":
        action = request.form.get("form_action", "").strip()

        if action == "delete":
            group_id = request.form.get("group_id", "").strip()
            settings["groups"] = [g for g in settings["groups"] if g.get("id") != group_id]
            save_settings(settings)
            flash("Gruppe gelöscht.", "success")
            return redirect(f"{request.headers.get('X-Ingress-Path', '').rstrip('/')}/groups")

        group_id = request.form.get("group_id", "").strip() or str(uuid.uuid4())
        selected_vehicles = sorted({extract_name(v) for v in request.form.getlist("vehicles") if extract_name(v)}, key=str.lower)

        group_data = {
            "id": group_id,
            "name": request.form.get("name", "").strip(),
            "recipient_name": request.form.get("recipient_name", "").strip(),
            "recipient_company": request.form.get("recipient_company", "").strip(),
            "recipient_email": request.form.get("recipient_email", "").strip(),
            "recipient_street": request.form.get("recipient_street", "").strip(),
            "recipient_zip": request.form.get("recipient_zip", "").strip(),
            "recipient_city": request.form.get("recipient_city", "").strip(),
            "vehicles": selected_vehicles,
            "grid_price_override": request.form.get("grid_price_override", "").strip().replace(",", "."),
        }

        if not group_data["name"]:
            flash("Gruppenname fehlt.", "error")
            return redirect(f"{request.headers.get('X-Ingress-Path', '').rstrip('/')}/groups")

        existing = find_group(settings, group_id)
        if existing:
            existing.update(group_data)
            flash("Gruppe aktualisiert.", "success")
        else:
            settings["groups"].append(group_data)
            flash("Gruppe angelegt.", "success")

        save_settings(settings)
        return redirect(f"{request.headers.get('X-Ingress-Path', '').rstrip('/')}/groups")

    edit_group_id = request.args.get("edit", "").strip()
    edit_group = find_group(settings, edit_group_id) if edit_group_id else None
    vehicles = settings.get("cached_vehicles", [])
    vehicle_entries = [x for x in vehicles if x.get("type") == "vehicle"]
    card_entries = [x for x in vehicles if x.get("type") == "card"]

    return render_template(
        "groups.html",
        settings=settings,
        edit_group=edit_group,
        vehicle_entries=vehicle_entries,
        card_entries=card_entries,
    )


@app.route("/report", methods=["GET", "POST"])
def report_page():
    settings = load_settings()

    if request.method == "POST":
        group_id = request.form.get("group_id", "").strip()
        mode = request.form.get("mode", "previous_month").strip()

        if mode == "manual":
            try:
                year = int(request.form.get("year", "").strip())
                month = int(request.form.get("month", "").strip())
            except ValueError:
                flash("Jahr oder Monat ist ungültig.", "error")
                return redirect(f"{request.headers.get('X-Ingress-Path', '').rstrip('/')}/report")
        else:
            year, month = get_previous_month()

        group = find_group(settings, group_id)
        if not group:
            flash("Gruppe nicht gefunden.", "error")
            return redirect(f"{request.headers.get('X-Ingress-Path', '').rstrip('/')}/report")

        try:
            output_file = write_txt_report(settings, group, year, month)
            flash(f"Bericht erzeugt: {output_file}", "success")
        except Exception as err:
            flash(f"Bericht konnte nicht erzeugt werden: {err}", "error")

        return redirect(f"{request.headers.get('X-Ingress-Path', '').rstrip('/')}/report")

    current_year = datetime.today().year
    years = list(range(current_year - 3, current_year + 2))
    months = list(range(1, 13))
    return render_template("report.html", settings=settings, years=years, months=months)


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=APP_PORT)
