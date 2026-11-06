# SCM-Simulation (einfache Version)

Deterministische Grundversion der Uhren-Lieferkette mit Montage in Heilbronn:
Oberfläche, Lieferwege, Szenarien auslösen. Ohne Zufall und ohne Zeitverlauf, damit
sie auch auf schwachen Rechnern läuft. Sie dient als Basis zum Ausarbeiten.

> Kennzeichen: **KI** (Claude-Erstentwurf). Nach eigener Überarbeitung im Dateikopf auf **E/G** setzen.

## Start (Windows, VS Code-Terminal)

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Tests: `python -m pytest`

## Aufbau

```
app.py                 Oberfläche (Streamlit): Szenario wählen, Störungen auslösen, Karte, Vergleich
scm_lite/daten.py      CSV- und YAML-Dateien laden, Basis + Szenario zusammenführen
scm_lite/netz.py       Liefernetz als Graph, Sperren, Routensuche (Dijkstra)
scm_lite/rechnung.py   Kennzahlen je Bauteil und je Uhr
scm_lite/karte.py      statische Weltkarte mit Routen und gesperrten Kanten
config/base.yaml       Standardwerte (Lieferanten, Sicherheitsbestand, Kosten …)
config/szenarien/      ein YAML je Szenario, nur Störungen/Abweichungen
data/*.csv             Lieferanten, Knoten, Transportkanten, Verkehrsträger, Tier 2
tests/                 Plausibilitätstests
docs/ARCHITEKTUR.md    Diagramme: Dateifluss, Ablauf, Klassen, Datenmodell
```

## Rechenlogik

Für jedes Bauteil:

- **Route:** Standardroute laut Poster. Ist sie gesperrt, wird die beste offene Umleitung gesucht (Dijkstra nach Zeit, Kosten oder CO₂e).
- **Bauteilwerte:**
  - Einkauf + Fracht (€/kg · Gewicht) + Zoll
  - Lieferzeit = Vorlauf + Transport
  - CO₂e = Gewicht · km · Faktor
- **Kapitalbindung** = Preis · Tagesbedarf · (Sicherheitstage + ½ Bestellrhythmus + Transporttage)
- **Bei Störungen** werden die Werte zeitanteilig gemittelt: während der Störungsdauer gelten Ersatzlieferant bzw. Umleitung, sonst der Normalzustand.
- **Fehltage:**
  - Ausfall ohne Ersatz: Dauer − Sicherheitstage
  - Mit Ersatz: min(Dauer, Lieferzeit des Ersatzlieferanten) − Sicherheitstage
  - Umleitung: Mehrtage − Sicherheitstage

Je Uhr:

- Kosten = Bauteile + Kapitalkosten + Montage + Versand
- Lieferzeit = langsamstes Bauteil
- Lieferfähigkeit ≈ 1 − (max. Fehltage / 365)

## Szenarien

S0 Basis · S1 Rotes Meer · S2 Seiko-Ausfall · S2b mit Zweitlieferant · S3 Niedrigwasser ·
S4 Nachfrage +30 % · S5 Hafen Rotterdam · S6 Stresstest.

Ein neues Szenario ist eine neue YAML-Datei. Möglich sind:

- `typ: engpass` mit Ziel `suez`, `panama`, `rhein`, `seidenstrasse` oder `luftraum`
- `typ: knoten` mit Ziel `RTM` oder `HAM`
- `typ: lieferant` mit einer Lieferanten-ID

Jede Störung braucht eine `dauer_tage`.

## Ausbaustufen (zum Aufteilen)

- Tier-2-Lieferanten in die Rechnung aufnehmen (Pflicht laut Aufgabenstellung)
- Zeitverlauf je Tag (Bestand, Fehlmengen) statt Näherung
- Zufall für Transportzeiten/Nachfrage (Dreieck, Poisson) + mehrere Läufe
- Animation der Sendungen auf der Karte
- Optimierung des Sicherheitsbestands, Pareto-Vergleich
