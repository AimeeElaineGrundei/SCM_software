"""Liefernetz als Graph: Sperren und kürzeste Umleitung (Dijkstra nach Tagen).

Kennzeichen: KI (Referenz) | nachprogrammieren: Leon
"""
import networkx as nx


class Netz:
    def __init__(self, stamm: dict):
        self.stamm = stamm
        self.kanten = stamm["kanten"].to_dict("index")      # kante_id -> Attribute
        for d in self.kanten.values():
            d["tags"] = [t for t in d["engpaesse"].split(";") if t]
        self.gesperrt = frozenset()                          # gesperrte Engpässe und Häfen
        self._cache = {}

    def setze_sperren(self, stoerungen: list[dict]) -> None:
        self.gesperrt = frozenset(s["ziel"] for s in stoerungen if s["typ"] in ("engpass", "knoten"))

    def offen(self, kid: str) -> bool:
        d = self.kanten[kid]
        return not ({d["von"], d["nach"], *d["tags"]} & self.gesperrt)

    def standardroute(self, lid: str) -> list[str]:
        """Posterroute aus lieferanten.csv, Format 'U_SEIKO>YOK>RTM>HN|lkw>see:suez>binnen'."""
        knoten, modi = self.stamm["lieferanten"].loc[lid, "standardroute"].split("|")
        knoten, modi = knoten.split(">"), modi.split(">")
        route = []
        for (von, nach), m in zip(zip(knoten, knoten[1:]), modi):
            modus, _, via = m.partition(":")
            kand = [k for k, d in self.kanten.items() if (d["von"], d["nach"], d["modus"]) == (von, nach, modus)]
            kand = [k for k in kand if (via in self.kanten[k]["tags"]) or (not via and self.kanten[k]["route"] != "kap")] or kand
            route.append(kand[0])
        return route

    def route(self, lid: str) -> list[str] | None:
        """Standardroute, wenn alle Kanten offen sind – sonst schnellste offene Umleitung (ohne Luftfracht)."""
        schluessel = (lid, self.gesperrt)
        if schluessel not in self._cache:
            r = self.standardroute(lid)
            self._cache[schluessel] = r if all(self.offen(k) for k in r) else self._umleitung(lid)
        return self._cache[schluessel]

    def _umleitung(self, start: str) -> list[str] | None:
        g = nx.DiGraph()
        for kid, d in self.kanten.items():
            if self.offen(kid) and d["modus"] != "luft" and d["route"] != "distribution":
                if not g.has_edge(d["von"], d["nach"]) or d["tage_modus"] < g.edges[d["von"], d["nach"]]["w"]:
                    g.add_edge(d["von"], d["nach"], w=d["tage_modus"], kid=kid)
        try:
            pfad = nx.dijkstra_path(g, start, "HN", weight="w")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
        return [g.edges[a, b]["kid"] for a, b in zip(pfad, pfad[1:])]
