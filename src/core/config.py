from typing import Dict, Tuple

def load_names(path: str) -> Dict[str, Tuple[str, int]]:
    m = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            nid, host, port = line.split()
            m[nid] = (host, int(port))
    return m

def load_topo(path: str) -> Dict[str, Dict[str, float]]:
    G = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            u, v, w = line.split()
            w = float(w)
            G.setdefault(u, {})[v] = w
            G.setdefault(v, {})[u] = w
    return G