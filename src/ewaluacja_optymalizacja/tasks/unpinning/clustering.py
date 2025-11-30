"""Funkcje klasteryzacji i partycjonowania prac dla analizy unpinning."""


def build_author_clusters(works_by_rekord):  # noqa: C901
    """
    Buduje klastry autorów metodą Union-Find.

    Jeśli dwóch autorów współpracowało przy jakiejkolwiek pracy, muszą być
    przetwarzani przez ten sam worker. W przeciwnym razie dwa workery mogłyby
    jednocześnie symulować odpięcia dla tego samego autora i uzyskać niespójne wyniki.

    Args:
        works_by_rekord: dict {rekord_tuple: {"rekord": ..., "authors": [...]}}

    Returns:
        dict: {cluster_id: {
            'authors': set of autor_ids,
            'works': list of rekord_tuples
        }}
    """
    # Union-Find structure
    parent = {}

    def find(x):
        if x not in parent:
            parent[x] = x
        if parent[x] != x:
            parent[x] = find(parent[x])  # Path compression
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Połącz autorów tej samej pracy
    for _rekord_tuple, work_data in works_by_rekord.items():
        authors = [a["autor_id"] for a in work_data["authors"]]
        if len(authors) >= 2:
            first = authors[0]
            for other in authors[1:]:
                union(first, other)

    # Grupuj prace według klastra
    clusters = {}
    for rekord_tuple, work_data in works_by_rekord.items():
        authors = [a["autor_id"] for a in work_data["authors"]]
        if authors:
            cluster_id = find(authors[0])
            if cluster_id not in clusters:
                clusters[cluster_id] = {"authors": set(), "works": []}
            clusters[cluster_id]["works"].append(rekord_tuple)
            clusters[cluster_id]["authors"].update(authors)

    return clusters


def partition_works_into_chunks(works_by_rekord, chunk_size=500):
    """
    Dzieli prace na chunki o określonej wielkości.

    Nie próbuje zachować klastrów autorów - po prostu dzieli równomiernie.
    Może powodować niespójności w symulacji gdy ten sam autor jest przetwarzany
    przez różne workery, ale pozwala na lepsze wykorzystanie wielu workerów.

    Args:
        works_by_rekord: dict {rekord_tuple: {"rekord": ..., "authors": [...]}}
        chunk_size: Docelowa liczba prac w każdym chunku (domyślnie 500)

    Returns:
        list of lists: [[rekord_tuples for chunk 0], [rekord_tuples for chunk 1], ...]
    """
    all_works = list(works_by_rekord.keys())
    total_works = len(all_works)

    if total_works == 0:
        return []

    # Oblicz liczbę chunków
    num_chunks = max(1, (total_works + chunk_size - 1) // chunk_size)

    # Podziel prace na chunki
    chunks = []
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = min(start_idx + chunk_size, total_works)
        chunks.append(all_works[start_idx:end_idx])

    return chunks
