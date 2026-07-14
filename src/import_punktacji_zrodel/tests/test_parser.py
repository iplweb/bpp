import zipfile
from decimal import Decimal

import pytest

from import_common.exceptions import DecompressionBombException
from import_punktacji_zrodel.parser import wczytaj_plik_jcr


def test_odrzuca_bombe_dekompresji(tmp_path):
    """XLSX-bomba (~KB na dysku, setki MB po rozpakowaniu) jest odrzucana PRZED
    materializacją wierszy do listy — inaczej ubija workera importu (OOM).

    Zapisujemy jeden silnie kompresowalny wpis (same zera) o zadeklarowanym
    rozmiarze rozpakowanym powyżej ``MAX_ROZMIAR_PO_DEKOMPRESJI`` (500 MB),
    streamując go 1-MB kawałkami — plik na dysku to kilkanaście KB, a w RAM
    trzymamy naraz tylko jeden kawałek.
    """
    p = tmp_path / "bomba.xlsx"
    with zipfile.ZipFile(str(p), "w", zipfile.ZIP_DEFLATED) as zf:
        with zf.open("xl/worksheets/sheet1.xml", "w") as f:
            chunk = b"\0" * (1024 * 1024)
            for _ in range(520):  # 520 MB > 500 MB limit
                f.write(chunk)
    with pytest.raises(DecompressionBombException):
        wczytaj_plik_jcr(str(p))


@pytest.mark.parametrize("fmt", ["xlsx", "csv"])
def test_wykrywa_rok(fmt, jcr_xlsx_path, jcr_csv_path):
    path = jcr_xlsx_path if fmt == "xlsx" else jcr_csv_path
    parsed = wczytaj_plik_jcr(path)
    assert parsed.rok == 2025


@pytest.mark.parametrize("fmt", ["xlsx", "csv"])
def test_licznosc_czasopism_136(fmt, jcr_xlsx_path, jcr_csv_path):
    path = jcr_xlsx_path if fmt == "xlsx" else jcr_csv_path
    parsed = wczytaj_plik_jcr(path)
    assert len(parsed.czasopisma) == 136


@pytest.mark.parametrize("fmt", ["xlsx", "csv"])
def test_pomija_stopke_clarivate(fmt, jcr_xlsx_path, jcr_csv_path):
    path = jcr_xlsx_path if fmt == "xlsx" else jcr_csv_path
    parsed = wczytaj_plik_jcr(path)
    nazwy = [c.nazwa for c in parsed.czasopisma]
    assert not any("Clarivate" in n for n in nazwy)
    assert not any("Terms of Use" in n for n in nazwy)


def test_lancet_wartosci(jcr_xlsx_path):
    parsed = wczytaj_plik_jcr(jcr_xlsx_path)
    lancet = next(c for c in parsed.czasopisma if c.nazwa == "LANCET")
    assert lancet.issn == "0140-6736"
    assert lancet.e_issn == "1474-547X"
    assert lancet.impact_factor == Decimal("109.0")
    assert lancet.kwartyl_wos == 1  # Q1


def test_najlepszy_kwartyl_przy_wielu_kategoriach(jcr_xlsx_path):
    # ISSN 0268-3369 (BONE MARROW TRANSPLANTATION) ma Q1,Q2,Q1,Q1 -> min=1
    parsed = wczytaj_plik_jcr(jcr_xlsx_path)
    bmt = next(c for c in parsed.czasopisma if c.issn == "0268-3369")
    assert bmt.kwartyl_wos == 1
    assert len(bmt.kategorie) >= 2


def test_na_w_issn_daje_none(jcr_xlsx_path):
    # "Nature Cancer": ISSN N/A, eISSN 2662-1347
    parsed = wczytaj_plik_jcr(jcr_xlsx_path)
    nc = next(c for c in parsed.czasopisma if c.nazwa == "Nature Cancer")
    assert nc.issn is None
    assert nc.e_issn == "2662-1347"


def test_elife_same_na(jcr_xlsx_path):
    parsed = wczytaj_plik_jcr(jcr_xlsx_path)
    elife = next(c for c in parsed.czasopisma if c.nazwa == "eLife")
    assert elife.impact_factor is None
    assert elife.kwartyl_wos is None


def test_csv_xlsx_parity(jcr_xlsx_path, jcr_csv_path):
    x = wczytaj_plik_jcr(jcr_xlsx_path)
    c = wczytaj_plik_jcr(jcr_csv_path)
    assert x.rok == c.rok
    assert len(x.czasopisma) == len(c.czasopisma)
    kx = {(z.issn, z.e_issn, z.nazwa) for z in x.czasopisma}
    kc = {(z.issn, z.e_issn, z.nazwa) for z in c.czasopisma}
    assert kx == kc
