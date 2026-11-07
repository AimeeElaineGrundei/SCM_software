# Architektur der einfachen Version

Die Diagramme sind in Mermaid geschrieben. GitHub/GitLab zeigen sie direkt an. In VS Code
braucht die Markdown-Vorschau die Erweiterung *Markdown Preview Mermaid Support*.

## 1. Welche Datei greift auf was zu

```mermaid
flowchart LR
    subgraph Eingaben
        BASE["config/base.yaml<br/>Standardwerte"]
        SZ["config/szenarien/*.yaml<br/>Störungen je Szenario"]
        CSV["data/*.csv<br/>Lieferanten · Knoten · Kanten"]
    end

    subgraph scm_lite["Paket scm_lite"]
        DATEN["daten.py<br/>laden + zusammenführen"]
        NETZ["netz.py<br/>Klasse Netz<br/>Sperren · Dijkstra"]
        RECH["rechnung.py<br/>Kennzahlen je Bauteil/Uhr"]
        KARTE["karte.py<br/>Plotly-Weltkarte"]
    end

    APP["app.py<br/>Streamlit-Oberfläche"]
    TEST["tests/test_rechnung.py"]

    CSV --> DATEN
    BASE --> DATEN
    SZ --> DATEN
    DATEN -->|"stamm (dict), cfg (dict)"| APP
    APP -->|"cfg + Eingriffe"| RECH
    RECH -->|nutzt| NETZ
    RECH -->|"teile (DataFrame), kpi (dict)"| APP
    APP -->|"teile, netz"| KARTE
    KARTE -->|Figure| APP
    NETZ -->|"Kanten, Routen"| KARTE
    TEST --> DATEN & NETZ & RECH
```

## 2. Was passiert bei einem Klick in der Oberfläche

```mermaid
sequenceDiagram
    actor N as Nutzer
    participant A as app.py
    participant D as daten.py
    participant R as rechnung.py
    participant Z as netz.py (Netz)
    participant K as karte.py

    N->>A: Szenario wählen / Störung auslösen
    A->>D: lade_szenario(key)
    D-->>A: cfg = base.yaml + Szenario
    A->>A: Eingriffe aus der Seitenleiste an cfg["stoerungen"] anhängen
    A->>R: berechne(cfg, stamm)
    R->>Z: Netz(stamm) + sperren(stoerungen)
    loop je Bauteil
        R->>R: Lieferant aktiv? sonst Zweitlieferant
        R->>Z: route(lieferant)
        Z-->>R: Standardroute oder Umleitung (Dijkstra)
        R->>R: Kosten, Tage, CO₂e, Kapital, Fehltage
    end
    R-->>A: teile, kpi
    A->>K: karte(teile, netz, stamm)
    K-->>A: Plotly-Figure
    A-->>N: Kennzahlen, Karte, Tabellen
```

## 3. Klassen und Funktionen

```mermaid
classDiagram
    class daten {
        <<Modul>>
        +lade_stammdaten() dict
        +szenario_liste() list
        +lade_szenario(key) dict
    }
    class Netz {
        +stamm: dict
        +kanten: dict
        +gesperrt_tags: set
        +gesperrt_knoten: set
        +sperren(stoerungen)
        +offen(kante_id) bool
        +standardroute(lieferant_id) list
        +beste_route(start, kriterium, luft) list
        +route(lieferant_id, kriterium, luft) list
    }
    class rechnung {
        <<Modul>>
        +KENNZAHLEN: dict
        +berechne(cfg, stamm) tuple
        +vergleiche_alle(stamm) DataFrame
        +routentext(netz, lid, route) str
        -_teil(...) dict
    }
    class karte {
        <<Modul>>
        +karte(teile, netz, stamm) Figure
        +linie(stamm, kante) tuple
        -_wegpunkte(...) list
    }
    class app {
        <<Streamlit>>
        Seitenleiste
        Tab Karte
        Tab Szenariovergleich
        Tab Stammdaten
    }
    app ..> daten : lädt
    app ..> rechnung : rechnet
    app ..> karte : zeichnet
    rechnung ..> Netz : erzeugt
    rechnung ..> daten : Szenarien
    karte ..> Netz : liest Kanten
```

## 4. Datenmodell (CSV-Dateien)

```mermaid
erDiagram
    LIEFERANTEN ||--o{ KANTEN : "Startknoten (lieferant_id = von)"
    KNOTEN ||--o{ KANTEN : "von / nach"
    LIEFERANTEN ||--o{ TIER2 : "liefert_an"
    VERKEHRSTRAEGER ||--o{ KANTEN : modus

    LIEFERANTEN {
        string lieferant_id PK
        string komponente
        float preis_eur
        int gewicht_brutto_g
        float vorlaufzeit_tage
        float zollsatz
        string standardroute
    }
    KNOTEN {
        string knoten_id PK
        string name
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
    TIER2 {
        string tier2_id PK
        string liefert_an FK
    }
    VERKEHRSTRAEGER {
        string modus PK
        float co2e_g_pro_tkm
    }
```

## 5. Wichtige Datenstrukturen zwischen den Dateien

| Name | Typ | Erzeugt in | Inhalt |
|---|---|---|---|
| `stamm` | dict aus DataFrames | `daten.lade_stammdaten` | `lieferanten`, `knoten`, `kanten` |
| `cfg` | dict | `daten.lade_szenario` | base.yaml + Szenario, z. B. `lieferanten`, `stoerungen`, `sicherheitstage` |
| `stoerungen` | Liste von dicts | YAML / Seitenleiste | `{typ, ziel, dauer_tage}` |
| `teile` | DataFrame | `rechnung.berechne` | eine Zeile je Bauteil: Lieferant, Route, Kosten, Tage, CO₂e, Fehltage |
| `kpi` | dict | `rechnung.berechne` | 6 Kennzahlen je Uhr |
