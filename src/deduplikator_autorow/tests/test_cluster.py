"""Testy union-find (connected components)."""

from deduplikator_autorow.utils.cluster import find_clusters


def test_two_disjoint_pairs():
    pairs = [(1, 2), (3, 4)]
    clusters = sorted(find_clusters(pairs), key=min)
    assert clusters == [{1, 2}, {3, 4}]


def test_transitive_cluster():
    """A~B and B~C → cluster {A, B, C}."""
    pairs = [(1, 2), (2, 3)]
    clusters = list(find_clusters(pairs))
    assert clusters == [{1, 2, 3}]


def test_single_pair():
    pairs = [(7, 8)]
    clusters = list(find_clusters(pairs))
    assert clusters == [{7, 8}]


def test_no_pairs():
    assert list(find_clusters([])) == []


def test_isolated_nodes_with_pairs():
    """Tylko węzły mające połączenia trafiają do klastrów."""
    pairs = [(1, 2), (5, 6), (2, 3)]
    clusters = sorted(find_clusters(pairs), key=min)
    assert clusters == [{1, 2, 3}, {5, 6}]


def test_duplicate_pairs_are_idempotent():
    pairs = [(1, 2), (1, 2), (2, 1)]
    clusters = list(find_clusters(pairs))
    assert clusters == [{1, 2}]
