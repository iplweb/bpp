"""Charakteryzacyjne testy dla matchuj_autora_po_stronie_pbn.

Pinują OBECNE zachowanie funkcji dopasowującej autora BPP do rekordu
naukowca po stronie PBN (kolejność strategii, wczesne returny, ścieżki
braku dopasowania oraz logika ratingu przy wielu dopasowaniach po nazwisku
spoza API instytucji). Mają przejść na NIEZMIENIONYM kodzie.
"""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_api.models import Scientist
from pbn_api.models.institution import Institution
from pbn_integrator.utils.scientists import matchuj_autora_po_stronie_pbn


def _make_scientist(
    *,
    from_institution_api,
    name="Jan",
    lastName="Kowalski",
    orcid=None,
    extra_object=None,
):
    """Utwórz Scientist z bieżącą wersją zawierającą podane pola obiektu."""
    obj = {"name": name, "lastName": lastName}
    if orcid is not None:
        obj["orcid"] = orcid
    if extra_object:
        obj.update(extra_object)
    return baker.make(
        Scientist,
        name=name,
        lastName=lastName,
        orcid=orcid or "",
        from_institution_api=from_institution_api,
        versions=[{"current": True, "object": obj}],
    )


@pytest.mark.django_db
def test_orcid_match_w_rekordach_z_api_instytucji():
    """ORCID w rekordzie from_institution_api=True → zwraca ten rekord."""
    s = _make_scientist(from_institution_api=True, orcid="0000-0001-1111-1111")
    res = matchuj_autora_po_stronie_pbn("Jan", "Kowalski", "0000-0001-1111-1111")
    assert res == s


@pytest.mark.django_db
def test_orcid_match_tylko_spoza_api_instytucji():
    """ORCID tylko w rekordzie spoza API instytucji → strategia A pudłuje,
    strategia B trafia."""
    s = _make_scientist(from_institution_api=False, orcid="0000-0002-2222-2222")
    res = matchuj_autora_po_stronie_pbn("Jan", "Kowalski", "0000-0002-2222-2222")
    assert res == s


@pytest.mark.django_db
def test_orcid_z_api_instytucji_ma_priorytet_nad_nazwiskiem():
    """Rekord ORCID z API instytucji wygrywa, zanim w ogóle padnie match po
    nazwisku."""
    orcid_inst = _make_scientist(
        from_institution_api=True,
        name="Jan",
        lastName="Kowalski",
        orcid="0000-0003-3333-3333",
    )
    # Inny rekord pasujący po nazwisku - nie powinien zostać wybrany.
    _make_scientist(
        from_institution_api=True, name="Jan", lastName="Kowalski", orcid=None
    )
    res = matchuj_autora_po_stronie_pbn("Jan", "Kowalski", "0000-0003-3333-3333")
    assert res == orcid_inst


@pytest.mark.django_db
def test_orcid_spoza_api_ma_priorytet_nad_nazwiskiem():
    """Strategia B (ORCID spoza API) ma priorytet nad matchowaniem po
    nazwisku."""
    orcid_rec = _make_scientist(
        from_institution_api=False,
        name="Anna",
        lastName="Nowak",
        orcid="0000-0004-4444-4444",
    )
    # Rekord z API instytucji pasujący po nazwisku, ale BEZ tego ORCID.
    _make_scientist(
        from_institution_api=True, name="Anna", lastName="Nowak", orcid=None
    )
    res = matchuj_autora_po_stronie_pbn("Anna", "Nowak", "0000-0004-4444-4444")
    assert res == orcid_rec


@pytest.mark.django_db
def test_orcid_multiple_w_api_instytucji_kontynuuje_do_nazwiska():
    """Wiele rekordów ORCID w API instytucji → strategia A loguje i pudłuje,
    ale match po nazwisku w API instytucji złapie."""
    _make_scientist(from_institution_api=True, orcid="0000-0005-5555-5555")
    _make_scientist(from_institution_api=True, orcid="0000-0005-5555-5555")
    # Z dwóch powyższych match po nazwisku też zwróci Multiple (strategia C),
    # więc oczekujemy None.
    res = matchuj_autora_po_stronie_pbn("Jan", "Kowalski", "0000-0005-5555-5555")
    assert res is None


@pytest.mark.django_db
def test_brak_orcid_pomija_strategie_orcid_i_idzie_po_nazwisku():
    """orcid=None → pomijamy strategie ORCID, dopasowanie po nazwisku."""
    s = _make_scientist(from_institution_api=True, name="Ewa", lastName="Wiśniewska")
    res = matchuj_autora_po_stronie_pbn("Ewa", "Wiśniewska", None)
    assert res == s


@pytest.mark.django_db
def test_nazwisko_match_z_api_instytucji():
    """Dopasowanie po imieniu+nazwisku w rekordach z API instytucji."""
    s = _make_scientist(from_institution_api=True, name="Piotr", lastName="Zieliński")
    res = matchuj_autora_po_stronie_pbn("Piotr", "Zieliński", None)
    assert res == s


@pytest.mark.django_db
def test_nazwisko_match_z_api_instytucji_ma_priorytet_nad_spoza():
    """Rekord z API instytucji wygrywa z rekordem spoza API instytucji
    przy dopasowaniu po nazwisku."""
    inst = _make_scientist(
        from_institution_api=True, name="Piotr", lastName="Zieliński"
    )
    _make_scientist(from_institution_api=False, name="Piotr", lastName="Zieliński")
    res = matchuj_autora_po_stronie_pbn("Piotr", "Zieliński", None)
    assert res == inst


@pytest.mark.django_db
def test_nazwisko_match_tylko_spoza_api_instytucji():
    """Dopasowanie po nazwisku tylko w rekordach spoza API instytucji."""
    s = _make_scientist(
        from_institution_api=False, name="Marek", lastName="Lewandowski"
    )
    res = matchuj_autora_po_stronie_pbn("Marek", "Lewandowski", None)
    assert res == s


@pytest.mark.django_db
def test_brak_dopasowania_zwraca_none():
    """Nikt nie pasuje → None."""
    res = matchuj_autora_po_stronie_pbn("Nikt", "Nieznany", None)
    assert res is None


@pytest.mark.django_db
def test_imiona_i_nazwisko_sa_strippowane():
    """Białe znaki w imionach/nazwisku są obcinane przed dopasowaniem."""
    s = _make_scientist(from_institution_api=True, name="Jan", lastName="Kowalski")
    res = matchuj_autora_po_stronie_pbn("  Jan  ", "  Kowalski  ", None)
    assert res == s


@pytest.mark.django_db
def test_nazwisko_multiple_z_api_instytucji_zwraca_none():
    """Wiele rekordów po nazwisku w API instytucji → strategia C loguje
    i pudłuje; brak rekordów spoza API → None."""
    _make_scientist(from_institution_api=True, name="Jan", lastName="Kowalski")
    _make_scientist(from_institution_api=True, name="Jan", lastName="Kowalski")
    res = matchuj_autora_po_stronie_pbn("Jan", "Kowalski", None)
    assert res is None


@pytest.mark.django_db
def test_nazwisko_multiple_spoza_api_wybiera_najlepszy_gdy_w_jednostce(uczelnia):
    """Wiele rekordów spoza API instytucji + jeden pracuje w jednostce →
    rating wybiera rekord z największą liczbą punktów."""
    inst = baker.make(Institution, mongoId="INST-PBN-UID")
    uczelnia.pbn_uid = inst
    uczelnia.save()
    Uczelnia.objects.__dict__.pop("default", None)

    najlepszy = _make_scientist(
        from_institution_api=False,
        name="Jan",
        lastName="Kowalski",
        extra_object={
            "currentEmployments": [{"institutionId": "INST-PBN-UID"}],
            "externalIdentifiers": ["x"],
            "legacyIdentifiers": ["y"],
            "qualifications": "prof.",
        },
    )
    # Drugi rekord - 0 punktów, nie pracuje w jednostce.
    _make_scientist(from_institution_api=False, name="Jan", lastName="Kowalski")

    res = matchuj_autora_po_stronie_pbn("Jan", "Kowalski", None)
    assert res == najlepszy

    Uczelnia.objects.__dict__.pop("default", None)


@pytest.mark.django_db
def test_nazwisko_multiple_spoza_api_nie_wybiera_gdy_nie_w_jednostce(uczelnia):
    """Wiele rekordów spoza API instytucji, żaden nie pracuje w jednostce →
    NIE WYBIERA NIC (None)."""
    inst = baker.make(Institution, mongoId="INST-PBN-UID")
    uczelnia.pbn_uid = inst
    uczelnia.save()
    Uczelnia.objects.__dict__.pop("default", None)

    _make_scientist(
        from_institution_api=False,
        name="Jan",
        lastName="Kowalski",
        extra_object={
            "currentEmployments": [{"institutionId": "INNA-INSTYTUCJA"}],
        },
    )
    _make_scientist(from_institution_api=False, name="Jan", lastName="Kowalski")

    res = matchuj_autora_po_stronie_pbn("Jan", "Kowalski", None)
    assert res is None

    Uczelnia.objects.__dict__.pop("default", None)


@pytest.mark.django_db
def test_orcid_brak_dopasowania_spada_do_nazwiska(uczelnia):
    """ORCID podany, ale nie pasuje nigdzie → spadamy do dopasowania po
    nazwisku, które trafia."""
    s = _make_scientist(
        from_institution_api=True, name="Jan", lastName="Kowalski", orcid=None
    )
    res = matchuj_autora_po_stronie_pbn("Jan", "Kowalski", "0000-0009-9999-9999")
    assert res == s
