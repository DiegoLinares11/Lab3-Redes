import heapq
from typing import Dict, Tuple, List

Graph = Dict[str, List[Tuple[str, float]]]

def dijkstra_next_hops(source: str, G: Graph):
    """
    Retorna:
      dist[dst] -> costo mínimo
      next_hop[dst] -> siguiente salto desde 'source' hacia 'dst'
    """
    dist = {u: float("inf") for u in G}
    parent = {u: None for u in G}
    dist[source] = 0.0

    pq = [(0.0, source)]
    while pq:
        d, u = heapq.heappop(pq)
        if d != dist[u]:
            continue
        for v, w in G.get(u, []):
            nd = d + float(w)
            if nd < dist[v]:
                dist[v] = nd
                parent[v] = u
                heapq.heappush(pq, (nd, v))

    # Construir next-hop desde el árbol de padres
    next_hop = {}
    for dst in G:
        if dst == source or dist[dst] == float("inf"):
            continue
        # retroceder desde dst hasta el vecino directo del source
        cur = dst
        prev = parent[cur]
        # si no hay ruta, se queda sin next-hop
        if prev is None:
            continue
        while prev is not None and prev != source:
            cur = prev
            prev = parent[cur]
        if prev == source:
            next_hop[dst] = cur
    return dist, next_hop
