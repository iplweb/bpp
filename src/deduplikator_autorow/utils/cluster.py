"""Union-find (connected components) dla par autorów.

Dla zbioru par (a, b) zwraca spójne komponenty grafu.
"""


def find_clusters(pairs):
    """Zwraca listę zbiorów (klastrów) z par.

    Args:
        pairs: iterable krotek (pk_a, pk_b).

    Returns:
        list[set[int]]: lista klastrów (każdy klaster to set PKów).
    """
    parent: dict = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in pairs:
        if a not in parent:
            parent[a] = a
        if b not in parent:
            parent[b] = b
        union(a, b)

    clusters_by_root: dict = {}
    for node in parent:
        root = find(node)
        clusters_by_root.setdefault(root, set()).add(node)

    return list(clusters_by_root.values())
