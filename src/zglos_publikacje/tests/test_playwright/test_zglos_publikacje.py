import os

import pytest
from django.urls import reverse
from playwright.sync_api import Page

from bpp.models import Autor_Dyscyplina, Autor_Jednostka
from django_bpp.playwright_util import (
    select_select2_autocomplete,
)


def wait_for_discipline_populated(
    page: Page, field_id: str, timeout: int = 10000
):
    """Wait for discipline field to be populated via AJAX."""
    page.wait_for_function(
        f"() => document.querySelector('#{field_id}')"
        f".value !== ''",
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
    page.goto(
        channels_live_server.url
        + reverse("zglos_publikacje:nowe_zgloszenie")
    )
    page.wait_for_load_state("domcontentloaded")
    page.evaluate(
        "if(window.Cookielaw) Cookielaw.accept()"
    )

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
        Autor_Jednostka.objects.get_or_create(
            autor=autor, jednostka=jednostka
        )

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
    admin_page.wait_for_selector(
        f"#id_3-{n}-autor", state="visible"
    )
    select_select2_autocomplete(
        admin_page,
        f"id_3-{n}-autor",
        "Kowal",
        timeout=30000,
    )

    wait_for_discipline_populated(
        admin_page, f"id_3-{n}-dyscyplina_naukowa"
    )

    assert admin_page.locator(
        f"#id_3-{n}-dyscyplina_naukowa"
    ).input_value() == str(dyscyplina1.pk)


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
        Autor_Jednostka.objects.get_or_create(
            autor=autor, jednostka=jednostka
        )

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
    plik = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "example.pdf"
        )
    )
    admin_page.set_input_files("[name='2-pliki']", plik)
    admin_page.click("#id-wizard-submit")
    admin_page.wait_for_load_state("domcontentloaded")

    # Krok 3: autorzy
    n = 1
    admin_page.click("#add-form")
    admin_page.wait_for_selector(
        f"#id_3-{n}-autor", state="attached", timeout=10000
    )

    admin_page.locator(f"#id_3-{n}-autor").scroll_into_view_if_needed()

    select_select2_autocomplete(
        admin_page,
        f"id_3-{n}-autor",
        "Kowal",
        timeout=30000,
    )

    wait_for_discipline_populated(
        admin_page, f"id_3-{n}-dyscyplina_naukowa"
    )

    assert admin_page.locator(
        f"#id_3-{n}-dyscyplina_naukowa"
    ).input_value() == str(dyscyplina1.pk)


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
        Autor_Jednostka.objects.get_or_create(
            autor=autor, jednostka=jednostka
        )

    _przejdz_kroki_0_1_2(
        admin_page,
        channels_live_server,
        rok,
        rodzaj="POZOSTALE",
        forma="OTWARTY",
    )

    # Krok 3: autorzy - kliknij "dodaj" 3 razy
    admin_page.click("#add-form")
    admin_page.wait_for_selector(
        "#id_3-0-autor", state="visible"
    )
    admin_page.click("#add-form")
    admin_page.wait_for_selector(
        "#id_3-1-autor", state="visible"
    )
    admin_page.click("#add-form")
    admin_page.wait_for_selector(
        "#id_3-2-autor", state="visible"
    )

    select_select2_autocomplete(
        admin_page,
        "id_3-1-autor",
        "Kowal",
        timeout=30000,
    )

    wait_for_discipline_populated(
        admin_page, "id_3-1-dyscyplina_naukowa"
    )

    assert admin_page.locator(
        "#id_3-1-dyscyplina_naukowa"
    ).input_value() == str(dyscyplina1.pk)

# Pełna integracja zgłoszenia z plikami (1 i wiele) jest pokryta
# webtest-owymi testami `test_pelny_formularz_ograniczony_*`
# w `tests_zglos_publikacje.py`. Browser tu nie jest potrzebny
# (a wprowadza flakiness przy autouzupełnianiu jednostki przez
# autorform_dependant.js).
