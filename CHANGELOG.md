# Changelog

Alle relevanten Änderungen an **EVCC to PDF** werden hier versionsweise dokumentiert.

## v1.3.05 – 14.08.2026

### Schlankere PDF-Gruppentabelle
- In **Weitere Abrechnungsgruppen** die Spalte **Strompreis** entfernt.
- **Gesamtverbrauch** und **Gesamtkosten** im Summenblock dezent hervorgehoben.
- Sensorgruppen zeigen im Standard-PDF nur noch Gruppenname, Verbrauch und Kosten.
- Der gemeinsame Strompreis wird weiterhin einmal zentral im Summenblock ausgewiesen.

### BMF-/Destatis-Grundlage präzisiert
- Preisermittlung im Standard-PDF als **BMF-Strompreispauschale <Jahr> (Jahrespauschale)** gekennzeichnet.
- Grundlage ergänzt um den Hinweis, dass das **1. Halbjahr des Vorjahres** die BMF-Basis für das gesamte Kalenderjahr ist.
- Für 2026 bleibt damit unverändert **0,34 €/kWh** maßgeblich, basierend auf Destatis 61243-0001, 1. Halbjahr 2025 (34,36 ct/kWh, auf volle Cent abgerundet).
- Dokumentation präzisiert den Anwendungsbereich: Die BMF-Pauschale ist eine Regel für häusliches Laden betrieblicher E-/Hybridfahrzeuge; bei zusätzlichen HA-Gruppen wird derselbe Wert nur als einheitlicher Rechenpreis verwendet.
- Kein unterjähriger Wechsel auf Werte des 2. Halbjahres.

### Template-Kompatibilität
- Unverändertes v1.3.04-Standardtemplate wird automatisch auf die neue dreispaltige Gruppentabelle migriert.
- Individuell bearbeitete Templates bleiben unangetastet.
- Versionsnummer auf **v1.3.05** angehoben.

## v1.3.04 – 14.08.2026

### Übersichtlicher Sensorgruppen-Editor
- Home-Assistant-Sensorgruppen werden nicht mehr gleichzeitig untereinander dargestellt.
- Neues Dropdown **Sensorgruppe auswählen**: Es ist immer genau eine Gruppe aktiv und sichtbar.
- Beim Bearbeiten werden nur Gruppenname und Sensoren der ausgewählten Gruppe angezeigt; alle anderen Gruppen bleiben ausgeblendet.
- **+ Neue Sensorgruppe** legt eine Gruppe an und aktiviert sie sofort, sodass der Name direkt vergeben werden kann.
- Der Sensorpicker ordnet neue Sensoren automatisch der aktiven Gruppe zu; die zusätzliche Auswahl **Zielgruppe** entfällt.
- Sortieren und Löschen wirken ausschließlich auf die aktuell ausgewählte Gruppe.
- Das Dropdown zeigt zusätzlich die Anzahl der zugeordneten Sensoren pro Gruppe an.

### Kompatibilität
- Datenmodell und PDF-Ausgabe bleiben unverändert: beliebig viele Sensorgruppen, beliebig viele Sensoren, HA-Gruppen nur als Summe und Fahrzeuge weiterhin einzeln transparent.
- Bestehende v1.3.03-Konfigurationen sind ohne Migration kompatibel.
- Persistenz, Legacy-Migration, Backups, Gunicorn und Home-Assistant-App-Lifecycle aus v1.3.03 bleiben unverändert erhalten.
- Versionsnummer auf **v1.3.04** angehoben.

## v1.3.03 – 14.08.2026

### Persistenz & Update-Sicherheit
- Primärer Datenspeicher auf **`/data/evcc_to_pdf`** umgestellt. Dort liegen `settings.json`, Backups sowie BMF- und HA-Entity-Caches.
- Vor dem Erzeugen von Werkseinstellungen werden alle bekannten älteren Speicherorte geprüft.
- Einstellungen aus v1.3.02 und älteren Versionen werden von `/config/settings.json` und weiteren Legacy-Pfaden automatisch nach `/data/evcc_to_pdf/settings.json` migriert.
- Ist eine alte `settings.json` beschädigt, wird zusätzlich nach einem gültigen Legacy-Backup gesucht und dieses zur Migration verwendet.
- Vorhandene Legacy-Backups und gültige Cache-Dateien werden übernommen, ohne die alten Dateien zu löschen.
- Atomare Speicherung und die letzten 20 gültigen Backups bleiben erhalten.

### Home-Assistant-App-Lifecycle
- `startup` von `services` auf **`application`** geändert, da EVCC to PDF auf Home Assistant und dessen API aufbaut.
- `init: false` entfernt; der Supervisor kann wieder sein Standard-Init verwenden.
- Supervisor-Stop-Timeout auf 20 Sekunden gesetzt.
- Legacy-Mount `addon_config` auf **`app_config`** umgestellt. Der Kompatibilitäts-Mount wird read-only unter `/config` eingebunden, damit alte Einstellungen während des Updates noch migriert werden können.

### Webserver & Logging
- Flask-Entwicklungsserver durch **Gunicorn** ersetzt.
- Ein Gunicorn-Worker mit vier Threads verhindert mehrfach gestartete Scheduler und erlaubt parallele Webanfragen.
- Scheduler wird über einen WSGI-Einstiegspunkt genau einmal pro Worker gestartet und beim Prozessende sauber beendet.
- Fehler beim Aktualisieren von EVCC-Assets und Home-Assistant-Entitäten werden jetzt zusätzlich mit Stacktrace ins App-Log geschrieben.
- Scheduler-Fehler werden nicht mehr still verworfen, sondern protokolliert.

### Kompatibilität
- Abrechnungsmodell aus v1.3.02 unverändert beibehalten: beliebig viele Sensor-Abrechnungsgruppen, beliebig viele Verbrauchssensoren, gemeinsame Preislogik und transparente Einzelausgabe der Fahrzeuge.
- Individuell bearbeitete Templates bleiben unverändert.
- Versionsnummer auf **v1.3.03** angehoben.

## v1.3.02 – 14.08.2026

### Beliebig viele Sensor-Abrechnungsgruppen
- Innerhalb einer Abrechnung können jetzt beliebig viele frei benannte Home-Assistant-Sensorgruppen angelegt werden, z. B. **HomeOffice**, **Server** oder **Klimaanlage**.
- Jeder Sensorgruppe können beliebig viele geeignete Energie-/Leistungssensoren zugewiesen werden.
- Gruppenreihenfolge kann über Auf/Ab-Schaltflächen geändert werden und bestimmt die Reihenfolge im Standard-PDF.
- Ein HA-Sensor kann über die Oberfläche nur einer Sensorgruppe zugeordnet werden, um versehentliche Mehrfachsummierung zu vermeiden.
- Der bestehende Schalter **In Gruppensumme einrechnen** bleibt pro Sensor erhalten.

### PDF-Transparenz
- Home-Assistant-Verbrauch wird im Standard-PDF nicht mehr bis auf einzelne Shelly-/Entity-IDs aufgelöst.
- Für HA erscheint nur **Gruppenname + Gruppenverbrauch + Strompreis + Gruppenbetrag**.
- EVCC-Fahrzeuge bleiben bewusst einzeln sichtbar. Ihre einzelnen Ladevorgänge und Fahrzeug-Zwischensummen werden weiterhin vollständig aufgeführt.
- Gesamtverbrauch und Gesamtkosten kombinieren Fahrzeugverbrauch und alle einbezogenen Sensorgruppen.

### Einheitlicher Preis
- Manueller oder automatischer Strompreis gilt weiterhin einmal für die komplette Abrechnung und damit identisch für Fahrzeuge und alle Sensorgruppen.
- Bei manueller Preiswahl bleibt die Zeile **Preisermittlung** im Standard-PDF ausgeblendet.

### Migration & Kompatibilität
- Flache `ha_sources`-Konfigurationen aus v1.3.01 werden automatisch in eine benannte Sensor-Abrechnungsgruppe migriert.
- `ha_sources` bleibt als flacher Template-Alias für bestehende eigene Templates erhalten.
- Neue Template-Kontexte `billing_groups` und `sensor_groups`.
- Das unveränderte v1.3.01-Standardtemplate wird automatisch auf die neue Gruppensummen-Darstellung migriert; bearbeitete Templates bleiben unangetastet.

### Oberfläche & Dokumentation
- Gruppenansicht trennt jetzt klar zwischen kompletter **Abrechnung**, einzelnen **Fahrzeugen** und benannten **Sensor-Abrechnungsgruppen**.
- Sensorpicker behält Suche sowie Filter Alle / Energie / Leistung und den EVCC-Sensor-Ausschluss bei.
- README, App-README, DOCS und Platzhalter-Dokumentation aktualisiert.
- Neue `RELEASE_CHECKLIST.md`, damit Persistenz-, Migrations-, Template- und Testregeln bei Folgeversionen beibehalten werden.
- Versionsnummer auf **v1.3.02** angehoben.

## v1.3.01 – 14.08.2026

### Gemeinsame Verbrauchergruppen
- Getrennte Gruppentypen **EVCC** und **Home Assistant** aufgehoben.
- Eine Abrechnungsgruppe kann jetzt gleichzeitig EVCC-Fahrzeuge und Home-Assistant-Verbrauchssensoren enthalten.
- Gemeinsame Gesamtsumme aus EVCC-Verbrauch und allen einbezogenen HA-Verbrauchern.
- Fahrzeuggruppierung und Fahrzeug-Zwischensummen bleiben innerhalb derselben Abrechnung erhalten.
- Home-Assistant-Verbraucher werden zusätzlich als eigene Positionen im selben PDF ausgegeben.
- Alte v1.3.0-Gruppen werden automatisch migriert; vorhandene Quellen bleiben erhalten.

### Einheitlicher Strompreis
- Der Gruppenstrompreis gilt jetzt für alle enthaltenen Verbraucher.
- BMF-/Destatis-Automatik ist nicht mehr an einen EVCC-Gruppentyp gekoppelt und kann für die komplette Abrechnungsgruppe verwendet werden.
- Manuelle Preiswahl zeigt weiterhin keine zusätzliche Zeile „Preisermittlung“.

### Sensorfilter
- HA-Auswahlliste beschränkt sich auf echte Energie- und Leistungssensoren.
- EVCC-eigene Home-Assistant-Sensoren werden über die Entity Registry bzw. einen Namens-Fallback automatisch ausgefiltert.
- Climate-, Switch- und andere reine Laufzeit-Entitäten werden im Picker nicht mehr angeboten.
- Neuer UI-Filter: **Alle Verbrauchssensoren / Energie / Leistung** plus Freitextsuche.
- Bereits konfigurierte v1.3.0-Laufzeitquellen bleiben aus Kompatibilitätsgründen erhalten.

### Templates & Oberfläche
- Standardtemplate auf kombinierte EVCC-/HA-Ausgabe umgestellt.
- Unverändertes v1.3.0-Standardtemplate wird automatisch migriert; bearbeitete Templates bleiben unangetastet.
- Dashboard, Gruppenansicht, README, Dokumentation und Platzhalterliste aktualisiert.
- Versionsnummer auf **v1.3.01** angehoben.

## v1.3.0 – 14.08.2026

### Modulare Abrechnungsgruppen
- Gruppen besitzen jetzt einen Typ: **EVCC** oder **Home Assistant**.
- Bestehende Gruppen werden automatisch als EVCC-Gruppen migriert und bleiben kompatibel.
- Home-Assistant-Gruppen können beliebig viele Verbrauchsquellen enthalten.
- Pro Quelle kann festgelegt werden, ob sie in die Gruppensumme einfließt. Dadurch lassen sich Detailzähler anzeigen, ohne sie doppelt zu summieren.

### Home-Assistant-Integration
- Direkter Zugriff auf Home Assistant Core über die offizielle interne App-API (`homeassistant_api: true`).
- Geeignete Entitäten können aus Home Assistant geladen und in der Gruppenoberfläche ausgewählt werden.
- Energie-Sensoren in Wh/kWh/MWh werden als Zähler ausgewertet.
- Leistungssensoren in W/kW/MW werden über den Zeitraum zu kWh integriert.
- Home-Assistant-Langzeitstatistiken werden bevorzugt verwendet; Recorder-History dient als Fallback.
- Climate-/Switch-/Binary-Sensor-/Input-Boolean-Entitäten können optional über Laufzeit × Nennleistung geschätzt werden.
- Enthaltene Quellen mit fehlender Datenbasis brechen die Abrechnung mit einer Fehlermeldung ab, statt einen unvollständigen Betrag auszugeben.

### Preise & Berichte
- Home-Assistant-Gruppen verwenden den manuellen Gruppen-/Standard-Strompreis.
- BMF-/Destatis-Automatik bleibt auf EVCC-Gruppen begrenzt.
- Standard-PDF unterstützt jetzt Home-Assistant-Quellen mit Entity-ID, Verbrauch, Kosten, Berechnungsmethode und Summierungsstatus.
- EVCC-Fahrzeuggruppierung und Fahrzeug-Zwischensummen bleiben erhalten.
- Neue Template-Kontexte: `group_name`, `group_type`, `ha_sources`.
- Editor-Tabellenblock kann EVCC- und Home-Assistant-Zeilen darstellen.

### Branding & Oberfläche
- Neues Homeoffice-/E-Mobility-Logo mit Schreibtisch, Wallbox, Fahrzeug und Energieabrechnung.
- App-Icon, Favicon, Store-Logo, Wide-Logo und README-Hero aktualisiert.
- Dashboard und Gruppenverwaltung auf die modulare Energieabrechnung umgestellt.
- Versionsnummer auf **v1.3.0** angehoben.

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
