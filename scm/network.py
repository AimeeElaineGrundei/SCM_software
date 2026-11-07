"""Netzwerk als gerichteter Multigraph (networkx) + Dijkstra-Routing + Störungszustand."""
from __future__ import annotations
import heapq
import networkx as nx
from .config import Config, Edge


class Disruptions:
    """Fragt zu jedem Zeitpunkt (Auswertungstag) ab, was gesperrt/gestört ist."""

    def __init__(self, cfg: Config):
        self.ev = cfg.events

    def _active(self, e, t):
        return e.start <= t < e.end

    def node_blocked(self, node, t):
        return any(e.type == "block_node" and e.node == node and self._active(e, t) for e in self.ev)

    def mode_blocked(self, mode, t):
        return any(e.type == "block_mode" and e.mode == mode and self._active(e, t) for e in self.ev)

    def supplier_ready_at(self, supplier, t):
        """Frühester Zeitpunkt >= t, an dem der Lieferant produzieren kann."""
        changed = True
        while changed:
            changed = False
            for e in self.ev:
                if e.type == "supplier_outage" and e.supplier == supplier and e.start <= t < e.end:
                    t = e.end
                    changed = True
        return t

    def demand_factor(self, t):
        f = 1.0
        for e in self.ev:
            if e.type == "demand_factor" and self._active(e, t):
                f *= e.factor
        return f

    def transit_factor(self, mode, t):
        f = 1.0
        for e in self.ev:
            if e.type == "transit_factor" and (e.mode in (None, mode)) and self._active(e, t):
                f *= e.factor
        return f

    def intervals(self):
        """Für die Darstellung: (Art, Objekt, Beginn, Ende)."""
        out = []
        for e in self.ev:
            if e.type == "block_node":
                out.append(("node", e.node, e.start, e.end))
            elif e.type == "block_mode":
                out.append(("mode", e.mode, e.start, e.end))
            elif e.type == "supplier_outage":
                out.append(("node", e.supplier, e.start, e.end))
        return out


class SupplyNetwork:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.g = nx.MultiDiGraph()
        for n in cfg.nodes.values():
            self.g.add_node(n.id, name=n.name, lat=n.lat, lon=n.lon, kind=n.kind)
        for e in cfg.edges.values():
            self.g.add_edge(e.src, e.dst, key=e.id, edge=e)
        self.focal = cfg.focal
        self.co2 = cfg.params["co2_g_per_tkm"]

    # ---- Kantenkennzahlen
    def edge_days_mode(self, e: Edge) -> float:
        return e.days[1]

    def edge_cost(self, e: Edge, kg: float) -> float:
        return e.fixed_eur + e.eur_per_kg * kg

    def edge_co2(self, e: Edge, kg: float) -> float:
        """kg CO2e = t * km * g/tkm / 1000"""
        return (kg / 1000.0) * e.km * self.co2[e.mode] / 1000.0

    def usable(self, e: Edge, t: float, dis: Disruptions, air_ok: bool) -> bool:
        if e.mode == "luft" and not air_ok:
            return False
        if e.kind == "outbound":
            return False
        if dis.mode_blocked(e.mode, t):
            return False
        if dis.node_blocked(e.dst, t):
            return False
        if self.g.nodes[e.src]["kind"] != "supplier" and dis.node_blocked(e.src, t):
            return False
        return True

    def route_open(self, edge_ids, t, dis, air_ok):
        return all(self.usable(self.cfg.edges[i], t, dis, air_ok) for i in edge_ids)

    # ---- Dijkstra
    def dijkstra(self, start: str, goal: str, t: float, dis: Disruptions, kg: float,
                 weight: str, air_ok: bool):
        """Kürzester Weg nach Zeit, Kosten oder CO2e über die zum Zeitpunkt t offenen Kanten."""
        def w(e):
            if weight == "time":
                return self.edge_days_mode(e)
            if weight == "cost":
                return self.edge_cost(e, kg)
            return self.edge_co2(e, kg)
        dist = {start: 0.0}
        prev = {}
        pq = [(0.0, start)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == goal:
                break
            if d > dist.get(u, float("inf")):
                continue
            for _, v, key, data in self.g.out_edges(u, keys=True, data=True):
                e = data["edge"]
                if not self.usable(e, t, dis, air_ok):
                    continue
                nd = d + w(e)
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prev[v] = (u, e.id)
                    heapq.heappush(pq, (nd, v))
        if goal not in dist:
            return None
        path, cur = [], goal
        while cur != start:
            u, eid = prev[cur]
            path.append(eid)
            cur = u
        return path[::-1]

    def plan_route(self, comp_id: str, start: str, t: float, dis: Disruptions, kg: float):
        """Regelroute, solange sie offen ist; sonst Umleitung (Dijkstra)."""
        pol = self.cfg.params["air_policy"]
        weight = self.cfg.params["route_weight"]
        base = self.cfg.base_routes[comp_id]
        if start != self.cfg.suppliers[self.cfg.components[comp_id].supplier].id:
            # mitten auf der Reise: Reste der Regelroute ab start verwenden, falls offen
            ids = [i for i in base]
            idx = next((k for k, i in enumerate(ids) if self.cfg.edges[i].src == start), None)
            rest = ids[idx:] if idx is not None else None
        else:
            rest = list(base)
        if pol == "always":
            return self.dijkstra(start, self.focal, t, dis, kg, "time", True)
        if rest is not None and self.route_open(rest, t, dis, False):
            return rest
        return self.dijkstra(start, self.focal, t, dis, kg, weight, pol == "on_disruption")
