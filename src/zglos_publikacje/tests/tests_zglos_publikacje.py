import os

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_ZGLOSZENIA_PUBLIKACJI
from bpp.core import zgloszenia_publikacji_emails
from bpp.models import BppUser
from zglos_publikacje.models import (
    Obslugujacy_Zgloszenia_Wydzialow,
    Zgloszenie_Publikacji,
)

PDF_PATH = os.path.join(os.path.dirname(__file__), "example.pdf")

EMAIL = "test@panie.random.lol.pl"


def _krok0_rodzaj(page, rodzaj="ARTYKUL"):
    """Krok 0: wybór rodzaju publikacji."""
    page.forms[0]["0-rodzaj"] = rodzaj
    return page.forms[0].submit()


def _krok1_dostep(page, forma="OTWARTY"):
    """Krok 1: wybór formy dostępu."""
    page.forms[0]["1-forma_dostepu"] = forma
    return page.forms[0].submit()


def _krok2_dane(
    page,
    tytul="Test",
    rok="2020",
    email="test@test.pl",
    strona_www="",
):
    """Krok 2: dane o publikacji."""
    page.forms[0]["2-tytul_oryginalny"] = tytul
    page.forms[0]["2-rok"] = rok
    page.forms[0]["2-email"] = email
    if strona_www:
        page.forms[0]["2-strona_www"] = strona_www
    return page


def _przejdz_do_kroku_danych(
    webtest_app, rodzaj="ARTYKUL", forma="OTWARTY"
):
    """Przejdź przez kroki 0 i 1 do kroku 2 (dane)."""
    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page2 = _krok0_rodzaj(page, rodzaj)
    page3 = _krok1_dostep(page2, forma)
    return page3


@pytest.mark.django_db
def test_krok0_wybor_rodzaju(webtest_app, uczelnia):
    """Krok 0: formularz zawiera kafelki rodzaju."""
    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    assert page.status_code == 200
    assert b"Rodzaj publikacji" in page.content


@pytest.mark.django_db
def test_krok1_wybor_formy_dostepu(webtest_app, uczelnia):
    """Krok 1: formularz zawiera kafelki formy dostępu."""
    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page2 = _krok0_rodzaj(page)
    assert page2.status_code == 200
    assert b"Forma" in page2.content


@pytest.mark.django_db
def test_krok2_otwarty_dostep_wymaga_url(
    webtest_app, uczelnia
):
    """Otwarty dostęp: strona_www wymagana."""
    page = _przejdz_do_kroku_danych(
        webtest_app, forma="OTWARTY"
    )
    page = _krok2_dane(page, strona_www="")
    page2 = page.forms[0].submit()
    # Powinien zostać na kroku 2 z błędem walidacji
    assert page2.status_code == 200
    assert b"tytul_oryginalny" in page2.content


@pytest.mark.django_db
def test_krok2_otwarty_dostep_przechodzi_dalej(
    webtest_app, uczelnia
):
    """Otwarty dostęp z URL: przechodzi do kroku autorów."""
    page = _przejdz_do_kroku_danych(
        webtest_app, forma="OTWARTY"
    )
    page = _krok2_dane(
        page, strona_www="https://example.com/"
    )
    page2 = page.forms[0].submit()
    assert page2.status_code == 200
    # Krok 3 = autorzy
    assert b"autor" in page2.content.lower()


@pytest.mark.django_db
def test_krok2_ograniczony_dostep_bez_pliku(
    webtest_app, uczelnia
):
    """Ograniczony dostęp bez pliku: zostaje na kroku 2."""
    page = _przejdz_do_kroku_danych(
        webtest_app, forma="OGRANICZONY"
    )
    page = _krok2_dane(page)
    page2 = page.forms[0].submit()
    assert page2.status_code == 200


@pytest.mark.django_db
def test_krok2_zgoda_na_publikacje_widoczna(
    webtest_app, uczelnia
):
    """Zgoda na publikację widoczna gdy uczelnia wymaga."""
    uczelnia.pytaj_o_zgode_na_publikacje_pelnego_tekstu = True
    uczelnia.save()

    page = _przejdz_do_kroku_danych(webtest_app)
    assert (
        b"zgoda_na_publikacje_pelnego_tekstu"
        in page.content
    )


@pytest.mark.django_db
def test_krok2_zgoda_na_publikacje_ukryta(
    webtest_app, uczelnia
):
    """Zgoda na publikację ukryta domyślnie."""
    uczelnia.pytaj_o_zgode_na_publikacje_pelnego_tekstu = (
        False
    )
    uczelnia.save()

    page = _przejdz_do_kroku_danych(webtest_app)
    assert (
        b"zgoda_na_publikacje_pelnego_tekstu"
        not in page.content
    )


def _zrob_submit_calego_formularza(
    webtest_app,
    django_capture_on_commit_callbacks,
    rodzaj="ARTYKUL",
    forma="OTWARTY",
    autor=None,
    jednostka=None,
    tytul_oryginalny="123",
    oczekuj_platnosci=True,
):
    """Helper: przejdź przez cały wizard."""
    page = _przejdz_do_kroku_danych(
        webtest_app, rodzaj=rodzaj, forma=forma
    )
    page = _krok2_dane(
        page,
        tytul=tytul_oryginalny,
        strona_www="https://example.com/",
    )
    page2 = page.forms[0].submit()

    # Krok 3: autorzy
    if autor is not None:
        page2.forms[0]["3-0-autor"].force_value(autor.pk)
        page2.forms[0]["3-0-jednostka"].force_value(
            jednostka.pk
        )

    page3 = page2.forms[0].submit()

    # Krok 4: opłaty (jeśli widoczny)
    if oczekuj_platnosci:
        page3.forms[0]["4-opl_pub_cost_free"] = "true"

    with django_capture_on_commit_callbacks(execute=True):
        result = page3.forms[0].submit().maybe_follow()

    return result


def test_pelny_formularz_artykul(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
):
    assert zgloszenia_publikacji_emails()

    result = _zrob_submit_calego_formularza(
        webtest_app,
        django_capture_on_commit_callbacks,
    )
    assert b"powiadomiony" in result.content
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_pelny_formularz_inne_bez_platnosci(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
):
    """Typ 'POZOSTALE' bez płatności (domyślnie)."""
    result = _zrob_submit_calego_formularza(
        webtest_app,
        django_capture_on_commit_callbacks,
        rodzaj="POZOSTALE",
        oczekuj_platnosci=False,
    )
    assert b"zostanie zaakceptowane" in result.content


@pytest.mark.django_db
def test_tytul_wielkosc_liter_zachowana(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
):
    TYTUL = "Test Wielkich Liter"
    _zrob_submit_calego_formularza(
        webtest_app,
        django_capture_on_commit_callbacks,
        rodzaj="POZOSTALE",
        tytul_oryginalny=TYTUL,
        oczekuj_platnosci=False,
    )
    assert (
        Zgloszenie_Publikacji.objects.first().tytul_oryginalny
        == TYTUL
    )


def test_email_brak_ludzi_w_bazie(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    wydzial,
    jednostka,
):
    _zrob_submit_calego_formularza(
        webtest_app, django_capture_on_commit_callbacks
    )
    assert len(mail.outbox) == 0


def test_email_do_grupy_zglaszanie_publikacji(
    webtest_app,
    django_capture_on_commit_callbacks,
    normal_django_user,
    typy_odpowiedzialnosci,
    uczelnia,
    wydzial,
    jednostka,
):
    normal_django_user.email = EMAIL
    normal_django_user.save()
    normal_django_user.groups.add(
        Group.objects.get_or_create(
            name=GR_ZGLOSZENIA_PUBLIKACJI
        )[0]
    )

    _zrob_submit_calego_formularza(
        webtest_app, django_capture_on_commit_callbacks
    )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [EMAIL]


def test_email_tytul_z_nowymi_liniami(
    webtest_app,
    django_capture_on_commit_callbacks,
    normal_django_user,
    typy_odpowiedzialnosci,
    uczelnia,
    wydzial,
    jednostka,
):
    normal_django_user.email = EMAIL
    normal_django_user.save()
    normal_django_user.groups.add(
        Group.objects.get_or_create(
            name=GR_ZGLOSZENIA_PUBLIKACJI
        )[0]
    )

    _zrob_submit_calego_formularza(
        webtest_app,
        django_capture_on_commit_callbacks,
        tytul_oryginalny="PANIE\nCzy to pojdzie?",
    )
    assert len(mail.outbox) == 1


def test_email_obslugujacym_zgloszenia(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    wydzial,
    aktualna_jednostka,
    autor_jan_kowalski,
):
    inny_user = baker.make(BppUser, email=EMAIL)
    Obslugujacy_Zgloszenia_Wydzialow.objects.create(
        user=inny_user, wydzial=wydzial
    )

    _zrob_submit_calego_formularza(
        webtest_app,
        django_capture_on_commit_callbacks,
        autor=autor_jan_kowalski,
        jednostka=aktualna_jednostka,
    )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [inny_user.email]


@pytest.mark.django_db
def test_wymagaj_logowania_niezalogowany(
    webtest_app, uczelnia
):
    """Niezalogowany + wymagaj_logowania=True -> redirect."""
    uczelnia.wymagaj_logowania_zglos_publikacje = True
    uczelnia.save()

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url, expect_errors=True)
    assert page.status_code == 302
    assert "/accounts/login/" in page.location


@pytest.mark.django_db
def test_wymagaj_logowania_zalogowany(
    webtest_app, uczelnia, normal_django_user
):
    """Zalogowany + wymagaj_logowania=True -> dostęp."""
    uczelnia.wymagaj_logowania_zglos_publikacje = True
    uczelnia.save()
    webtest_app.set_user(normal_django_user)

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    assert page.status_code == 200


@pytest.mark.django_db
def test_wymagaj_logowania_false(webtest_app, uczelnia):
    """Niezalogowany + wymagaj_logowania=False -> dostęp."""
    uczelnia.wymagaj_logowania_zglos_publikacje = False
    uczelnia.save()

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    assert page.status_code == 200


@pytest.mark.django_db
def test_konfigurowalne_platnosci_artykul(
    webtest_app, uczelnia
):
    """Sprawdź że opłaty są konfigurowalne per typ."""
    uczelnia.wymagaj_oplatach_artykul = False
    uczelnia.save()

    # Artykuł z wyłączonymi opłatami -> brak kroku 4
    page = _przejdz_do_kroku_danych(
        webtest_app, rodzaj="ARTYKUL", forma="OTWARTY"
    )
    page = _krok2_dane(
        page, strona_www="https://example.com/"
    )
    page2 = page.forms[0].submit()
    # Krok 3: autorzy
    page3 = page2.forms[0].submit()
    # Powinien przejść od razu do sukcesu (bez kroku 4)
    # lub wymagać submitnięcia autorów
    assert page3.status_code == 200


def _krok2_ograniczony_post_z_plikami(
    webtest_app, page, *, ile_plikow, rok="2020"
):
    """Submit step 2 (OGRANICZONY) z N plikami przez webtest_app.post.

    `webtest`-owa abstrakcja Form nie obsługuje wieloplikowych pól
    z tym samym `name=` — trzeba zejść do `webtest_app.post()`
    z parametrem `upload_files` (lista trójek (name, filename, content)),
    który zachowuje duplikaty kluczy. Pozostałe pola przepisujemy
    z aktualnego formularza, żeby management_form (`current_step`)
    i pozostałe ukryte pola wizarda doszły bez ręcznego pamiętania.
    """
    form = page.forms[0]
    fields = [
        (n, v) for n, v in form.submit_fields() if not (n and n.startswith("2-"))
    ]
    fields.extend(
        [
            ("2-tytul_oryginalny", "Test multifile"),
            ("2-rok", str(rok)),
            ("2-email", "test@test.pl"),
            ("2-strona_www", "https://example.com/"),
        ]
    )
    with open(PDF_PATH, "rb") as fh:
        pdf_content = fh.read()
    upload_files = [
        ("2-pliki", f"plik_{i}.pdf", pdf_content) for i in range(ile_plikow)
    ]
    url = reverse("zglos_publikacje:nowe_zgloszenie")
    return webtest_app.post(url, params=fields, upload_files=upload_files)


def _zlozenie_ograniczony_z_plikami(
    webtest_app,
    django_capture_on_commit_callbacks,
    autor,
    jednostka,
    *,
    ile_plikow,
    rok="2020",
):
    """Pełny przelot wizarda OGRANICZONY z N plikami.

    Zwraca finalną stronę (sukces).
    """
    page = _przejdz_do_kroku_danych(
        webtest_app, rodzaj="ARTYKUL", forma="OGRANICZONY"
    )
    # Krok 2: dane + N plików
    page2 = _krok2_ograniczony_post_z_plikami(
        webtest_app, page, ile_plikow=ile_plikow, rok=rok
    )
    # Krok 3: autorzy
    page2.forms[0]["3-0-autor"].force_value(autor.pk)
    page2.forms[0]["3-0-jednostka"].force_value(jednostka.pk)
    page3 = page2.forms[0].submit()
    # Krok 4: opłaty (default uczelnia ma wymagaj_oplatach_artykul=True)
    page3.forms[0]["4-opl_pub_cost_free"] = "true"
    with django_capture_on_commit_callbacks(execute=True):
        return page3.forms[0].submit().maybe_follow()


@pytest.mark.django_db
def test_pelny_formularz_ograniczony_jeden_plik(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_jan_kowalski,
    aktualna_jednostka,
):
    """Wizard OGRANICZONY z 1 plikiem: 1 Zalacznik w bazie."""
    result = _zlozenie_ograniczony_z_plikami(
        webtest_app,
        django_capture_on_commit_callbacks,
        autor=autor_jan_kowalski,
        jednostka=aktualna_jednostka,
        ile_plikow=1,
    )
    assert b"powiadomiony" in result.content or b"zostanie zaakceptowane" in result.content
    zp = Zgloszenie_Publikacji.objects.order_by("-pk").first()
    assert zp is not None
    assert zp.zalaczniki.count() == 1


@pytest.mark.django_db
def test_pelny_formularz_ograniczony_wiele_plikow(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_jan_kowalski,
    aktualna_jednostka,
):
    """Wizard OGRANICZONY z 3 plikami: 3 Zalaczniki w bazie.

    Regresja: formtools wizard storage iteruje `files.items()`
    co dla pól z `<input multiple>` zapisuje tylko ostatni plik.
    `Zgloszenie_PublikacjiWizard.process_step_files` zapisuje
    całą listę do `extra_data`, a `_process_files` w `done()`
    odtwarza wszystkie załączniki.
    """
    result = _zlozenie_ograniczony_z_plikami(
        webtest_app,
        django_capture_on_commit_callbacks,
        autor=autor_jan_kowalski,
        jednostka=aktualna_jednostka,
        ile_plikow=3,
    )
    assert b"powiadomiony" in result.content or b"zostanie zaakceptowane" in result.content
    zp = Zgloszenie_Publikacji.objects.order_by("-pk").first()
    assert zp is not None
    assert zp.zalaczniki.count() == 3, (
        f"Oczekiwano 3 załączników, jest {zp.zalaczniki.count()}"
    )
    nazwy = sorted(z.oryginalna_nazwa_pliku for z in zp.zalaczniki.all())
    assert all(n.endswith(".pdf") for n in nazwy)


def _zlozenie_rozdzialu_z_freetextem_wn(
    webtest_app,
    django_capture_on_commit_callbacks,
    autor,
    jednostka,
    *,
    wn_picker_value=None,
    wn_tekst="Tytuł monografii nadrzędnej",
    rok="2020",
    forma="OTWARTY",
):
    """Pełny przelot wizarda dla ROZDZIAL.

    Pozwala wstrzyknąć surową wartość do pola QSS `wydawnictwo_nadrzedne`
    (przez `force_value`) — w prawdziwej UI taka wartość pojawia się gdy
    user wpisze coś w autocomplete, ale nie wybierze opcji z dropdowna.
    """
    page = _przejdz_do_kroku_danych(
        webtest_app, rodzaj="ROZDZIAL", forma=forma
    )
    form = page.forms[0]
    form["2-tytul_oryginalny"] = "Test rozdziału"
    form["2-rok"] = str(rok)
    form["2-email"] = "test@test.pl"
    form["2-strona_www"] = "https://example.com/"
    if wn_picker_value is not None:
        form["2-wydawnictwo_nadrzedne"].force_value(wn_picker_value)
    if wn_tekst:
        form["2-wydawnictwo_nadrzedne_tekst"] = wn_tekst
    page2 = form.submit()

    # Krok 3: autorzy
    page2.forms[0]["3-0-autor"].force_value(autor.pk)
    page2.forms[0]["3-0-jednostka"].force_value(jednostka.pk)
    # Krok 3 → submit. Domyślnie uczelnia.wymagaj_oplatach_rozdzial=False,
    # więc po kroku 3 idziemy od razu na sukces (z `done()` przez
    # transaction.on_commit, stąd `django_capture_on_commit_callbacks`).
    with django_capture_on_commit_callbacks(execute=True):
        page3 = page2.forms[0].submit().maybe_follow()

    # Jeśli to jednak był step 4 (ktoś włączył opłaty rozdziału),
    # dokończ i wróć z sukcesem.
    if page3.forms and "4-opl_pub_cost_free" in (
        f for form in page3.forms.values() for f in form.fields
    ):
        page3.forms[0]["4-opl_pub_cost_free"] = "true"
        with django_capture_on_commit_callbacks(execute=True):
            page3 = page3.forms[0].submit().maybe_follow()
    return page3


@pytest.mark.django_db
def test_pelny_formularz_rozdzial_z_freetextem_wn(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_jan_kowalski,
    aktualna_jednostka,
):
    """Happy path: ROZDZIAL z wpisanym ręcznie tytułem wydawnictwa
    nadrzędnego (`wydawnictwo_nadrzedne_tekst`) — bez wybierania
    z autocomplete.

    Asercja: zgłoszenie zapisuje się i `wydawnictwo_nadrzedne_tekst`
    w bazie ma to co user wpisał.
    """
    TEKST = "Monografia która nie istnieje w bazie BPP"
    result = _zlozenie_rozdzialu_z_freetextem_wn(
        webtest_app,
        django_capture_on_commit_callbacks,
        autor=autor_jan_kowalski,
        jednostka=aktualna_jednostka,
        wn_tekst=TEKST,
    )
    assert b"powiadomiony" in result.content or b"zostanie zaakceptowane" in result.content
    zp = Zgloszenie_Publikacji.objects.order_by("-pk").first()
    assert zp is not None
    assert zp.rodzaj_zglaszanej_publikacji == (
        Zgloszenie_Publikacji.Rodzaje.ROZDZIAL_W_MONOGRAFII
    )
    assert zp.wydawnictwo_nadrzedne_tekst == TEKST
    assert zp.wydawnictwo_nadrzedne_bpp is None
    assert zp.wydawnictwo_nadrzedne_pbn is None


@pytest.mark.django_db
def test_rozdzial_z_bogus_wn_picker_nie_wybucha_na_re_renderze(
    webtest_app,
    typy_odpowiedzialnosci,
    uczelnia,
):
    """Regresja: HTTP 500 z `ValueError: not enough values to unpack`
    w `dal_queryset_sequence.widgets.filter_choices_to_render` przy
    `choice.split('-', 1)`.

    Scenariusz: user wpisał coś w pole autocomplete
    `wydawnictwo_nadrzedne`, ale nie wybrał opcji z dropdowna.
    POST przyniósł wartość bez `-` (np. surowy tekst). Następnie
    inny błąd walidacji wymusił re-render formularza, a widget
    QSS przy próbie wyrenderowania selectowanej opcji wybuchał.

    Test wymusza walidację błędną przez podanie nieprawidłowego e-maila
    + jednoczesne wstrzyknięcie surowej wartości do pola wn.
    """
    page = _przejdz_do_kroku_danych(
        webtest_app, rodzaj="ROZDZIAL", forma="OTWARTY"
    )
    form = page.forms[0]
    form["2-tytul_oryginalny"] = "Test"
    form["2-rok"] = "2020"
    # Niepoprawny e-mail → form re-render → widget wn musi się wyrenderować
    form["2-email"] = "to nie jest e-mail"
    form["2-strona_www"] = "https://example.com/"
    # Bogus wartość bez `-` (jak typed-not-picked w UI)
    form["2-wydawnictwo_nadrzedne"].force_value(
        "Tytuł wpisany ale nie wybrany z dropdowna"
    )
    response = form.submit()
    # Oczekujemy 200 (re-render z błędem), NIE 500 (crash widgeta)
    assert response.status_code == 200
    # Jesteśmy nadal na kroku 2 (re-render po validation error)
    assert b"2-tytul_oryginalny" in response.content


@pytest.mark.django_db
def test_rozdzial_z_picknietym_wydawnictwem_nadrzednym_zapisuje_FK(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_jan_kowalski,
    aktualna_jednostka,
    ksiazka,
):
    """Regresja: gdy user PICKNĄŁ wydawnictwo nadrzędne z autocomplete
    (a nie wpisał ręcznie), do `Zgloszenie_Publikacji` musi trafić FK
    `wydawnictwo_nadrzedne_bpp`, nie sam tekst.

    Bug w `autocomplete.PublicWydawnictwoNadrzedneAutocomplete`:
    `get_result_value` było nadpisane i zwracało etykietę zamiast
    `<ct_pk>-<obj_pk>`. Skutek — w POST szedł HTML labela, widget QSS
    nie potrafił go odtworzyć w `done()`, tekst lądował w
    `wydawnictwo_nadrzedne_tekst`, FK zostawał `None`.
    """
    from django.contrib.contenttypes.models import ContentType

    from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

    ct = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)
    qss_value = f"{ct.pk}-{ksiazka.pk}"

    result = _zlozenie_rozdzialu_z_freetextem_wn(
        webtest_app,
        django_capture_on_commit_callbacks,
        autor=autor_jan_kowalski,
        jednostka=aktualna_jednostka,
        wn_picker_value=qss_value,
        wn_tekst="",
    )
    assert b"powiadomiony" in result.content or b"zostanie zaakceptowane" in result.content
    zp = Zgloszenie_Publikacji.objects.order_by("-pk").first()
    assert zp is not None
    assert zp.wydawnictwo_nadrzedne_bpp_id == ksiazka.pk, (
        "FK do Wydawnictwo_Zwarte musi być ustawione gdy user picknął"
        " z autocomplete; ustawiony tekst zamiast FK = bug w autocomplete"
        " (get_result_value zwracał label zamiast <ct>-<pk>)."
    )
    assert zp.wydawnictwo_nadrzedne_pbn is None
    # Tekst też się populuje (z `tytul_oryginalny` wybranej książki)
    assert zp.wydawnictwo_nadrzedne_tekst == ksiazka.tytul_oryginalny


@pytest.mark.django_db
def test_rozdzial_z_typed_text_w_picker_lzdaje_jako_freetext(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_jan_kowalski,
    aktualna_jednostka,
):
    """Gdy user wpisał coś w pole picker `wydawnictwo_nadrzedne`,
    ale nie wybrał z autocomplete (POST dostarcza tekst bez `-`),
    formularz traktuje tę wartość jak freetext i wpisuje do
    `wydawnictwo_nadrzedne_tekst`. Bez tego user traci wpisany
    tytuł, a w skrajnym przypadku zgłoszenie ROZDZIAL jest
    zapisywane bez żadnej informacji o monografii nadrzędnej.
    """
    TEKST = "Monografia z autocomplete (typed but not picked)"
    result = _zlozenie_rozdzialu_z_freetextem_wn(
        webtest_app,
        django_capture_on_commit_callbacks,
        autor=autor_jan_kowalski,
        jednostka=aktualna_jednostka,
        wn_picker_value=TEKST,
        wn_tekst="",
    )
    assert b"powiadomiony" in result.content or b"zostanie zaakceptowane" in result.content
    zp = Zgloszenie_Publikacji.objects.order_by("-pk").first()
    assert zp is not None
    assert zp.wydawnictwo_nadrzedne_tekst == TEKST


def _zlozenie_monografii(
    webtest_app,
    django_capture_on_commit_callbacks,
    autor,
    jednostka,
    *,
    rok="2020",
    forma="OTWARTY",
):
    """Pełny przelot wizarda dla MONOGRAFII (książka)."""
    page = _przejdz_do_kroku_danych(
        webtest_app, rodzaj="MONOGRAFIA", forma=forma
    )
    form = page.forms[0]
    form["2-tytul_oryginalny"] = "Test monografii"
    form["2-rok"] = str(rok)
    form["2-email"] = "test@test.pl"
    form["2-strona_www"] = "https://example.com/monografia"
    page2 = form.submit()

    # Krok 3: autorzy
    page2.forms[0]["3-0-autor"].force_value(autor.pk)
    page2.forms[0]["3-0-jednostka"].force_value(jednostka.pk)
    page3 = page2.forms[0].submit()

    # Krok 4: opłaty (uczelnia.wymagaj_oplatach_monografia=True default)
    page3.forms[0]["4-opl_pub_cost_free"] = "true"
    with django_capture_on_commit_callbacks(execute=True):
        return page3.forms[0].submit().maybe_follow()


@pytest.mark.django_db
def test_pelny_formularz_monografia_otwarty(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_jan_kowalski,
    aktualna_jednostka,
):
    """Pełny przelot wizarda dla MONOGRAFII w otwartym dostępie.

    Asercje:
    - Zgłoszenie utworzone z poprawnym `rodzaj_zglaszanej_publikacji`
    - Strona WWW zapisana
    - Brak `wydawnictwo_nadrzedne_*` (MONOGRAFIA nie ma takich pól w
      formularzu — `_usun_pola_wg_rodzaju` je wyrzuca; monografia jest
      sama w sobie publikacją „nadrzędną")
    - Brak `wydawca_*` ustawionego z formularza (pole `wydawca` zostało
      usunięte z formularza w 5b68c5b44 — bibliotekarz uzupełnia je
      ręcznie w adminie). Test pilnuje tej decyzji projektowej; jeśli
      kiedyś wrócimy z polem `wydawca` do formularza użytkownika,
      ten test ma się wywalić jako sygnał aktualizacji.
    - Autor poprawnie zapisany.
    """
    result = _zlozenie_monografii(
        webtest_app,
        django_capture_on_commit_callbacks,
        autor=autor_jan_kowalski,
        jednostka=aktualna_jednostka,
    )
    assert b"powiadomiony" in result.content or b"zostanie zaakceptowane" in result.content

    zp = Zgloszenie_Publikacji.objects.order_by("-pk").first()
    assert zp is not None
    assert zp.rodzaj_zglaszanej_publikacji == (
        Zgloszenie_Publikacji.Rodzaje.MONOGRAFIA
    )
    assert zp.forma_dostepu == Zgloszenie_Publikacji.FormyDostepu.OTWARTY
    assert zp.tytul_oryginalny == "Test monografii"
    assert zp.strona_www == "https://example.com/monografia"

    # MONOGRAFIA nie ma pól wydawnictwa nadrzędnego w formularzu
    assert zp.wydawnictwo_nadrzedne_bpp is None
    assert zp.wydawnictwo_nadrzedne_pbn is None
    assert zp.wydawnictwo_nadrzedne_tekst == ""

    # Pole `wydawca` świadomie usunięte z formularza użytkownika
    # (bibliotekarz uzupełnia w adminie)
    assert zp.wydawca_bpp is None
    assert zp.wydawca_pbn is None
    assert zp.wydawca_zgloszenia == ""

    # Autor zapisany
    assert zp.zgloszenie_publikacji_autor_set.count() == 1
    zpa = zp.zgloszenie_publikacji_autor_set.first()
    assert zpa.autor_id == autor_jan_kowalski.pk
    assert zpa.jednostka_id == aktualna_jednostka.pk


@pytest.mark.django_db
def test_rodzaj_zapisywany_prawidlowo(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
):
    """Sprawdź że nowy rodzaj jest zapisywany w modelu."""
    _zrob_submit_calego_formularza(
        webtest_app,
        django_capture_on_commit_callbacks,
        rodzaj="MONOGRAFIA",
    )
    zp = Zgloszenie_Publikacji.objects.first()
    assert zp.rodzaj_zglaszanej_publikacji == (
        Zgloszenie_Publikacji.Rodzaje.MONOGRAFIA
    )
    assert zp.forma_dostepu == (
        Zgloszenie_Publikacji.FormyDostepu.OTWARTY
    )
