import sys, socket, json, uuid

# Uso: python send_data.py HOST PORT SRC DST PROTO "mensaje"
if len(sys.argv) < 6:
    print("Uso: python send_data.py HOST PORT SRC DST PROTO 'mensaje'")
    sys.exit(1)

host   = sys.argv[1]
port   = int(sys.argv[2])
src    = sys.argv[3]
dst    = sys.argv[4]
proto  = sys.argv[5].lower()
payload = " ".join(sys.argv[6:]) if len(sys.argv) > 6 else ""

msg = {
    "type": "DATA",
    "proto": proto,            # ahora se elige desde CLI
    "id": str(uuid.uuid4()),
    "src": src,
    "dst": dst,
    "ttl": 8,
    "headers": [],
    "payload": payload
}

with socket.create_connection((host, port), timeout=2.0) as s:
    s.sendall((json.dumps(msg) + "\n").encode("utf-8"))

print(f"OK sent {msg['id']} from {src} to {dst} via {proto.upper()}")
