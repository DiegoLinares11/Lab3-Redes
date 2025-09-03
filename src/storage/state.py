from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time
import asyncio

class TTLCache:
    """
    Cache de 'msg_id' vistos con TTL (para de-dupe de INFO/MESSAGE).
    """
    def __init__(self, ttl_seconds: int = 120) -> None:
        self.ttl = ttl_seconds
        self._store: Dict[str, float] = {}

    def add(self, key: str) -> None:
        self._store[key] = time.time() + self.ttl

    def __contains__(self, key: str) -> bool:
        exp = self._store.get(key)
        if exp is None:
            return False
        if exp < time.time():
            self._store.pop(key, None)
            return False
        return True

    def purge(self) -> None:
        now = time.time()
        expired = [k for k, exp in self._store.items() if exp < now]
        for k in expired:
            self._store.pop(k, None)


@dataclass
class NeighborInfo:
    cost: float = 1.0
    last_hello_ts: float = field(default_factory=lambda: 0.0)


@dataclass
class State:
    """
    Estado compartido del nodo:
    - neighbors: información de enlaces directos y último HELLO recibido
    - lsdb: base de datos de estado de enlaces (LSR)
    - routing_table: destino -> next_hop
    - seen_cache: ids de mensajes vistos (de-dupe)
    """
    node_id: str
    neighbors: Dict[str, NeighborInfo] = field(default_factory=dict)
    lsdb: Dict[str, Dict[str, float]] = field(default_factory=dict)  # por nodo: {vecino: costo}
    lsdb_ts: dict[str, float] = field(default_factory=dict)  # <-- nuevo: último INFO por origin
    routing_table: Dict[str, str] = field(default_factory=dict)      # dst -> next_hop
    seen_cache: TTLCache = field(default_factory=lambda: TTLCache(120))

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    # -----------------------------
    # Vecinos directos
    # -----------------------------
    async def set_neighbors(self, initial: List[Tuple[str, float]]) -> None:
        async with self._lock:
            self.neighbors = {n: NeighborInfo(cost=c) for n, c in initial}
            self.lsdb[self.node_id] = {n: c for n, c in initial}

    async def add_neighbor(self, neighbor_id: str, cost: float = 1.0) -> None:
        async with self._lock:
            self.neighbors[neighbor_id] = NeighborInfo(cost=cost)
            self.lsdb.setdefault(self.node_id, {})[neighbor_id] = cost

    async def remove_neighbor(self, neighbor_id: str) -> None:
        async with self._lock:
            self.neighbors.pop(neighbor_id, None)
            if self.node_id in self.lsdb:
                self.lsdb[self.node_id].pop(neighbor_id, None)

    async def touch_hello(self, neighbor_id: str, now: Optional[float] = None) -> None:
        ts = now if now is not None else time.time()
        async with self._lock:
            info = self.neighbors.get(neighbor_id)
            if info:
                info.last_hello_ts = ts

    async def dead_neighbors(self, timeout_sec: float) -> List[str]:
        now = time.time()
        async with self._lock:
            return [
                n for n, info in self.neighbors.items()
                if info.last_hello_ts and (now - info.last_hello_ts) > timeout_sec
            ]

    async def update_link_cost(self, neighbor_id: str, cost: float = 1.0) -> None:
        async with self._lock:
            if neighbor_id in self.neighbors:
                self.neighbors[neighbor_id].cost = cost
                self.lsdb.setdefault(self.node_id, {})[neighbor_id] = cost

    # -----------------------------
    # LSDB
    # -----------------------------
    async def update_lsdb(self, origin: str, links: dict[str, float]) -> None:
        async with self._lock:
            self.lsdb[origin] = dict(links)
            self.lsdb_ts[origin] = time.time()

    async def purge_stale_lsdb(self, max_age_sec: float) -> list[str]:
        """Elimina orígenes cuyo INFO está viejo. Devuelve la lista de purgados."""
        now = time.time()
        removed = []
        async with self._lock:
            for origin, ts in list(self.lsdb_ts.items()):
                if (now - ts) > max_age_sec:
                    self.lsdb.pop(origin, None)
                    self.lsdb_ts.pop(origin, None)
                    removed.append(origin)
        return removed

    async def get_lsdb_snapshot(self) -> Dict[str, Dict[str, float]]:
        async with self._lock:
            return {k: dict(v) for k, v in self.lsdb.items()}


    async def build_graph(self, hello_timeout_sec: float | None = None) -> dict[str, dict[str, float]]:
        async with self._lock:
            now = time.time()
            graph: dict[str, dict[str, float]] = {}

            # 1) Mis enlaces: opcionalmente filtrar por HELLO
            graph.setdefault(self.node_id, {})
            for n, info in self.neighbors.items():
                if hello_timeout_sec is not None:
                    if info.last_hello_ts == 0 or (now - info.last_hello_ts) > hello_timeout_sec:
                        continue
                graph[self.node_id][n] = info.cost
                graph.setdefault(n, {}).setdefault(self.node_id, info.cost)

            # 2) LSP de terceros: aceptarlos, pero opcionalmente
            #    descartar aristas hacia nodos que nunca hemos visto vivos
            def is_alive(node_id: str) -> bool:
                ni = self.neighbors.get(node_id)
                return bool(ni and ni.last_hello_ts and (now - ni.last_hello_ts) <= (hello_timeout_sec or 0))

            for u, edges in self.lsdb.items():
                graph.setdefault(u, {})
                for v, w in edges.items():
                    if hello_timeout_sec is not None and not is_alive(v) and v != self.node_id:
                        # si no tenemos evidencia de vida de 'v', evita usarlo
                        continue
                    graph[u][v] = w
                    graph.setdefault(v, {})
                    graph[v].setdefault(u, w)

            return graph


    async def get_alive_links(self, hello_timeout_sec: float) -> dict[str, float]:
        now = time.time()
        async with self._lock:
            out = {}
            for n, info in self.neighbors.items():
                if info.last_hello_ts and (now - info.last_hello_ts) <= hello_timeout_sec:
                    out[n] = info.cost
            return out

    # -----------------------------
    # Tabla de ruteo (costos fijos en 1)
    # -----------------------------
    async def set_routing_table(self, table: Dict[str, str]) -> None:
        async with self._lock:
            self.routing_table = dict(table)

    async def get_next_hop(self, dst: str) -> Optional[str]:
        async with self._lock:
            return self.routing_table.get(dst)

    async def get_routing_snapshot(self) -> Dict[str, str]:
        async with self._lock:
            return dict(self.routing_table)

    async def get_routing_table(self) -> Dict[str, Dict[str, float]]:
        """
        Devuelve {dst: {"next_hop": <id|->, "cost": <float|inf>}}
        Usando:
        - routing_table (next-hop ya calculado por LSR)
        - LSDB -> grafo -> Dijkstra para costos reales
        """
        # snapshot de lo que ya tienes
        routing = await self.get_routing_snapshot()
        graph   = await self.build_graph()

        # asegura que exista mi nodo en el grafo
        if self.node_id not in graph:
            graph[self.node_id] = {}

        # Dijkstra local (distancias mínimas desde self.node_id)
        import math
        dist = {n: math.inf for n in graph.keys()}
        vis  = {n: False     for n in graph.keys()}
        dist[self.node_id] = 0.0

        for _ in range(len(graph)):
            u, best = None, math.inf
            for n in graph.keys():
                if not vis[n] and dist[n] < best:
                    u, best = n, dist[n]
            if u is None:
                break
            vis[u] = True
            for v, w in graph[u].items():
                if vis.get(v): 
                    continue
                alt = dist[u] + float(w)
                if alt < dist[v]:
                    dist[v] = alt

        # arma tabla con next-hop (de routing_table) y costo (de dist)
        out: Dict[str, Dict[str, float]] = {}
        for dst in sorted(routing.keys()):
            if dst == self.node_id:
                continue
            nh = routing.get(dst)
            c  = dist.get(dst, math.inf)
            out[dst] = {"next_hop": nh or "-", "cost": c}
        return out

    async def print_routing_table(self) -> None:
        """
        Imprime la tabla de ruteo bonita: destino, next-hop y costo total.
        Recalcula costos en el momento usando la LSDB.
        """
        table = await self.get_routing_table()
        print(f"\n== Tabla de ruteo de {self.node_id} ==")
        print(f"{'Destino':<10} {'NextHop':<10} {'Costo':>10}")
        print("-" * 34)
        if not table:
            print("(sin rutas calculadas aún)")
        else:
            import math
            for dst, info in table.items():
                nh = info.get("next_hop", "-")
                c  = info.get("cost", math.inf)
                cost_str = f"{c:.4f}" if c != math.inf else "inf"
                print(f"{dst:<10} {nh:<10} {cost_str:>10}")
        print("-" * 34)

    # -----------------------------
    # seen_cache
    # -----------------------------
    def mark_seen(self, msg_id: str) -> None:
        self.seen_cache.add(msg_id)

    def is_seen(self, msg_id: str) -> bool:
        return msg_id in self.seen_cache

    def purge_seen(self) -> None:
        self.seen_cache.purge()
