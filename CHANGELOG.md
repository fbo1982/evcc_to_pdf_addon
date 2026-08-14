# Changelog

## v1.2.0

- Persistenzfehler behoben: `addon_config` wird in Home Assistant unter `/config` in den Container gemountet; Einstellungen werden jetzt dort statt im nicht persistenten `/addon_config/...` gespeichert.
- Einstellungen werden atomar geschrieben und vor Änderungen automatisch gesichert (bis zu 20 Backups).
- Bei beschädigter `settings.json` wird zuerst ein gültiges Backup, danach der MQTT-Spiegel verwendet; beschädigte Dateien bleiben als `settings_corrupt_*.json` erhalten.
- Werkseinstellungen werden bei einem kurzzeitig nicht erreichbaren MQTT-Broker nicht mehr automatisch als retained Konfiguration veröffentlicht.
- Bestehende Legacy-Einstellungen werden, soweit noch vorhanden, nach `/config/settings.json` migriert.
- Neue Gruppenoption **BMF-Strompreispauschale automatisch ermitteln**.
- Für 2026 ist der amtliche Wert 0,34 €/kWh hinterlegt (Basis: Destatis 61243-0001, 1. Halbjahr 2025: 0,3436 €/kWh, auf volle Cent abgerundet).
- Für Folgejahre 2027–2030 versucht das Add-on den amtlichen Destatis-Wert automatisch aus der veröffentlichten CSV-Tabelle zu ermitteln und speichert ihn persistent im Cache.
- Bei manueller Preiswahl bleibt der bisherige Preis-Override unverändert nutzbar.
- In der PDF-Ausgabe wird der zugrunde gelegte Strompreis ausgewiesen. Die Zeile **„Preisermittlung“** wird nur bei BMF-Automatik ausgegeben und entfällt bei manueller Preiswahl vollständig.
- Standardausgabe nach Fahrzeugen gruppiert; jedes Fahrzeug erhält eine eigene Tabelle und eine Zwischensumme.
- Neue Template-Kontexte: `vehicle_groups`, `electricity_price`, `electricity_price_eur_kwh`, `price_mode`, `price_method_label`, `price_source_label`, `price_source_year`.
- Das unveränderte mit v1.1.2 ausgelieferte Standardtemplate wird automatisch auf die neue Ausgabe migriert; individuell bearbeitete Standardtemplates werden nicht überschrieben.

## v1.1.2

- Version auf **v1.1.2** angehoben.
- Fix für das mitgelieferte Standard-Template: verhält sich jetzt wie ein normales Benutzer-Template.
- Änderungen im Editor werden für das Standard-Template gespeichert.
- Standard-Template kann gelöscht werden, sobald ein anderes Template als Default gesetzt ist.
- Ausgeliefertes Standard-HTML auf das bereitgestellte Template aktualisiert.

## v1.1.1

- Version auf **v1.1.1** angehoben.
- Das bisherige **Standard-Template** wird nun als Editor-kompatibles Template ausgeliefert.
- Standard-Template enthält jetzt bereits strukturierte Editor-Bausteine mit den vorhandenen EVCC-/Jinja-Platzhaltern, sodass es direkt im grafischen Editor bearbeitet werden kann.
- Bestehende Installationen erhalten für das Default-Template automatisch die editorfähige Standardstruktur.
- Das mitgelieferte Standard-Template verhält sich jetzt wie ein normales Benutzer-Template: Änderungen aus dem Editor bleiben erhalten und es kann gelöscht werden, sobald ein anderes Template als Default gesetzt wurde.
- Das ausgelieferte Standard-Template verwendet jetzt den bereitgestellten HTML-Inhalt als Startvorlage.

## v1.1.0

✨ Grafischer Template-Editor integriert

### Features
- Neuer visueller Editor für HTML-Templates
- Button "Im Editor" in der Template-Liste
- Drag-&-Drop-Bausteine für strukturierte Layouts
- Live-Vorschau im Editor
- Speicherung kompatibel zum bestehenden Template-System

### Improvements
- Bestehende Templates können weiterhin als freies HTML bearbeitet werden
- Bessere Grundlage für EVCC-spezifische Berichtsvorlagen

---

## v1.0.2

🚀 First stable release

### Features
- Automatische Abrechnung
- Gruppenverwaltung
- HTML Templates
- PDF-Erstellung
- E-Mail Versand
- Scheduler

### Fixes
- Template Rendering
- Datenfilterung
- Safe Storage stabilisiert

---

## v0.7.0
- Automatik eingeführt

## v0.6.x
- PDF Layout
- Templates
- Gruppenlogik
