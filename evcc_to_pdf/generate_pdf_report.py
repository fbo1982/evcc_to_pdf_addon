import json
from pathlib import Path

import pandas as pd
import requests


def load_options() -> dict:
    options_file = Path("/data/options.json")
    if not options_file.exists():
        raise FileNotFoundError("options.json unter /data nicht gefunden")

    with options_file.open("r", encoding="utf-8") as f:
        return json.load(f)


OPTIONS = load_options()

EVCC_URL = str(OPTIONS.get("evcc_url", "")).rstrip("/")
EVCC_PASSWORD = str(OPTIONS.get("evcc_password", ""))
GRID_PRICE = float(OPTIONS.get("grid_price", 0))
SELECTED_VEHICLES = [
    v.strip() for v in str(OPTIONS.get("selected_vehicles", "")).split(",") if v.strip()
]


def get_sessions():
    if not EVCC_URL:
        raise ValueError("EVCC_URL ist leer")

    url = f"{EVCC_URL}/api/sessions"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()
    if isinstance(data, dict) and "result" in data:
        return data["result"]
    return data


def main():
    sessions = get_sessions()
    df = pd.DataFrame(sessions)

    if df.empty:
        raise ValueError("Keine Sessions gefunden")

    if "vehicle" in df.columns and SELECTED_VEHICLES:
        df = df[df["vehicle"].fillna("").isin(SELECTED_VEHICLES)]

    if df.empty:
        raise ValueError("Keine Sessions nach Fahrzeugfilter gefunden")

    if "chargedEnergy" not in df.columns:
        raise ValueError("Spalte 'chargedEnergy' fehlt in der EVCC-Antwort")

    if "created" in df.columns:
        df["created"] = pd.to_datetime(df["created"], errors="coerce")
        df = df.sort_values("created", ascending=True)

    df["chargedEnergy"] = pd.to_numeric(df["chargedEnergy"], errors="coerce").fillna(0)
    df["price"] = (df["chargedEnergy"] * GRID_PRICE).round(2)

    total_energy = round(df["chargedEnergy"].sum(), 2)
    total_price = round(df["price"].sum(), 2)

    lines = []
    lines.append("EVCC Abrechnung")
    lines.append("================")
    lines.append(f"Fahrzeuge: {', '.join(SELECTED_VEHICLES) if SELECTED_VEHICLES else 'Alle'}")
    lines.append(f"Netzstrompreis: {GRID_PRICE:.2f} €/kWh")
    lines.append("")
    lines.append("Chronologische Ladeliste:")
    lines.append("")

    for _, row in df.iterrows():
        created = row.get("created")
        vehicle = row.get("vehicle", "")
        energy = row.get("chargedEnergy", 0)
        price = row.get("price", 0)

        created_str = ""
        if pd.notna(created):
            created_str = created.strftime("%Y-%m-%d %H:%M")

        lines.append(f"{created_str} | {vehicle} | {energy:.2f} kWh | {price:.2f} €")

    lines.append("")
    lines.append(f"Gesamtenergie: {total_energy:.2f} kWh")
    lines.append(f"Gesamtbetrag: {total_price:.2f} €")

    output_dir = Path("/share/evcc-pdfs")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "evcc_abrechnung.txt"
    output_file.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nDatei geschrieben: {output_file}")


if __name__ == "__main__":
    main()
