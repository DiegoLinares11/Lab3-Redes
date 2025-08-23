# algoritmos/dv.py
import math

class DistanceVector:
    def __init__(self, me: str, link_costs: dict):
        self.me = me
        self.link_costs = link_costs  # costos a vecinos directos
        self.dv_table = {me: 0.0, **{nb: c for nb, c in link_costs.items()}}
        self.next_hop = {nb: nb for nb in link_costs}
        self.vectors = {}  # almacena vectores de vecinos

    def make_vector(self):
        return {"origin": self.me, "dist": self.dv_table}

    def ingest_vector(self, vector: dict):
        origin = vector["origin"]
        dist_v = vector["dist"]
        self.vectors[origin] = dist_v
        changed = False

        for dst, d_v in dist_v.items():
            if dst == self.me: 
                continue
            cost_via = self.link_costs.get(origin, math.inf) + d_v
            if cost_via < self.dv_table.get(dst, math.inf):
                self.dv_table[dst] = cost_via
                self.next_hop[dst] = origin
                changed = True
        return changed