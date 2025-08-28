from typing import Dict, Optional

class RoutingTable:
    def __init__(self):
        self.next_hop: Dict[str, str] = {}
        self.cost: Dict[str, float] = {}

    def update_from_lsr(self, dist: Dict[str, float], next_hop: Dict[str, str], me: str):
        self.next_hop.clear(); self.cost.clear()
        for dst, d in dist.items():
            if dst == me or d == float("inf"):
                continue
            nh = next_hop.get(dst)
            if nh is not None:
                self.next_hop[dst] = nh
                self.cost[dst] = d

    def get_next_hop(self, dst: str) -> Optional[str]:
        return self.next_hop.get(dst)
