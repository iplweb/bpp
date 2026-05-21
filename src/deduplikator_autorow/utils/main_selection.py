"""Wybór głównego rekordu (main) w klastrze duplikatów.

Hierarchia (kolejne kryteria odpalają tylko przy remisie):
1. ma_orcid (DESC)
2. ma_pbn_uid (DESC)
3. ma_tytul (DESC)
4. ma_dyscypline (DESC)
5. publikacje_count (DESC)
6. max_rok (DESC)
7. pk (ASC)
"""


def _selection_key(pk: int, meta: dict) -> tuple:
    """Klucz sortowania — niższe wartości = lepszy kandydat na main."""
    return (
        not meta["ma_orcid"],
        not meta["ma_pbn_uid"],
        not meta["ma_tytul"],
        not meta["ma_dyscypline"],
        -meta["publikacje_count"],
        -(meta["max_rok"] or 0),
        pk,
    )


def pick_main_pk(cluster: set[int], metas: dict[int, dict]) -> int:
    """Z klastra (set PKów) wybiera PK głównego rekordu.

    Args:
        cluster: set PKów członków klastra.
        metas: {pk -> meta dict z polami ma_orcid, ma_pbn_uid, ma_tytul,
                ma_dyscypline, publikacje_count, max_rok}.

    Returns:
        PK rekordu wybranego jako main.
    """
    return min(cluster, key=lambda pk: _selection_key(pk, metas[pk]))
