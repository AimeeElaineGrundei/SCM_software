# Architektur

Die Diagramme sind in Mermaid geschrieben. GitHub zeigt sie direkt an. In VS Code braucht die
Vorschau (Strg+Shift+V) die Erweiterung *Markdown Preview Mermaid Support*.

## 1. Schichten und Datenfluss

```mermaid
flowchart LR
    subgraph Eingaben["Eingaben (ändern ohne Code)"]
        BASE["config/base.yaml"]
        SZ["config/szenarien/*.yaml"]
        CSV["data/*.csv"]
    end
    subgraph Modell["Modell (scm_lite)"]
        DATEN["daten.py<br/>laden"]
        NETZ["netz.py<br/>Klasse Netz"]
        SIM["simulation.py<br/>Tagesschleife"]
        AUSW["auswertung.py<br/>Kennzahlen · Vergleich · Pareto · Sensitivität"]
    end
    subgraph Sichten["Sichten"]
        APP["app.py<br/>Kennzahlen + Diagramme"]
        KARTE["karte.py<br/>animierte Karte"]
    end
    BASE & SZ & CSV --> DATEN
    DATEN -->|"stamm, cfg"| AUSW
    AUSW -->|"rechne(cfg)"| SIM
    SIM -->|"route(lieferant)"| NETZ
    SIM -->|"tage, sendungen"| AUSW
    AUSW -->|"kpi, teile, tage, sendungen"| APP
    APP --> KARTE
    KARTE --> NETZ
```

Alle drei Sichten lesen dasselbe Ergebnis von `auswertung.rechne()`. Deshalb passen Karte,
Diagramme und Kennzahlen immer zueinander.

## 2. Tagesschleife (`simulation.simuliere`)

```mermaid
flowchart TD
    A([Tag t]) --> B[Störungen des Tages setzen]
    B --> C[Eingetroffene Sendungen ins Lager]
    C --> D[Montage = min Kapazität, Nachfrage+Rückstand, Lager aller 6 Teile]
    D --> E[Kunden beliefern: sofort oder Rückstand]
    E --> F{je Bauteil: Lager + Unterwegs ≤ Bestellpunkt?}
    F -- nein --> H
    F -- ja --> G{Lieferant aktiv?}
    G -- ja --> R[Route: Posterroute oder Umleitung]
    G -- nein --> Z{Zweitlieferant an?}
    Z -- ja --> R
    Z -- nein --> H
    R --> S[Sendung anlegen: Kosten, CO₂e, Etappen]
    S --> H[Tageswerte speichern]
    H --> I([t + 1])
```

## 3. Ablauf bei einem Klick

```mermaid
sequenceDiagram
    actor N as Nutzer
    participant A as app.py
    participant D as daten.py
    participant W as auswertung.py
    participant S as simulation.py
    participant Z as netz.py
    participant K as karte.py
    N->>A: Ereignis + Reaktion wählen
    A->>D: lade_szenario("s0_basis") + Störungen der Ereignisse
    A->>W: rechne(cfg, stamm)
    W->>S: simuliere(cfg, stamm)
    loop 365 Tage × 6 Bauteile
        S->>Z: route(lieferant)
        Z-->>S: Kanten-IDs
    end
    S-->>W: tage, sendungen
    W-->>A: kpi, teile, tage, sendungen
    A->>K: karte(ergebnis)
    A-->>N: Ampeln, Text, Karte, Diagramme
```

## 4. Klassen und Funktionen

```mermaid
classDiagram
    class daten {
        <<Modul · Leon>>
        +lade_stammdaten() dict
        +szenario_liste() list
        +lade_szenario(key) dict
    }
    class Netz {
        <<Klasse · Leon>>
        +kanten: dict
        +gesperrt: frozenset
        +setze_sperren(stoerungen)
        +offen(kante_id) bool
        +standardroute(lieferant_id) list
        +route(lieferant_id) list
        -_umleitung(start) list
    }
    class simulation {
        <<Modul · Alex>>
        +simuliere(cfg, stamm) dict
        +aktiv(stoerungen, t) list
        +faellt_aus(lid, t, cfg, tier2) bool
        -_sendung(...) dict
    }
    class auswertung {
        <<Modul · Elaine>>
        +KENNZAHLEN: dict
        +rechne(cfg, stamm) dict
        +vergleich(stamm) DataFrame
        +massnahmen(cfg, stamm) DataFrame
        +ist_pareto(df, spalten) list
        +sensitivitaet(cfg, stamm) DataFrame
    }
    class karte {
        <<Modul · Merle>>
        +karte(ergebnis, cfg, stamm) Figure
        +linie(stamm, kante) tuple
    }
    class app {
        <<Streamlit · Merle>>
        Ereignisse
        Reaktion
        Kennzahlen
        Karte und Diagramme
        Auswertung
    }
    app ..> daten
    app ..> auswertung
    app ..> karte
    auswertung ..> simulation
    auswertung ..> daten
    simulation ..> Netz
    karte ..> Netz
```

## 5. Datenmodell

```mermaid
erDiagram
    LIEFERANTEN ||--o{ KANTEN : "Start der Route"
    KNOTEN ||--o{ KANTEN : "von / nach"
    TIER2 }o--|| LIEFERANTEN : "liefert_an"
    LIEFERANTEN {
        string lieferant_id PK
        string komponente
        float preis_eur
        int gewicht_brutto_g
        float vorlaufzeit_tage
        float zollsatz
        string standardroute
    }
    TIER2 {
        string tier2_id PK
        string liefert_an FK
        float transport_tage
    }
    KNOTEN {
        string knoten_id PK
        string typ
        float lat
        float lon
    }
    KANTEN {
        string kante_id PK
        string von FK
        string nach FK
        string modus
        float distanz_km
        float tage_modus
        float kosten_eur_pro_kg
        float co2e_g_pro_tkm
        string engpaesse
    }
```

## 6. Schnittstellen zwischen den Modulen

| Objekt | Typ | erzeugt von | Inhalt |
|---|---|---|---|
| `stamm` | dict aus DataFrames | `daten.lade_stammdaten()` | `lieferanten`, `tier2`, `knoten`, `kanten` |
| `cfg` | dict | `daten.lade_szenario()` | Inhalt von base.yaml + `stoerungen` (Liste von `{typ, ziel, start_tag, dauer_tage}`) |
| `tage` | DataFrame | `simulation.simuliere()` | je Tag: `nachfrage, montage, sofort, rueckstand, lager_<teil>, unterwegs_<teil>` |
| `sendungen` | DataFrame | `simulation.simuliere()` | je Bestellung: `bauteil, lieferant, bestellt, ankunft, menge, kosten_stk, co2_g_stk, umgeleitet, etappen` |
| `kpi` | dict | `auswertung.rechne()` | 5 Kennzahlen (Schlüssel wie in `KENNZAHLEN`) |
| `teile` | DataFrame | `auswertung.rechne()` | je Bauteil: `lieferant, bestellungen, kosten_stk, lieferzeit, co2_g_stk, status` |
