import time

class Flooding:
    def __init__(self, me: str):
        self.me = me
        self.seen = set()  # evitar reenvío de duplicados

    def handle_data(self, msg: dict, transport, neighbors):
        mid = msg.get("id")
        if not mid or mid in self.seen:
            return
        self.seen.add(mid)

        # Si el mensaje es para mí → lo entrego
        if msg.get("dst") == self.me:
            print(f"\n[{self.me}] DELIVER DATA id={mid} from={msg.get('src')} payload={msg.get('payload')}")
            print(f"[{self.me}] trace={msg.get('headers', [])}")
            return

        # Si no es para mí → lo reenvío a todos los vecinos
        hdrs = msg.get("headers", [])
        hdrs.append({"hop": self.me, "ts": time.time()})
        msg["headers"] = hdrs

        for nb in neighbors.keys():
            transport.send_json(nb, msg)
