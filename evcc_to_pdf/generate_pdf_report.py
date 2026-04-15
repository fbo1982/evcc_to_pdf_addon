import os
from pathlib import Path
import requests
import pandas as pd

EVCC_URL = os.getenv("EVCC_URL", "").rstrip("/")
EVCC_PASSWORD = os.getenv("EVCC_PASSWORD", "")
GRID_PRICE = float(os.getenv("GRID_PRICE", "0"))
SELECTED_VEHICLES = [v.strip() for v in os.getenv("SELECTED_VEHICLES", "").split(",") if v.strip()]

def get_sessions():
    if not EVCC_URL:
        raise ValueError("EVCC_URL ist leer")

    url = f"{EVCC_URL}/api/sessions"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()
    if "result" in data:
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
    output_file = output_dir / "evcc_abrrechnung.txt"
    output_file.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nDatei geschrieben: {output_file}")

if __name__ == "__main__":
    main()
