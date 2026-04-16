# EVCC to PDF

Automatisierte Abrechnung von Ladevorgängen aus EVCC als PDF inklusive E-Mail Versand.

## 💡 Motivation

Aktuell existiert kein Tool, das automatisch aus den EVCC-Daten eine saubere Abrechnung für Arbeitgeber generiert.

Gerade bei Firmenfahrzeugen, die zu Hause geladen werden, muss der Stromverbrauch dokumentiert und abgerechnet werden.

Dieses Projekt löst genau dieses Problem:
- Auslesen der Ladevorgänge aus EVCC
- Aufbereitung als übersichtliche Abrechnung
- Automatische PDF-Erstellung
- Versand per E-Mail

Zusätzlich können mehrere Gruppen verwaltet werden, z. B.:
- mehrere Arbeitgeber
- mehrere Fahrzeuge
- unterschiedliche Abrechnungslogiken

---

## 🔗 Repository

GitHub Repository:  
[https://github.com/fbo1982/evcc_to_pdf_addon.git](https://github.com/fbo1982/evcc_to_pdf_addon.git)

---

## 🏠 Home Assistant Repository direkt hinzufügen

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_addon_repository/?repository_url=https://github.com/fbo1982/evcc_to_pdf_addon.git)

---

## ⚙️ Installation in Home Assistant

### Variante 1: Direkt per Button
Einfach den Button oben anklicken und das Repository direkt in Home Assistant hinzufügen.

### Variante 2: Manuell
1. Home Assistant öffnen
2. **Einstellungen** → **Add-ons**
3. **Add-on Store** öffnen
4. oben rechts auf Menü **⋮**
5. **Repositories** auswählen
6. folgendes Repository einfügen:

```text
https://github.com/fbo1982/evcc_to_pdf_addon.git
