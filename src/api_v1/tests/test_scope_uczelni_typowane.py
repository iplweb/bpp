"""Typowane viewsety publikacji muszą zawężać wynik do uczelni z ``Host`` (#808).

``/api/v1/szukaj/``, ``/api/v1/zapytanie/rekord/`` i endpointy „recent"
stosują ``api_v1.scoping.scope_rekord_api``; typowane viewsety
(``wydawnictwo_ciagle``, ``wydawnictwo_zwarte``, ``patent``,
``praca_doktorska``, ``praca_habilitacyjna``) i ich pod-zasoby oddawały
w instalacji wielouczelnianej rekordy wszystkich uczelni. Polityka
widoczności nie może zależeć od wyboru endpointu.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka, Rekord, Uczelnia, Wydawnictwo_Ciagle
from fixtures.conftest_publications import _wydawnictwo_ciagle_maker


@pytest.fixture
def jednostka_b(uczelnia):
    """Jednostka drugiej uczelni (B, osobny Site). ``uczelnia`` (A) jest
    zmapowana na Site ``testserver`` — tam idą requesty klienta testowego."""
    site_b = Site.objects.create(domain="uczelnia-b.example.com", name="B")
    uczelnia_b = Uczelnia.objects.create(nazwa="Uczelnia B", skrot="BB", site=site_b)
    parent_b = Jednostka.objects.create(
        uczelnia=uczelnia_b, nazwa="WB", skrot="WB", parent=None
    )
    return Jednostka.objects.create(
        nazwa="Jedn. B", skrot="JB", parent=parent_b, uczelnia=uczelnia_b
    )


@pytest.fixture
def pary_publikacji(
    uczelnia,
    jednostka,
    jednostka_b,
    autor_jan_kowalski,
    autor_jan_nowak,
    wydawnictwo_ciagle,
    zwarte_maker,
    patent_maker,
    doktorat_maker,
    habilitacja_maker,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Dla każdego typu: (publikacja uczelni A, publikacja uczelni B)."""
    ciagle_b = _wydawnictwo_ciagle_maker()
    pary = {
        "wydawnictwo_ciagle": (wydawnictwo_ciagle, ciagle_b),
        "wydawnictwo_zwarte": (zwarte_maker(), zwarte_maker()),
        "patent": (patent_maker(), patent_maker()),
    }
    for publikacja_a, publikacja_b in pary.values():
        publikacja_a.dodaj_autora(autor_jan_kowalski, jednostka)
        publikacja_b.dodaj_autora(autor_jan_nowak, jednostka_b)

    pary["praca_doktorska"] = (
        doktorat_maker(autor=autor_jan_kowalski, jednostka=jednostka),
        doktorat_maker(autor=autor_jan_nowak, jednostka=jednostka_b),
    )
    pary["praca_habilitacyjna"] = (
        habilitacja_maker(autor=baker.make(Autor), jednostka=jednostka),
        habilitacja_maker(autor=baker.make(Autor), jednostka=jednostka_b),
    )
    return pary


def _ids_listy(api_client, basename):
    res = api_client.get(reverse(f"api_v1:{basename}-list"), {"page_size": 100})
    assert res.status_code == 200
    return {pozycja["id"] for pozycja in res.json()["results"]}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "basename",
    [
        "wydawnictwo_ciagle",
        "wydawnictwo_zwarte",
        "patent",
        "praca_doktorska",
        "praca_habilitacyjna",
    ],
)
def test_typowany_viewset_zawezony_do_uczelni(api_client, pary_publikacji, basename):
    publikacja_a, publikacja_b = pary_publikacji[basename]

    ids = _ids_listy(api_client, basename)
    assert publikacja_a.pk in ids
    assert publikacja_b.pk not in ids

    detal_b = reverse(f"api_v1:{basename}-detail", args=(publikacja_b.pk,))
    assert api_client.get(detal_b).status_code == 404
    detal_a = reverse(f"api_v1:{basename}-detail", args=(publikacja_a.pk,))
    assert api_client.get(detal_a).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "basename,typ",
    [
        ("wydawnictwo_ciagle_autor", "wydawnictwo_ciagle"),
        ("wydawnictwo_zwarte_autor", "wydawnictwo_zwarte"),
        ("patent_autor", "patent"),
    ],
)
def test_autorstwa_zawezone_do_uczelni(api_client, pary_publikacji, basename, typ):
    publikacja_a, publikacja_b = pary_publikacji[typ]
    autorstwo_a = publikacja_a.autorzy_set.get()
    autorstwo_b = publikacja_b.autorzy_set.get()

    ids = _ids_listy(api_client, basename)
    assert autorstwo_a.pk in ids
    assert autorstwo_b.pk not in ids

    detal_b = reverse(f"api_v1:{basename}-detail", args=(autorstwo_b.pk,))
    assert api_client.get(detal_b).status_code == 404


@pytest.mark.django_db
def test_autorstwo_innej_uczelni_na_wspolnej_publikacji_widoczne(
    api_client, pary_publikacji, jednostka_b, autor_jan_nowak
):
    """Pod-zasób dziedziczy widoczność rekordu nadrzędnego: publikacja
    współautorska A+B jest widoczna w A w całości, z autorstwem z B włącznie
    (tak jak oddaje ją detal publikacji)."""
    publikacja_a, _ = pary_publikacji["wydawnictwo_ciagle"]
    autorstwo_b = publikacja_a.dodaj_autora(autor_jan_nowak, jednostka_b)

    assert autorstwo_b.pk in _ids_listy(api_client, "wydawnictwo_ciagle_autor")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "basename,typ",
    [
        ("wydawnictwo_ciagle_streszczenie", "wydawnictwo_ciagle"),
        ("wydawnictwo_zwarte_streszczenie", "wydawnictwo_zwarte"),
    ],
)
def test_streszczenia_zawezone_do_uczelni(
    api_client, pary_publikacji, jezyki, basename, typ
):
    _, publikacja_b = pary_publikacji[typ]
    streszczenie_b = publikacja_b.streszczenia.create(
        jezyk_streszczenia=jezyki["pol."], streszczenie="Streszczenie B"
    )

    detal_b = reverse(f"api_v1:{basename}-detail", args=(streszczenie_b.pk,))
    assert api_client.get(detal_b).status_code == 404


@pytest.mark.django_db
def test_typowany_viewset_zgodny_z_szukaj(api_client, pary_publikacji):
    """Ten sam host → ten sam zbiór rekordów w ``/szukaj/`` i w typowanym
    viewsecie (jedna polityka widoczności, niezależnie od endpointu)."""
    token = "kwakwahita808"
    publikacje = pary_publikacji["wydawnictwo_ciagle"]
    for publikacja in publikacje:
        publikacja.tytul_oryginalny = f"{token} {publikacja.pk}"
        publikacja.save()
    Rekord.objects.full_refresh()

    res = api_client.get(reverse("api_v1:szukaj-list"), {"q": token})
    assert res.status_code == 200
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    w_szukaj = {pozycja["id"] for pozycja in res.json()["results"]}

    pk_testowe = {publikacja.pk for publikacja in publikacje}
    w_typowanym = _ids_listy(api_client, "wydawnictwo_ciagle") & pk_testowe
    assert w_szukaj == {f"{ct.pk}-{pk}" for pk in w_typowanym}
    assert len(w_szukaj) == 1


@pytest.mark.django_db
def test_jedna_uczelnia_bez_zawezania(
    api_client, uczelnia, wydawnictwo_ciagle, zwarte_maker
):
    """Instalacja jednouczelniana: zawężenie to no-op — publikacja bez
    autorstw (nieprzypisana do żadnej uczelni) dalej jest w API."""
    assert wydawnictwo_ciagle.pk in _ids_listy(api_client, "wydawnictwo_ciagle")
