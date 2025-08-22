import json, socket, threading, time
from typing import Dict, Tuple, Callable

class SocketTransport:
    def __init__(self, me: str, port: int, neighbors: Dict[str, Tuple[str,int]]):
        self.me = me
        self.port = port
        self.neighbors = neighbors
        self._server_th = None
        self.on_message: Callable[[dict], None] = lambda msg: None

    def start_server(self):
        def _server():
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", self.port))
            srv.listen()
            while True:
                conn, _ = srv.accept()
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
        self._server_th = threading.Thread(target=_server, daemon=True)
        self._server_th.start()
        time.sleep(0.2)

    def _handle_client(self, conn: socket.socket):
        buf = b""
        with conn:
            while True:
                data = conn.recv(4096)
                if not data: return
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip(): continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    self.on_message(msg)

    def send_json(self, to_id: str, obj: dict):
        host, port = self.neighbors[to_id]
        try:
            with socket.create_connection((host, port), timeout=1.5) as s:
                s.sendall((json.dumps(obj)+"\n").encode("utf-8"))
        except OSError:
            pass  # vecino caído/ausente

    def flood(self, obj: dict, sender: str | None = None):
        for nid in self.neighbors:
            if nid != sender:
                self.send_json(nid, obj)