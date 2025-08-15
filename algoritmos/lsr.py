from typing import Dict, List, Tuple, Optional
from .dijkstra import dijkstra_next_hops

# Un LSP describe los enlaces salientes de un origen, con un número de secuencia
# Ejemplo payload LSP (JSON):
# {"origin":"A","seq":12,"links":[{"to":"B","w":1.0},{"to":"C","w":2.5}]}

class LSDB:
    """ Link-State Database: guarda el último LSP por origen (por seq) """
    def __init__(self):
        self._by_origin: Dict[str, Dict] = {}   # origin -> LSP dict
        self._seq_seen: Dict[str, int] = {}     # origin -> highest seq

    def should_accept(self, lsp: Dict) -> bool:
        o = lsp["origin"]; s = int(lsp["seq"])
        return (o not in self._seq_seen) or (s > self._seq_seen[o])

    def insert(self, lsp: Dict) -> bool:
        if not self.should_accept(lsp):
            return False
        o = lsp["origin"]; s = int(lsp["seq"])
        self._seq_seen[o] = s
        self._by_origin[o] = lsp
        return True

    def build_graph(self) -> Dict[str, List[Tuple[str, float]]]:
        """ Construye grafo no dirigido a partir de todos los LSPs """
        G: Dict[str, List[Tuple[str, float]]] = {}
        for origin, lsp in self._by_origin.items():
            G.setdefault(origin, [])
            for e in lsp.get("links", []):
                v, w = e["to"], float(e.get("w", 1.0))
                G.setdefault(v, [])
                # agregar arista origin->v y v->origin (si se desea simétrico)
                if (v, w) not in G[origin]:
                    G[origin].append((v, w))
                if (origin, w) not in G[v]:
                    G[v].append((origin, w))
        return G

class LSR:
    def __init__(self, node_id: str, neighbors: Dict[str, float]):
        """
        neighbors: mapa { vecino: peso/enlace } conocido localmente (p. ej. por HELLO)
        """
        self.node_id = node_id
        self.neighbors = neighbors
        self.lsdb = LSDB()
        self.seq = 0
        self.routing_next_hop: Dict[str, str] = {}
        self.routing_dist: Dict[str, float] = {}

    def make_local_lsp(self) -> Dict:
        self.seq += 1
        links = [{"to": nb, "w": w} for nb, w in self.neighbors.items()]
        return {"origin": self.node_id, "seq": self.seq, "links": links}

    def ingest_lsp(self, lsp: Dict) -> bool:
        """
        Devuelve True si este LSP es nuevo/mejor y debe
        (a) actualizar la LSDB,
        (b) recalcular rutas,
        (c) **flood** a vecinos (lo maneja el forwarding).
        """
        changed = self.lsdb.insert(lsp)
        if changed:
            self._recompute()
        return changed

    def _recompute(self):
        G = self.lsdb.build_graph()
        dist, nh = dijkstra_next_hops(self.node_id, G)
        self.routing_dist = dist
        self.routing_next_hop = nh

    def get_next_hop(self, dst: str) -> Optional[str]:
        return self.routing_next_hop.get(dst)

    def on_hello_result(self, neighbor: str, weight: float):
        """Actualizar costo a vecino tras HELLO/ping (opcional)"""
        self.neighbors[neighbor] = weight
        # emitimos un nuevo LSP local para anunciar el cambio
        # (el envío/flood real lo hace el plano de forwarding)
