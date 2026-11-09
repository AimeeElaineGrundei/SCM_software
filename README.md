# Supply-Chain-Simulation Heilbronn (Gruppensoftware)

Ereignisdiskrete Simulation (SimPy) des Liefernetzwerks einer Premium-Armbanduhr mit Montage in Heilbronn,
bedienbar über eine Dash-Oberfläche mit animierter Karte, Diagrammen und Kennzahlen.

## Start
```
pip install -r requirements.txt
python app.py                 # Oberfläche: http://127.0.0.1:8050 (läuft offline, Kartendaten liegen in assets/)
python -m scm.cli report --reps 30      # alle Szenarien x 30 Replikationen -> outputs/*.csv
python -m scm.cli run S1_suez --seed 42
python -m scm.cli pareto S1_suez --reps 5
python -m pytest -q tests     # 21 Tests (Verifikation, Szenarien, Routing, Reproduzierbarkeit)
```

## Aufbau
```
config/base.yaml            Netz, Lieferanten (Tier 1/2), Komponenten, Kanten, Regelrouten, Parameter  (alle Einheiten: d, €, kg, km, g CO2e/tkm)
config/scenarios/*.yaml     Szenarien = Parameter-Überschreibungen + Ereignisliste (gleiches Modell)
scm/config.py               Laden, Validierung (Einheiten/Plausibilität), Szenario anwenden, Prüfung der Aufgabenanforderungen
scm/network.py              networkx-MultiDiGraph, Dijkstra-Umleitung (Zeit/Kosten/CO2e), Störungszustand
scm/engine.py               SimPy-Kern: Nachfrage -> Verkauf -> Montage -> (s,Q)-Bestellung -> Tier-2 -> Tier-1 -> Transportkette -> Wareneingang
scm/runner.py               Replikationen, 95-%-Konfidenzintervall, Szenariovergleich, Rastersuche, Pareto-Front
scm/viz.py                  die drei Sichten aus demselben RunResult
scm/cli.py, app.py          Kommandozeile, Oberfläche
tests/test_scm.py           pytest
```

## Modell in Kürze
- **Graph:** 6 Tier-1 (Schweiz, Frankreich, China, USA, Australien, Südafrika), Tier-2 für Uhrwerk (2) und Armband (2), Häfen, Suez/Kap, Flughafen, Heilbronn, 5 Kundenregionen.
- **Transportketten (Regelrouten):** Seeschiff, Güterzug, Lkw, Binnenschiff; Luftfracht nur als Notoption (`air_policy`).
- **Steuerung:** (s,Q)-Politik je Komponente, s = d·(L + SB); Montage make-to-stock bis Zielbestand, Kapazität begrenzt, Arbeitstage.
- **Störungen** (Ereignisse mit Beginn/Ende, Tage ab Auswertungsstart): `block_node`, `block_mode`, `supplier_outage`, `demand_factor`, `transit_factor`. Gesperrte Kanten -> automatische Umleitung per Dijkstra.
- **Zufall:** Dreiecksverteilung (Produktion, Transport), Poisson (Nachfrage); fester Seed; Replikation i nutzt Strom (Seed, i), dadurch in allen Szenarien gleiche Zufallszahlen (Common Random Numbers). Einschwingphase 60 Tage, 365 Auswertungstage.
- **Fünf Zielkriterien, getrennt ausgewiesen:** Landed Cost [€/Uhr], Lieferzeit [Tage], Servicegrad β [%] (Nebenbedingung ≥ 97 %), CO2e [kg/Uhr], Ø Lagerwert [€]. Zusätzlich Lagerhaltungskosten und Versandkosten als Zusatzgrößen. Kein Einzel-Score; Vergleich per Pareto-Front.

## Eigene Szenarien / Parameter ohne Neuprogrammierung
Neue Datei `config/scenarios/S5_xyz.yaml` anlegen, z. B.
```yaml
name: S5 Hafenstreik Rotterdam
params: {air_policy: on_disruption}
events:
  - {type: block_node, node: p_rotterdam, start: 100, end: 114}
```
oder in der Oberfläche unter „Eingriffe“ bzw. per Klick auf einen Kartenknoten.

## Bekannte Grenzen (bitte im Bericht kritisch erwähnen)
- **Zahlenwerte stützen sich teils auf Quellen, teils auf begründete Annahmen**, siehe `ANNAHMEN.md`; Menge und Zölle bitte in der Gruppe bestätigen.
- Fracht + Zoll sind bei leichten Uhrenteilen nur ~0,7 % der Landed Cost; die Kostenkennzahl reagiert daher kaum auf Szenarien (Wirkung zeigt sich bei Lieferzeit, Servicegrad, Lagerwert, CO2e).
- Tier-2 liefern auftragsbezogen (kein Tier-2-Bestand); keine Qualitätsfehler/Ausschuss; Fehlmengen gehen verloren (kein Nachlieferauftrag).
- Sendungen, die bereits auf einer Kante unterwegs sind, laufen bei einer neuen Sperrung bis zum nächsten Knoten weiter.
- Kartenposition der Sendungen ist schematisch (Zwischenpunkte `via` nur zur Darstellung).
- Der Seefaktor ist aus GLEC (TEU-km) mit einer Annahme von 10 t/TEU abgeleitet.
