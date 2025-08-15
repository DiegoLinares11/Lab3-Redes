import uuid
from typing import Dict, Any

def make_msg(proto: str, mtype: str, src: str, dst: str, payload: Any, ttl: int = 8, headers=None):
    return {
        "id": str(uuid.uuid4()),
        "proto": proto,              # "lsr" | "dijkstra" | ...
        "type": mtype,               # "info" (LSP) | "message" | "hello"
        "from": src,
        "to": dst,
        "ttl": ttl,
        "headers": headers or [],
        "payload": payload           # para LSR: LSP dict
    }