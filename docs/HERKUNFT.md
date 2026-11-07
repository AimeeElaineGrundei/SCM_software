# Herkunft der Lösung – was wurde aus welchem Vorschlag übernommen?

Grundlage für den Abschnitt „Abweichungen zwischen eigenem Vorschlag und Gruppenlösung“
im Programmentwurf und für die individuelle Reflexion im Projektbericht.

**Quellen:**

| Kürzel | Dokument |
|---|---|
| P-Alex, P-Elaine, P-Merle, P-Leon | Poster aus Aufgabe 1 |
| K-Alex, K-Elaine, K-Merle | Simulationskonzepte aus Aufgabe 2 (von Leon lag kein Konzept vor) |

**Legende:** ✅ übernommen · ◐ angepasst übernommen · ✗ nicht übernommen

---

## 1. Fachliches Modell (Aufgabe 1)

| Baustein | Umsetzung in der Software | Herkunft | Status |
|---|---|---|---|
| Liefernetz mit 6 Tier-1 | Seiko (JP), Gehäuse Shenzhen (CN), Saphirglas Gladstone (AU), Zifferblatt Los Angeles (US), Lederarmband São Paulo (BR), Zeiger Doubs (FR) | P-Alex | ✅ Einziges Netz, das alle Muss-Vorgaben (4 Kontinente + EU + alle 4 Verkehrsträger) in einem Modell erfüllt |
| Tier-2-Vorlieferanten | Spiralfeder Genf + Lagersteine Tianjin → Seiko; Edelstahl Tsingshan + Dichtungen Genf → Gehäuse | P-Alex | ✅ |
| Weitere Tier-2 | Daten von Merle, Leon, Elaine in `tier2.csv` | P-Merle, P-Leon, P-Elaine | ◐ als Daten vorhanden, nur bei gewähltem Lieferanten aktiv |
| Alternative Lieferanten | alle 25 Lieferanten der vier Poster in `lieferanten.csv` | alle Poster | ✅ |
| Zweitlieferanten | Uhrwerk Miyota 8215 (Idee P-Alex, Lieferant P-Merle/P-Leon), Gehäuse/Glas/Zifferblatt/Armband P-Merle, Zeiger P-Elaine | P-Alex, P-Merle, P-Elaine | ◐ Miyota als mechanische Variante ergänzt |
| Transportketten | Posterrouten je Lieferant (`standardroute`) | je Poster | ✅ |
| Kap-Route, Landbrücke USA, Hamburg statt Rotterdam | zusätzliche Kanten für Umleitungen | P-Alex (Kap), P-Leon (Kap, Lkw bei Niedrigwasser) | ◐ ergänzt |
| Distribution | Montage → Zentrallager → Paketdienst (6,19 €, 1–2 T) → Endkunde DE | P-Alex | ✅ |
| Nachfrage | 10.000 Uhren/Jahr | P-Merle, P-Leon (P-Elaine: 12.000) | ✅ |
| Montagekosten | 0,5 h × 17 €/h = 8,50 €/Uhr | P-Merle | ✅ |
| Kapitalzins | 12 % (8 % Kapital + 4 % Lager) | P-Merle | ✅ |

### Zielsystem

| Kriterium | Umsetzung | Herkunft | Status |
|---|---|---|---|
| Kosten €/Uhr | Einkauf + Fracht + Zoll + Kapital + Montage + Versand | alle Poster | ✅ |
| Lieferzeit (langsamstes Bauteil) | Ø Wiederbeschaffungszeit | P-Alex, P-Leon | ✅ |
| Kapitalbindung € | Ø Wert Lager + Unterwegs | P-Elaine (P-Alex: Bestandsreichweite in Tagen) | ◐ in € statt Tagen |
| CO₂e kg/Uhr | Gewicht · km · Faktor | P-Alex, P-Elaine | ✅ |
| Lieferfähigkeit ≥ 95 % | sofort erfüllte / nachgefragte Uhren | P-Alex (P-Elaine 97 %, P-Leon 96 %) | ◐ 95 % als Ziel |
| Gewicht der Uhr | – | P-Merle | ✗ für Lieferkettenentscheidung nicht relevant |
| Qualität / Fehlerquote | – | P-Merle, P-Leon | ✗ keine belastbaren Daten, Ausblick |

### Szenarien

| Szenario | Herkunft | Status |
|---|---|---|
| S1 Rotes Meer gesperrt → Kap | P-Alex, P-Leon | ✅ |
| S2 Ausfall Uhrwerk-Lieferant | P-Alex (8 Wochen), P-Elaine (1 Monat) | ✅ 8 Wochen |
| S3 Rhein-Niedrigwasser | P-Alex, P-Leon | ✅ |
| S4 Nachfrage +30 % Q4 | P-Elaine | ✅ |
| S5 Hafen Rotterdam gesperrt | P-Alex (Rotterdam als SPOF), P-Elaine (Hafenverzug) | ◐ Sperrung statt Verzug |
| S6 Tier-2-Ausfall | P-Alex (Tier-2 Schweiz) | ◐ neu als Szenario formuliert |
| Luftraum gesperrt | P-Leon | ✗ Luftfracht ist nicht Teil der Lösung |
| Materialalternativen Textil/Alu | P-Merle | ✗ Produktentscheidung, keine Lieferkettenstörung |

---

## 2. Methodik und Technik (Aufgabe 2)

| Baustein | Umsetzung | Herkunft | Status |
|---|---|---|---|
| Netz als gerichteter Graph (NetworkX) | `netz.py`, Kanten mit Distanz, Dauer, Kosten, CO₂e, Engpass | K-Alex, K-Merle, K-Elaine | ✅ |
| Umleitung per Dijkstra bei Sperrung | `Netz.route()` | K-Alex | ✅ nach Zeit |
| Bestellpunkt s = d · (L + SB) | `simulation.py` | K-Alex | ✅ |
| Bestellmenge nach Andler | – | K-Elaine | ✗ feste 30 Tage Bedarf; einfacher und gut nachvollziehbar |
| Tagestakt | 365 Tagesschritte | K-Elaine | ✅ |
| Reaktionsregel Zweitlieferant | Umschalter in der Oberfläche | K-Elaine (Agentenverhalten), P-Alex | ✅ |
| Notfall-Luftfracht | – | K-Elaine, P-Leon | ✗ zugunsten eines minimalen Modells weggelassen |
| Ereignisdiskrete Simulation mit SimPy | – | K-Alex, K-Merle | ✗ Tagesschleife ohne Framework (siehe Abschnitt 3) |
| Agentenbasierte Simulation mit Mesa | – | K-Elaine | ✗ (siehe Abschnitt 3) |
| Konfiguration Basis + Szenario in YAML | `config/` | K-Alex, K-Merle, K-Elaine | ✅ |
| Ergebnisse als Tabellen | `tage`, `sendungen` | K-Alex (Ereignisprotokoll), K-Elaine (Tabelle je Tag) | ◐ Tages- und Sendungstabelle |
| Pareto-Vergleich | Maßnahmen: Sicherheitsbestand × Zweitlieferant | K-Alex, K-Elaine | ✅ |
| Gewichteter Score | – | K-Merle | ✗ Pareto zeigt Zielkonflikte ohne willkürliche Gewichte |
| Rastersuche Sicherheitsbestand | Maßnahmentabelle 0/7/14/28/42 Tage | K-Alex | ◐ als Tabelle statt Optimierer |
| Sensitivität ±10 % | Nachfrage, Preise, Transportzeiten, Sicherheitstage | K-Alex, K-Elaine | ✅ |
| Verifikation per Handrechnung | Test Saphirglas = 52 Tage | K-Alex (42 T), K-Merle (Score 70,25) | ◐ Binnenschiff realistisch 4 statt 1 Tag |
| Oberfläche Streamlit + Plotly | `app.py` | K-Merle | ✅ |
| Dash mit Live-Klick auf der Karte | – | K-Alex | ✗ Eingriffe als Ereignis-Knöpfe |
| Animierte Karte mit Frames (`scatter_geo`) | `karte.py`, ein Bild je Woche | K-Merle, K-Elaine (bewegte Sendungen) | ◐ wöchentlich statt täglich |
| Drei Sichten aus einer Ergebnisquelle | `auswertung.rechne()` | K-Alex, K-Merle, K-Elaine | ✅ |
| Stochastik, 30 Replikationen, Konfidenzintervall | – | K-Alex, K-Merle, K-Elaine | ✗ (siehe Abschnitt 3) |

---

## 3. Größere Abweichungen und Begründung

| Abweichung | Begründung | Bewertung / Grenze |
|---|---|---|
| Keine DES (SimPy) und keine ABS (Mesa), sondern eine eigene Tagesschleife | Erste Version mit SimPy und 30 Replikationen war zu speicherhungrig für die Gruppenrechner. Eine Tagesschleife ist kurz, ohne Framework verständlich und per Handrechnung prüfbar. | Ereignisse innerhalb eines Tages werden auf Tage gerundet. Für Lieferzeiten von 1–60 Tagen ausreichend genau. |
| Kein Zufall | Deterministische Ergebnisse sind reproduzierbar und erklärbar. Unsicherheit wird über die Sensitivitätsanalyse abgedeckt. | Schwankungen (z. B. nur 50–65 % pünktliche Schiffe) fehlen. Erweiterbar mit Dreiecksverteilung und festem Seed. |
| Keine Luftfracht, keine Notfallreaktion | Fokus auf die Pflichtverkehrsträger und zwei klare Gegenmaßnahmen (Zweitlieferant, Sicherheitsbestand). | Schnelle, aber CO₂-intensive Option fehlt im Zielkonflikt. |
| Feste Bestellmenge statt Andler | Andler setzt konstante Nachfrage und Kosten voraus. Bei Störungen bringt sie wenig Mehrwert. | Bestellkosten werden nicht optimiert. |
| Oberfläche als „Leitstand-Spiel“ | Bei der Vorführung schnell verständlich. Die Auswertung steht im Aufklapper. | – |

---

## 4. Spickzettel je Person für die eigene Ausarbeitung

| Person | Eingebracht und übernommen | Nicht übernommen |
|---|---|---|
| **Alex** | Netz mit 6 Tier-1 + Tier-2, Distribution, β ≥ 95 %, Szenarien S1/S2/S3/S5/S6, Graph + Dijkstra, Bestellpunkt (s, Q), Pareto, Sensitivität ±10 %, Handrechnungs-Test | SimPy-DES, Dash mit Live-Klick, 30 Seeds, Rastersuche als Optimierer |
| **Elaine** | Kapitalbindung in €, Szenario S4 Nachfrage +30 %, Tagestakt, Reaktionsregel Zweitlieferant, Pareto, Lieferant Zeigerset als Ersatz | ABS mit Mesa, Andler-Losgröße, Notfall-Luftfracht, β ≥ 97 % |
| **Merle** | Nachfrage 10.000, Montagekosten 17 €/h, Zinssatz 12 %, Streamlit + Plotly, animierte Karte mit Frames, Test gegen Handrechnung, 4 Ersatzlieferanten | gewichteter Score, Gewicht und Fehlerquote als Kriterien, Quarzuhr-Netz |
| **Leon** | Suez/Kap und Niedrigwasser als Szenarien, Lkw-Umleitung ab Rotterdam, Zollsätze, Lieferantendaten (Lucentis, Taratec, Proto Labs, Steelux) | Luftraum-Szenario, Luftfracht, Qualität in ppm, eigenes Netz |
