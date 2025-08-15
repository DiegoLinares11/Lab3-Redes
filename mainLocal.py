from algoritmos.dijkstra import dijkstra_next_hops

G = {
  "A": [("B",1), ("C",4)],
  "B": [("A",1), ("C",2)],
  "C": [("A",4), ("B",2)],
}

for src in ["A","B","C"]:
    dist, nh = dijkstra_next_hops(src, G)
    print(f"\nDesde {src}:")
    for dst in sorted(G.keys()):
        if dst == src: 
            continue
        print(f"  {src}->{dst}: costo={dist[dst]} next_hop={nh.get(dst)}")
