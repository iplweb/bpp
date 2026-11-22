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
    return [
        f"{lata} ({liczba})"
        for lata, liczba in re.findall(
            r'class="przycisk-prac__pozycja przycisk-prac__pozycja--okres"[^>]*>'
            r"<span>Prace z lat ([^<]*)</span>"
            r'<span class="przycisk-prac__liczba">(\d+)</span>',
            tresc,
        )
    ]


def test_liczby_prac_autora(
    okresy, autor_jan_kowalski, jednostka, statusy_korekt, typy_odpowiedzialnosci
):
    _prace(autor_jan_kowalski, jednostka, [2019, 2022, 2023, 2025, 2027])
    # Każda praca testowa dostaje własny (losowy) charakter formalny.
    nazwy = sorted(
        autor_jan_kowalski.wydawnictwo_ciagle_set.values_list(
            "charakter_formalny__nazwa", flat=True
        )
    )
    wynik = liczby_prac_autora(autor_jan_kowalski)
    # Przy równych liczbach kolejność zależy od sortowania nazw w bazie.
    wynik["charaktery"].sort(key=lambda c: c["nazwa"])
    # Losowe charaktery testowe nie są ani publikacją, ani streszczeniem.
    assert wynik.pop("typy") == [{"nazwa": "inne", "liczba": 5}]
    assert wynik.pop("ma_menu") is True
    assert wynik == {
        "wszystkie": 5,
        "okresy": [
            {"rok_od": 2022, "rok_do": 2025, "liczba": 3},
            {"rok_od": 2026, "rok_do": 2030, "liczba": 1},
        ],
        "charaktery": [{"nazwa": nazwa, "liczba": 1} for nazwa in nazwy],
    }


def test_liczby_prac_autora_trzy_zapytania(
    okresy, autor_jan_kowalski, jednostka, statusy_korekt, typy_odpowiedzialnosci
):
    """Okresy (jedno małe zapytanie) + wszystkie liczby JEDNYM agregatem +
    najliczniejsze charaktery (jedno grupujące) — niezależnie od liczby
    okresów i prac."""
    _prace(autor_jan_kowalski, jednostka, [2022, 2023, 2027])
    OkresEwaluacji.objects.create(rok_od=2031, rok_do=2035)
    with CaptureQueriesContext(connection) as zapytania:
        liczby_prac_autora(autor_jan_kowalski)
    assert len(zapytania) == 3


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
    assert "przycisk-prac__menu" not in tresc


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


def test_menu_przycisku_ma_typy_charaktery_i_link_do_filtrow(
    client, okresy, autor_jan_kowalski, jednostka, statusy_korekt, typy_odpowiedzialnosci
):
    _prace(autor_jan_kowalski, jednostka, [2022, 2023])
    charakter = autor_jan_kowalski.wydawnictwo_ciagle_set.first().charakter_formalny
    tresc = client.get(
        reverse("bpp:browse_autor", args=(autor_jan_kowalski.slug,))
    ).content.decode()
    assert "Według typu" in tresc
    assert 'name="typ" value="inne"' in tresc
    assert "Według charakteru" in tresc
    assert f'name="charakter_formalny" value="{charakter.nazwa}"' in tresc
    assert 'href="#wyszukaj-publikacje-autora"' in tresc


def test_post_charakteru_prowadzi_do_prac_o_tym_charakterze(
    client, okresy, autor_jan_kowalski, jednostka, statusy_korekt, typy_odpowiedzialnosci
):
    _prace(autor_jan_kowalski, jednostka, [2022])
    charakter = autor_jan_kowalski.wydawnictwo_ciagle_set.first().charakter_formalny
    res = client.post(
        reverse("bpp:browse_build_search"),
        {
            "autor": autor_jan_kowalski.pk,
            "charakter_formalny": charakter.nazwa,
            "cel": "wyniki",
        },
    )
    assert res.status_code == 302
    assert "Praca 2022" in client.get(res["Location"]).content.decode()


def test_strona_jednostki_ma_przycisk_z_menu(
    client, okresy, autor_jan_kowalski, jednostka, statusy_korekt, typy_odpowiedzialnosci
):
    """Jednostka (i wydział — ten sam szablon) ma ten sam przycisk z menu,
    zawężony do jednostki zamiast autora."""
    _prace(autor_jan_kowalski, jednostka, [2022, 2023, 2027])
    tresc = client.get(
        reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    ).content.decode()
    assert "Pokaż wszystkie publikacje (3)" in tresc
    assert _przyciski_okresow(tresc) == ["2022–2025 (2)", "2026–2030 (1)"]
    assert "Według typu" in tresc
    assert "Według charakteru" in tresc
    menu = tresc[tresc.index("przycisk-prac__menu") :]
    assert f'name="jednostka" value="{jednostka.pk}"' in menu
    assert 'name="autor"' not in menu[: menu.index("</details>")]


def test_post_okresu_jednostki_prowadzi_do_jej_prac_z_okresu(
    client, okresy, autor_jan_kowalski, jednostka, statusy_korekt, typy_odpowiedzialnosci
):
    _prace(autor_jan_kowalski, jednostka, [2019, 2022])
    res = client.post(
        reverse("bpp:browse_build_search"),
        {"jednostka": jednostka.pk, "zakres_lat": "[2022,2025]", "cel": "wyniki"},
    )
    assert res.status_code == 302
    tresc = client.get(res["Location"]).content.decode()
    assert "Praca 2022" in tresc
    assert "Praca 2019" not in tresc
