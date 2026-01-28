"""Test weryfikujący naprawę błędu podwójnego potwierdzenia dla data-confirm.

Ten test sprawdza, czy kliknięcie przycisku z atrybutem data-confirm
wyświetla tylko JEDEN dialog potwierdzenia (a nie dwa, jak było przed naprawą).
"""

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page, expect

from bpp.models import Uczelnia


@pytest.mark.django_db
def test_data_confirm_shows_single_dialog(
    admin_page: Page,
    channels_live_server,
):
    """Test sprawdzający, że data-confirm wyświetla tylko jeden dialog.

    Przed naprawą, kliknięcie przycisku z data-confirm powodowało wyświetlenie
    dwóch dialogów potwierdzenia (jeden z globalnego handlera w event-handlers.js,
    drugi z lokalnego handlera w szablonie). Po naprawie powinien być tylko jeden.
    """
    # Utwórz uczelnię wymaganą przez widok
    baker.make(Uczelnia, nazwa="Testowa Uczelnia")

    dialog_count = 0
    dialog_messages = []

    def handle_dialog(dialog):
        nonlocal dialog_count
        dialog_count += 1
        dialog_messages.append(dialog.message)
        # Odrzuć dialog żeby nie wysyłać formularza
        dialog.dismiss()

    # Zarejestruj handler dialogów
    admin_page.on("dialog", handle_dialog)

    # Przejdź do strony ewaluacja_optymalizacja
    url = channels_live_server.url + reverse("ewaluacja_optymalizacja:index")
    admin_page.goto(url)
    admin_page.wait_for_load_state("networkidle")

    # Zamknij banner cookie, jeśli istnieje (blokuje kliknięcia)
    admin_page.evaluate("if(window.Cookielaw) Cookielaw.accept()")

    # Znajdź przycisk z data-confirm - MUSI istnieć
    confirm_button = admin_page.locator("[data-confirm]").first
    expect(confirm_button).to_be_visible(
        timeout=5000,
    )

    # Kliknij przycisk
    confirm_button.click()

    # Poczekaj chwilę na ewentualne dodatkowe dialogi
    admin_page.wait_for_timeout(500)

    # Sprawdź że pojawił się dokładnie JEDEN dialog
    assert dialog_count == 1, (
        f"Oczekiwano 1 dialogu potwierdzenia, otrzymano {dialog_count}. "
        f"Komunikaty: {dialog_messages}"
    )


@pytest.mark.django_db
def test_data_confirm_cancel_prevents_action(
    admin_page: Page,
    channels_live_server,
):
    """Test sprawdzający, że anulowanie dialogu data-confirm blokuje akcję.

    Po kliknięciu 'Anuluj' w dialogu potwierdzenia, formularz nie powinien
    zostać wysłany (nie powinno być żadnych requestów POST).
    """
    # Utwórz uczelnię wymaganą przez widok
    baker.make(Uczelnia, nazwa="Testowa Uczelnia")

    dialog_appeared = False
    form_submitted = False

    def handle_dialog(dialog):
        nonlocal dialog_appeared
        dialog_appeared = True
        # Odrzuć dialog (kliknij Anuluj)
        dialog.dismiss()

    def handle_request(request):
        nonlocal form_submitted
        # Sprawdź czy to request POST do bulk-start
        if "bulk/start" in request.url and request.method == "POST":
            form_submitted = True

    # Zarejestruj handlery
    admin_page.on("dialog", handle_dialog)
    admin_page.on("request", handle_request)

    # Przejdź do strony
    url = channels_live_server.url + reverse("ewaluacja_optymalizacja:index")
    admin_page.goto(url)
    admin_page.wait_for_load_state("networkidle")

    # Zamknij banner cookie, jeśli istnieje (blokuje kliknięcia)
    admin_page.evaluate("if(window.Cookielaw) Cookielaw.accept()")

    # Znajdź przycisk z data-confirm - MUSI istnieć
    confirm_button = admin_page.locator("[data-confirm]").first
    expect(confirm_button).to_be_visible(timeout=5000)

    # Kliknij przycisk
    confirm_button.click()

    # Poczekaj na potencjalne requesty
    admin_page.wait_for_timeout(500)

    # Sprawdź że dialog się pojawił
    assert dialog_appeared, "Dialog potwierdzenia nie pojawił się"

    # Sprawdź że formularz NIE został wysłany
    assert not form_submitted, (
        "Formularz został wysłany mimo anulowania dialogu potwierdzenia"
    )
