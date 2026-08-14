# Changelog

Alle relevanten Änderungen an **EVCC to PDF** werden hier versionsweise dokumentiert.

## v1.2.02

### Branding & Home Assistant
- Neues EVCC-to-PDF-App-Icon hinzugefügt (`icon.png`, 128×128).
- Neues Home-Assistant-App-Logo hinzugefügt (`logo.png`, 250×100).
- Weboberfläche zeigt das neue Logo-Icon direkt im Kopfbereich.
- Favicon für die Weboberfläche ergänzt.
- Branding bewusst ohne fest eingebrannte Versionsnummer aufgebaut, damit es bei zukünftigen Releases weiterverwendet werden kann.

### Dokumentation
- Root-README vollständig überarbeitet und für die öffentliche GitHub-Seite aufbereitet.
- Hero-Grafik, Funktionsübersicht, Schnellstart, Screenshots, Persistenz- und Template-Hinweise ergänzt.
- Home-Assistant-App-README auf eine kompakte Store-Beschreibung zugeschnitten.
- Neue `DOCS.md` mit ausführlicher Bedienungs- und Konfigurationsdokumentation ergänzt.
- Changelog strukturiert und Branding-Release dokumentiert.

## v1.2.01

- Versionsanzeige im Kopfbereich der Weboberfläche ergänzt.
- Die angezeigte Version wird zentral aus `APP_VERSION` übernommen.
- Add-on-Version auf **v1.2.01** angehoben.

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

- Fix für das mitgelieferte Standard-Template: verhält sich jetzt wie ein normales Benutzer-Template.
- Änderungen im Editor werden für das Standard-Template gespeichert.
- Standard-Template kann gelöscht werden, sobald ein anderes Template als Default gesetzt ist.
- Ausgeliefertes Standard-HTML auf das bereitgestellte Template aktualisiert.

## v1.1.1

- Standard-Template als Editor-kompatibles Template ausgeliefert.
- Strukturierte Editor-Bausteine mit EVCC-/Jinja-Platzhaltern ergänzt.
- Bestehende Installationen erhalten für das Default-Template automatisch die editorfähige Standardstruktur.
- Standard-Template kann wie ein Benutzer-Template gespeichert und – mit anderem Default – gelöscht werden.

## v1.1.0

- Grafischen Template-Editor integriert.
- Drag-&-Drop-Bausteine und Live-Vorschau ergänzt.
- Bestehende Templates können weiterhin als freies HTML bearbeitet werden.

## v1.0.2

- Erste stabile Version mit automatischer Abrechnung, Gruppenverwaltung, HTML-Templates, PDF-Erstellung, E-Mail-Versand und Scheduler.

## v0.7.0

- Automatik eingeführt.

## v0.6.x

- PDF-Layout, Templates und Gruppenlogik aufgebaut.
