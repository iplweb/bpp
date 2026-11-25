"""FD#624: książka z BibTeX-a (``@book``) trafiała na ścieżkę czasopisma.

Zgłoszenie: „Typ importowanej pozycji BIBTEX to książka, a każe wskazać
czasopismo a nie wydawnictwo" — krok „Dopasowanie źródła".

Przyczyna: rodzaj rekordu (ciągłe/zwarte) był podpowiadany z typu publikacji
TYLKO wtedy, gdy ten typ miał w „mapowaniu typów CrossRef na BPP" przypisany
charakter formalny. Typ ``book`` bez przypisanego charakteru (stan z
instalacji: ``book -> [brak zamapowania]``, ale „Jest wydawnictwem zwartym"
zaznaczone) zostawiał więc sesję jako wydawnictwo ciągłe: krok „Weryfikacja"
zaznaczał „Wydawnictwo ciągłe (artykuł)", a krok „Dopasowanie źródła" żądał
pola „Źródło (czasopismo)" zamiast wydawcy.

Wpis BibTeX poniżej ma strukturę wpisu ze zgłoszenia (te same pola), dane
są zmyślone.
"""

import pytest
from django.urls import reverse

from bpp.models import Charakter_Formalny, Jezyk, Typ_KBN
from importer_publikacji.models import ImportSession
from importer_publikacji.providers.bibtex import BibTeXProvider
from importer_publikacji.tasks import _auto_match_type_and_language
from importer_publikacji.views.helpers import _get_crossref_mapper
from importer_publikacji.views.steps import _verify_context

BIBTEX_BOOK = """@book{Kowalska2026Modul,
  author    = {Kowalska, Anna},
  title     = {Moduł przykładowy. Podręcznik dla studentów},
  publisher = {Instytut Przykładowy},
  address   = {Warszawa},
  year      = {2026},
  isbn      = {978-83-00000-00-0}
}
"""

BIBTEX_ARTICLE = """@article{Kowalska2026Artykul,
  author  = {Kowalska, Anna},
  title   = {Artykuł przykładowy},
  journal = {Przegląd Przykładowy},
  year    = {2026},
  volume  = {12},
  pages   = {1--10}
}
"""

LABEL_ZRODLO = "Źródło (czasopismo)"
POMOC_WYDAWCA = "Podaj wydawcę lub wpisz szczegóły wydawcy."


def _ustaw_mapper(typ, charakter=None, zwarte=None):
    """Stan mapowania typu jak w panelu administracyjnym."""
    mapper = _get_crossref_mapper(typ)
    mapper.charakter_formalny_bpp = charakter
    if zwarte is not None:
        mapper.jest_wydawnictwem_zwartym = zwarte
    mapper.save()
    return mapper


def _sesja_z_bibtex(importer_user, bibtex):
    """Sesja po kroku pobierania — jak zostawia ją zadanie pobierające."""
    result = BibTeXProvider().fetch(bibtex)
    session = ImportSession(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier=bibtex,
        raw_data=result.raw_data,
        normalized_data={
            "title": result.title,
            "year": result.year,
            "publication_type": result.publication_type,
            "publisher": result.publisher,
            "source_title": result.source_title,
            "isbn": result.isbn,
            "doi": None,
        },
    )
    _auto_match_type_and_language(session, result)
    session.save()
    return session


def _przejdz_weryfikacje(importer_client, session, charakter):
    """GET kroku „Weryfikacja" i POST z rodzajem rekordu, jaki formularz
    zaznaczył domyślnie (operator nie dotyka radia)."""
    url = reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})
    response = importer_client.get(url)
    assert response.status_code == 200
    rodzaj = response.context["form"].initial["rodzaj_rekordu"]
    response = importer_client.post(
        url,
        {
            "rodzaj_rekordu": rodzaj,
            "charakter_formalny": charakter.pk,
            "typ_kbn": Typ_KBN.objects.first().pk,
            "jezyk": Jezyk.objects.filter(widoczny=True).first().pk,
            "rok": "2026",
        },
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status == ImportSession.Status.VERIFIED
    return rodzaj


def _html_kroku_zrodla(importer_client, session):
    url = reverse("importer_publikacji:source", kwargs={"session_id": session.pk})
    response = importer_client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_book_bez_zamapowanego_charakteru_jest_wydawnictwem_zwartym(
    importer_user, charaktery_formalne, jezyki
):
    """Sedno zgłoszenia: ``@book`` + typ ``book`` bez charakteru formalnego
    w mapowaniu → sesja mimo to jest wydawnictwem zwartym."""
    _ustaw_mapper("book", charakter=None, zwarte=True)

    session = _sesja_z_bibtex(importer_user, BIBTEX_BOOK)

    assert session.raw_data["bibtex_type"] == "book"
    assert session.normalized_data["publication_type"] == "book"
    assert session.jest_wydawnictwem_zwartym is True
    # Charakteru nie zgadujemy — wybiera go operator.
    assert session.charakter_formalny is None


@pytest.mark.django_db
def test_book_krok_zrodla_pyta_o_wydawce_nie_o_czasopismo(
    importer_client, importer_user, charaktery_formalne, typy_kbn, jezyki
):
    """Pełna ścieżka operatora: Weryfikacja (bez ruszania radia) →
    Dopasowanie źródła pokazuje wydawcę, a nie „Źródło (czasopismo)"."""
    _ustaw_mapper("book", charakter=None, zwarte=True)
    session = _sesja_z_bibtex(importer_user, BIBTEX_BOOK)

    rodzaj = _przejdz_weryfikacje(
        importer_client, session, Charakter_Formalny.objects.get(skrot="KSP")
    )

    assert rodzaj == ImportSession.RodzajRekordu.ZWARTE
    html = _html_kroku_zrodla(importer_client, session)
    assert POMOC_WYDAWCA in html
    assert LABEL_ZRODLO not in html
    assert "Instytut Przykładowy" in html


@pytest.mark.django_db
def test_stara_sesja_book_weryfikacja_zaznacza_zwarte(
    importer_user, charaktery_formalne, jezyki, rf
):
    """Sesja pobrana PRZED poprawką (flaga zwarte=False, brak charakteru),
    otwarta ponownie w kroku „Weryfikacja": radio i tak wskazuje zwarte."""
    _ustaw_mapper("book", charakter=None, zwarte=True)
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier=BIBTEX_BOOK,
        raw_data={"bibtex_type": "book"},
        normalized_data={"title": "x", "year": 2026, "publication_type": "book"},
        jest_wydawnictwem_zwartym=False,
    )
    request = rf.get("/")
    request.user = importer_user

    ctx = _verify_context(request, session)

    assert ctx["form"].initial["rodzaj_rekordu"] == ImportSession.RodzajRekordu.ZWARTE
    assert "charakter_formalny" not in ctx["form"].initial
    assert ctx["auto_tylko_rodzaj"] is True


# --- Strażnicy: zachowanie, które ma się NIE zmienić ---------------------------


@pytest.mark.django_db
def test_article_nadal_pyta_o_czasopismo(
    importer_client, importer_user, charaktery_formalne, typy_kbn, jezyki
):
    """``@article`` zostaje wydawnictwem ciągłym — krok źródła pyta o
    czasopismo, także gdy typ nie ma zamapowanego charakteru."""
    _ustaw_mapper("journal-article", charakter=None, zwarte=False)
    session = _sesja_z_bibtex(importer_user, BIBTEX_ARTICLE)
    assert session.jest_wydawnictwem_zwartym is False

    rodzaj = _przejdz_weryfikacje(
        importer_client, session, Charakter_Formalny.objects.get(skrot="AC")
    )

    assert rodzaj == ImportSession.RodzajRekordu.CIAGLE
    html = _html_kroku_zrodla(importer_client, session)
    assert LABEL_ZRODLO in html
    assert POMOC_WYDAWCA not in html


@pytest.mark.django_db
def test_zamapowany_charakter_nadal_ustawiany_razem_z_rodzajem(
    importer_user, charaktery_formalne, jezyki
):
    """Typ z przypisanym charakterem: jak dotąd charakter + rodzaj z mapowania."""
    ksiazka = Charakter_Formalny.objects.get(skrot="KSP")
    _ustaw_mapper("book", charakter=ksiazka, zwarte=True)

    session = _sesja_z_bibtex(importer_user, BIBTEX_BOOK)

    assert session.charakter_formalny == ksiazka
    assert session.jest_wydawnictwem_zwartym is True


@pytest.mark.django_db
def test_ustawienie_administratora_w_mapowaniu_ma_pierwszenstwo(
    importer_user, charaktery_formalne, jezyki
):
    """„Jest wydawnictwem zwartym" odznaczone przez administratora dla typu
    ``book`` jest respektowane — rodzaju nie wymuszamy po nazwie typu."""
    _ustaw_mapper("book", charakter=None, zwarte=False)

    session = _sesja_z_bibtex(importer_user, BIBTEX_BOOK)

    assert session.jest_wydawnictwem_zwartym is False


@pytest.mark.django_db
def test_wybor_operatora_w_weryfikacji_nie_jest_nadpisywany(
    importer_user, charaktery_formalne, jezyki, rf
):
    """Operator już zatwierdził „Weryfikację" jako wydawnictwo ciągłe —
    powrót do kroku pokazuje jego wybór, nie podpowiedź z typu."""
    _ustaw_mapper("book", charakter=None, zwarte=True)
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier=BIBTEX_BOOK,
        raw_data={"bibtex_type": "book"},
        normalized_data={"title": "x", "year": 2026, "publication_type": "book"},
        charakter_formalny=Charakter_Formalny.objects.get(skrot="AC"),
        jest_wydawnictwem_zwartym=False,
    )
    request = rf.get("/")
    request.user = importer_user

    ctx = _verify_context(request, session)

    assert ctx["form"].initial["rodzaj_rekordu"] == ImportSession.RodzajRekordu.CIAGLE
