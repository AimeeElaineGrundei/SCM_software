# Abgestimmte Werte, Quellen und Annahmen (config/base.yaml)

**Q** = durch Quelle gestützt, **A** = begründete Annahme (in der Gruppe bestätigen). Zahlen lassen sich in `config/base.yaml` ohne Programmieren ändern.

## Parameter
| Größe | Wert | Status | Herleitung / Quelle |
|---|---|---|---|
| Jahresnachfrage | 12.000 Uhren | A | Poster Elaine (Merle/Leon: 10.000) – gemeinsame Zahl in der Gruppe festlegen |
| Montagelohn | 45 €/h | Q | Ø Arbeitskosten Deutschland 2025 ≈ 45 €/h (Destatis; IHK Heilbronn-Franken: „Eine Arbeitsstunde kostete 2025 durchschnittlich 45 Euro“) |
| Montagezeit | 1,0 h/Uhr, 8 Monteure, 5 Tage/Woche | A | Mechanisches Uhrwerk, Premium; Quarz laut Poster Leon 15 min. Kapazität 64/Arbeitstag > Bedarf ca. 48 |
| Emissionsfaktor Lkw / Bahn / Binnenschiff | 118 / 14 / 32 g CO₂e/tkm | Q | UBA, TREMOD 6.71B (10/2025), Tab. „Vergleich der durchschnittlichen Emissionen einzelner Verkehrsmittel im Güterverkehr 2024“ |
| Emissionsfaktor Luft | 788 g CO₂e/tkm | Q (sekundär) | GLEC Framework v3.2, Langstrecke (zitiert nach greencalculus.com) – Primärquelle prüfen |
| Emissionsfaktor See | 7,2 g CO₂e/tkm | abgeleitet | GLEC v3.2: 71,7 g/TEU-km, Annahme 10 t/TEU; für leichte Ware (volumenbegrenzt) eher zu niedrig |
| Lagerhaltungskostensatz | 22 % p. a. | A | wie im Projekt bisher verwendet (Vorlesung) |
| Servicegrad-Ziel | β ≥ 97 % | A | Zielsystem Elaine |
| Sicherheitsbestand | 10 Tage Nachfrage | A | so gewählt, dass S0 β ≥ 97 % sicher erreicht (Basis 99,6 %); per Rastersuche begründbar |

## Komponenten (Einkaufspreis je Stück, Gewicht inkl. Verpackung, Zollsatz)
| Komponente | Herkunft | Preis | Gewicht | Zoll | Q | Herleitung |
|---|---|---|---|---|---|---|
| Uhrwerk (SW200-1-Klasse) | Schweiz | 150 € | 0,03 kg | 0 % | 400 | Händlerpreis einzeln 215 USD (diywatch.club) bzw. 269 USD (ofrei.com) ≈ 192 € (1,12 USD/€); bei 12.000 Stück ca. 20 % Mengenrabatt (A). CH-Ursprung zollfrei (EU–CH-Abkommen) |
| Zifferblatt + Zeigerset | Frankreich | 20 € | 0,01 kg | 0 % | 2.500 | A; Binnenmarkt. Poster Leon: Zifferblatt+Zeiger 5 € (Indien), Premium-Niveau höher angesetzt |
| Gehäuse 316L | China | 25 € | 0,055 kg | 2,7 % | 2.500 | A; Leon: China-Gehäuse ≈ halber Preis von 35 € (US-CNC) bzw. 16,40 € (eBay), Premium-Veredelung. Zoll: KN 9111 20 00, 0,50 €/Stk, mind. 2,7 %, max. 4,6 % (zolltarifnummern.de 2026) – bei 25 € greift das Minimum 2,7 % |
| Saphirglas | USA | 6 € | 0,005 kg | 0 % | 1.000 | A; Leon 6 € (Spanne 3–10 €). Synthetischer Saphir KN 7104 99 00: 0 % (Poster Leon); US-Ursprung für 9111-Teile 0 % seit 01.07.2026 (zolltarifnummern.de) |
| Perlmutt-Zifferblattplatte | Australien | 18 € | 0,006 kg | 2,7 % | 1.000 | A; KN 9114 90 00: 2,7 % Drittlandszoll (zolltarifnummern.de 2026); ein Präferenzsatz für AU wurde nicht geprüft |
| Lederarmband | Südafrika | 22 € | 0,02 kg | 0 % | 4.000 | A; Poster Elaine ≈ 21,76 €, Merle 20 €. Zollfreiheit durch EU–SADC-WPA angenommen (A, prüfen) |

Gewichte: Gehäuse 45 g, Uhrwerk 25 g, Glas 4 g, Armband 16 g aus Posterangaben (Leon, Merle) plus 10–20 % Verpackung (Poster Leon). Bestellmengen Q aus den Versandgrößen im Poster Elaine.

## Transportkosten (Fixkosten je Sendung + €/kg)
| Position | Wert | Status | Herleitung |
|---|---|---|---|
| Seefracht Hauptlauf (LCL) | 110 € fix + 0,05 €/kg | A | LCL ≈ 120 USD/m³, Mindestmenge 1 m³ (Poster Leon, iContainers 2026/Suaid 2026); Sendungen < 1 m³ → praktisch Fixkosten |
| Import Seehafen | 358 € fix | Q (sekundär) | Zollabfertigung 165,6 € + Terminal Handling 192,4 € (Poster Leon, iContainers 2026) |
| Luftfracht | 250 € fix + 4,29 €/kg | Q (sekundär) | 4,80 USD/kg (Poster Leon, Suaid 2026) ÷ 1,12; Fix: Abfertigung FRA ≈ 47 € + Luftfrachtbrief 35,8 € + Zollabfertigung 165,6 €. Mindestabrechnungsgewicht (45 kg) nicht modelliert |
| Binnenschiff Rotterdam–Heilbronn | 86 € fix + 0,02 €/kg | Q (sekundär) | 16,50 €/t + Entladung 35,8 € + Umschlag (Poster Leon: inlandcargo.eu 2026) |
| Bahn / Lkw Hinterland | 150 € bzw. 165–180 € fix + 0,04–0,06 €/kg | A | Lkw: Palette ≈ 165 € (Eurosender, Poster Leon); Bahn angelehnt, keine Quelle |
| Paketzustellung Heilbronn → Kunde | DE ≈ 20 €, EU 28–33 € je Uhr | Q/A | DHL Paket bis 31,5 kg 23,99 € brutto = 20,16 € netto (Poster Leon); EU-Preise A |
| Transportzeiten See | [Plan−2, Plan, Plan+7] Tage je Seeleg | A/Q | Pünktlichkeit See 50,6 %, Ø Verspätung 6,65 Tage (Sea-Intelligence 2026, laut Poster Leon/Alexander): erwartete Verspätung ≈ 3,3 Tage je Reise, auf zwei Legs verteilt |
| Suez vs. Kap | Kap +12 Tage | Q (sekundär) | FR8 Logistik 2026 (Poster Leon): +10–14 Tage |
| Produktionszeiten Tier 1 | z. B. Uhrwerk [25, 35, 50] Tage | A | Poster Leon: Bereitstellung ca. 30 Tage (HKTDC) |

## Quellenverzeichnis (abgerufen 07.11.2026)
- Umweltbundesamt (2025): TREMOD 6.71B, Tabelle „Vergleich der durchschnittlichen Emissionen einzelner Verkehrsmittel im Güterverkehr 2024“. https://www.umweltbundesamt.de/sites/default/files/medien/366/bilder/dateien/vtv_2024_gv_tab_pdf.pdf
- Smart Freight Centre: GLEC Framework v3.2 (Werte zitiert nach https://greencalculus.com/glossary/tonne-kilometre/).
- IHK Heilbronn-Franken (2026): Eine Arbeitsstunde kostete 2025 durchschnittlich 45 Euro. https://www.ihk.de/heilbronn-franken/produktmarken/zahlen-daten-fakten/aktuelles/eine-arbeitsstunde-kostete-2025-durchschnittlich-45-euro-7043140
- zolltarifnummern.de (2026): KN 9111 20 00 https://www.zolltarifnummern.de/2026/91112000 ; KN 9114 90 00 https://www.zolltarifnummern.de/2026/91149090
- diywatch.club: Sellita SW200-1, 215 USD. https://shop.diywatch.club/products/swiss-sw200-with-date-with-3-oclock-crown-position
- ofrei.com: Sellita SW200-1, 269,40 USD. https://www.ofrei.com/Sellita-Watch-Movement.html
- Frachtraten, Gebühren, Sea-Intelligence, FR8 Logistik: so in den Postern von Leon Isamuchamedow und Merle Wittmann zitiert; für die Abgabe die Primärquellen dort nachschlagen.

## Hinweise
- Weiter zu klären: Menge (12.000 vs. 10.000), Zollsatz Australien/Südafrika, Primärquellen für Frachtraten.
- Frachtkosten machen nur ca. 0,7 % der Landed Cost aus; die Kostenkennzahl bleibt daher in allen Szenarien nahezu gleich. Der Einkauf (≈ 241 € von 289 €) und die Montage (45 €) dominieren.
- KI-Nachweis (Aufgabenstellung 9.3): Software und Werterecherche mit Claude erstellt; eigene Prüfung, Änderungen und Prompts im Programmentwurf dokumentieren. Konzept, Parameterwahl und Interpretation sind nicht delegierbar (9.2).
