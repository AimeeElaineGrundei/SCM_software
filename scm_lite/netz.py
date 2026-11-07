"""Liefernetz: Graph, Sperren, Routensuche (Dijkstra).

Kennzeichen: KI (Claude-Erstentwurf) – nach eigener Überarbeitung E setzen
"""
import networkx as nx

ZIEL = "HN"


class Netz:
    def __init__(self, stamm: dict):
        self.stamm = stamm
        self.kanten = {k: r for k, r in stamm["kanten"].to_dict("index").items()}
        for d in self.kanten.values():
            d["tags"] = [t for t in d["engpaesse"].split(";") if t]
        self.gesperrt_tags: set[str] = set()
        self.gesperrt_knoten: set[str] = set()

    def sperren(self, stoerungen: list[dict]) -> None:
        for s in stoerungen:
            if s["typ"] == "engpass":
                self.gesperrt_tags.add(s["ziel"])
            elif s["typ"] == "knoten":
                self.gesperrt_knoten.add(s["ziel"])

    def offen(self, kid: str) -> bool:
        d = self.kanten[kid]
        if d["von"] in self.gesperrt_knoten or d["nach"] in self.gesperrt_knoten:
            return False
        return not (set(d["tags"]) & self.gesperrt_tags)

    def standardroute(self, lid: str) -> list[str]:
        """Posterroute aus lieferanten.csv, z. B. 'U_SEIKO>YOK>RTM>HN|lkw>see:suez>binnen'."""
        knoten, modi = self.stamm["lieferanten"].loc[lid, "standardroute"].split("|")
        knoten, modi = knoten.split(">"), modi.split(">")
        route = []
        for (v, n), m in zip(zip(knoten, knoten[1:]), modi):
            modus, _, via = m.partition(":")
            kand = [k for k, d in self.kanten.items() if d["von"] == v and d["nach"] == n and d["modus"] == modus]
            if via == "kap":
                kand = [k for k in kand if self.kanten[k]["route"] == "kap"]
            elif via:
                kand = [k for k in kand if via in self.kanten[k]["tags"]]
            else:
                kand = [k for k in kand if self.kanten[k]["route"] != "kap"] or kand
            route.append(kand[0])
        return route

    def beste_route(self, start: str, kriterium: str = "zeit", luft: bool = False) -> list[str] | None:
        g = nx.DiGraph()
        for kid, d in self.kanten.items():
            if not self.offen(kid) or (d["modus"] == "luft" and not luft):
                continue
            w = {"zeit": d["tage_modus"], "kosten": d["kosten_eur_pro_kg"],
                 "co2e": d["distanz_km"] * d["co2e_g_pro_tkm"]}[kriterium]
            if not g.has_edge(d["von"], d["nach"]) or w < g.edges[d["von"], d["nach"]]["w"]:
                g.add_edge(d["von"], d["nach"], w=w, kid=kid)
        try:
            pfad = nx.dijkstra_path(g, start, ZIEL, weight="w")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
        return [g.edges[a, b]["kid"] for a, b in zip(pfad, pfad[1:])]

    def route(self, lid: str, kriterium: str = "zeit", luft: bool = False) -> list[str] | None:
        """Standardroute, wenn offen – sonst beste offene Umleitung."""
        r = self.standardroute(lid)
        if all(self.offen(k) for k in r):
            return r
        return self.beste_route(lid, kriterium, luft)
