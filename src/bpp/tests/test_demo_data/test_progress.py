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
