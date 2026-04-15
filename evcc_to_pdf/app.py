import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from flask import Flask, flash, redirect, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

APP_PORT = 8099
SETTINGS_DIR = Path("/addon_config/evcc_to_pdf")
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
LEGACY_SETTINGS_FILES = [
    Path("/config/evcc_to_pdf/settings.json"),
    Path("/data/options.json"),
]
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




def vehicle_entries_from_cache(settings: dict) -> list[dict]:
    entries = []
    for item in settings.get("cached_vehicles", []):
        if isinstance(item, str):
            entries.append(normalize_vehicle_entry(item, "vehicle"))
        elif isinstance(item, dict) and item.get("name"):
            kind = item.get("type", "vehicle")
            entries.append(normalize_vehicle_entry(str(item["name"]), kind))
    return sorted(entries, key=lambda x: (x["type"], x["name"].lower()))


def fetch_available_vehicles(settings: dict) -> list[dict]:
    base_url = str(settings["evcc"].get("url", "")).rstrip("/")
    session = evcc_session(settings)
    entries: dict[str, dict] = {}

    def add_entry(name: str, kind: str = "vehicle") -> None:
        normalized_name = extract_name(name)
        if not normalized_name:
            return
        current = entries.get(normalized_name)
        if current is None:
            entries[normalized_name] = normalize_vehicle_entry(normalized_name, kind)
        elif current.get("type") != "vehicle" and kind == "vehicle":
            entries[normalized_name] = normalize_vehicle_entry(normalized_name, kind)

    response = session.get(f"{base_url}/api/state", timeout=15)
    response.raise_for_status()
    data = response.json()
    result = data.get("result", data) if isinstance(data, dict) else {}

    vehicles_data = result.get("vehicles", []) if isinstance(result, dict) else []
    if isinstance(vehicles_data, dict):
        vehicles_iter = vehicles_data.values()
    elif isinstance(vehicles_data, list):
        vehicles_iter = vehicles_data
    else:
        vehicles_iter = []

    for item in vehicles_iter:
        if isinstance(item, dict):
            add_entry(item.get("title") or item.get("name") or item.get("vehicle"), "vehicle")
            # manche EVCC-Versionen haben identifiers / tokens / cards als Liste von Strings oder Dicts
            for key in ("identifiers", "identifier", "cards", "rfid", "tokens"):
                extra = item.get(key)
                if isinstance(extra, list):
                    for sub in extra:
                        sub_name = extract_name(sub)
                        if sub_name:
                            add_entry(sub_name, "card")
                else:
                    sub_name = extract_name(extra)
                    if sub_name:
                        add_entry(sub_name, "card")
        else:
            add_entry(item, "vehicle")

    try:
        sessions = fetch_sessions(settings)
        for item in sessions:
            if not isinstance(item, dict):
                continue
            vehicle = extract_name(item.get("vehicle"))
            if vehicle:
                kind = "card" if "ladekarte" in vehicle.lower() else "vehicle"
                add_entry(vehicle, kind)
    except Exception:
        pass

    return sorted(entries.values(), key=lambda x: (0 if x["type"] == "vehicle" else 1, x["name"].lower()))

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
    grid_price = group.get("grid_price_override")
    try:
        grid_price = float(grid_price) if str(grid_price).strip() else float(settings["reporting"].get("grid_price", 0) or 0)
    except ValueError:
        grid_price = float(settings["reporting"].get("grid_price", 0) or 0)

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

def find_group(settings: dict, group_id: str):
    for group in settings["groups"]:
        if group.get("id") == group_id:
            return group
    return None

@app.context_processor
def inject_common():
    settings = load_settings()
    ingress_path = request.headers.get("X-Ingress-Path", "").rstrip("/")
    return {
        "settings": settings,
        "group_count": len(settings.get("groups", [])),
        "vehicle_count": len(settings.get("cached_vehicles", [])),
        "ingress_path": ingress_path,
    }

@app.route("/")
def dashboard():
    settings = load_settings()
    cached_vehicle_entries = vehicle_entries_from_cache(settings)
    return render_template("dashboard.html", settings=settings, cached_vehicle_entries=cached_vehicle_entries, title="Dashboard")

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
        return redirect((request.headers.get("X-Ingress-Path", "").rstrip("/") or "") + "/settings")
    return render_template("settings.html", settings=settings, title="Einstellungen")

@app.route("/refresh_vehicles", methods=["POST"])
def refresh_vehicles():
    settings = load_settings()
    try:
        vehicles = fetch_available_vehicles(settings)
        settings["cached_vehicles"] = vehicles
        save_settings(settings)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "available_vehicles.txt").write_text("\n".join(v["name"] for v in vehicles), encoding="utf-8")
        flash(f"{len(vehicles)} Fahrzeuge geladen.", "success")
    except Exception as err:
        flash(f"Fahrzeuge konnten nicht geladen werden: {err}", "error")
    return redirect((request.headers.get("X-Ingress-Path", "").rstrip("/") or "") + "/groups")

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
            return redirect((request.headers.get("X-Ingress-Path", "").rstrip("/") or "") + "/groups")

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
            return redirect((request.headers.get("X-Ingress-Path", "").rstrip("/") or "") + "/groups")
        existing = find_group(settings, group_id)
        if existing:
            existing.update(group_data)
            flash("Gruppe aktualisiert.", "success")
        else:
            settings["groups"].append(group_data)
            flash("Gruppe angelegt.", "success")
        save_settings(settings)
        return redirect((request.headers.get("X-Ingress-Path", "").rstrip("/") or "") + "/groups")

    edit_group_id = request.args.get("edit", "").strip()
    edit_group = find_group(settings, edit_group_id) if edit_group_id else None
    return render_template("groups.html", settings=settings, edit_group=edit_group, title="Gruppen")

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
                return redirect((request.headers.get("X-Ingress-Path", "").rstrip("/") or "") + "/report")
        else:
            year, month = get_previous_month()

        group = find_group(settings, group_id)
        if not group:
            flash("Gruppe nicht gefunden.", "error")
            return redirect((request.headers.get("X-Ingress-Path", "").rstrip("/") or "") + "/report")
        try:
            generated_file = write_txt_report(settings, group, year, month)
            flash(f"Bericht erzeugt: {generated_file}", "success")
        except Exception as err:
            flash(f"Bericht konnte nicht erzeugt werden: {err}", "error")

    current_year = datetime.today().year
    years = list(range(current_year - 3, current_year + 2))
    months = list(range(1, 13))
    return render_template("report.html", settings=settings, years=years, months=months, generated_file=generated_file, title="Testbericht")

@app.route("/health")
def health():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=APP_PORT)
