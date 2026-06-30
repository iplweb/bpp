"""Charakteryzacyjne testy dla bpp.finders.get_files.

Pinują OBECNE zachowanie przeszukiwania storage (filesystem walk),
aby umożliwić bezpieczny refactor (zdjęcie # noqa: C901).
"""

from django.core.files.storage import FileSystemStorage

from bpp.finders import get_files, may_contain_match


def _make_tree(tmp_path):
    (tmp_path / "a.css").write_text("a")
    (tmp_path / "b.js").write_text("b")
    (tmp_path / "skip.css").write_text("s")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.css").write_text("c")
    (sub / "d.txt").write_text("d")
    other = tmp_path / "other"
    other.mkdir()
    (other / "e.css").write_text("e")
    return FileSystemStorage(location=str(tmp_path))


def test_match_wszystkie_pliki_rekurencyjnie(tmp_path):
    storage = _make_tree(tmp_path)
    # match_patterns="*" jako string przekazany do matches_patterns;
    # rekursja wchodzi do podkatalogów bo may_contain_match("*"...).
    result = sorted(get_files(storage, match_patterns="*"))
    assert result == [
        "a.css",
        "b.js",
        "other/e.css",
        "skip.css",
        "sub/c.css",
        "sub/d.txt",
    ]


def test_ignore_patterns_pomijaja_pliki(tmp_path):
    storage = _make_tree(tmp_path)
    result = sorted(
        get_files(storage, match_patterns="*", ignore_patterns=["*.js", "skip.css"])
    )
    assert result == [
        "a.css",
        "other/e.css",
        "sub/c.css",
        "sub/d.txt",
    ]


def test_ignore_patterns_pomija_caly_katalog(tmp_path):
    storage = _make_tree(tmp_path)
    result = sorted(
        get_files(
            storage,
            match_patterns=["*.css", "sub/*", "other/*"],
            ignore_patterns=["other"],
        )
    )
    # katalog "other" jest ignorowany w całości
    assert "other/e.css" not in result
    assert "a.css" in result
    assert "sub/c.css" in result


def test_match_pattern_konkretny_glob(tmp_path):
    storage = _make_tree(tmp_path)
    # Tylko pliki .css na poziomie root pasują wzorcem "*.css";
    # do podkatalogów "sub"/"other" wchodzi rekursja gdy
    # may_contain_match (pattern.startswith(directory)) — tu nie pasuje,
    # więc podkatalogi NIE są przeszukiwane.
    result = sorted(get_files(storage, match_patterns=["*.css"]))
    assert result == ["a.css", "skip.css"]


def test_match_pattern_z_prefiksem_podkatalogu(tmp_path):
    storage = _make_tree(tmp_path)
    # "sub/*.css" → may_contain_match("sub") True, więc wchodzi do "sub",
    # ale nie do "other".
    result = sorted(get_files(storage, match_patterns=["sub/*.css"]))
    assert result == ["sub/c.css"]


def test_match_patterns_none_daje_pusta_liste(tmp_path):
    storage = _make_tree(tmp_path)
    # match_patterns=None → [] → matches_patterns zawsze False → nic.
    assert list(get_files(storage, match_patterns=None)) == []


def test_location_zaweza_przeszukiwanie(tmp_path):
    storage = _make_tree(tmp_path)
    result = sorted(get_files(storage, match_patterns="*", location="sub"))
    assert result == ["sub/c.css", "sub/d.txt"]


def test_may_contain_match_helper():
    assert may_contain_match("sub", ["sub/foo.css"]) is True
    assert may_contain_match("other", ["sub/foo.css"]) is False
    assert may_contain_match("sub", []) is False
