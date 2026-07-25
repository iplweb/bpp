"""Strażnik: zapytania LICZĄCE muszą brać zakres lat z ``OKRES_DOMYSLNY``.

Okres 2022-2025 był wpisany na sztywno w kilkudziesięciu filtrach ORM.
To groźniejsza kategoria niż literał w etykiecie: po przestawieniu
``OKRES_DOMYSLNY`` na kolejny okres takie miejsce dalej liczyłoby po cichu
2022-2025 — bez wyjątku, bez ostrzeżenia, tylko ze złym wynikiem.

Test celuje w najcięższe miejsce w apce ``ewaluacja_liczba_n`` — queryset
listy udziałów, z którego wyrasta cała liczba N — i sprawdza, że podmiana
stałej faktycznie zmienia to, co widok pobiera z bazy. Sam fakt, że w kodzie
stoi ``OKRES_DOMYSLNY[0]``, jest tu niewystarczający: liczy się, czy wartość
jest czytana w momencie WYWOŁANIA (a nie zapieczona np. w domyślnym
argumencie funkcji, gdzie ``mock.patch`` już by nie pomógł).
"""

from decimal import Decimal
from unittest import mock

import pytest
from django.test import RequestFactory
from model_bakery import baker

from bpp.models import Autor, Dyscyplina_Naukowa, Jednostka, Uczelnia
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok
from ewaluacja_liczba_n.views import list as widok_listy

# Okres celowo rozłączny z 2022-2025 — gdyby widok dalej filtrował po starych
# latach, przecięcie zbiorów byłoby puste i test padnie jednoznacznie.
OKRES_TESTOWY = (2026, 2029)

LATA_STAREGO_OKRESU = [2022, 2023, 2024, 2025]
LATA_TESTOWEGO_OKRESU = [2026, 2027, 2028, 2029]


@pytest.fixture
def uczelnia_z_udzialami_z_dwoch_okresow(db):
    """Udziały za oba okresy naraz — po jednym rekordzie na każdy rok."""
    uczelnia = baker.make(Uczelnia)
    jednostka = baker.make(Jednostka, uczelnia=uczelnia, skupia_pracownikow=True)
    autor = baker.make(Autor, aktualna_jednostka=jednostka)
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    for rok in LATA_STAREGO_OKRESU + LATA_TESTOWEGO_OKRESU:
        IloscUdzialowDlaAutoraZaRok.objects.create(
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            uczelnia=uczelnia,
            rok=rok,
            ilosc_udzialow=Decimal("1.0"),
            ilosc_udzialow_monografie=Decimal("0.5"),
        )

    return uczelnia


def _lata_widziane_przez_widok(uczelnia):
    """Lata, które widok listy faktycznie wyciąga z bazy."""
    request = RequestFactory().get("/")
    # Podstawiamy uczelnię wprost — ``get_for_request`` czyta ten cache jako
    # pierwszy, więc omijamy rozwiązywanie domena → Site → Uczelnia.
    request._uczelnia = uczelnia

    widok = widok_listy.AutorzyLiczbaNListView()
    widok.request = request
    return sorted(widok.get_queryset().values_list("rok", flat=True))


@pytest.mark.django_db
def test_lista_udzialow_filtruje_po_okresie_domyslnym(
    uczelnia_z_udzialami_z_dwoch_okresow,
):
    uczelnia = uczelnia_z_udzialami_z_dwoch_okresow

    # Stan bazowy: bieżący OKRES_DOMYSLNY to 2022-2025.
    assert _lata_widziane_przez_widok(uczelnia) == LATA_STAREGO_OKRESU

    # A teraz sedno: po podmianie okresu widok MUSI pokazać nowe lata.
    with mock.patch.object(widok_listy, "OKRES_DOMYSLNY", OKRES_TESTOWY):
        assert _lata_widziane_przez_widok(uczelnia) == LATA_TESTOWEGO_OKRESU
