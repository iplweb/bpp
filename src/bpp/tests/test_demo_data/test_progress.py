"""Test fasady progress (tqdm) — minimalna, glownie do mock w testach."""

from bpp.demo_data.progress import make_progress


def test_make_progress_yields_all_items():
    items = list(make_progress(range(5), desc="t", total=5, disable=True))
    assert items == [0, 1, 2, 3, 4]


def test_make_progress_disabled_does_not_print(capsys):
    list(make_progress(range(3), desc="t", total=3, disable=True))
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


def test_obserwuj_postep_raportuje_kazdy_krok_paska():
    from bpp.demo_data.progress import obserwuj_postep

    zdarzenia = []
    with obserwuj_postep(lambda desc, n, total: zdarzenia.append((desc, n, total))):
        items = list(make_progress(range(3), desc="Autorzy", disable=True))
    assert items == [0, 1, 2]
    assert zdarzenia == [
        ("Autorzy", 0, 3),
        ("Autorzy", 1, 3),
        ("Autorzy", 2, 3),
        ("Autorzy", 3, 3),
    ]


def test_bez_obserwatora_make_progress_nie_raportuje():
    from bpp.demo_data.progress import obserwuj_postep

    zdarzenia = []
    with obserwuj_postep(lambda *a: zdarzenia.append(a)):
        pass
    list(make_progress(range(2), desc="t", disable=True))
    assert zdarzenia == []
