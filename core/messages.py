import uuid, time

def msg_info(lsp: dict):
    return {"type":"INFO","proto":"lsr","payload": lsp}

def msg_hello(src: str, dst: str):
    return {"type":"HELLO","proto":"lsr","id": str(uuid.uuid4()),
            "from": src, "to": dst, "ts": time.time()}

def msg_echo(src: str, dst: str, hello_id: str, ts: float):
    return {"type":"ECHO","proto":"lsr","id": hello_id, "from": src, "to": dst, "ts": ts}

def msg_data(src: str, dst: str, payload: str, ttl: int = 8):
    return {"type":"DATA","proto":"lsr","id": str(uuid.uuid4()),
            "src": src, "dst": dst, "ttl": ttl, "headers": [], "payload": payload}