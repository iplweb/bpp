"""Repro dla FD#389 — autodetekcja języka pracy w importerze publikacji.

Wykrywanie języka (``_detect_language``) już istnieje, ale przypisanie
wykrytego/podanego kodu do obiektu ``Jezyk`` w
``_auto_match_type_and_language`` szło wyłącznie przez
``Komparator.porownaj_language``, które twardo odrzuca każdy kod spoza
statycznego enuma ``Jezyk.SKROT_CROSSREF`` = {en, es, pl}
(crossref_bpp/core.py). W efekcie publikacja niemiecka/francuska/rosyjska
/ukraińska była poprawnie wykrywana, ale jej język NIE był przypisywany —
mimo że instalacja miała pasujący rekord ``Jezyk``.

Te testy pinują oczekiwanie: jeśli istnieje ``Jezyk`` z danym
``skrot_crossref``, autodetekcja przypisuje go do sesji — także dla kodów
spoza {en, es, pl}.
"""

from unittest.mock import patch

import pytest

from importer_publikacji.providers import FetchedPublication
from importer_publikacji.tasks import _auto_match_type_and_language


def _jezyk(skrot_crossref, nazwa, skrot):
    """Pobierz/utwórz Jezyk o danym skrot_crossref.

    Baseline bazy ma już rekordy języków (z reguły bez skrot_crossref),
    więc dopasowujemy po unikalnym skrot_crossref i nie kolidujemy z
    nazwą/skrótem rekordów referencyjnych.
    """
    from bpp.models import Jezyk

    obj, _ = Jezyk.objects.get_or_create(
        skrot_crossref=skrot_crossref,
        defaults={"nazwa": nazwa, "skrot": skrot},
    )
    return obj


def _session(importer_user):
    from importer_publikacji.models import ImportSession

    return ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier="repro-fd389",
        raw_data={},
        normalized_data={"title": "x"},
    )


@pytest.mark.django_db
def test_jezyk_podany_przez_zrodlo_spoza_enum_zostaje_przypisany(importer_user):
    """Źródło podaje język "de" (spoza {en, es, pl}); istnieje Jezyk z
    skrot_crossref="de" → po dopasowaniu session.jezyk == ten Jezyk.
    """
    jez_de = _jezyk("de", "TEST-niemiecki-fd389", "tde389")
    session = _session(importer_user)
    result = FetchedPublication(
        raw_data={},
        title="Der Einfluss von Umweltfaktoren auf die Gesundheit",
        language="de",
    )

    _auto_match_type_and_language(session, result)

    assert session.jezyk == jez_de


@pytest.mark.django_db
def test_jezyk_wykryty_heurystycznie_spoza_enum_zostaje_przypisany(importer_user):
    """Źródło NIE podaje języka; wykrywanie zwraca "de"; istnieje Jezyk z
    skrot_crossref="de" → session.jezyk == ten Jezyk.

    Wykrywanie patchujemy, by test był deterministyczny niezależnie od
    biblioteki langdetect — sprawdzamy ścieżkę przypisania, nie samą
    bibliotekę.
    """
    jez_de = _jezyk("de", "TEST-niemiecki-fd389", "tde389")
    session = _session(importer_user)
    result = FetchedPublication(
        raw_data={},
        title="Der Einfluss von Umweltfaktoren auf die Gesundheit",
        language=None,
    )

    with patch("importer_publikacji.views.helpers._detect_language", return_value="de"):
        _auto_match_type_and_language(session, result)

    assert session.jezyk == jez_de


@pytest.mark.django_db
def test_jezyk_z_enum_nadal_dziala(importer_user):
    """Regression guard: kod z enuma ({en}) nadal dopasowuje się przez
    Komparator gdy istnieje pasujący Jezyk.
    """
    jez_en = _jezyk("en", "TEST-angielski-fd389", "ten389")
    session = _session(importer_user)
    result = FetchedPublication(
        raw_data={},
        title="The influence of environmental factors on health",
        language="en",
    )

    _auto_match_type_and_language(session, result)

    assert session.jezyk == jez_en
