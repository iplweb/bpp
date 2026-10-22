"""Kontrakt: strona potwierdzenia kasowania NIE wypisuje wszystkiego, co
poleci kaskadą.

``BaseBppAdminMixin.delete_confirmation_max_display`` (Django >= 6.1) tnie
wyliczankę obiektów zależnych do 100 pozycji i dokleja na końcu „…i N innych
obiektów". Dla ``Autor``, ``Zrodlo`` czy masowego ``delete_selected`` na
przefiltrowanej changeliście różnica to kilkanaście MB HTML-a, którego
przeglądarka i tak nie renderuje sensownie.

Testy tutaj pilnują rzeczy, których łatwo NIE zauważyć:

1. sama wartość jest sensowna z punktu widzenia Django (``admin.E041``),
2. obcinanie NAPRAWDĘ się dzieje na wyrenderowanej stronie — a to wcale nie
   wynika z ustawienia atrybutu. Aktywną skórką admina jest grappelli, której
   szablony renderują listę filtrem ``|unordered_list`` (bez obcinania).
   Gdyby ktoś skasował nadpisania z ``src/django_bpp/templates/admin/``,
   atrybut zostałby ustawiony, checki Django przeszłyby — a strona dalej
   wypisywałaby wszystko. Dlatego testujemy przez klienta HTTP, na realnym
   łańcuchu szablonów, a nie przez ``assert admin.delete_confirmation_max_display``,
3. obcinana jest WYŁĄCZNIE wyliczanka obiektów. Sekcja „Podsumowanie"
   (pełne liczniki per model) i lista blokad ``protected`` (w BPP niosąca
   ręcznie pisane komunikaty ``JednostkaAdmin.get_deleted_objects``) muszą
   zostać nietknięte — inaczej obcinanie ukrywałoby informacje, po które
   użytkownik na tę stronę przyszedł.
"""

import re
from unittest import mock

import pytest
from django.contrib import admin as dj_admin
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.translation import ngettext
from model_bakery import baker

from bpp.admin.core import MAKSYMALNA_LICZBA_OBIEKTOW_NA_STRONIE_KASOWANIA
from bpp.admin.jednostka import JednostkaAdmin
from bpp.admin.wydawnictwo_ciagle import Wydawnictwo_CiagleAdmin
from bpp.models import (
    Autor,
    BppUser,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

LICZBA_AUTOROW = 6
"""Ilu autorów doczepiamy do rekordu w testach obcinania.

Musi być zauważalnie większa od podstawianego limitu (2), żeby różnica
„z limitem / bez limitu" była jednoznaczna, i na tyle mała, żeby test nie
kosztował sekundy na samym zapisie do bazy.
"""

LIMIT_TESTOWY = 2
"""Limit podstawiany na czas testu. Produkcyjnych 100 nie da się sensownie
sprawdzić bez tworzenia >100 obiektów — a testujemy MECHANIZM, nie liczbę
(liczbę pilnuje ``test_wartosc_limitu_jest_ta_udokumentowana``)."""


@pytest.fixture
def administracja_client(client, db):
    """Zalogowany superuser w grupie ``administracja`` — obie przesłanki
    ``has_delete_permission`` w adminach BPP spełnione naraz."""
    grupa, _ = Group.objects.get_or_create(name="administracja")
    user = baker.make(BppUser, is_superuser=True, is_staff=True)
    user.groups.add(grupa)
    client.force_login(user)
    return client


@pytest.fixture
def ciagle_z_autorami(wydawnictwo_ciagle, jednostka) -> tuple[Wydawnictwo_Ciagle, list]:
    """Rekord z ``LICZBA_AUTOROW`` powiązaniami autorów.

    Nazwiska są unikalne i „nieżyciowe", żeby dało się je jednoznacznie
    wyszukać w HTML-u strony potwierdzenia (``Wydawnictwo_Ciagle_Autor.__str__``
    zaczyna się od ``str(autor)``)."""
    nazwiska = []
    for i in range(LICZBA_AUTOROW):
        nazwisko = f"Obcinalski{i:02d}"
        autor = baker.make(Autor, nazwisko=nazwisko, imiona="Test")
        wydawnictwo_ciagle.dodaj_autora(autor, jednostka)
        nazwiska.append(nazwisko)
    return wydawnictwo_ciagle, nazwiska


def _widoczne(nazwiska: list[str], html: str) -> list[str]:
    return [nazwisko for nazwisko in nazwiska if nazwisko in html]


def _komunikat_o_ukrytych(html: str) -> int | None:
    """Zwraca liczbę obiektów zgłoszonych jako ukryte, albo ``None``.

    Wzorzec budujemy z ``ngettext`` zamiast wpisywać tekst na sztywno — dzięki
    temu test nie pęknie, gdy Django dorzuci polskie tłumaczenie tego (nowego
    w 6.1) komunikatu."""
    szablon = ngettext(
        "…and %(count)d more object.",
        "…and %(count)d more objects.",
        LICZBA_AUTOROW,
    )
    wzorzec = re.escape(szablon).replace(re.escape("%(count)d"), r"(\d+)")
    dopasowanie = re.search(wzorzec, html)
    return int(dopasowanie.group(1)) if dopasowanie else None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model", [Autor, Jednostka, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte]
)
def test_opcja_przechodzi_walidacje_django(model):
    """Django waliduje tę opcję własnym checkiem (``admin.E041``: musi być
    nieujemnym intem albo ``None``). Odpalamy checki admina w całości, więc
    test złapie też przypadek, w którym ktoś wpisze tam np. string albo -1.

    Sięgamy po ZAREJESTROWANĄ instancję admina, a nie po klasę — dopiero ona
    ma podpięty model i realny ``admin_site``."""
    bledy = [b.id for b in dj_admin.site.get_model_admin(model).check()]
    assert "admin.E041" not in bledy, bledy


def test_wartosc_limitu_jest_ta_udokumentowana():
    """Wartość jest uzasadniona (2× ``list_per_page``, przykład z docstringu
    filtra Django) — jeżeli ktoś ją zmienia, ma zaktualizować uzasadnienie
    przy stałej w ``bpp/admin/core.py``, a nie tylko liczbę."""
    assert MAKSYMALNA_LICZBA_OBIEKTOW_NA_STRONIE_KASOWANIA == 100
    assert Wydawnictwo_CiagleAdmin.delete_confirmation_max_display == (
        MAKSYMALNA_LICZBA_OBIEKTOW_NA_STRONIE_KASOWANIA
    )


@pytest.mark.django_db
def test_lista_obiektow_zaleznych_jest_obcinana(
    administracja_client, ciagle_z_autorami
):
    """Realna strona potwierdzenia (szablon grappelli + nadpisanie BPP)
    pokazuje MNIEJ obiektów, niż jest do skasowania, i mówi ile ukryła."""
    wydawnictwo, nazwiska = ciagle_z_autorami
    url = reverse("admin:bpp_wydawnictwo_ciagle_delete", args=(wydawnictwo.pk,))

    with mock.patch.object(
        Wydawnictwo_CiagleAdmin, "delete_confirmation_max_display", LIMIT_TESTOWY
    ):
        html = administracja_client.get(url).content.decode()

    widoczne = _widoczne(nazwiska, html)
    assert len(widoczne) < LICZBA_AUTOROW, (
        "Lista nie została obcięta — sprawdź, czy nadpisania szablonów w "
        "src/django_bpp/templates/admin/ nadal używają "
        "|truncated_unordered_list:delete_confirmation_max_display"
    )

    ukryte = _komunikat_o_ukrytych(html)
    assert ukryte, "Brak informacji o tym, ile obiektów ukryto"


@pytest.mark.django_db
def test_bez_limitu_lista_jest_pelna(administracja_client, ciagle_z_autorami):
    """Kontrola negatywna: ``None`` = „bez ograniczeń" (zachowanie sprzed
    Django 6.1). Bez tego testu poprzedni przechodziłby również wtedy, gdyby
    szablon gubił obiekty z zupełnie innego powodu."""
    wydawnictwo, nazwiska = ciagle_z_autorami
    url = reverse("admin:bpp_wydawnictwo_ciagle_delete", args=(wydawnictwo.pk,))

    with mock.patch.object(
        Wydawnictwo_CiagleAdmin, "delete_confirmation_max_display", None
    ):
        html = administracja_client.get(url).content.decode()

    assert _widoczne(nazwiska, html) == nazwiska
    assert _komunikat_o_ukrytych(html) is None


@pytest.mark.django_db
def test_podsumowanie_pokazuje_pelne_liczniki(administracja_client, ciagle_z_autorami):
    """Obcinamy wyliczankę, ale NIE liczniki.

    To jest cała przesłanka, dla której obcinanie jest bezpieczne: sekcja
    „Podsumowanie" nad listą (``model_count``) nadal podaje dokładnie, ile
    obiektów każdego typu zniknie."""
    wydawnictwo, nazwiska = ciagle_z_autorami
    url = reverse("admin:bpp_wydawnictwo_ciagle_delete", args=(wydawnictwo.pk,))

    with mock.patch.object(
        Wydawnictwo_CiagleAdmin, "delete_confirmation_max_display", LIMIT_TESTOWY
    ):
        html = administracja_client.get(url).content.decode()

    etykieta = str(wydawnictwo.autorzy_set.model._meta.verbose_name_plural).capitalize()
    assert f"{etykieta}: {LICZBA_AUTOROW}" in html


@pytest.mark.django_db
def test_kasowanie_masowe_tez_obcina(administracja_client, ciagle_z_autorami):
    """``delete_selected`` renderuje INNY szablon
    (``admin/delete_selected_confirmation.html``) i to tam obcinanie boli
    najbardziej — zaznaczenie całej changelisty wciąga wszystkie kaskady
    naraz. Osobny szablon = osobny test."""
    wydawnictwo, nazwiska = ciagle_z_autorami

    with mock.patch.object(
        Wydawnictwo_CiagleAdmin, "delete_confirmation_max_display", LIMIT_TESTOWY
    ):
        html = administracja_client.post(
            reverse("admin:bpp_wydawnictwo_ciagle_changelist"),
            {"action": "delete_selected", "_selected_action": [wydawnictwo.pk]},
        ).content.decode()

    assert len(_widoczne(nazwiska, html)) < LICZBA_AUTOROW
    assert _komunikat_o_ukrytych(html)


@pytest.mark.django_db
def test_lista_blokad_nie_jest_obcinana(administracja_client, jednostka: Jednostka):
    """``protected`` renderujemy BEZ obcinania — świadomie.

    ``JednostkaAdmin.get_deleted_objects`` dokłada tam własny komunikat
    („nie można usunąć, bo są przypięte…") na KOŃCU listy. Gdyby obcinanie
    objęło też ``protected``, przy dłuższej liście blokad zniknąłby dokładnie
    ten komunikat, który tłumaczy użytkownikowi, co ma zrobić."""
    jednostka.dodaj_autora(baker.make(Autor))
    url = reverse("admin:bpp_jednostka_delete", args=(jednostka.pk,))

    # Limit 1 — gdyby dotyczył ``protected``, komunikat BPP wypadłby z listy.
    with mock.patch.object(JednostkaAdmin, "delete_confirmation_max_display", 1):
        html = administracja_client.get(url).content.decode()

    assert "nie można usunąć" in html
