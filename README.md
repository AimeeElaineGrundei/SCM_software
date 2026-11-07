# Uhren-Leitstand – Simulation der Lieferkette einer Uhrenmontage in Heilbronn

Portfolioprüfung *Logistik und Supply Chain Management*, DHBW Heilbronn, Gruppe Surfer
(Alex, Elaine, Merle, Leon).

Die Software bildet die globale Lieferkette einer mechanischen Armbanduhr im Tagestakt ab:
6 Tier-1-Lieferanten auf 5 Kontinenten, Tier-2-Vorlieferanten, Transportketten mit See, Bahn,
Lkw und Binnenschiff, Montage in Heilbronn, Zentrallager und Paketversand an Endkunden.
In der Oberfläche löst man Störungen aus, wählt Gegenmaßnahmen und sieht an fünf Kennzahlen,
was das für Kosten, Lieferzeit, Kapitalbindung, CO₂e und Lieferfähigkeit bedeutet.

| Dokument | Inhalt |
|---|---|
| [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md) | Aufbau, Datenfluss, Klassen, Datenmodell (Diagramme) |
| [docs/HERKUNFT.md](docs/HERKUNFT.md) | Was aus welchem Poster/Konzept übernommen wurde, was nicht und warum |
| [docs/AUFTEILUNG.md](docs/AUFTEILUNG.md) | Wer welches Modul programmiert, Schnittstellen, Kennzeichnung E/G/KI/F |
| [prompts/README.md](prompts/README.md) | KI-Nutzungsnachweis |

## Startvoraussetzungen

- Python 3.10 oder neuer
- Pakete aus `requirements.txt`: pandas, networkx, pyyaml, plotly, streamlit, pytest
- Etwa 200 MB Arbeitsspeicher

## Installation und Start (Windows, Terminal in VS Code)

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Der Browser öffnet `http://localhost:8501`. Tests laufen mit `python -m pytest`.

## Bedienung

1. **Was passiert in der Welt?** Ein oder mehrere Ereignisse anklicken (Szenarien S1–S6).
2. **Wie reagierst du?** Zweitlieferant einschalten und/oder das Sicherheitslager ändern.
3. **Ergebnis nach einem Jahr** ansehen:
   - Kennzahlensicht: fünf Kennzahlen mit Ampel, Abweichung zur Basis und einem kurzen Text, was passiert ist
   - Netzwerksicht: animierte Weltkarte (▶); Sendungen bewegen sich Woche für Woche, gesperrte Strecken rot
   - Diagrammsicht: Lagerbestand je Bauteil und wartende Kunden je Tag
4. **Auswertung** (Aufklapper unten): Vergleich aller Szenarien, Pareto-Vergleich der Maßnahmen,
   Sensitivität ±10 % und die Rohdaten

## Dateistruktur

```
app.py                     Oberfläche (Streamlit)
scm_lite/
  daten.py                 CSV- und YAML-Dateien laden
  netz.py                  Klasse Netz: Graph, Sperren, Umleitung (Dijkstra)
  simulation.py            Tagesschleife: Bestellung, Transport, Lager, Montage, Kunde
  auswertung.py            Kennzahlen, Szenariovergleich, Pareto, Sensitivität
  karte.py                 animierte Karte (Plotly)
config/
  base.yaml                Standardwerte (Lieferanten, Sicherheitsbestand, Kosten, Ziel)
  szenarien/s0 … s6.yaml   ein Szenario je Datei, nur die Störungen
data/
  lieferanten.csv          25 Tier-1-Lieferanten aus allen vier Postern
  tier2.csv                15 Vorlieferanten
  knoten.csv               Standorte, Häfen, Terminals, Werk, Lager, Kunde
  kanten.csv               84 Transportrelationen mit Tagen, €/kg, g CO₂e/tkm, Engpass
tests/test_simulation.py   Verifikation und Plausibilität
docs/                      Architektur, Herkunft, Aufteilung
prompts/                   KI-Nachweis
```

## Modell

**Zeit:** 365 Tagesschritte, deterministisch, also ohne Zufall. Gleiche Eingaben liefern immer gleiche Ergebnisse.

**Ablauf je Tag:**

1. Die Störungen des Tages anwenden: gesperrte Engpässe und Häfen, Lieferantenausfälle, Nachfrageänderungen.
2. Eingetroffene Sendungen ins Lager buchen.
3. Uhren montieren, soweit alle 6 Bauteile da sind. Die Menge ist die Nachfrage plus Rückstand, begrenzt durch die Kapazität.
4. Je Bauteil eine Bestellung über 30 Tage Bedarf auslösen, wenn gilt:
   Lager + Unterwegs ≤ Tagesbedarf · (Wiederbeschaffungszeit + Sicherheitstage).
   - Die Route ist die Posterroute oder, falls gesperrt, die schnellste offene Umleitung (Dijkstra).
   - Fällt der Lieferant aus, springt der Zweitlieferant ein, falls er eingeschaltet ist.
   - Ein Tier-2-Ausfall stoppt den Tier-1, sobald dessen Puffer von 14 Tagen aufgebraucht ist.

**Zielkriterien:**

| Kriterium | Berechnung | Einheit | Richtung |
|---|---|---|---|
| Kosten | Ø Stückkosten (Einkauf + Fracht + Zoll) aller Bauteile + Kapitalkosten + Montage + Versand | €/Uhr | min |
| Lieferzeit | Ø Wiederbeschaffungszeit des langsamsten Bauteils | Tage | min |
| Kapitalbindung | Ø Wert von Lager und Unterwegs-Bestand | € | min |
| CO₂e | Σ Gewicht · km · Faktor je Kante + Paket | kg/Uhr | min |
| Lieferfähigkeit | am selben Tag erfüllte / nachgefragte Uhren | % | ≥ 95 |

## Szenarien

| Datei | Störung | Herkunft |
|---|---|---|
| s0_basis | keine | – |
| s1_rotes_meer | Suez ab Tag 60 gesperrt → Kap-Route | Alex, Leon |
| s2_seiko_ausfall | Uhrwerk-Lieferant 56 Tage aus | Alex, Elaine |
| s3_niedrigwasser | Rhein 60 Tage nicht befahrbar | Alex, Leon |
| s4_nachfrage_q4 | Nachfrage +30 % im 4. Quartal | Elaine |
| s5_hafen_rotterdam | Rotterdam 30 Tage gesperrt | Alex (SPOF Rotterdam) |
| s6_tier2_ausfall | Vorlieferant Spiralfeder 45 Tage aus | Alex (Tier-2) |

**Neues Szenario anlegen:** eine YAML-Datei mit `name`, `beschreibung` und `stoerungen` ablegen. Jede Störung hat die Felder `typ`, `ziel`, `start_tag` und `dauer_tage`:

| typ | ziel | weitere Felder |
|---|---|---|
| `engpass` | `suez`, `panama`, `rhein`, `seidenstrasse` | – |
| `knoten` | `RTM`, `HAM` | – |
| `lieferant` | Lieferanten-ID | – |
| `tier2` | Tier-2-ID | – |
| `nachfrage` | – | `faktor` |

Code muss dafür nicht geändert werden.

## Grenzen

- Kein Zufall: Unsicherheit wird über die Sensitivitätsanalyse (±10 %) untersucht.
- Die Route wird bei der Bestellung festgelegt. Sendungen, die schon unterwegs sind, werden nicht umgeleitet.
- Lieferantenkapazitäten, Qualität und Rohstoffstufe (Tier 3) sind nicht abgebildet.
- Preise und Transportwerte sind teils Annahmen, siehe Spalten `preis_status` und `quelle`.

## Beiträge

Siehe [docs/AUFTEILUNG.md](docs/AUFTEILUNG.md). Kurzfassung:

| Person | Modul |
|---|---|
| Leon | Daten und Netz (`daten.py`, `netz.py`, `data/`, `config/`) |
| Alex | Simulation (`simulation.py`, Verifikationstests) |
| Elaine | Auswertung (`auswertung.py`, Kennzahl- und Pareto-Tests) |
| Merle | Oberfläche und Karte (`app.py`, `karte.py`) |
