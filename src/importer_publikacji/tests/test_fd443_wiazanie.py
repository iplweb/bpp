"""FD#443 — wiązanie sesji importu ze zgłoszeniem publikacji.

Pokrywa trzy ścieżki wiązania ze specu
``docs/superpowers/specs/2026-07-22-zgloszenie-zaimportowane-przez-\
importer-design.md``:

* **A** — jawna, z przycisku „Użyj importera" (``?zgloszenie=<pk>``
  przeżywa rundę GET → render → POST),
* **B** — automatyczna po DOI, gdy kandydat jest dokładnie jeden,
* **C** — wybór operatora, gdy kandydatów jest ≥2 (plus regresja IDOR).

Plus reguły doboru kandydatów (``kandydaci_dla_sesji``) i wpływ wiązania
na prefill dyscyplin.
"""

from unittest.mock import patch

import pytest
from django.contrib.sites.models import Site
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import ImportedAuthor, ImportSession
from importer_publikacji.views.authors import (
    _prefill_dyscypliny_z_zgloszen,
    _zgloszenie_dla_prefilla,
)
from importer_publikacji.zgloszenia import kandydaci_dla_sesji, zwiaz_automatycznie

DOI = "10.1234/fd443.test"
INNE_DOI = "10.9999/fd443.inne"
TYTUL = "Wpływ czegoś na coś innego w badaniach modelowych"


# --------------------------------------------------------------------------
# Pomocnicze
# --------------------------------------------------------------------------


def _zgl(doi=DOI, tytul=TYTUL, status=0, **kwargs):
    """Zgłoszenie publikacji (domyślnie NOWY, z DOI sesji testowej)."""
    return baker.make(
        "zglos_publikacje.Zgloszenie_Publikacji",
        doi=doi,
        tytul_oryginalny=tytul,
        status=status,
        rok=2024,
        rodzaj_zglaszanej_publikacji=1,
        **kwargs,
    )


def _zpa(zgloszenie, jednostka=None, autor=None, dyscyplina=None):
    """Autor w zgłoszeniu — nośnik atrybucji zgłoszenia do uczelni (D8)."""
    return baker.make(
        "zglos_publikacje.Zgloszenie_Publikacji_Autor",
        rekord=zgloszenie,
        autor=autor or baker.make("bpp.Autor"),
        jednostka=jednostka or baker.make("bpp.Jednostka"),
        dyscyplina_naukowa=dyscyplina,
        rok=2024,
    )


def _sesja(user, doi=DOI, tytul=TYTUL, uczelnia=None, **kwargs):
    return ImportSession.objects.create(
        created_by=user,
        uczelnia=uczelnia,
        provider_name="CrossRef",
        identifier=doi or "brak-doi",
        raw_data={},
        normalized_data={
            "title": tytul,
            "doi": doi,
            "year": 2024,
            "authors": [],
        },
        **kwargs,
    )


def _url_wyboru(session):
    return reverse(
        "importer_publikacji:zgloszenie-wybierz",
        kwargs={"session_id": session.pk},
    )


@pytest.fixture
def uczelnia_b(db):
    """Druga uczelnia — włącza zawężanie (``tylko_jedna_uczelnia`` → False)."""
    from bpp.models import Uczelnia

    site = Site.objects.create(domain="uczelnia-b.example.com", name="B")
    return Uczelnia.objects.create(nazwa="Uczelnia B", skrot="BB", site=site)


# --------------------------------------------------------------------------
# kandydaci_dla_sesji
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_kandydaci_brak_doi_pusty_queryset(importer_user):
    """Bez DOI nie ma czym wiązać — pusty queryset, nie None."""
    session = _sesja(importer_user, doi=None)
    _zgl(doi=None)

    assert list(kandydaci_dla_sesji(session)) == []


@pytest.mark.django_db
def test_kandydaci_jedno_pasujace_zgloszenie(importer_user):
    session = _sesja(importer_user)
    zgl = _zgl()

    assert list(kandydaci_dla_sesji(session)) == [zgl]


@pytest.mark.django_db
def test_kandydaci_dwa_zgloszenia_tego_samego_doi(importer_user):
    session = _sesja(importer_user)
    a = _zgl()
    b = _zgl(tytul="Zupełnie inny tytuł, to samo DOI")

    assert set(kandydaci_dla_sesji(session)) == {a, b}


@pytest.mark.django_db
def test_kandydaci_doi_znormalizowane(importer_user):
    """DOI z sesji jest normalizowane (URL, wielkość liter) przed matchem."""
    session = _sesja(importer_user, doi=f"https://doi.org/{DOI.upper()}")
    zgl = _zgl()

    assert list(kandydaci_dla_sesji(session)) == [zgl]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,nazwa",
    [
        (4, "ODRZUCONO"),
        (5, "SPAM"),
        (6, "ZAIMPORTOWANY"),
        (1, "ZAAKCEPTOWANY"),
        (2, "WYMAGA_ZMIAN"),
    ],
)
def test_kandydaci_wykluczone_statusy(importer_user, status, nazwa):
    session = _sesja(importer_user)
    _zgl(status=status)

    assert list(kandydaci_dla_sesji(session)) == [], nazwa


@pytest.mark.django_db
@pytest.mark.parametrize("status,nazwa", [(0, "NOWY"), (3, "PO_ZMIANACH")])
def test_kandydaci_dopuszczone_statusy(importer_user, status, nazwa):
    """Kontrola pozytywna do testu wykluczeń — te statusy przechodzą."""
    session = _sesja(importer_user)
    zgl = _zgl(status=status)

    assert list(kandydaci_dla_sesji(session)) == [zgl], nazwa


@pytest.mark.django_db
def test_kandydaci_pomijaja_soft_usuniete(importer_user):
    """``objects`` to SoftDeleteManager — skasowane zgłoszenie wypada."""
    session = _sesja(importer_user)
    zgl = _zgl()
    zgl.delete()

    assert list(kandydaci_dla_sesji(session)) == []


@pytest.mark.django_db
def test_kandydaci_nie_wiaza_po_tytule(importer_user):
    """D5: identyczny tytuł, inne DOI → NIE jest kandydatem.

    Regresja: dopasowanie po tytule jest wykluczone z wiązania, bo dwa
    zgłoszenia o tym samym tytule oznaczyłyby przypadkowe.
    """
    session = _sesja(importer_user)
    pasujace_doi = _zgl(doi=DOI, tytul=TYTUL)
    _zgl(doi=INNE_DOI, tytul=TYTUL)

    assert list(kandydaci_dla_sesji(session)) == [pasujace_doi]


@pytest.mark.django_db
def test_kandydaci_nie_przekraczaja_granicy_uczelni(
    importer_user, uczelnia1, uczelnia2, jednostka_uczelnia1, jednostka_uczelnia2
):
    """D8: zgłoszenie autora z cudzej uczelni nie trafia na listę."""
    session = _sesja(importer_user, uczelnia=uczelnia1)

    moje = _zgl()
    _zpa(moje, jednostka=jednostka_uczelnia1)

    cudze = _zgl(tytul="Praca z drugiej uczelni")
    _zpa(cudze, jednostka=jednostka_uczelnia2)

    kandydaci = list(kandydaci_dla_sesji(session))
    assert kandydaci == [moje]
    assert cudze not in kandydaci


@pytest.mark.django_db
def test_kandydaci_bez_uczelni_sesji_bez_zawezenia(
    importer_user, uczelnia1, uczelnia2, jednostka_uczelnia2
):
    """Sesja bez uczelni (brak mapowania Site→Uczelnia) → filtr no-op."""
    session = _sesja(importer_user, uczelnia=None)
    cudze = _zgl()
    _zpa(cudze, jednostka=jednostka_uczelnia2)

    assert list(kandydaci_dla_sesji(session)) == [cudze]


@pytest.mark.django_db
def test_kandydaci_jedna_uczelnia_bez_zawezenia(importer_user, uczelnia, jednostka):
    """Single-install: filtr per-uczelnia jest no-opem (i kosztowałby JOIN)."""
    session = _sesja(importer_user, uczelnia=uczelnia)
    zgl = _zgl()
    # Zgłoszenie BEZ żadnego autora — przy aktywnym zawężeniu wypadłoby
    # (JOIN po autorach), w single-install ma pozostać widoczne.
    assert list(kandydaci_dla_sesji(session)) == [zgl]


@pytest.mark.django_db
def test_kandydaci_bez_duplikatow_przy_wielu_autorach(
    importer_user, uczelnia1, uczelnia2, jednostka_uczelnia1
):
    """JOIN przez autorów mnoży wiersze — ``.distinct()` musi to sklejać."""
    session = _sesja(importer_user, uczelnia=uczelnia1)
    zgl = _zgl()
    for _ in range(3):
        _zpa(zgl, jednostka=jednostka_uczelnia1)

    assert kandydaci_dla_sesji(session).count() == 1
    assert list(kandydaci_dla_sesji(session)) == [zgl]


# --------------------------------------------------------------------------
# zwiaz_automatycznie (ścieżka B)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_zwiaz_automatycznie_jeden_kandydat(importer_user):
    session = _sesja(importer_user)
    zgl = _zgl()

    assert zwiaz_automatycznie(session) is True

    session.refresh_from_db()
    assert session.zgloszenie_id == zgl.pk


@pytest.mark.django_db
def test_zwiaz_automatycznie_dwaj_kandydaci_nie_zgaduje(importer_user):
    """D6: przy ≥2 kandydatach decyduje operator, nie system."""
    session = _sesja(importer_user)
    _zgl()
    _zgl(tytul="Drugi kandydat na to samo DOI")

    assert zwiaz_automatycznie(session) is False

    session.refresh_from_db()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_zwiaz_automatycznie_zero_kandydatow(importer_user):
    session = _sesja(importer_user)

    assert zwiaz_automatycznie(session) is False

    session.refresh_from_db()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_zwiaz_automatycznie_nie_nadpisuje_istniejacego(importer_user):
    """Jawny wybór (ścieżka A) jest mocniejszy od heurystyki po DOI."""
    jawne = _zgl(doi=INNE_DOI, tytul="Jawnie wskazane zgłoszenie")
    session = _sesja(importer_user, zgloszenie=jawne)
    _zgl()  # jedyny kandydat po DOI — a jednak nie wygrywa

    assert zwiaz_automatycznie(session) is False

    session.refresh_from_db()
    assert session.zgloszenie_id == jawne.pk


@pytest.mark.django_db
def test_kandydaci_zgloszen_wyciszone_po_odrzuceniu(importer_user):
    """``ImportSession.kandydaci_zgloszen`` milknie po „żadne z nich"."""
    session = _sesja(importer_user, zgloszenie_odrzucone_przez_operatora=True)
    _zgl()

    assert list(session.kandydaci_zgloszen) == []


# --------------------------------------------------------------------------
# Wybór operatora (ścieżka C) — widok ZgloszenieWyborView
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_wybor_ustawia_fk(importer_client, importer_user):
    session = _sesja(importer_user)
    a = _zgl()
    _zgl(tytul="Drugi kandydat")

    response = importer_client.post(_url_wyboru(session), {"zgloszenie": a.pk})

    assert response.status_code == 302
    session.refresh_from_db()
    assert session.zgloszenie_id == a.pk
    assert session.zgloszenie_odrzucone_przez_operatora is False


@pytest.mark.django_db
def test_wybor_spoza_listy_kandydatow_odrzucony(importer_client, importer_user):
    """Regresja IDOR: id spoza listy kandydatów NIE może związać sesji."""
    session = _sesja(importer_user)
    _zgl()
    obce = _zgl(doi=INNE_DOI, tytul="Cudze zgłoszenie, inne DOI")

    response = importer_client.post(_url_wyboru(session), {"zgloszenie": obce.pk})

    assert response.status_code == 400
    session.refresh_from_db()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_wybor_zgloszenia_o_wykluczonym_statusie_odrzucony(
    importer_client, importer_user
):
    """Status wykluczony ⇒ poza listą kandydatów ⇒ nie da się go wybrać."""
    session = _sesja(importer_user)
    spam = _zgl(status=5)

    response = importer_client.post(_url_wyboru(session), {"zgloszenie": spam.pk})

    assert response.status_code == 400
    session.refresh_from_db()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_wybor_smiec_zamiast_id_odrzucony(importer_client, importer_user):
    session = _sesja(importer_user)
    _zgl()

    response = importer_client.post(_url_wyboru(session), {"zgloszenie": "abc"})

    assert response.status_code == 400
    session.refresh_from_db()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_wybor_bez_uprawnien_importera(client, django_user_model, importer_user):
    """Zalogowany bez GR_WPROWADZANIE_DANYCH → 403 (anonim → redirect)."""
    session = _sesja(importer_user)
    zgl = _zgl()

    obcy = baker.make(django_user_model, is_staff=True, is_superuser=False)
    client.force_login(obcy)

    response = client.post(_url_wyboru(session), {"zgloszenie": zgl.pk})

    assert response.status_code == 403
    session.refresh_from_db()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_wybor_anonim_przekierowany(client, importer_user):
    session = _sesja(importer_user)
    zgl = _zgl()

    response = client.post(_url_wyboru(session), {"zgloszenie": zgl.pk})

    assert response.status_code in (302, 403)
    session.refresh_from_db()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_wybor_na_sesje_innej_uczelni_404(
    importer_client, importer_user, uczelnia, uczelnia_b
):
    """Sesja spoza uczelni redaktora nie istnieje dla niego (404)."""
    session = _sesja(importer_user, uczelnia=uczelnia_b)
    zgl = _zgl()

    response = importer_client.post(_url_wyboru(session), {"zgloszenie": zgl.pk})

    assert response.status_code == 404
    session.refresh_from_db()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_wybor_zadne_wycisza_baner(importer_client, importer_user):
    session = _sesja(importer_user)
    _zgl()
    _zgl(tytul="Drugi kandydat")

    response = importer_client.post(_url_wyboru(session), {"zadne": "1"})

    assert response.status_code == 302
    session.refresh_from_db()
    assert session.zgloszenie_odrzucone_przez_operatora is True
    assert session.zgloszenie_id is None
    assert list(session.kandydaci_zgloszen) == []


@pytest.mark.django_db
def test_wybor_odepnij_kasuje_automatyczne_wiazanie(importer_client, importer_user):
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    response = importer_client.post(_url_wyboru(session), {"odepnij": "1"})

    assert response.status_code == 302
    session.refresh_from_db()
    assert session.zgloszenie_id is None
    assert session.zgloszenie_odrzucone_przez_operatora is True


@pytest.mark.django_db
def test_wybor_hx_request_zwraca_hx_redirect(importer_client, importer_user):
    session = _sesja(importer_user)
    zgl = _zgl()

    response = importer_client.post(
        _url_wyboru(session),
        {"zgloszenie": zgl.pk},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert response["HX-Redirect"]


# --------------------------------------------------------------------------
# Ścieżka A — parametr ?zgloszenie= przeżywa rundę GET → render → POST
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_index_renderuje_ukryte_pole_zgloszenia(importer_client):
    zgl = _zgl()
    url = reverse("importer_publikacji:index")

    response = importer_client.get(f"{url}?provider=CrossRef&zgloszenie={zgl.pk}")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'name="zgloszenie"' in content
    assert f'value="{zgl.pk}"' in content


@pytest.mark.django_db
def test_index_bez_parametru_nie_wypelnia_pola(importer_client):
    url = reverse("importer_publikacji:index")

    response = importer_client.get(f"{url}?provider=CrossRef")

    content = response.content.decode()
    assert 'name="zgloszenie"' in content
    # Puste ukryte pole nie renderuje atrybutu ``value``.
    assert 'name="zgloszenie" value=' not in content.replace("\n", " ")


def _post_fetch(client, **extra):
    """POST na FetchView z zamockowanym providerem i taskiem Celery."""
    dane = {"provider": "CrossRef", "identifier": "10.1234/x"}
    dane.update(extra)

    with (
        patch("importer_publikacji.views.wizard.fetch_session_task") as mock_task,
        patch("importer_publikacji.views.wizard.get_provider") as mock_provider,
    ):
        from importer_publikacji.providers import InputMode

        mock_provider.return_value.input_mode = InputMode.IDENTIFIER
        mock_provider.return_value.validate_identifier.return_value = "10.1234/x"
        mock_task.delay.return_value.id = "task-uuid"

        return client.post(reverse("importer_publikacji:fetch"), dane)


@pytest.mark.django_db
def test_fetch_wiaze_sesje_ze_zgloszeniem(importer_client):
    zgl = _zgl()

    response = _post_fetch(importer_client, zgloszenie=zgl.pk)

    assert response.status_code == 302
    session = ImportSession.objects.get()
    assert session.zgloszenie_id == zgl.pk


@pytest.mark.django_db
@pytest.mark.parametrize("wartosc", ["abc", "0", "-5", "999999999999999999999"])
def test_fetch_niepoprawna_wartosc_bez_bledu_i_bez_wiazania(importer_client, wartosc):
    """Śmieć w ukrytym polu nie może zablokować importu ani go związać."""
    response = _post_fetch(importer_client, zgloszenie=wartosc)

    assert response.status_code == 302
    session = ImportSession.objects.get()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_fetch_nieistniejacy_pk_bez_wiazania(importer_client):
    response = _post_fetch(importer_client, zgloszenie=123456)

    assert response.status_code == 302
    session = ImportSession.objects.get()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_fetch_soft_usuniety_pk_bez_wiazania(importer_client):
    zgl = _zgl()
    zgl.delete()

    response = _post_fetch(importer_client, zgloszenie=zgl.pk)

    assert response.status_code == 302
    session = ImportSession.objects.get()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_fetch_idempotency_dopisuje_wiazanie_do_sesji_in_flight(
    importer_client, importer_user
):
    """Gałąź double-click omija ``_start_import_session`` — FK dopisujemy."""
    istniejaca = baker.make(
        ImportSession,
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/x",
        status=ImportSession.Status.FETCHING,
        zgloszenie=None,
    )
    zgl = _zgl()

    response = _post_fetch(importer_client, zgloszenie=zgl.pk)

    assert response.status_code == 302
    assert ImportSession.objects.count() == 1
    istniejaca.refresh_from_db()
    assert istniejaca.zgloszenie_id == zgl.pk


@pytest.mark.django_db
def test_fetch_idempotency_nie_nadpisuje_istniejacego_wiazania(
    importer_client, importer_user
):
    """Pierwsze wiązanie wygrywa — re-submit nie przestemplowuje sesji."""
    pierwsze = _zgl(tytul="Pierwsze wiązanie")
    drugie = _zgl(doi=INNE_DOI, tytul="Drugie wiązanie")
    istniejaca = baker.make(
        ImportSession,
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/x",
        status=ImportSession.Status.FETCHING,
        zgloszenie=pierwsze,
    )

    _post_fetch(importer_client, zgloszenie=drugie.pk)

    istniejaca.refresh_from_db()
    assert istniejaca.zgloszenie_id == pierwsze.pk


# --------------------------------------------------------------------------
# Prefill dyscyplin korzysta z jawnego wiązania
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_prefill_uzywa_zwiazanego_zgloszenia(importer_user):
    """Wiązanie bije heurystykę: dyscyplina z ``session.zgloszenie``."""
    from bpp.models import Autor_Dyscyplina

    autor = baker.make("bpp.Autor")
    dysc_zwiazana = baker.make("bpp.Dyscyplina_Naukowa")
    dysc_heurystyczna = baker.make("bpp.Dyscyplina_Naukowa")

    # ``Zgloszenie_Publikacji_Autor.clean()`` wymaga przypisania autora do
    # dyscypliny na dany rok — obie muszą być legalne dla tego autora.
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2024,
        dyscyplina_naukowa=dysc_zwiazana,
        subdyscyplina_naukowa=dysc_heurystyczna,
    )

    # Zgłoszenie związane — inne DOI i inny tytuł niż sesja, więc
    # heurystyka nigdy by go nie wybrała.
    zwiazane = _zgl(doi=INNE_DOI, tytul="Zupełnie inny tytuł niż w sesji")
    _zpa(zwiazane, autor=autor, dyscyplina=dysc_zwiazana)

    # Zgłoszenie, które wygrałoby heurystycznie (to samo DOI co sesja).
    heurystyczne = _zgl()
    _zpa(heurystyczne, autor=autor, dyscyplina=dysc_heurystyczna)

    session = _sesja(importer_user, zgloszenie=zwiazane)
    imported = ImportedAuthor.objects.create(
        session=session,
        order=0,
        family_name="Test",
        given_name="Autor",
        matched_autor=autor,
        match_status=ImportedAuthor.MatchStatus.AUTO_EXACT,
    )

    assert _zgloszenie_dla_prefilla(session).pk == zwiazane.pk

    _prefill_dyscypliny_z_zgloszen(session)

    imported.refresh_from_db()
    assert imported.matched_dyscyplina == dysc_zwiazana


@pytest.mark.django_db
def test_prefill_bez_wiazania_uzywa_heurystyki(importer_user):
    """Sesje niezwiązane zachowują się jak dotąd (fallback po DOI/tytule)."""
    session = _sesja(importer_user)
    heurystyczne = _zgl()

    assert _zgloszenie_dla_prefilla(session).pk == heurystyczne.pk
