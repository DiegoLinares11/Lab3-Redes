from algoritmos.lsr import LSR
from core.table import RoutingTable
from collections import deque

# Topología: A-B (1), A-C (4), B-C (2)
A = LSR("A", {"B": 1.0, "C": 4.0})
B = LSR("B", {"A": 1.0, "C": 2.0})
C = LSR("C", {"A": 4.0, "B": 2.0})
nodes = {"A": A, "B": B, "C": C}

# --- Mecanismo de flood (event-driven) ---
queue = deque()
seen = set()  # pares (origin, seq) ya procesados por el "canal" de demo

def enqueue_to_all(lsp, sender=None):
    """Encola el LSP para todos los nodos distintos del sender."""
    for nid in nodes:
        if nid != sender:
            queue.append(("NET", nid, lsp))  # (tipo, receptor, lsp)

# 1) Boot: cada nodo emite su LSP local UNA sola vez y lo floodeamos
for nid, node in nodes.items():
    lsp = node.make_local_lsp()
    # el emisor también debe ingerir su propio LSP (como haría localmente)
    node.ingest_lsp(lsp)
    enqueue_to_all(lsp, sender=nid)

# 2) Procesar cola hasta converger
while queue:
    _, target_id, lsp = queue.popleft()
    key = (target_id, lsp["origin"], int(lsp["seq"]))
    if key in seen:
        continue
    seen.add(key)

    target = nodes[target_id]
    # Si el LSP es nuevo para el target, actualiza LSDB+rutas y re-floodea el MISMO LSP
    if target.ingest_lsp(lsp):
        enqueue_to_all(lsp, sender=target_id)

# 3) Imprimir tablas
for nid, node in nodes.items():
    rt = RoutingTable()
    rt.update_from_lsr(node.routing_dist, node.routing_next_hop, nid)
    print(f"\n== Tabla de {nid} ==")
    for dst in sorted(nodes.keys()):
        if dst == nid:
            continue
        nh = rt.get_next_hop(dst)
        d = rt.cost.get(dst, float("inf"))
        print(f"  destino {dst:>2}  via {nh}   costo {d}")
