"""Lock the multi-hosted R2 delta in matchuj_autora_po_stronie_pbn.

Konsekwentna decyzja projektowa (reguła R2): autor bez macierzystej
uczelni (``aktualna_jednostka=None`` → ``uczelnia=None``) NIE jest
auto-matchowany po danych zatrudnienia PBN. Branch ``can_be_set`` w
``matchuj_autora_po_stronie_pbn`` wymaga ``uczelnia is not None`` ORAZ
zgodności ``institutionId`` w ``currentEmployments`` z
``uczelnia.pbn_uid_id``. Gdy ``uczelnia is None`` — branch jest pomijany,
``can_be_set`` zostaje False i funkcja zwraca None.

Ten test jest charakteryzacyjny (zachowanie już istnieje w kodzie) i
nie-wakuotyczny: pozytywna kontrola (z prawdziwą uczelnią) dowodzi, że
fixtura DA SIĘ zmatchować, więc wynik None dla ``uczelnia=None`` wynika
z delty R2, a nie z błędnych danych.
"""

import pytest
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from pbn_api.models import Institution, Scientist
from pbn_integrator.utils.scientists import matchuj_autora_po_stronie_pbn

IMIONA = "Jan Sebastian"
NAZWISKO = "Kowalski-Testowy"


def _make_uczelnia_with_pbn():
    institution = baker.make(Institution)
    uczelnia = baker.make(Uczelnia, pbn_uid=institution)
    obca = baker.make(Jednostka, uczelnia=uczelnia, skupia_pracownikow=False)
    uczelnia.obca_jednostka = obca
    uczelnia.save()
    return uczelnia


def _make_scientist(*, employments_institution_id, extra_marker, rich=False):
    """Scientist niez-API-instytucji, dopasowany po imieniu/nazwisku.

    ``versions[*].object`` zawiera lastName/name (żeby trafił w
    ``versions__contains`` query) oraz currentEmployments z podanym
    institutionId (żeby branch ``can_be_set`` mógł go zaakceptować przy
    podanej uczelni). ``rich=True`` dokłada legacyIdentifiers +
    qualifications, żeby rekord miał ściśle więcej punktów ratingu i
    deterministycznie wylądował jako ``rated_elems[0]``.
    """
    obj = {
        "lastName": NAZWISKO,
        "name": IMIONA,
        "currentEmployments": [
            {
                "institutionId": employments_institution_id,
                "institutionDisplayName": f"Inst {extra_marker}",
            }
        ],
        "externalIdentifiers": {"marker": extra_marker},
    }
    if rich:
        obj["legacyIdentifiers"] = {"legacy": extra_marker}
        obj["qualifications"] = "dr hab."
    return baker.make(
        Scientist,
        from_institution_api=False,
        versions=[{"current": True, "object": obj}],
    )


@pytest.mark.django_db
def test_r2_delta_uczelnia_none_brak_matchu_a_z_uczelnia_match():
    """uczelnia=None → None (delta R2); ta sama fixtura z uczelnią → match."""
    uczelnia = _make_uczelnia_with_pbn()

    # DWA rekordy z tym samym imieniem/nazwiskiem, oba spoza API
    # instytucji → ``.get()`` w name-path rzuca MultipleObjectsReturned i
    # wchodzimy w pętlę ratingu, gdzie żyje branch uczelnia/can_be_set.
    s1 = _make_scientist(
        employments_institution_id=uczelnia.pbn_uid_id,
        extra_marker="A",
        rich=True,
    )
    _make_scientist(
        employments_institution_id="INNA-INSTYTUCJA",
        extra_marker="B",
    )

    # Sanity: brak rekordu z API instytucji, więc nie ma wcześniejszego
    # return-a; w grze jest tylko ścieżka non-API z ratingiem.
    assert not Scientist.objects.filter(from_institution_api=True).exists()

    # NEGATYWNA (delta): bez macierzystej uczelni nie matchujemy.
    res_none = matchuj_autora_po_stronie_pbn(
        IMIONA, NAZWISKO, orcid=None, uczelnia=None
    )
    assert res_none is None

    # POZYTYWNA kontrola: z uczelnią, której pbn_uid_id jest w
    # currentEmployments → zwracamy Scientisa (dowodzi, że fixtura jest
    # matchowalna, a None powyżej wynika z delty R2).
    res_match = matchuj_autora_po_stronie_pbn(
        IMIONA, NAZWISKO, orcid=None, uczelnia=uczelnia
    )
    assert res_match is not None
    assert isinstance(res_match, Scientist)
    # Zwrócony rekord to ten z employmentem w naszej uczelni.
    assert res_match.pk == s1.pk
