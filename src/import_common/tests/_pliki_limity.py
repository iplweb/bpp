"""Pomocnicze funkcje testów bezpieczników rozmiaru plików importu
(``import_common.util.sprawdz_plik_importu``) — współdzielone przez testy
poszczególnych importerów."""

import zipfile

import import_common.util

MALY_LIMIT_PLIKU = 200  # B
MALY_LIMIT_PO_DEKOMPRESJI = 1024 * 1024  # 1 MB


def zrob_bombe(path, rozpakowany=4 * 1024 * 1024):
    """ZIP (XLSX-podobny) z jednym silnie kompresowalnym wpisem — kilka KB na
    dysku, ``rozpakowany`` bajtów po dekompresji."""
    with zipfile.ZipFile(str(path), "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/worksheets/sheet1.xml", b"\0" * rozpakowany)
    return str(path)


def zrob_duzy_plik(path, rozmiar=MALY_LIMIT_PLIKU * 10):
    path.write_bytes(b"a;b;c\n" * (rozmiar // 6 + 1))
    return str(path)


def maly_limit_pliku(monkeypatch):
    """Zmniejsza limit rozmiaru na dysku (czytany w chwili wywołania), żeby
    testy nie musiały tworzyć plików setek MB."""
    monkeypatch.setattr(import_common.util, "MAX_ROZMIAR_PLIKU", MALY_LIMIT_PLIKU)


def maly_limit_dekompresji(monkeypatch):
    """Zmniejsza limit rozmiaru po dekompresji do 1 MB — bomba z
    ``zrob_bombe`` (4 MB po rozpakowaniu) go przekracza."""
    monkeypatch.setattr(
        import_common.util, "MAX_ROZMIAR_PO_DEKOMPRESJI", MALY_LIMIT_PO_DEKOMPRESJI
    )
