# Anwendung erklärt und Aufteilung in vier gleichwertige Teile

## 1. Was die Anwendung kann
Die Software simuliert ein Jahr (365 Tage, nach 60 Tagen Einschwingphase) einer Premium-Armbanduhr mit Montage in Heilbronn.
Jede Nachfrage, Bestellung, Fertigung und Sendung ist ein Ereignis (SimPy). Ihr könnt Szenarien wählen, Störungen einbauen,
Stammdaten ändern und die Ergebnisse in drei Sichten ansehen.

**Bedienung (linke Seite)**
1. *Szenario & Parameter:* Basis und vier Stressszenarien, Sicherheitsbestand, Bestellmengen-Faktor, Jahresnachfrage, Luftfracht-Politik, Umleitung nach Zeit/Kosten/CO₂e, stochastisch oder deterministisch, Seed, Anzahl Replikationen.
2. *Eingriffe:* Knoten sperren, Lieferant ausfallen lassen, Verkehrsträger sperren, Nachfrage ×, Transportzeit ×. Auch per Klick auf einen Kartenknoten.
3. *Läufe:* Einzellauf (Animation), Auswertung (alle Szenarien × n Replikationen), Rastersuche mit Pareto-Front.

**Register (oben im Hauptfenster)**
| Register | Was es zeigt |
|---|---|
| Karte (animiert) | Sendungen als Punkte auf ihren Transportwegen, Farbe = Komponente, Größe = Menge. Gesperrte Wege rot gestrichelt, ausgefallene Knoten rotes X, Klick auf Knoten = Eingriff. Geschwindigkeit wählbar (sehr langsam bis sehr schnell), Schieberegler = Tag, Knöpfe Welt/Europa. |
| Diagramme | (1) **Bestandsreichweite** je Komponente in Tagen der Durchschnittsnachfrage, rote Flächen = Störung. Sägezahn = Verbrauch und Wareneingang; Null = Fehlbestand. (2) **Nachfrage je Woche**: Balken geliefert (grün) und Fehlmenge (rot), Linie = Servicegrad der Woche, gestrichelt = Ziel 97 %. (3) **Lagerwert** in € (Komponenten + Fertigwaren). (4) **Wiederbeschaffungszeit** je Komponente von Bestellung bis Wareneingang (inkl. Tier-2-Vorlauf, Fertigung, Transport). (5) **Aufbau der Landed Cost** (Einkauf, Fracht, Zoll, Montage). |
| Kennzahlen | Die fünf Zielkriterien des Einzellaufs und der Szenariovergleich (Mittelwert ± 95-%-Konfidenzintervall über n Replikationen) mit Balkendiagrammen; „NEIN“ markiert, wenn β < 97 %. |
| Pareto / Rastersuche | Variantenraster (Sicherheitsbestand × Luftfracht × Bestellmenge) im gewählten Szenario; rote Rauten = Pareto-optimal unter β ≥ 97 %. Achsen wählbar. |
| Stammdaten (editierbar) | Preis, Gewicht, Zoll, Bestellmenge je Komponente; Kosten, Dauer je Transportkante; Fertigungszeiten je Lieferant; Lohn, Montagezeit, Lagerzins, Emissionsfaktoren. Gelbe Zellen sind editierbar, die Prüfung zeigt sofort die Handrechnung der Landed Cost oder einen Fehler. |
| Prüfung & Annahmen | Automatischer Check der Mindestanforderungen aus der Aufgabenstellung und die Stammdaten. |

**Die fünf Zielkriterien (getrennt, ohne Gesamt-Score)**
Landed Cost [€/Uhr] (Einkauf + Fracht + Zoll + Montage), Lieferzeit [Tage] (langsamste Komponente), Servicegrad β [%] (Anteil befriedigter Nachfrage), CO₂e [kg/Uhr], Ø Lagerwert [€].

**Wichtig bei der Interpretation:** Fracht und Zoll machen nur etwa 0,7 % der Landed Cost aus; die Kosten ändern sich daher kaum. Die Wirkung der Szenarien sieht man bei Lieferzeit, Servicegrad, Lagerwert und CO₂e.

## 2. Aufteilung in vier gleichwertige Teile
Maßstab: etwa 450–500 Zeilen Code bzw. Konfiguration je Teil, vergleichbarer Schwierigkeitsgrad, je ein eigener Testblock, je ein Kapitel im Bericht. Wer welchen Teil übernimmt, entscheidet die Gruppe.

| Teil | Titel | Dateien | Inhalt | Schnittstelle / Abnahme |
|---|---|---|---|---|
| **A Alex** | Simulationskern & Routing | `scm/engine.py` (324 Z.), `scm/network.py` (152 Z.) | SimPy-Prozesse (Nachfrage → Verkauf → Montage → (s,Q)-Bestellung → Tier-2 → Tier-1 → Transport → Wareneingang), Lagerbewertung, KPI-Berechnung, Störungszustand, Dijkstra-Umleitung | Liefert `RunResult`. Tests: Handrechnung, Flusserhaltung, Reproduzierbarkeit, Routing |
| **B Leon** | Daten, Konfiguration & Recherche | `scm/config.py` (334 Z. inkl. Stammdaten-Override), `config/base.yaml` (141 Z.), `config/scenarios/*.yaml`, `ANNAHMEN.md` | Datenmodell, Validierung (Einheiten, Plausibilität), Szenarien, Mindestanforderungen-Check, Quellenrecherche und Pflege aller Werte | Liefert `Config`. Tests: ungültige Konfigurationen, Szenarien auf gleichem Modell, Stammdaten-Override |
| **C Elaine** | Experimente & Auswertung | `scm/runner.py` (97 Z.), `scm/cli.py` (54 Z.), Auswertungsteile von `scm/viz.py` (Szenario-Balken, Kennzahlen, Pareto, ca. 100 Z.), Callbacks Auswertung/Pareto in `app.py` (ca. 80 Z.) | Replikationen, Konfidenzintervalle, Common Random Numbers, Szenariovergleich, Rastersuche, Pareto-Front; zusätzlich Sensitivitätsanalyse und Validierung (neu zu schreiben) | Nutzt `Config` und `RunResult`. Tests: Intervalle, Pareto, Szenarien schlechter als Basis |
| **D Merle** | Oberfläche & Visualisierung | `app.py` (übrige ca. 285 Z.), Karte und Diagramme in `scm/viz.py` (ca. 150 Z.), `README.md` | Layout, Eingriffe per Klick, animierte Karte, Diagramme, Stammdaten-Register, Bedienungsanleitung | Nutzt alle anderen Teile. Abnahme: Bedienung nach README ohne Fehler, alle Register füllen sich |

**Gemeinsam:** Gruppenpräsentation, Projektbericht (je ein Kapitel zum eigenen Teil: Entwurf, Verifikation, Grenzen), Abstimmung der Werte in `base.yaml`.
**Individuell nach Aufgabenstellung:** Jeder dokumentiert in seinem Programmentwurf den eigenen Teil, die eigene Prüfung der KI-Vorschläge, Änderungen und Prompts (Abschnitt 9.3). Konzept, Parameterwahl und Interpretation sind Eigenleistung (9.2). Für Teil C und D lohnt sich zusätzlich eine eigene Erweiterung (z. B. Sensitivitätsanalyse, weitere Sicht).

## 3. Reihenfolge der Zusammenarbeit
1. Gruppe bestätigt Menge, Preise und Zölle (Teil B pflegt `base.yaml`).
2. A, B, C, D arbeiten parallel an ihren Dateien; Schnittstellen stehen fest (`Config`, `RunResult`).
3. Gemeinsamer Testlauf `python -m pytest -q tests`, danach `python -m scm.cli report --reps 30`.
4. Ergebnisse in Bericht und Präsentation übernehmen.
