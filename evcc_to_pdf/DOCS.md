# EVCC to PDF – Dokumentation

## Zweck

EVCC to PDF liest Ladevorgänge aus einer EVCC-Installation aus, ordnet sie konfigurierten Gruppen und Fahrzeugen zu und erstellt daraus PDF-Abrechnungen. Die Berichte können manuell erzeugt oder zeitgesteuert per E-Mail verschickt werden.

## 1. EVCC verbinden

Öffne **Einstellungen** und trage die Basis-URL deiner EVCC-Instanz ein. Falls deine EVCC-Instanz geschützt ist, ergänze das Passwort.

## 2. E-Mail-Versand einrichten

Für den automatischen Versand werden SMTP-Host, Port, Benutzername und Passwort benötigt. TLS kann in der Oberfläche aktiviert werden. Als Absender kann je Gruppe eine passende Absenderadresse verwendet werden.

## 3. Gruppen anlegen

Eine Gruppe bündelt die Regeln für eine Abrechnung. Dazu gehören unter anderem:

- Name der Gruppe
- zu berücksichtigende Fahrzeuge
- Empfänger und Absender
- Abrechnungsintervall
- Versandtag
- Ort und optionale Kontodaten
- HTML-Template
- Strompreismodus

### Strompreis: Manuell

Bei **Manuell** wird der eingetragene Preis-Override in €/kWh verwendet. Im fertigen Bericht erscheint nur der tatsächlich zugrunde gelegte Strompreis.

### Strompreis: BMF-Strompreispauschale

Bei aktivierter Automatik ermittelt das Add-on den für das Abrechnungsjahr vorgesehenen Pauschalwert. Für 2026 ist 0,34 €/kWh hinterlegt. Für unterstützte Folgejahre versucht das Add-on den passenden Destatis-Wert abzurufen und lokal zwischenzuspeichern.

Im Bericht werden dann zusätzlich Preisermittlung, Quelle und Bezugsjahr ausgewiesen.

## 4. Berichte erzeugen

Unter **Manuell** können Zeitraum und Gruppe ausgewählt werden. Vor dem Versand empfiehlt sich zunächst eine Vorschau.

Die Standardausgabe gliedert die Ladevorgänge nach Fahrzeug. Jedes Fahrzeug erhält:

- eigene Ladevorgangstabelle
- geladene kWh
- Kosten je Ladevorgang
- Fahrzeug-Zwischensumme

Am Ende folgen GesamtkWh, Gesamtkosten und der verwendete Strompreis.

## 5. Automatik

Der Scheduler kann unter **Einstellungen** aktiviert werden. Der konkrete Versandtag kann pro Gruppe gesetzt werden. Bereits abgearbeitete Perioden werden gespeichert, damit dieselbe Abrechnung nicht versehentlich mehrfach automatisch verschickt wird.

## 6. HTML-Templates

Unter **HTML Templates** können Vorlagen erstellt, bearbeitet und als Standard gewählt werden. Das mitgelieferte Standardtemplate verhält sich wie ein normales Benutzer-Template.

Der grafische Editor bietet Bausteine und eine Vorschau; alternativ kann HTML direkt bearbeitet werden. Verfügbare Variablen und Platzhalter sind in `PLACEHOLDERS.md` dokumentiert.

## 7. Speicherung und Backups

Benutzerdaten werden persistent im von Home Assistant bereitgestellten App-Konfigurationsbereich gespeichert. Änderungen an `settings.json` erfolgen atomar. Vor Änderungen werden Backups erzeugt.

Falls die Hauptdatei beschädigt ist, wird versucht:

1. ein gültiges lokales Backup zu laden,
2. alternativ die MQTT-Spiegelung zu verwenden.

Beschädigte Dateien werden nicht kommentarlos überschrieben, sondern separat aufbewahrt.

## 8. PDF-Ablage

Erzeugte PDFs werden unter `/share/evcc-pdfs` gespeichert und können dadurch auch außerhalb des Containers über Home Assistant verwendet werden.

## 9. Branding

Die App liefert `icon.png` und `logo.png` direkt mit. Home Assistant kann diese Dateien im App-Store und in der App-Darstellung verwenden. Die Weboberfläche verwendet dasselbe Icon im Header und als Favicon.

## 10. Hinweise

EVCC to PDF ist keine Steuer-, Rechts- oder Lohnabrechnungsberatung. Die BMF-/Destatis-Funktion dient dazu, die technische Berechnung nach der implementierten Regel nachvollziehbar zu automatisieren. Prüfe betriebliche und rechtliche Anforderungen für deinen konkreten Einsatz.
