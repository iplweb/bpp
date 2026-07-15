"""Characterization tests pinning current behavior of the C901 dictionary
transforms before refactoring:

* ``integruj_jezyki``     (pbn_integrator/utils/dictionaries.py)
* ``integruj_zrodla``     (pbn_integrator/utils/journals.py)

These lock the OBSERVABLE behavior of every branch so the subsequent
complexity-reducing refactor can be proven behavior-preserving.
"""

from unittest.mock import Mock

import pytest
from model_bakery import baker

from bpp.models import Jezyk, Zrodlo
from pbn_api.models import Journal, Language

# ---------------------------------------------------------------------------
# integruj_jezyki
# ---------------------------------------------------------------------------


def _lang_payload(code, **lang):
    return {"code": code, "language": dict(lang)}


@pytest.mark.django_db
def test_jezyki_creates_then_updates_remote_language():
    """Loop 1: Language is created when absent and updated when payload
    differs from the stored ``language`` dict."""
    from pbn_integrator.utils import integruj_jezyki

    client = Mock()
    client.get_languages.return_value = [
        _lang_payload("zzz", **{"639-2": "zzz", "pl": None, "en": "Zzz"}),
    ]
    integruj_jezyki(client, create_if_not_exists=False)
    created = Language.objects.get(code="zzz")
    assert created.language == {"639-2": "zzz", "pl": None, "en": "Zzz"}

    # Second pass with a changed language dict -> updated in place.
    client.get_languages.return_value = [
        _lang_payload("zzz", **{"639-2": "zzz", "pl": None, "en": "Changed"}),
    ]
    integruj_jezyki(client, create_if_not_exists=False)
    created.refresh_from_db()
    assert created.language["en"] == "Changed"


@pytest.mark.django_db
def test_jezyki_maps_existing_jezyk_by_skrot_and_does_not_overwrite():
    """Loop 2: an existing BPP ``Jezyk`` matched by ``skrot`` gets its
    ``pbn_uid`` set when empty, and is left untouched when already set."""
    from pbn_integrator.utils import integruj_jezyki

    lang = baker.make(Language, code="zzz", language={"639-2": "zzz", "pl": "Zetka"})
    jezyk = baker.make(Jezyk, nazwa="Zetka jezyk", skrot="zzz", pbn_uid=None)

    client = Mock()
    client.get_languages.return_value = []
    integruj_jezyki(client, create_if_not_exists=False)

    jezyk.refresh_from_db()
    assert jezyk.pbn_uid_id == lang.pk

    # Re-running must not overwrite an already-mapped pbn_uid.
    other = baker.make(Language, code="zzz2", language={"639-2": "zzz"})
    jezyk.pbn_uid = other
    jezyk.save()
    integruj_jezyki(client, create_if_not_exists=False)
    jezyk.refresh_from_db()
    assert jezyk.pbn_uid_id == other.pk


@pytest.mark.django_db
def test_jezyki_found_by_nazwa_fallback_maps_pbn_uid():
    """Loop 2: not matched by skrot, but matched by ``nazwa__iexact`` of the
    Polish name -> falls through to the bottom mapping."""
    from pbn_integrator.utils import integruj_jezyki

    lang = baker.make(Language, code="qqq", language={"639-2": "qqq", "pl": "Kwakwa"})
    # skrot deliberately does NOT match 'qqq'; nazwa matches the 'pl' value.
    jezyk = baker.make(Jezyk, nazwa="Kwakwa", skrot="nomatch9", pbn_uid=None)

    client = Mock()
    client.get_languages.return_value = []
    integruj_jezyki(client, create_if_not_exists=False)

    jezyk.refresh_from_db()
    assert jezyk.pbn_uid_id == lang.pk


@pytest.mark.django_db
def test_jezyki_creates_jezyk_from_pl_when_missing_and_flag_set():
    """Loop 2: unmatched, ``pl`` present, create flag set -> new Jezyk with
    nazwa=pl, skrot=639-2, pbn_uid set."""
    from pbn_integrator.utils import integruj_jezyki

    lang = baker.make(
        Language,
        code="ppp",
        language={"639-2": "ppp", "pl": "Brakujacy", "en": "Missing"},
    )

    client = Mock()
    client.get_languages.return_value = []
    integruj_jezyki(client, create_if_not_exists=True)

    created = Jezyk.objects.get(nazwa="Brakujacy")
    assert created.skrot == "ppp"
    assert created.pbn_uid_id == lang.pk


@pytest.mark.django_db
def test_jezyki_creates_jezyk_from_en_when_no_pl():
    """Loop 2: unmatched, ``pl`` is None, create flag set -> new Jezyk uses
    the English name."""
    from pbn_integrator.utils import integruj_jezyki

    lang = baker.make(
        Language,
        code="eee",
        language={"639-2": "eee", "pl": None, "en": "OnlyEnglish"},
    )

    client = Mock()
    client.get_languages.return_value = []
    integruj_jezyki(client, create_if_not_exists=True)

    created = Jezyk.objects.get(nazwa="OnlyEnglish")
    assert created.skrot == "eee"
    assert created.pbn_uid_id == lang.pk


@pytest.mark.django_db
def test_jezyki_warns_when_missing_and_no_create_flag_with_pl():
    """Loop 2: unmatched, pl present, create flag unset -> warn, no Jezyk."""
    from pbn_integrator.utils import integruj_jezyki

    baker.make(Language, code="www", language={"639-2": "www", "pl": "Niematego"})

    client = Mock()
    client.get_languages.return_value = []
    with pytest.warns(UserWarning, match="Brak jezyka po stronie BPP"):
        integruj_jezyki(client, create_if_not_exists=False)

    assert not Jezyk.objects.filter(nazwa="Niematego").exists()


@pytest.mark.django_db
def test_jezyki_warns_when_missing_and_no_create_flag_without_pl():
    """Loop 2: unmatched, pl None, create flag unset -> warn (en branch)."""
    from pbn_integrator.utils import integruj_jezyki

    baker.make(
        Language,
        code="vvv",
        language={"639-2": "vvv", "pl": None, "en": "NoPl"},
    )

    client = Mock()
    client.get_languages.return_value = []
    with pytest.warns(UserWarning, match="Brak jezyka po stronie BPP"):
        integruj_jezyki(client, create_if_not_exists=False)

    assert not Jezyk.objects.filter(nazwa="NoPl").exists()


@pytest.mark.django_db
def test_jezyki_639_1_participates_in_query():
    """Loop 2: a Jezyk whose skrot equals the 639-1 code is matched via the
    extra OR term added only when 639-1 is present."""
    from pbn_integrator.utils import integruj_jezyki

    lang = baker.make(
        Language,
        code="aaa",
        language={"639-2": "nomatchX", "639-1": "qx", "pl": "Cos"},
    )
    jezyk = baker.make(Jezyk, nazwa="Cos jezyk", skrot="qx", pbn_uid=None)

    client = Mock()
    client.get_languages.return_value = []
    integruj_jezyki(client, create_if_not_exists=False)

    jezyk.refresh_from_db()
    assert jezyk.pbn_uid_id == lang.pk


# ---------------------------------------------------------------------------
# integruj_zrodla
# ---------------------------------------------------------------------------


def _journal(**kw):
    kw.setdefault("status", "ACTIVE")
    return baker.make(Journal, **kw)


@pytest.mark.django_db
def test_zrodla_matches_by_issn():
    from pbn_integrator.utils import integruj_zrodla

    j = _journal(issn="1111-1111", eissn="", title="Cokolwiek", mniswId=1)
    z = baker.make(
        Zrodlo, nazwa="Inny tytul", issn="1111-1111", e_issn="", pbn_uid=None
    )

    integruj_zrodla(disable_progress_bar=True)
    z.refresh_from_db()
    assert z.pbn_uid_id == j.pk


@pytest.mark.django_db
def test_zrodla_matches_by_eissn():
    from pbn_integrator.utils import integruj_zrodla

    j = _journal(issn="", eissn="2222-2222", title="Brak", mniswId=2)
    z = baker.make(
        Zrodlo, nazwa="Bez tytulu", issn="", e_issn="2222-2222", pbn_uid=None
    )

    integruj_zrodla(disable_progress_bar=True)
    z.refresh_from_db()
    assert z.pbn_uid_id == j.pk


@pytest.mark.django_db
def test_zrodla_matches_by_title():
    from pbn_integrator.utils import integruj_zrodla

    j = _journal(issn="", eissn="", title="Dokladny Tytul", mniswId=3)
    z = baker.make(Zrodlo, nazwa="Dokladny Tytul", issn="", e_issn="", pbn_uid=None)

    integruj_zrodla(disable_progress_bar=True)
    z.refresh_from_db()
    assert z.pbn_uid_id == j.pk


@pytest.mark.django_db
def test_zrodla_no_match_leaves_pbn_uid_none():
    from pbn_integrator.utils import integruj_zrodla

    _journal(issn="9999-9999", eissn="", title="Zupelnie inne", mniswId=4)
    z = baker.make(
        Zrodlo,
        nazwa="Nieistniejace zrodlo",
        issn="0000-0001",
        e_issn="",
        pbn_uid=None,
    )

    integruj_zrodla(disable_progress_bar=True)
    z.refresh_from_db()
    assert z.pbn_uid_id is None


@pytest.mark.django_db
def test_zrodla_integruje_wiele_zrodel_w_jednym_przebiegu():
    """Wszystkie pasujące źródła dostają ``pbn_uid`` w jednym przebiegu.

    Guard strumieniowej iteracji: ``integruj_zrodla`` iteruje po
    ``Zrodlo.objects.filter(pbn_uid_id=None)`` i JEDNOCZEŚNIE w pętli zapisuje
    ``pbn_uid`` (co usuwa wiersz ze zbioru pasującego do filtra). Migawka
    kursora musi wydać wszystkie wiersze niezależnie od tych zapisów —
    inaczej część źródeł zostałaby pominięta.
    """
    from pbn_integrator.utils import integruj_zrodla

    pary = []
    for i in range(5):
        issn = f"55{i}0-000{i}"
        j = _journal(issn=issn, eissn="", title=f"Tytul {i}", mniswId=100 + i)
        z = baker.make(Zrodlo, nazwa=f"Zrodlo {i}", issn=issn, e_issn="", pbn_uid=None)
        pary.append((z, j))

    integruj_zrodla(disable_progress_bar=True)

    for z, j in pary:
        z.refresh_from_db()
        assert z.pbn_uid_id == j.pk


@pytest.mark.django_db
def test_zrodla_multiple_matches_prefers_one_with_mniswid():
    """Multiple PBN journals match -> the one with a mniswId wins."""
    from pbn_integrator.utils import integruj_zrodla

    _journal(issn="3333-3333", eissn="", title="Wielo A", mniswId=None)
    with_mnisw = _journal(issn="3333-3333", eissn="", title="Wielo B", mniswId=77)
    z = baker.make(
        Zrodlo, nazwa="Wieloznaczne", issn="3333-3333", e_issn="", pbn_uid=None
    )

    integruj_zrodla(disable_progress_bar=True)
    z.refresh_from_db()
    assert z.pbn_uid_id == with_mnisw.pk


@pytest.mark.django_db
def test_zrodla_multiple_matches_no_mniswid_picks_longest_versions():
    """Multiple matches, none with mniswId -> picks the journal whose
    ``versions`` blob is the largest (longest pg_column_size)."""
    from pbn_integrator.utils import integruj_zrodla

    _journal(
        issn="4444-4444",
        eissn="",
        title="Krotki",
        mniswId=None,
        versions=[{"current": True, "object": {"title": "Krotki"}}],
    )
    big = _journal(
        issn="4444-4444",
        eissn="",
        title="Dlugi",
        mniswId=None,
        versions=[
            {
                "current": True,
                "object": {"title": "Dlugi", "blob": "y" * 5000},
            }
        ],
    )
    z = baker.make(
        Zrodlo, nazwa="Dwa bez mnisw", issn="4444-4444", e_issn="", pbn_uid=None
    )

    integruj_zrodla(disable_progress_bar=True)
    z.refresh_from_db()
    assert z.pbn_uid_id == big.pk
