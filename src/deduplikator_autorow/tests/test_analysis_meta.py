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
    # Identyczne imiona (żeby hard-rejection nie zadziałał i ORCID-mismatch
    # mógł być widoczny jako dominujący sygnał).
    a = _meta(
        nazwisko="kowalski",
        imiona=("jan",),
        orcid="0000-0001-1111-1111",
    )
    b = _meta(
        nazwisko="nowak",
        imiona=("jan",),
        orcid="0000-0002-2222-2222",
    )
    score, reasons = analiza_pary_meta(a, b)
    # +30 wspólne imię, -50 różny ORCID, +10 mało publikacji = -10 raw,
    # ale plus inne drobne. Sprawdzamy że ORCID-mismatch wypłynął jako
    # negatywny element (nie samo +30 dominuje).
    assert any("różny ORCID" in r for r in reasons)
    # Sumarycznie score powinien być wyraźnie obniżony przez ORCID
    assert score < 30


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


# --- Penalty za różne imiona (rozłączne, brak overlap-u w żadnym wymiarze) ----


def test_rozne_imiona_bez_zadnego_overlap_odejmuje_punkty():
    """'Jan' vs 'Stefan': brak common, brak similar (3-prefix), brak inicjału.

    Realny case użytkownika: 'Jan Kowalski' vs 'Stefan
    Kowalski-Nowak' — system dawał ~49% mimo zupełnie innych imion.
    Penalty ma zniwelować inne przesłanki tak, żeby raw score spadał poniżej
    progu MIN_CONFIDENCE_TO_STORE.
    """
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="kowalski-nowak", imiona=("stefan",))
    score, reasons = analiza_pary_meta(a, b)
    assert any("różne imiona" in r.lower() for r in reasons), (
        f"Brak powodu 'różne imiona' w {reasons}"
    )
    # Bez penalty: +30 (zawieranie nazwiska) + drobne plusy ≈ 30-50 raw.
    # Z penalty -40: powinno spaść poniżej progu 50 wymaganego do zapisu.
    assert score < 50, (
        f"Score {score} >= 50 mimo zupełnie różnych imion (powody: {reasons})"
    )


def test_jedno_wspolne_imie_nie_powoduje_penalty():
    """'Jan Maria' vs 'Maria Kasia' mają wspólne 'maria' — bez penalty."""
    a = _meta(imiona=("jan", "maria"))
    b = _meta(imiona=("maria", "kasia"))
    _, reasons = analiza_pary_meta(a, b)
    assert not any("różne imiona" in r.lower() for r in reasons)


def test_podobne_imie_nie_powoduje_penalty():
    """'Jan' vs 'Janusz' — startsWith(3) wystarcza, brak penalty."""
    a = _meta(imiona=("jan",))
    b = _meta(imiona=("janusz",))
    _, reasons = analiza_pary_meta(a, b)
    assert not any("różne imiona" in r.lower() for r in reasons)


def test_pasujacy_inicjal_nie_powoduje_penalty():
    """Wspólny inicjał (J vs J) traktowany jako sygnał - bez penalty."""
    # _common_initials w meta bierze pierwszy znak imienia. "jan" i "jakub"
    # mają wspólny inicjał "j" — i jednocześnie startsWith(3) NIE pasuje
    # ('jan' vs 'jakub' — różne 3 prefiksy 'jan' vs 'jak'). Penalty nie powinien
    # pojawić się tylko z powodu wspólnego inicjału.
    a = _meta(imiona=("jan",))
    b = _meta(imiona=("jakub",))
    _, reasons = analiza_pary_meta(a, b)
    assert not any("różne imiona" in r.lower() for r in reasons)


def test_brak_imion_po_jednej_stronie_nie_aktywuje_penalty():
    """Hard-rejection wymaga, by OBIE strony miały imiona — w przeciwnym razie
    nie ma o czym mówić, że są 'różne'."""
    a = _meta(imiona=("jan",))
    b = _meta(imiona=())
    _, reasons = analiza_pary_meta(a, b)
    assert not any("różne imiona" in r.lower() for r in reasons)


# --- Hard rejection: rozłączne imiona = NIE jest duplikatem (regardless of all) ----


def test_zupelnie_rozne_imiona_jest_hard_rejected():
    """Jan vs Agnieszka — różne imiona, brak swap → score mocno ujemny,
    żeby pair na pewno NIE przeszedł progu zapisu."""
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="kowalski", imiona=("agnieszka",))
    score, reasons = analiza_pary_meta(a, b)
    assert score < 0, f"Score {score} - pair powinna być twardo odrzucona"
    assert score <= -1000, f"Score {score} - powinien być sentinel ≤ -1000"
    assert any("odrzucono" in r.lower() for r in reasons)


def test_hard_rejection_wygrywa_z_identycznym_orcid():
    """Nawet identyczny ORCID (+50) nie ratuje pary z totalnie różnymi imionami.

    Jeżeli ORCID jest taki sam ale imiona zupełnie różne, system nadal
    odrzuca - to bardziej prawdopodobnie błąd w ORCID/imionach niż realny
    duplikat (bo imiona człowieka raczej nie zmieniają się tak drastycznie).
    """
    a = _meta(nazwisko="kowalski", imiona=("jan",), orcid="0000-0001-1111-1111")
    b = _meta(
        nazwisko="kowalski-nowak", imiona=("stefan",), orcid="0000-0001-1111-1111"
    )
    score, reasons = analiza_pary_meta(a, b)
    assert score <= -1000
    assert any("odrzucono" in r.lower() for r in reasons)


def test_hard_rejection_nie_blokuje_swap():
    """Klasyczny swap 'Jan Kowalski' ↔ 'Kowalski Jan' nie jest hard-rejected,
    mimo że wartości imion się nie pokrywają z imionami drugiego."""
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="jan", imiona=("kowalski",))
    score, reasons = analiza_pary_meta(a, b)
    assert score > 0
    assert any("zamian" in r.lower() for r in reasons)


# --- Inicjały: kiedy MOŻE być duplikatem, kiedy NIE MOŻE ----------------------


def test_jan_kowalski_vs_j_kropka_kowalski_moze_byc_duplikatem():
    """'Jan Kowalski' vs 'J. Kowalski' — to samo nazwisko, inicjał J się
    zgadza → kandydat MOŻE być duplikatem (nie hard-reject)."""
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="kowalski", imiona=("j.",))
    score, reasons = analiza_pary_meta(a, b)
    assert score > 0, (
        f"Para 'Jan' vs 'J.' powinna być akceptowalna, score={score}, reasons={reasons}"
    )
    assert not any("odrzucono" in r.lower() for r in reasons)


def test_jan_kowalski_vs_a_kropka_kowalski_NIE_moze_byc_duplikatem():
    """'Jan Kowalski' vs 'A. Kowalski' — to samo nazwisko, ale inicjał A != J
    → hard-reject (różne osoby)."""
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="kowalski", imiona=("a.",))
    score, reasons = analiza_pary_meta(a, b)
    assert score <= -1000, (
        f"Inicjał A != J — para powinna być twardo odrzucona, score={score}"
    )
    assert any("odrzucono" in r.lower() for r in reasons)


def test_jan_kowalski_vs_kowalski_j_swap_z_inicjalem_moze_byc():
    """'Jan Kowalski' vs 'Kowalski J.' — swap z inicjałem (database
    swap: imiona='Kowalski', nazwisko='J.'). Inicjał J pasuje do 'Jan' →
    MOŻE być duplikatem."""
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="j.", imiona=("kowalski",))
    score, reasons = analiza_pary_meta(a, b)
    assert score > 0, (
        f"Swap z pasującym inicjałem powinien przejść, score={score}, reasons={reasons}"
    )
    assert not any("odrzucono" in r.lower() for r in reasons)


def test_jan_kowalski_vs_kowalski_a_swap_z_innym_inicjalem_NIE_moze_byc():
    """'Jan Kowalski' vs 'Kowalski A.' — swap-like layout, ale 'A.' nie
    pasuje do 'Jan' (różne inicjały) → hard-reject."""
    a = _meta(nazwisko="kowalski", imiona=("jan",))
    b = _meta(nazwisko="a.", imiona=("kowalski",))
    score, reasons = analiza_pary_meta(a, b)
    assert score <= -1000, (
        f"Swap-shape z różnym inicjałem powinien być odrzucony, score={score}"
    )
    assert any("odrzucono" in r.lower() for r in reasons)
