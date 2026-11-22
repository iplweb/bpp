"""Przyciski „Pokaż wszystkie prace (N)” i zakresów lat na stronie autora.

Liczby z ``liczby_prac_autora`` (jedno zapytanie agregujące), przycisk okresu
POST-uje „autor = X” + ``zakres_lat`` z ``cel=wyniki`` → lista wyników.
"""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from bpp.views.browse import liczby_prac_autora
from ewaluacja_common.models import OkresEwaluacji
from fixtures.conftest_publications import _wydawnictwo_ciagle_maker

pytestmark = pytest.mark.django_db


@pytest.fixture
def okresy():
    # Okresy z bazy (zasiane migracją) — test nie zakłada konkretnych lat,
    # ale potrzebuje znanych: ustawiamy je jawnie.
    OkresEwaluacji.objects.all().delete()
    return [
        OkresEwaluacji.objects.create(rok_od=2022, rok_do=2025),
        OkresEwaluacji.objects.create(rok_od=2026, rok_do=2030),
    ]


def _prace(autor, jednostka, lata):
    for rok in lata:
        praca = _wydawnictwo_ciagle_maker(rok=rok, tytul_oryginalny=f"Praca {rok}")
        praca.dodaj_autora(autor, jednostka)


def _przyciski_okresow(tresc):
    return re.findall(r'class="button hollow autor-page__okres-btn"[^>]*>([^<]*)<', tresc)


def test_liczby_prac_autora(
    okresy, autor_jan_kowalski, jednostka, statusy_korekt, typy_odpowiedzialnosci
):
    _prace(autor_jan_kowalski, jednostka, [2019, 2022, 2023, 2025, 2027])
    wynik = liczby_prac_autora(autor_jan_kowalski)
    assert wynik == {
        "wszystkie": 5,
        "okresy": [
            {"rok_od": 2022, "rok_do": 2025, "liczba": 3},
            {"rok_od": 2026, "rok_do": 2030, "liczba": 1},
        ],
    }


def test_liczby_prac_autora_dwa_zapytania(
    okresy, autor_jan_kowalski, jednostka, statusy_korekt, typy_odpowiedzialnosci
):
    """Okresy (jedno małe zapytanie) + wszystkie liczby JEDNYM agregatem —
    niezależnie od liczby okresów i prac."""
    _prace(autor_jan_kowalski, jednostka, [2022, 2023, 2027])
    OkresEwaluacji.objects.create(rok_od=2031, rok_do=2035)
    with CaptureQueriesContext(connection) as zapytania:
        liczby_prac_autora(autor_jan_kowalski)
    assert len(zapytania) == 2


def test_strona_autora_jeden_okres(
    client,
    okresy,
    autor_jan_kowalski,
    jednostka,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Prace tylko w jednym zakresie lat → jeden przycisk zakresu, z liczbą.
    Autor nie ma dyscypliny ani statusu „w N” — przyciski i tak są."""
    _prace(autor_jan_kowalski, jednostka, [2022, 2024])
    tresc = client.get(autor_jan_kowalski.get_absolute_url()).content.decode()
    assert "Pokaż wszystkie prace (2)" in tresc
    assert _przyciski_okresow(tresc) == ["2022–2025 (2)"]
    assert 'name="zakres_lat" value="[2022,2025]"' in tresc
    assert f"{autor_jan_kowalski} — prace 2022–2025" in tresc
    # Neutralne słownictwo — BPP to nie tylko ewaluacja.
    assert 'title="Prace z lat 2022–2025"' in tresc
    przyciski = tresc[tresc.index("autor-page__quick-actions") :]
    przyciski = przyciski[: przyciski.index("shaded-hr-div-small")]
    assert "ewaluac" not in przyciski.lower()


def test_strona_autora_bez_prac_w_okresach(client, okresy):
    autor = baker.make(Autor)
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "Pokaż wszystkie prace (0)" in tresc
    assert _przyciski_okresow(tresc) == []
    assert "autor-page__okresy" not in tresc


def test_post_okresu_prowadzi_do_prac_z_okresu(
    client,
    okresy,
    autor_jan_kowalski,
    jednostka,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    _prace(autor_jan_kowalski, jednostka, [2019, 2022, 2025, 2027])
    res = client.post(
        reverse("bpp:browse_build_search"),
        {
            "autor": autor_jan_kowalski.pk,
            "zakres_lat": "[2022,2025]",
            "suggested-title": "X — prace 2022–2025",
            "cel": "wyniki",
        },
    )
    assert res.status_code == 302
    assert res["Location"].endswith(reverse("multiseek:results"))

    tresc = client.get(res["Location"]).content.decode()
    assert "Praca 2022" in tresc
    assert "Praca 2025" in tresc
    assert "Praca 2019" not in tresc
    assert "Praca 2027" not in tresc


def test_liczby_prac_autora_bez_ukrytych_statusow_dla_anonima(
    okresy,
    uczelnia,
    autor_jan_kowalski,
    jednostka,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Jak w multiseeku: anonim nie liczy prac o statusie ukrytym
    w multiwyszukiwarce, zalogowany — liczy."""
    from bpp.models import Status_Korekty, Ukryj_Status_Korekty

    _prace(autor_jan_kowalski, jednostka, [2022, 2023])
    status = Status_Korekty.objects.create(nazwa="ukryty-test")
    praca = _wydawnictwo_ciagle_maker(rok=2024, status_korekty=status)
    praca.dodaj_autora(autor_jan_kowalski, jednostka)
    Ukryj_Status_Korekty.objects.create(
        uczelnia=uczelnia, status_korekty=status, multiwyszukiwarka=True
    )

    anonim = liczby_prac_autora(autor_jan_kowalski, uczelnia)
    assert anonim["wszystkie"] == 2
    assert anonim["okresy"][0]["liczba"] == 2

    zalogowany = liczby_prac_autora(autor_jan_kowalski, uczelnia, zalogowany=True)
    assert zalogowany["wszystkie"] == 3


def test_skroty_na_stronie_autora_prowadza_do_listy_prac(
    client,
    okresy,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Każdy formularz do BuildSearch na stronie autora (wszystkie prace,
    zakresy lat, rok na wykresie, statystyki wg charakteru, współautorzy)
    niesie ``cel=wyniki`` — klik prowadzi prosto do listy prac. Wyjątek:
    formularz z filtrami „Wyszukaj publikacje autora”."""
    for rok in (2022, 2023, 2027):
        praca = _wydawnictwo_ciagle_maker(rok=rok, tytul_oryginalny=f"Praca {rok}")
        praca.dodaj_autora(autor_jan_kowalski, jednostka)
        praca.dodaj_autora(autor_jan_nowak, jednostka)
    # Sekcja współautorów czyta przeliczone powiązania (powiazania_autorow).
    from powiazania_autorow.models import AuthorConnection

    baker.make(
        AuthorConnection,
        primary_author=autor_jan_kowalski,
        secondary_author=autor_jan_nowak,
        shared_publications_count=3,
    )

    tresc = client.get(autor_jan_kowalski.get_absolute_url()).content.decode()
    akcja = reverse("bpp:browse_build_search")
    formularze = [
        f
        for f in re.findall(r"<form\b.*?</form>", tresc, re.S)
        if f'action="{akcja}"' in f and "autor-page__search-form" not in f
    ]
    # Sprawdź, że są wszystkie rodzaje skrótów (inaczej test nic nie mówi).
    klasy = " ".join(re.match(r"<form\b[^>]*>", f).group(0) for f in formularze)
    assert "autor-page__quick-actions-form" in klasy
    assert "autor-page__wykres-form" in klasy
    assert any('name="charakter_formalny"' in f for f in formularze)
    assert any('name="wspolautor"' in f for f in formularze)
    for f in formularze:
        assert 'name="cel" value="wyniki"' in f, f[:300]


def test_klik_w_wspolautora_prowadzi_do_wspolnych_prac(
    client, autor_jan_kowalski, autor_jan_nowak
):
    res = client.post(
        reverse("bpp:browse_build_search"),
        {
            "autor": autor_jan_kowalski.pk,
            "wspolautor": autor_jan_nowak.pk,
            "cel": "wyniki",
        },
    )
    assert res["Location"].endswith(reverse("multiseek:results"))
