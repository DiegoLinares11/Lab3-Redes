import sys
from core.config import load_names, load_topo
from core.transport_socket import SocketTransport
from core.node import Node

# Uso:
#   python run_node.py --proto lsr --id A --names configs/names-demo.txt --topo configs/topo-demo.txt

def parse_args(argv):
    args = {"--proto":"lsr","--id":None,"--names":None,"--topo":None}
    it = iter(argv[1:])
    for tok in it:
        if tok in args:
            args[tok] = next(it, None)
    if not args["--id"] or not args["--names"] or not args["--topo"]:
        raise SystemExit("Uso: python run_node.py --proto lsr --id A --names <path> --topo <path>")
    return args

if __name__ == "__main__":
    args = parse_args(sys.argv)
    names = load_names(args["--names"])
    topo  = load_topo(args["--topo"])
    if args["--id"] not in names:
        raise SystemExit(f"ID {args['--id']} no está en names")
    host, port = names[args["--id"]]
    trans = SocketTransport(args["--id"], port, {nb:names[nb] for nb in topo.get(args["--id"], {})})
    node  = Node(args["--id"], names, topo, proto=args["--proto"], transport=trans)
    node.start()
    # mantener vivo
    import time
    while True:
        time.sleep(1)