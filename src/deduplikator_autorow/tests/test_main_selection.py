"""Testy hierarchii wyboru głównego rekordu (hierarchia B)."""

from deduplikator_autorow.utils.main_selection import pick_main_pk


def _meta(**kwargs):
    """Helper — minimalny wpis meta."""
    base = {
        "ma_orcid": False,
        "ma_pbn_uid": False,
        "ma_tytul": False,
        "ma_dyscypline": False,
        "publikacje_count": 0,
        "max_rok": 0,
    }
    base.update(kwargs)
    return base


def test_orcid_wins_over_everything():
    metas = {
        1: _meta(ma_orcid=False, publikacje_count=100, max_rok=2025),
        2: _meta(ma_orcid=True, publikacje_count=1, max_rok=2000),
    }
    cluster = {1, 2}
    assert pick_main_pk(cluster, metas) == 2


def test_pbn_uid_wins_when_orcid_tied():
    metas = {
        1: _meta(ma_orcid=True, ma_pbn_uid=False),
        2: _meta(ma_orcid=True, ma_pbn_uid=True),
    }
    assert pick_main_pk({1, 2}, metas) == 2


def test_tytul_wins_when_above_tied():
    metas = {
        1: _meta(ma_orcid=True, ma_pbn_uid=True, ma_tytul=False),
        2: _meta(ma_orcid=True, ma_pbn_uid=True, ma_tytul=True),
    }
    assert pick_main_pk({1, 2}, metas) == 2


def test_dyscyplina_wins_when_above_tied():
    metas = {
        1: _meta(ma_orcid=True, ma_pbn_uid=True, ma_tytul=True, ma_dyscypline=False),
        2: _meta(ma_orcid=True, ma_pbn_uid=True, ma_tytul=True, ma_dyscypline=True),
    }
    assert pick_main_pk({1, 2}, metas) == 2


def test_publikacje_count_wins_when_above_tied():
    metas = {
        1: _meta(publikacje_count=5),
        2: _meta(publikacje_count=10),
    }
    assert pick_main_pk({1, 2}, metas) == 2


def test_max_rok_wins_when_publikacje_tied():
    metas = {
        1: _meta(publikacje_count=5, max_rok=2020),
        2: _meta(publikacje_count=5, max_rok=2025),
    }
    assert pick_main_pk({1, 2}, metas) == 2


def test_pk_lowest_wins_when_all_tied():
    metas = {
        77: _meta(),
        12: _meta(),
        99: _meta(),
    }
    assert pick_main_pk({77, 12, 99}, metas) == 12
