import json, socket, threading, time, sys
from typing import Dict, Tuple, Optional
from algoritmos.lsr import LSR
from core.table import RoutingTable

# ---- CLI: python run_node.py A 5000 B:127.0.0.1:5001:1 C:127.0.0.1:5002:4
me = sys.argv[1]
port = int(sys.argv[2])

TCP_NEIGHBORS: Dict[str, Tuple[str, int]] = {}   # id -> (host, port)
link_costs: Dict[str, float] = {}                # id -> peso

for item in sys.argv[3:]:
    parts = item.split(":")
    if len(parts) < 3:
        raise SystemExit(f"Vecino mal formado: {item}  (usa ID:HOST:PUERTO[:COSTO])")
    nid, host, nport = parts[0], parts[1], int(parts[2])
    cost = float(parts[3]) if len(parts) >= 4 else 1.0
    TCP_NEIGHBORS[nid] = (host, nport)
    link_costs[nid] = cost

lsr = LSR(me, link_costs)

# --- deduplicación de LSPs vistos: (origin, seq)
seen = set()
seen_lock = threading.Lock()

def send_json(to_id: str, obj: dict):
    host, nport = TCP_NEIGHBORS[to_id]
    try:
        with socket.create_connection((host, nport), timeout=1.5) as s:
            s.sendall((json.dumps(obj) + "\n").encode("utf-8"))
    except OSError:
        # vecino puede estar caído o aún no levantó; está bien ignorar
        pass

def flood_same_lsp(lsp: dict, sender: Optional[str]):
    for nid in TCP_NEIGHBORS.keys():
        if nid != sender:
            send_json(nid, {"type": "INFO", "proto": "lsr", "payload": lsp})

def server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen()
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_client, args=(conn,), daemon=True).start()

def handle_client(conn: socket.socket):
    buf = b""
    with conn:
        while True:
            data = conn.recv(4096)
            if not data:
                return
            buf += data
            # procesar por líneas (\n)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                on_message(msg)

def on_message(msg: dict):
    if msg.get("type") == "INFO" and msg.get("proto") == "lsr":
        lsp = msg["payload"]
        key = (lsp["origin"], int(lsp["seq"]))
        with seen_lock:
            if key in seen:
                return
            changed = lsr.ingest_lsp(lsp)
            seen.add(key)
        # re-flood el MISMO LSP si fue nuevo
        if changed:
            flood_same_lsp(lsp, sender=None)
            maybe_print_tables()

def maybe_print_tables():
    # pequeña pausa para agrupar cambios
    time.sleep(0.05)
    rt = RoutingTable()
    rt.update_from_lsr(lsr.routing_dist, lsr.routing_next_hop, me)
    print(f"\n== {me} tabla ==")
    for dst, d in sorted(lsr.routing_dist.items()):
        if dst == me or d == float("inf"):
            continue
        nh = rt.get_next_hop(dst)
        print(f"  {me}->{dst}: via {nh}  costo {d}")

if __name__ == "__main__":
    threading.Thread(target=server, daemon=True).start()
    time.sleep(0.2)

    # 1) anuncio local inicial
    lsp0 = lsr.make_local_lsp()
    lsr.ingest_lsp(lsp0)
    # marcamos este LSP como visto por nosotros mismos para no “rebote interno”
    with seen_lock:
        seen.add((lsp0["origin"], int(lsp0["seq"])))
    flood_same_lsp(lsp0, sender=me)
    maybe_print_tables()

    # 2) mantener vivo el proceso
    print(f"[{me}] escuchando en {port}, vecinos: {list(TCP_NEIGHBORS.keys())}")
    while True:
        time.sleep(1)
