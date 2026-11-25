import os

import pytest
from django.urls import reverse
from playwright.sync_api import Page, expect

from bpp.models import Autor_Dyscyplina, Autor_Jednostka
from django_bpp.playwright_util import (
    select_select2_autocomplete,
    set_select2_value,
)


def wait_for_discipline_populated(page: Page, field_id: str, timeout: int = 10000):
    """Wait for discipline field to be populated via AJAX."""
    page.wait_for_function(
        f"() => document.querySelector('#{field_id}').value !== ''",
        timeout=timeout,
    )


def _przejdz_kroki_0_1_2(
    page: Page,
    channels_live_server,
    rok,
    rodzaj="ARTYKUL",
    forma="OTWARTY",
    strona_www="https://www.onet.pl/",
):
    """Przejdź kroki 0 (rodzaj), 1 (dostęp), 2 (dane)."""
    page.goto(channels_live_server.url + reverse("zglos_publikacje:nowe_zgloszenie"))
    page.wait_for_load_state("domcontentloaded")
    page.evaluate("if(window.Cookielaw) Cookielaw.accept()")

    # Krok 0: rodzaj — klik na kafelek auto-submituje form (tile JS handler).
    # Radio input jest ukryty wewnątrz <label class="tile-card">.
    page.click(f".tile-card[data-value='{rodzaj}']")
    page.wait_for_load_state("domcontentloaded")

    # Krok 1: forma dostępu — identyczny wzorzec jak krok 0.
    page.click(f".tile-card[data-value='{forma}']")
    page.wait_for_load_state("domcontentloaded")

    # Krok 2: dane
    page.fill("[name='2-tytul_oryginalny']", "test")
    page.fill("[name='2-rok']", str(rok))
    # Pole e-mail jest `disabled` i pre-wypełnione kontem dla zalogowanego
    # użytkownika z e-mailem (F2) — wypełniamy je tylko gdy edytowalne
    # (anonim / zalogowany bez e-maila).
    if page.is_editable("[name='2-email']"):
        page.fill("[name='2-email']", "moj@email.pl")
    if strona_www:
        page.fill("[name='2-strona_www']", strona_www)

    page.click("#id-wizard-submit")
    page.wait_for_load_state("domcontentloaded")


@pytest.mark.django_db(transaction=True)
def test_zglos_publikacje_drugi_autor_dyscyplina(
    admin_page: Page,
    channels_live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    """Test discipline auto-population when adding
    2nd author."""
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina1,
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    _przejdz_kroki_0_1_2(
        admin_page,
        channels_live_server,
        rok,
        rodzaj="POZOSTALE",
        forma="OTWARTY",
    )

    # Krok 3: autorzy
    n = 1
    admin_page.click("#add-form")
    admin_page.wait_for_selector(f"#id_3-{n}-autor", state="visible")
    set_select2_value(
        admin_page,
        f"id_3-{n}-autor",
        autor_jan_kowalski.pk,
        label=str(autor_jan_kowalski),
        timeout=30000,
    )

    wait_for_discipline_populated(admin_page, f"id_3-{n}-dyscyplina_naukowa")

    assert admin_page.locator(f"#id_3-{n}-dyscyplina_naukowa").input_value() == str(
        dyscyplina1.pk
    )


@pytest.mark.django_db(transaction=True)
def test_zglos_publikacje_ograniczony_dostep(
    admin_page: Page,
    channels_live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    """Test z ograniczonym dostępem i plikiem PDF."""
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina1,
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    _przejdz_kroki_0_1_2(
        admin_page,
        channels_live_server,
        rok,
        rodzaj="POZOSTALE",
        forma="OGRANICZONY",
    )

    # Powinien być na kroku 2 z polem pliku
    # (bo brak pliku = błąd walidacji serwerowej dla OGRANICZONY)
    assert admin_page.locator("[name='2-pliki']").count() > 0

    # Dodaj plik
    plik = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "example.pdf"))
    admin_page.set_input_files("[name='2-pliki']", plik)
    admin_page.click("#id-wizard-submit")
    admin_page.wait_for_load_state("domcontentloaded")

    # Krok 3: autorzy
    n = 1
    admin_page.click("#add-form")
    admin_page.wait_for_selector(f"#id_3-{n}-autor", state="attached", timeout=10000)

    admin_page.locator(f"#id_3-{n}-autor").scroll_into_view_if_needed()

    set_select2_value(
        admin_page,
        f"id_3-{n}-autor",
        autor_jan_kowalski.pk,
        label=str(autor_jan_kowalski),
        timeout=30000,
    )

    wait_for_discipline_populated(admin_page, f"id_3-{n}-dyscyplina_naukowa")

    assert admin_page.locator(f"#id_3-{n}-dyscyplina_naukowa").input_value() == str(
        dyscyplina1.pk
    )


@pytest.mark.django_db(transaction=True)
def test_zglos_publikacje_wiele_klikniec(
    admin_page: Page,
    channels_live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    rok,
):
    """Test that multiple 'add author' clicks don't break
    Select2."""
    for autor in autor_jan_kowalski, autor_jan_nowak:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina1,
        )
        Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)

    _przejdz_kroki_0_1_2(
        admin_page,
        channels_live_server,
        rok,
        rodzaj="POZOSTALE",
        forma="OTWARTY",
    )

    # Krok 3: autorzy - kliknij "dodaj" 3 razy
    admin_page.click("#add-form")
    admin_page.wait_for_selector("#id_3-0-autor", state="visible")
    admin_page.click("#add-form")
    admin_page.wait_for_selector("#id_3-1-autor", state="visible")
    admin_page.click("#add-form")
    admin_page.wait_for_selector("#id_3-2-autor", state="visible")

    # NIE ZASTĘPOWAĆ przez set_select2_value: test ma potwierdzać, że po
    # wielokrotnym dodaniu formularzy Select2 nadal przyjmuje wpisywanie.
    select_select2_autocomplete(
        admin_page,
        "id_3-1-autor",
        "Kowal",
        timeout=30000,
    )

    wait_for_discipline_populated(admin_page, "id_3-1-dyscyplina_naukowa")

    assert admin_page.locator("#id_3-1-dyscyplina_naukowa").input_value() == str(
        dyscyplina1.pk
    )


@pytest.mark.django_db(transaction=True)
def test_fd640_dyscyplina_ukryta_dla_autora_spoza_uczelni(
    admin_page: Page,
    channels_live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    obca_jednostka,
    uczelnia_z_obca_jednostka,
    dyscyplina1,
    rok,
):
    """FD#640: po wybraniu autora spoza uczelni pole „Dyscyplina naukowa”
    znika (i jest czyszczone), a jednostka zmienia się na obcą jednostkę
    uczelni — lista jednostek podpowiada mu tylko ją. Po wybraniu autora
    uczelni pole dyscypliny wraca, a jednostka to jego jednostka."""
    obcy, swoj = autor_jan_nowak, autor_jan_kowalski
    Autor_Jednostka.objects.get_or_create(autor=obcy, jednostka=obca_jednostka)
    Autor_Jednostka.objects.get_or_create(autor=swoj, jednostka=jednostka)
    for autor in obcy, swoj:
        Autor_Dyscyplina.objects.get_or_create(
            autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina1
        )

    _przejdz_kroki_0_1_2(
        admin_page,
        channels_live_server,
        rok,
        rodzaj="POZOSTALE",
        forma="OTWARTY",
    )

    pole = admin_page.locator("#div_id_3-0-dyscyplina_naukowa")
    expect(pole).to_be_visible()

    set_select2_value(
        admin_page, "id_3-0-autor", obcy.pk, label=str(obcy), timeout=30000
    )
    expect(pole).to_be_hidden()
    assert admin_page.locator("#id_3-0-dyscyplina_naukowa").input_value() == ""
    jednostka_pole = admin_page.locator("#id_3-0-jednostka")
    expect(jednostka_pole).to_have_value(str(obca_jednostka.pk))

    # Autocomplete jednostki podpowiada obcemu autorowi tylko jednostkę obcą.
    admin_page.locator("#div_id_3-0-jednostka .select2-selection").click()
    wyniki = admin_page.locator(".select2-results__option")
    expect(wyniki).to_have_count(1)
    expect(wyniki.first).to_contain_text(obca_jednostka.nazwa)
    admin_page.keyboard.press("Escape")

    set_select2_value(
        admin_page, "id_3-0-autor", swoj.pk, label=str(swoj), timeout=30000
    )
    expect(pole).to_be_visible()
    wait_for_discipline_populated(admin_page, "id_3-0-dyscyplina_naukowa")
    expect(jednostka_pole).to_have_value(str(jednostka.pk))


# Pełna integracja zgłoszenia z plikami (1 i wiele) jest pokryta
# webtest-owymi testami `test_pelny_formularz_ograniczony_*`
# w `tests_zglos_publikacje.py`. Browser tu nie jest potrzebny
# (a wprowadza flakiness przy autouzupełnianiu jednostki przez
# autorform_dependant.js).


_WSTRZYMAJ_AJAX_AUTORA = """() => {
    const $ = django.jQuery;
    const oryginalny = $.ajax;
    window.__zadaniaAutora = [];
    $.ajax = function (opcje) {
        if ((opcje.url || '').indexOf('ostatnia-jednostka-i-dyscyplina') < 0)
            return oryginalny.apply(this, arguments);
        const odroczone = $.Deferred();
        const zadanie = {odroczone: odroczone, odpowiedz: null};
        oryginalny(opcje).done(function (dane) { zadanie.odpowiedz = dane; });
        window.__zadaniaAutora.push(zadanie);
        return odroczone.promise();
    };
}"""


def _zwolnij_odpowiedz(page: Page, nr: int):
    """Oddaj odpowiedź serwera na ``nr``-te żądanie (gdy już przyszła)."""
    page.wait_for_function(
        f"() => window.__zadaniaAutora[{nr}] "
        f"&& window.__zadaniaAutora[{nr}].odpowiedz !== null"
    )
    page.evaluate(
        f"() => {{ const z = window.__zadaniaAutora[{nr}];"
        f" z.odroczone.resolve(z.odpowiedz); }}"
    )


@pytest.mark.django_db(transaction=True)
def test_fd640_spozniona_odpowiedz_nie_nadpisuje_wyboru(
    admin_page: Page,
    channels_live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    druga_jednostka,
    wydzial,
    jednostka_maker,
    rok,
):
    """FD#640 (punkt 5): ostatnie żądanie wygrywa — spóźniona odpowiedź dla
    autora A po zmianie A → B nie nadpisuje jednostki B; odpowiedź po ręcznej
    zmianie jednostki nie nadpisuje wyboru użytkownika."""
    a, b = autor_jan_kowalski, autor_jan_nowak
    Autor_Jednostka.objects.get_or_create(autor=a, jednostka=jednostka)
    Autor_Jednostka.objects.get_or_create(autor=b, jednostka=druga_jednostka)
    for autor, j in ((a, jednostka), (b, druga_jednostka)):
        autor.refresh_from_db()
        assert autor.aktualna_jednostka == j

    _przejdz_kroki_0_1_2(
        admin_page, channels_live_server, rok, rodzaj="POZOSTALE", forma="OTWARTY"
    )
    admin_page.evaluate(_WSTRZYMAJ_AJAX_AUTORA)
    jednostka_pole = admin_page.locator("#id_3-0-jednostka")

    # A → B, odpowiedzi w odwrotnej kolejności.
    set_select2_value(admin_page, "id_3-0-autor", a.pk, label=str(a))
    set_select2_value(admin_page, "id_3-0-autor", b.pk, label=str(b))
    _zwolnij_odpowiedz(admin_page, 1)
    expect(jednostka_pole).to_have_value(str(druga_jednostka.pk))
    _zwolnij_odpowiedz(admin_page, 0)
    admin_page.wait_for_timeout(300)
    expect(jednostka_pole).to_have_value(str(druga_jednostka.pk))

    # A, potem ręczna zmiana jednostki zanim przyjdzie odpowiedź.
    trzecia = jednostka_maker("Trzecia Katedra", skrot="TK", wydzial=wydzial)
    set_select2_value(admin_page, "id_3-0-autor", a.pk, label=str(a))
    set_select2_value(admin_page, "id_3-0-jednostka", trzecia.pk, label=str(trzecia))
    _zwolnij_odpowiedz(admin_page, 2)
    admin_page.wait_for_timeout(300)
    expect(jednostka_pole).to_have_value(str(trzecia.pk))


@pytest.mark.django_db(transaction=True)
def test_fd640_zmiana_autora_czysci_dyscypline_poprzedniego(
    admin_page: Page,
    channels_live_server,
    autor_jan_kowalski,
    autor_jan_nowak,
    uczelnia,
    jednostka,
    druga_jednostka,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    rok,
):
    """FD#640: po zmianie autora A → B, gdy B ma w roku dwie dyscypliny (API
    nie podpowiada żadnej), dyscyplina autora A nie zostaje w polu."""
    a, b = autor_jan_kowalski, autor_jan_nowak
    Autor_Jednostka.objects.get_or_create(autor=a, jednostka=jednostka)
    Autor_Jednostka.objects.get_or_create(autor=b, jednostka=druga_jednostka)
    Autor_Dyscyplina.objects.get_or_create(
        autor=a, rok=rok, dyscyplina_naukowa=dyscyplina1
    )
    Autor_Dyscyplina.objects.get_or_create(
        autor=b,
        rok=rok,
        dyscyplina_naukowa=dyscyplina2,
        subdyscyplina_naukowa=dyscyplina3,
    )

    _przejdz_kroki_0_1_2(
        admin_page, channels_live_server, rok, rodzaj="POZOSTALE", forma="OTWARTY"
    )
    dyscyplina_pole = admin_page.locator("#id_3-0-dyscyplina_naukowa")
    jednostka_pole = admin_page.locator("#id_3-0-jednostka")

    set_select2_value(admin_page, "id_3-0-autor", a.pk, label=str(a), timeout=30000)
    expect(dyscyplina_pole).to_have_value(str(dyscyplina1.pk))

    set_select2_value(admin_page, "id_3-0-autor", b.pk, label=str(b), timeout=30000)
    # Jednostka B przychodzi w tej samej odpowiedzi — po niej pole dyscypliny
    # musi być puste.
    expect(jednostka_pole).to_have_value(str(druga_jednostka.pk))
    expect(dyscyplina_pole).to_have_value("")
