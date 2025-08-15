import sys, socket, json, uuid

# Uso: python send_data.py HOST PORT SRC DST "mensaje"
host = sys.argv[1]
port = int(sys.argv[2])
src  = sys.argv[3]
dst  = sys.argv[4]
payload = " ".join(sys.argv[5:]) if len(sys.argv) > 5 else ""

msg = {
    "type": "DATA",
    "proto": "lsr",
    "id": str(uuid.uuid4()),
    "src": src,
    "dst": dst,
    "ttl": 8,
    "headers": [],
    "payload": payload
}

with socket.create_connection((host, port), timeout=2.0) as s:
    s.sendall((json.dumps(msg) + "\n").encode("utf-8"))
print("OK sent:", msg["id"])
