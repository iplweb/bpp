"""Testy analiza_pary_meta — scoring par autorów na bazie meta."""

from deduplikator_autorow.utils.analysis_meta import analiza_pary_meta


def _meta(
    nazwisko="kowalski",
    imiona=("jan",),
    orcid=None,
    pbn_uid=False,
    tytul=False,
    pubs=0,
    max_rok=0,
    lata=None,
):
    return {
        "nazwisko_norm": nazwisko,
        "nazwisko_parts": nazwisko.split("-"),
        "imiona_norm": list(imiona),
        "orcid_value": orcid,
        "ma_orcid": bool(orcid),
        "ma_pbn_uid": pbn_uid,
        "ma_tytul": tytul,
        "tytul_id": 1 if tytul else None,
        "publikacje_count": pubs,
        "max_rok": max_rok,
        "lata_publikacji": set(lata or []),
    }


def test_identyczne_orcid_dodaje_50():
    a = _meta(orcid="0000-0001-2345-6789")
    b = _meta(orcid="0000-0001-2345-6789")
    score, reasons = analiza_pary_meta(a, b)
    assert score >= 50
    assert any("ORCID" in r for r in reasons)


def test_rozne_orcid_odejmuje_50():
    # Różne nazwiska/imiona, żeby ORCID był dominującym sygnałem.
    a = _meta(
        nazwisko="kowalski",
        imiona=("jan",),
        orcid="0000-0001-1111-1111",
    )
    b = _meta(
        nazwisko="nowak",
        imiona=("piotr",),
        orcid="0000-0002-2222-2222",
    )
    score, reasons = analiza_pary_meta(a, b)
    assert score <= -40  # -50 plus drobne plusy z innych kryteriów
    assert any("różny ORCID" in r for r in reasons)


def test_identyczne_nazwisko_dodaje_40():
    a = _meta(nazwisko="kowalski")
    b = _meta(nazwisko="kowalski")
    score, reasons = analiza_pary_meta(a, b)
    assert score >= 40
    assert any("nazwisko" in r.lower() for r in reasons)


def test_wspolne_lata_publikacji_dodaje_20():
    a = _meta(lata=[2020, 2021, 2022])
    b = _meta(lata=[2021, 2022])
    score, reasons = analiza_pary_meta(a, b)
    assert any("wspólne lata" in r.lower() for r in reasons)


def test_score_to_int():
    a = _meta()
    b = _meta()
    score, _ = analiza_pary_meta(a, b)
    assert isinstance(score, int)


def test_swap_imienia_z_nazwiskiem_dodaje_50():
    """Pełna zamiana imię ↔ nazwisko: A 'kowalski jan', B 'jan kowalski'."""
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="jan", imiona=("kowalski",))
    score, reasons = analiza_pary_meta(a, b)
    assert any("zamian" in r.lower() for r in reasons)
