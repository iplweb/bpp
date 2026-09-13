"""Autodetekcja języka musi działać na DANYCH REFERENCYJNYCH BPP.

FD#389 dorzucił fallback ``_resolve_jezyk`` dla kodów spoza enuma
``Jezyk.SKROT_CROSSREF`` = {en, es, pl}, ale oba tory — ``Komparator`` i sam
fallback — pytają wyłącznie o ``Jezyk.skrot_crossref``. A tę kolumnę
wypełnia tylko migracja ``0410``, i tylko dla polskiego; enum ogranicza też
listę wyboru w adminie do trzech pozycji, więc redakcja nie ustawi tam np.
„de". Efekt: na czystej instalacji import pracy z ``language="en"``
(np. DOI 10.1007/s00005-017-0485-3 z CrossRef) zostawiał pole „Język" puste,
a testy FD#389 tego nie łapały, bo same zakładały brakujący rekord.

Poprawne kody ISO są w BPP od dawna — w ``Jezyk.kod_bcp47``, wypełnianym
kuratorsko przez fixture ``jezyk.json`` i migrację ``0480`` (pl, en, de, fr,
es, ru, it). Fallback korzysta więc również z tej kolumny.
"""

import pytest

from importer_publikacji.providers import FetchedPublication
from importer_publikacji.tasks import _auto_match_type_and_language
from importer_publikacji.views.publikacja import _resolve_jezyk


def _session(importer_user):
    from importer_publikacji.models import ImportSession

    return ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1007/s00005-017-0485-3",
        raw_data={},
        normalized_data={"title": "x"},
    )


@pytest.mark.django_db
def test_import_angielskiej_pracy_ustawia_jezyk_bez_dosypywania_danych(importer_user):
    """Sedno zgłoszenia: dane referencyjne BPP wystarczają, żeby ``en``
    z CrossRef trafiło na rekord „angielski" — bez ręcznego ustawiania
    ``skrot_crossref`` w Danych systemowych."""
    from bpp.models import Jezyk

    angielski = Jezyk.objects.filter(kod_bcp47="en").order_by("pk").first()
    assert angielski is not None, (
        "dane referencyjne powinny mieć język z kod_bcp47='en'"
    )

    session = _session(importer_user)
    result = FetchedPublication(
        raw_data={},
        title="The PD-1/PD-L1 Inhibitory Pathway is Altered in Primary Glomerulonephritides",
        language="en",
    )

    _auto_match_type_and_language(session, result)

    assert session.jezyk == angielski


@pytest.mark.django_db
def test_resolve_jezyk_dopasowuje_po_kod_bcp47():
    from bpp.models import Jezyk

    jez = Jezyk.objects.create(nazwa="TEST-klingoński", skrot="tlh.", kod_bcp47="tlh")

    assert _resolve_jezyk("tlh") == jez


@pytest.mark.django_db
def test_resolve_jezyk_woli_skrot_crossref_od_kod_bcp47():
    """``skrot_crossref`` to jawna decyzja redakcji — ma pierwszeństwo przed
    kodem BCP 47, gdy oba wskazują na różne rekordy."""
    from bpp.models import Jezyk

    jawny = Jezyk.objects.create(
        nazwa="TEST-jawny", skrot="tj.", skrot_crossref="es", kod_bcp47=""
    )
    Jezyk.objects.filter(kod_bcp47="es").exclude(pk=jawny.pk).update(
        kod_bcp47="es-TESTOWY"
    )
    posredni = Jezyk.objects.create(nazwa="TEST-posredni", skrot="tp.", kod_bcp47="es")

    assert _resolve_jezyk("es") == jawny
    assert _resolve_jezyk("es") != posredni


@pytest.mark.django_db
def test_resolve_jezyk_ignoruje_region_w_kodzie():
    """CrossRef i langdetect potrafią zwrócić kod z regionem (``en-GB``,
    ``zh-cn``); dopasowujemy po podstawowym podtagu, w obie strony."""
    from bpp.models import Jezyk

    jez = Jezyk.objects.create(nazwa="TEST-region", skrot="tr.", kod_bcp47="qaa-QX")

    assert _resolve_jezyk("qaa") == jez
    assert _resolve_jezyk("qaa-QY") == jez


@pytest.mark.django_db
def test_resolve_jezyk_nieznany_kod_zwraca_none():
    assert _resolve_jezyk("qqq") is None
    assert _resolve_jezyk("") is None
    assert _resolve_jezyk(None) is None


@pytest.mark.django_db
def test_krok_weryfikacji_pokazuje_wykryty_jezyk_jako_wybrany(
    importer_user, importer_client
):
    """Domknięcie ścieżki: nie wystarczy ustawić ``session.jezyk`` — krok
    „Weryfikacja" musi wyrenderować ten język jako ``selected`` w liście
    wyboru. Bez tej asercji poprawka mapowania mogłaby być zielona, a pole
    w formularzu i tak zostawałoby puste."""
    from django.urls import reverse

    from bpp.models import Jezyk
    from importer_publikacji.models import ImportSession

    angielski = Jezyk.objects.filter(kod_bcp47="en").order_by("pk").first()
    assert angielski is not None

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1007/s00005-017-0485-3",
        raw_data={},
        normalized_data={"title": "x", "year": 2017},
    )
    result = FetchedPublication(
        raw_data={},
        title="The PD-1/PD-L1 Inhibitory Pathway is Altered in Primary Glomerulonephritides",
        language="en",
    )
    _auto_match_type_and_language(session, result)
    session.save()

    content = importer_client.get(
        reverse("importer_publikacji:verify", args=[session.pk])
    ).content.decode()

    assert f'<option value="{angielski.pk}" selected>' in content, (
        "krok weryfikacji nie zaznaczył wykrytego języka w liście wyboru"
    )
