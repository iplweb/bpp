"""Strona importera dokleja skrypt czyszczący cache historii HTMX-a.

``#importer-wizard`` ma ``hx-history="false"``, co blokuje wyłącznie ZAPIS
snapshotu do localStorage — ``restoreHistory()`` w HTMX czyta cache tak czy
inaczej. Wpis zapisany przed zmianą layoutu kroku 1 (radiowy wybór źródła +
lista sesji) przeżywał więc bezterminowo i wracał po naciśnięciu „Wstecz".
``history_cache.js`` kasuje takie wpisy — ale tylko jeśli wykona się PRZED
htmx.min.js, stąd asercja na kolejność.

Logika samego czyszczenia jest testowana jednostkowo w
``tests/js/importer-history-cache.test.js`` (vitest).
"""

import pytest
from django.urls import reverse

# Nazwy plików statycznych niosą hash treści (ManifestStaticFilesStorage),
# więc szukamy po rdzeniu nazwy, nie po pełnym „history_cache.js".


@pytest.mark.django_db
def test_index_laduje_czyszczenie_historii_przed_htmx(importer_client):
    content = importer_client.get(reverse("importer_publikacji:index")).content.decode()

    assert "history_cache" in content, "brak skryptu czyszczącego cache historii"
    assert 'data-prefiks="/importer_publikacji/"' in content, (
        "skrypt bez prefiksu URL-a nie wie, które wpisy skasować"
    )
    assert content.index("history_cache") < content.index("htmx.min"), (
        "czyszczenie musi wykonać się przed załadowaniem HTMX-a"
    )
