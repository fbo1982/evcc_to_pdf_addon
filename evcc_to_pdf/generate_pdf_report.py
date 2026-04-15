import argparse
import locale
import logging
import os
import smtplib
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


class InfoFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == logging.INFO


stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
stdout_handler.addFilter(InfoFilter())

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[stdout_handler, stderr_handler],
)
logger = logging.getLogger(__name__)
logging.getLogger("fontTools.subset").setLevel(logging.WARN)


@dataclass
class Config:
    evcc_url: str
    evcc_password: str
    grid_price: float
    selected_vehicles: List[str]
    smtp_server: Optional[str]
    smtp_port: int
    sender_email: Optional[str]
    sender_password: Optional[str]
    recipient_email: Optional[str]
    sender_name: str
    sender_street: str
    sender_city: str
    locale: str
    output_folder: str = "./output"

    @classmethod
    def from_env(cls) -> "Config":
        raw_vehicles = os.environ.get("SELECTED_VEHICLES", "")
        selected_vehicles = [item.strip() for item in raw_vehicles.split(",") if item.strip()]
        return cls(
            evcc_url=os.environ.get("EVCC_URL", "http://localhost:7070").rstrip("/"),
            evcc_password=os.environ.get("EVCC_PASSWORD", ""),
            grid_price=float(os.environ.get("GRID_PRICE", "0.0")),
            selected_vehicles=selected_vehicles,
            smtp_server=os.environ.get("SMTP_SERVER") or None,
            smtp_port=int(os.environ.get("SMTP_PORT", 587)),
            sender_email=os.environ.get("SENDER_EMAIL") or None,
            sender_password=os.environ.get("SENDER_PASSWORD") or None,
            recipient_email=os.environ.get("RECIPIENT_EMAIL") or None,
            sender_name=os.environ.get("SENDER_NAME", "John Doe"),
            sender_street=os.environ.get("SENDER_STREET", "Sample Street 123"),
            sender_city=os.environ.get("SENDER_CITY", "12345 Sample City"),
            locale=os.environ.get("LOCALE", "de_DE.UTF-8"),
        )


class ReportGenerator:
    def __init__(self, config: Config):
        self.config = config
        self._setup_locale()

    def _setup_locale(self) -> None:
        candidates = [self.config.locale, "de_DE.UTF-8", "en_US.UTF-8", "C.UTF-8", "C"]
        for candidate in candidates:
            try:
                locale.setlocale(locale.LC_ALL, candidate)
                logger.info("Locale gesetzt: %s", candidate)
                return
            except locale.Error:
                continue
        logger.warning("Keine gewünschte Locale verfügbar. Nutze Standard-Locale.")

    @property
    def template_file(self) -> str:
        if self.config.locale.lower().startswith("de"):
            return "template_de.html"
        return "template_en.html"

    def fetch_data(self, year: int, month: int) -> Optional[List[Dict[str, Any]]]:
        api_url = f"{self.config.evcc_url}/api/sessions?lang=en&year={year}&month={month}"
        session = requests.Session()

        if self.config.evcc_password:
            try:
                login_url = f"{self.config.evcc_url}/api/auth/login"
                login_resp = session.post(
                    login_url,
                    json={"password": self.config.evcc_password},
                    timeout=20,
                    verify=False,
                )
                if login_resp.status_code != 200:
                    logger.error("Fehler beim Login. Statuscode: %s", login_resp.status_code)
                    return None
            except requests.exceptions.RequestException as err:
                logger.error("Verbindungsfehler beim Login: %s", err)
                return None

        logger.info("Lade EVCC-Sessions für %02d/%04d von %s", month, year, api_url)
        try:
            response = session.get(api_url, timeout=30, verify=False)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                logger.info("%d Sessions geladen.", len(payload))
                return payload
            logger.error("Unerwartetes API-Format erhalten.")
            return None
        except requests.exceptions.HTTPError as err:
            logger.error("HTTP-Fehler beim Abruf: %s", err)
        except requests.exceptions.RequestException as err:
            logger.error("Verbindungsfehler zu EVCC: %s", err)
        return None

    def process_data(self, json_data: List[Dict[str, Any]]) -> pd.DataFrame:
        if not json_data:
            return pd.DataFrame()

        raw = pd.DataFrame(json_data)
        mapping = {
            "created": "Start Time",
            "finished": "End Time",
            "loadpoint": "Charging Point",
            "vehicle": "Vehicle",
            "chargedEnergy": "Energy (kWh)",
        }

        available = [src for src in mapping if src in raw.columns]
        if not available:
            logger.warning("Keine erwarteten Spalten in den EVCC-Sessions gefunden.")
            return pd.DataFrame()

        df = raw.rename(columns=mapping)

        for col in ["Start Time", "End Time"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        if "Vehicle" not in df.columns:
            df["Vehicle"] = ""

        if self.config.selected_vehicles:
            wanted = set(self.config.selected_vehicles)
            df = df[df["Vehicle"].fillna("").isin(wanted)]

        if df.empty:
            return pd.DataFrame()

        if "Energy (kWh)" in df.columns:
            df["Energy (kWh)"] = pd.to_numeric(df["Energy (kWh)"], errors="coerce").fillna(0.0)
        else:
            df["Energy (kWh)"] = 0.0

        if "Start Time" in df.columns and "End Time" in df.columns:
            duration = df["End Time"] - df["Start Time"]
            df["Charging Duration"] = duration.apply(self._format_duration)
        else:
            df["Charging Duration"] = ""

        df["Price"] = (df["Energy (kWh)"] * self.config.grid_price).round(2)

        if "Start Time" in df.columns:
            df = df.sort_values(by="Start Time", ascending=True, na_position="last").reset_index(drop=True)

        ordered_columns = [
            "Start Time",
            "End Time",
            "Charging Point",
            "Vehicle",
            "Energy (kWh)",
            "Charging Duration",
            "Price",
        ]
        for column in ordered_columns:
            if column not in df.columns:
                df[column] = ""
        return df[ordered_columns]

    @staticmethod
    def _format_duration(value: Any) -> str:
        if pd.isna(value):
            return ""
        total_minutes = int(value.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        return f"{hours}h {minutes:02d}m"

    def _format_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        if "Start Time" in result.columns:
            result["Start Time"] = result["Start Time"].dt.strftime("%Y-%m-%d %H:%M").fillna("")
        if "End Time" in result.columns:
            result["End Time"] = result["End Time"].dt.strftime("%Y-%m-%d %H:%M").fillna("")
        if "Energy (kWh)" in result.columns:
            result["Energy (kWh)"] = result["Energy (kWh)"].apply(
                lambda x: locale.format_string("%.3f", x, grouping=True)
            )
        if "Price" in result.columns:
            result["Price"] = result["Price"].apply(
                lambda x: locale.format_string("%.2f", x, grouping=True)
            )
        return result

    def generate_pdf(self, df: pd.DataFrame, year: int, month: int) -> Tuple[Optional[str], Optional[str]]:
        if df.empty:
            logger.warning("Keine passenden Ladesessions gefunden. Es wird kein PDF erstellt.")
            return None, None

        env = Environment(loader=FileSystemLoader("."))
        template = env.get_template(self.template_file)
        formatted = self._format_dataframe(df)

        total_energy = float(df["Energy (kWh)"].sum())
        total_price = float(df["Price"].sum())
        month_name = self._month_name(year, month)

        summary = {
            "selected_vehicles": ", ".join(self.config.selected_vehicles) if self.config.selected_vehicles else "Alle Fahrzeuge",
            "grid_price": locale.format_string("%.2f", self.config.grid_price, grouping=True),
            "total_energy": locale.format_string("%.3f", total_energy, grouping=True),
            "total_price": locale.format_string("%.2f", total_price, grouping=True),
        }
        sender = {
            "name": self.config.sender_name,
            "street": self.config.sender_street,
            "city": self.config.sender_city,
        }

        html = template.render(
            sender=sender,
            creation_date=datetime.now().strftime("%Y-%m-%d"),
            period=f"{month_name} {year}",
            charges=formatted.to_dict("records"),
            total_energy=summary["total_energy"],
            total_price=summary["total_price"],
            summary=summary,
        )

        pdf_filename = f"ChargingCostSummary_{year}-{month:02d}.pdf"
        os.makedirs(self.config.output_folder, exist_ok=True)
        pdf_path = os.path.join(self.config.output_folder, pdf_filename)
        HTML(string=html).write_pdf(pdf_path)
        logger.info("PDF erstellt: %s", pdf_path)
        return pdf_path, pdf_filename

    def _month_name(self, year: int, month: int) -> str:
        try:
            return locale.nl_langinfo(locale.MON_1 + month - 1)
        except Exception:
            return datetime(year, month, 1).strftime("%B")

    def send_email(self, subject: str, body: str, attachment_path: str) -> None:
        if not all([
            self.config.sender_email,
            self.config.sender_password,
            self.config.recipient_email,
            self.config.smtp_server,
        ]):
            logger.info("Mailversand übersprungen: SMTP-Daten unvollständig.")
            return

        msg = MIMEMultipart()
        msg["From"] = self.config.sender_email
        msg["To"] = self.config.recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with open(attachment_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(attachment_path)}",
            )
            msg.attach(part)

        server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
        server.starttls()
        server.login(self.config.sender_email, self.config.sender_password)
        server.send_message(msg)
        server.quit()
        logger.info("E-Mail erfolgreich versendet.")

    def run(self, year: Optional[int] = None, month: Optional[int] = None) -> None:
        if year is None or month is None:
            today = datetime.now()
            last_day_previous_month = today.replace(day=1) - timedelta(days=1)
            year = year or last_day_previous_month.year
            month = month or last_day_previous_month.month

        logger.info("Starte Bericht für %02d/%04d", month, year)
        json_data = self.fetch_data(year, month)
        if not json_data:
            logger.error("Keine Daten von EVCC erhalten.")
            return

        df = self.process_data(json_data)
        pdf_path, _ = self.generate_pdf(df, year, month)
        if not pdf_path:
            return

        month_name = self._month_name(year, month)
        subject = f"Charging Cost Summary for {month_name} {year}"
        body = f"Attached is the charging cost summary for {month_name} {year}."
        self.send_email(subject, body, pdf_path)
        logger.info("Bericht abgeschlossen.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate EVCC charging report PDF.")
    parser.add_argument("--year", type=int, help="Year for the report, e.g. 2025")
    parser.add_argument("--month", type=int, help="Month for the report, 1-12")
    args = parser.parse_args()

    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
    config = Config.from_env()
    generator = ReportGenerator(config)
    generator.run(year=args.year, month=args.month)


if __name__ == "__main__":
    main()
