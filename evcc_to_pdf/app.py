import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

APP_PORT = 8099
SETTINGS_DIR = Path("/addon_config/evcc_to_pdf")
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
REPORT_DIR = Path("/share/evcc-pdfs")

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
    },
    "cached_vehicles": [],
    "groups": [],
}

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "evcc-to-pdf-dev-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)
app.config["APPLICATION_ROOT"] = "/"


@app.before_request
def fix_ingress_prefix() -> None:
    if "X-Ingress-Path" in request.headers:
        app.config["APPLICATION_ROOT"] = request.headers["X-Ingress-Path"]


def ensure_dirs() -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    ensure_dirs()
    if not SETTINGS_FILE.exists():
        settings = deepcopy(DEFAULT_SETTINGS)
        save_settings(settings)
        return settings

    with SETTINGS_FILE.open("r", encoding="utf-8") as f:
        loaded = json.load(f)

    settings = deepcopy(DEFAULT_SETTINGS)

    for key, value in loaded.items():
        if key in ("evcc", "sender", "smtp", "scheduler", "reporting") and isinstance(value, dict):
            merged = deepcopy(DEFAULT_SETTINGS[key])
            merged.update(value)
            settings[key] = merged
        else:
            settings[key] = value

    if not isinstance(settings.get("groups"), list):
        settings["groups"] = []
    if not isinstance(settings.get("cached_vehicles"), list):
        settings["cached_vehicles"] = []

    return settings


def save_settings(settings: dict) -> None:
    ensure_dirs()
    with SETTINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


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


def fetch_available_vehicles(settings: dict) -> list[str]:
    sessions = fetch_sessions(settings)
    vehicles = set()

    for item in sessions:
        vehicle = item.get("vehicle")
        if vehicle is None:
            continue
        vehicle = str(vehicle).strip()
        if vehicle:
            vehicles.add(vehicle)

    return sorted(vehicles, key=lambda x: x.lower())


def report_rows_for_group(settings: dict, group: dict, year: int, month: int) -> tuple[pd.DataFrame, dict]:
    sessions = fetch_sessions(settings)
    df = pd.DataFrame(sessions)

    if df.empty:
        raise ValueError("Keine Sessions gefunden.")

    if "created" not in df.columns:
        raise ValueError("Spalte 'created' fehlt in den EVCC-Sessions.")
    if "chargedEnergy" not in df.columns:
        raise ValueError("Spalte 'chargedEnergy' fehlt in den EVCC-Sessions.")

    df["created"] = pd.to_datetime(df["created"], errors="coerce", utc=True).dt.tz_localize(None)
    df = df.dropna(subset=["created"])
    df = df[(df["created"].dt.year == year) & (df["created"].dt.month == month)]

    selected_vehicles = group.get("vehicles", [])
    if "vehicle" in df.columns and selected_vehicles:
        df["vehicle"] = df["vehicle"].fillna("").astype(str)
        df = df[df["vehicle"].isin(selected_vehicles)]

    if df.empty:
        raise ValueError("Keine Sessions für die Auswahl gefunden.")

    df["chargedEnergy"] = pd.to_numeric(df["chargedEnergy"], errors="coerce").fillna(0)
    raw_override = group.get("grid_price_override")
    grid_price = 0.0
    if raw_override not in (None, ""):
        try:
            grid_price = float(str(raw_override).replace(",", "."))
        except ValueError:
            grid_price = 0.0
    if not grid_price:
        grid_price = float(settings.get("reporting", {}).get("grid_price", 0) or 0)

    df["price"] = (df["chargedEnergy"] * grid_price).round(2)
    df = df.sort_values("created", ascending=True)

    summary = {
        "year": year,
        "month": month,
        "group_name": group.get("name", ""),
        "recipient_name": group.get("recipient_name", ""),
        "recipient_company": group.get("recipient_company", ""),
        "recipient_email": group.get("recipient_email", ""),
        "vehicles": selected_vehicles,
        "grid_price": grid_price,
        "total_energy": round(float(df["chargedEnergy"].sum()), 2),
        "total_price": round(float(df["price"].sum()), 2),
        "row_count": int(len(df)),
    }
    return df, summary


def write_txt_report(settings: dict, group: dict, year: int, month: int) -> Path:
    df, summary = report_rows_for_group(settings, group, year, month)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_group = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in group["name"]).strip("_") or "gruppe"
    output_file = REPORT_DIR / f"evcc_report_{year:04d}-{month:02d}_{safe_group}.txt"

    lines = [
        "EVCC Abrechnung",
        "================",
        "",
        f"Gruppe: {summary['group_name']}",
        f"Empfänger: {summary['recipient_name']}",
        f"Firma: {summary['recipient_company']}",
        f"E-Mail: {summary['recipient_email']}",
        "",
        f"Monat: {year:04d}-{month:02d}",
        f"Fahrzeuge: {', '.join(summary['vehicles']) if summary['vehicles'] else 'Alle'}",
        f"Netzstrompreis: {summary['grid_price']:.2f} €/kWh",
        "",
        "Chronologische Ladeliste:",
        "",
    ]

    for _, row in df.iterrows():
        created_str = row["created"].strftime("%Y-%m-%d %H:%M")
        vehicle = str(row.get("vehicle", ""))
        energy = float(row.get("chargedEnergy", 0))
        price = float(row.get("price", 0))
        lines.append(f"{created_str} | {vehicle} | {energy:.2f} kWh | {price:.2f} €")

    lines.extend([
        "",
        f"Anzahl Ladevorgänge: {summary['row_count']}",
        f"Gesamtenergie: {summary['total_energy']:.2f} kWh",
        f"Gesamtbetrag: {summary['total_price']:.2f} €",
    ])

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
        "group_count": len(settings.get("groups", [])),
        "vehicle_count": len(settings.get("cached_vehicles", [])),
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
        return redirect(url_for("settings_page"))

    return render_template("settings.html", settings=settings)


@app.route("/refresh_vehicles", methods=["POST"])
def refresh_vehicles():
    settings = load_settings()
    try:
        vehicles = fetch_available_vehicles(settings)
        settings["cached_vehicles"] = vehicles
        save_settings(settings)

        cache_file = REPORT_DIR / "available_vehicles.txt"
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("\n".join(vehicles), encoding="utf-8")

        flash(f"{len(vehicles)} Fahrzeuge geladen.", "success")
    except Exception as err:
        flash(f"Fahrzeuge konnten nicht geladen werden: {err}", "error")
    return redirect(url_for("groups_page"))


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
            return redirect(url_for("groups_page"))

        group_id = request.form.get("group_id", "").strip() or str(uuid.uuid4())
        selected_vehicles = request.form.getlist("vehicles")

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
            return redirect(url_for("groups_page"))

        existing = find_group(settings, group_id)
        if existing:
            existing.update(group_data)
            flash("Gruppe aktualisiert.", "success")
        else:
            settings["groups"].append(group_data)
            flash("Gruppe angelegt.", "success")

        save_settings(settings)
        return redirect(url_for("groups_page"))

    edit_group_id = request.args.get("edit", "").strip()
    edit_group = find_group(settings, edit_group_id) if edit_group_id else None

    return render_template("groups.html", settings=settings, edit_group=edit_group)


@app.route("/report", methods=["GET", "POST"])
def report_page():
    settings = load_settings()
    generated_file = None

    if request.method == "POST":
        group_id = request.form.get("group_id", "").strip()
        mode = request.form.get("mode", "previous_month").strip()

        if mode == "manual":
            try:
                year = int(request.form.get("year", "").strip())
                month = int(request.form.get("month", "").strip())
            except ValueError:
                flash("Jahr oder Monat ist ungültig.", "error")
                return redirect(url_for("report_page"))
        else:
            year, month = get_previous_month()

        group = find_group(settings, group_id)
        if not group:
            flash("Gruppe nicht gefunden.", "error")
            return redirect(url_for("report_page"))

        try:
            generated_file = write_txt_report(settings, group, year, month)
            flash(f"Bericht erzeugt: {generated_file}", "success")
        except Exception as err:
            flash(f"Bericht konnte nicht erzeugt werden: {err}", "error")

    current_year = datetime.today().year
    years = list(range(current_year - 3, current_year + 2))
    months = list(range(1, 13))

    return render_template(
        "report.html",
        settings=settings,
        years=years,
        months=months,
        generated_file=generated_file,
    )


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=APP_PORT)
