import time, threading
from typing import Dict, Tuple
from core.utils import Repeater
from core.messages import msg_info, msg_hello, msg_echo
from core.table import RoutingTable
from algoritmos.lsr import LSR
from algoritmos.flooding import Flooding
from algoritmos.dv import DistanceVector


class Node:
    def __init__(self, me: str, names: Dict[str, Tuple[str,int]], topo: Dict[str, Dict[str,float]],
                 proto: str = "lsr", transport=None):
        self.me = me
        self.proto = proto  # "lsr"|"dv"|"flooding"
        # vecinos y costos iniciales desde topo
        self.neigh_tcp = {nb: names[nb] for nb in topo.get(me, {}) if nb in names}
        self.link_costs = {nb: float(w) for nb,w in topo.get(me, {}).items()}
        self.transport = transport
        self.transport.on_message = self.on_message

        # Routing según protocolo
        self.rt = RoutingTable()
        if proto == "lsr":
            self.lsr = LSR(me, self.link_costs)
            self.seen_lsp = set()   # (origin, seq)
        elif proto == "flooding":
            self.flooding = Flooding(me)
        elif proto == "dv":
            self.dv = DistanceVector(me, self.link_costs)

        # dedup para DATA
        self.seen_data = set()

        # hello tracking (LSR)
        self.hello_out = {}
        self.hello_lock = threading.Lock()


    # ---------- lifecycle ----------
    def start(self, hello_every=5.0, lsp_every=20.0):
        self.transport.start_server()

        if self.proto == "lsr":
            # LSP inicial
            lsp = self.lsr.make_local_lsp()
            self.lsr.ingest_lsp(lsp)
            self.seen_lsp.add((lsp["origin"], int(lsp["seq"])))
            self.transport.flood(msg_info(lsp), sender=self.me)
            self.print_table()
            # loops periódicos
            Repeater(hello_every, self.send_hellos).start()
            Repeater(lsp_every, self.reannounce_lsp).start()

        elif self.proto == "dv":
            # Enviar vector inicial y repetir periódicamente
            def loop():
                while True:
                    vec = self.dv.make_vector()
                    self.transport.flood({"proto": "dv", "type": "INFO", "from": self.me, "payload": vec})
                    time.sleep(10)
            threading.Thread(target=loop, daemon=True).start()
            self.print_table()

        elif self.proto == "flooding":
            print(f"[{self.me}] Nodo en modo Flooding iniciado.")


    # ---------- forwarding handlers ----------
    def on_message(self, msg: dict):
        t = msg.get("type")
        proto = msg.get("proto")

        # ---------------- FLOODING ----------------
        if self.proto == "flooding":
            if t == "DATA":
                self.flooding.handle_data(msg, self.transport, self.neigh_tcp)
            return

        # ---------------- DISTANCE VECTOR ----------------
        if self.proto == "dv":
            if t == "INFO":
                vec = msg["payload"]
                changed = self.dv.ingest_vector(vec)
                if changed:
                    self.print_table()
            elif t == "DATA":
                mid = msg.get("id")
                if mid in self.seen_data:
                    return
                self.seen_data.add(mid)

                if msg.get("dst") == self.me:
                    print(f"\n[{self.me}] DELIVER DATA id={mid} from={msg.get('src')} payload={msg.get('payload')}")
                    print(f"[{self.me}] trace={msg.get('headers', [])}")
                else:
                    dst = msg["dst"]
                    nh = self.dv.next_hop.get(dst)
                    if not nh:
                        print(f"[{self.me}] DROP no-route DATA {msg.get('id')} dst={dst}")
                        return
                    msg["headers"] = msg.get("headers", []) + [{"hop": self.me}]
                    self.transport.send_json(nh, msg)
            return

        # ---------------- LINK STATE ROUTING ----------------
        if self.proto == "lsr":
            if proto != "lsr": 
                return

            if t == "HELLO":
                # responder ECHO
                self.transport.send_json(msg["from"], msg_echo(self.me, msg["from"], msg["id"], msg.get("ts")))
                return

            if t == "ECHO":
                mid = msg.get("id")
                if not mid: return
                with self.hello_lock:
                    self.hello_out.pop(mid, None)
                return

            if t == "INFO":
                lsp = msg["payload"]
                key = (lsp["origin"], int(lsp["seq"]))
                if key in self.seen_lsp: return
                changed = self.lsr.ingest_lsp(lsp)
                self.seen_lsp.add(key)
                if changed:
                    self.transport.flood(msg, sender=None)
                    self.print_table()
                return

            if t == "DATA":
                mid = msg.get("id")
                if not mid or mid in self.seen_data: 
                    return
                self.seen_data.add(mid)
                if msg.get("dst") == self.me:
                    print(f"\n[{self.me}] DELIVER DATA id={mid} from={msg.get('src')} payload={msg.get('payload')}")
                    print(f"[{self.me}] trace={msg.get('headers', [])}")
                else:
                    self.forward_data(msg)
                return


    # ---------- helpers ----------
    def forward_data(self, msg: dict):
        ttl = int(msg.get("ttl", 8))
        if ttl <= 0:
            print(f"[{self.me}] DROP ttl=0 DATA {msg.get('id')}")
            return
        dst = msg["dst"]
        nh = self.lsr.get_next_hop(dst)
        if not nh:
            print(f"[{self.me}] DROP no-route DATA {msg.get('id')} dst={dst}")
            return
        msg["ttl"] = ttl - 1
        msg["headers"] = msg.get("headers", []) + [{"hop": self.me}]
        self.transport.send_json(nh, msg)


    def send_hellos(self):
        for nb in self.neigh_tcp.keys():
            m = msg_hello(self.me, nb)
            with self.hello_lock:
                self.hello_out[m["id"]] = (time.time(), nb)
            self.transport.send_json(nb, m)


    def reannounce_lsp(self):
        lsp = self.lsr.make_local_lsp()
        self.lsr.ingest_lsp(lsp)
        self.seen_lsp.add((lsp["origin"], int(lsp["seq"])))
        self.transport.flood(msg_info(lsp), sender=self.me)


    def print_table(self):
        print(f"\n== {self.me} tabla ==")
        if self.proto == "lsr":
            self.rt.update_from_lsr(self.lsr.routing_dist, self.lsr.routing_next_hop, self.me)
            for dst, d in sorted(self.lsr.routing_dist.items()):
                if dst == self.me or d == float('inf'): continue
                nh = self.rt.get_next_hop(dst)
                print(f"  {self.me}->{dst}: via {nh}  costo {d}")

        elif self.proto == "dv":
            for dst, d in sorted(self.dv.dv_table.items()):
                if dst == self.me or d == float('inf'): continue
                nh = self.dv.next_hop.get(dst)
                print(f"  {self.me}->{dst}: via {nh}  costo {d}")