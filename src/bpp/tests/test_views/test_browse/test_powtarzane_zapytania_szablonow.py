"""Testy liczby zapytań dla publicznych stron: rekordu, jednostki, autora.

Szablony tych stron wielokrotnie odwoływały się do tych samych METOD modelu
(``autorzy_dla_opisu``, ``pracownicy``, ``wspolpracowali``,
``liczba_cytowan``, ``jednostki_gdzie_ma_publikacje``), a każde odwołanie
budowało świeży, niezmaterializowany QuerySet — czyli osobny roundtrip do
bazy. Te testy pilnują, żeby każdy taki zestaw danych był pobierany raz.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, RodzajJednostki
from bpp.models.autor import Funkcja_Autora
from bpp.models.fields import OpcjaWyswietlaniaField
from bpp.tests.util import any_ciagle


def _queries(ctx, fragment):
    """Zapytania, których SQL zawiera podany fragment (nazwę tabeli)."""
    return [q["sql"] for q in ctx.captured_queries if fragment in q["sql"]]


def _dodaj_autorow(wydawnictwo_ciagle, jednostka, ile):
    for i in range(ile):
        autor = baker.make(Autor, nazwisko=f"Nazwisko{i:03d}", imiona="Imię")
        wydawnictwo_ciagle.dodaj_autora(
            autor,
            jednostka,
            zapisany_jako=f"Nazwisko{i:03d} Imię",
            kolejnosc=i,
        )


@pytest.mark.django_db
def test_strona_rekordu_autorzy_pobierani_raz(client, uczelnia, wydawnictwo_ciagle):
    """Strona rekordu ma pobrać listę autorów JEDNYM zapytaniem."""
    jednostka = baker.make(Jednostka, uczelnia=uczelnia, skupia_pracownikow=True)
    _dodaj_autorow(wydawnictwo_ciagle, jednostka, 6)

    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
            wydawnictwo_ciagle.pk,
        ),
    )

    with CaptureQueriesContext(connection) as ctx:
        res = client.get(url, follow=True)

    assert res.status_code == 200
    # Interesuje nas queryset z autorzy_dla_opisu(), czyli ten z JOIN-em
    # na bpp_autor + bpp_typ_odpowiedzialnosci. (Pozostałe zapytania do tej
    # tabeli — EXISTS-y ma_procenty / odpiete_dyscypliny — to co innego.)
    autorzy = [
        q
        for q in _queries(ctx, "bpp_wydawnictwo_ciagle_autor")
        if "bpp_typ_odpowiedzialnosci" in q
    ]
    assert len(autorzy) == 1, f"{len(autorzy)} zapytań o autorów:\n" + "\n".join(
        autorzy
    )


@pytest.mark.django_db
def test_strona_rekordu_streszczenia_pobierane_raz(
    client, uczelnia, wydawnictwo_ciagle
):
    """Streszczenia rekordu mają być pobrane jednym zapytaniem."""
    jednostka = baker.make(Jednostka, uczelnia=uczelnia, skupia_pracownikow=True)
    _dodaj_autorow(wydawnictwo_ciagle, jednostka, 2)

    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
            wydawnictwo_ciagle.pk,
        ),
    )

    with CaptureQueriesContext(connection) as ctx:
        res = client.get(url, follow=True)

    assert res.status_code == 200
    # PRZED: 6 zapytań (3x EXISTS + 2x SELECT + 1x COUNT). PO: 1 prefetch.
    streszczenia = _queries(ctx, "bpp_wydawnictwo_ciagle_streszczenie")
    assert len(streszczenia) == 1, (
        f"{len(streszczenia)} zapytań o streszczenia:\n" + "\n".join(streszczenia)
    )


@pytest.mark.django_db
def test_strona_jednostki_pracownicy_bez_powtorzen(client, uczelnia):
    """Lista pracowników i współpracowników — bez powtarzanych zapytań
    i bez N+1 na ``autor.aktualna_funkcja``."""
    jednostka = baker.make(
        Jednostka, uczelnia=uczelnia, skupia_pracownikow=True, widoczna=True
    )
    funkcja = baker.make(Funkcja_Autora, pokazuj_za_nazwiskiem=True)
    for i in range(12):
        autor = baker.make(
            Autor,
            nazwisko=f"Pracownik{i:03d}",
            imiona="Imię",
            aktualna_jednostka=jednostka,
            aktualna_funkcja=funkcja,
            pokazuj=True,
        )
        baker.make(
            Autor_Jednostka,
            autor=autor,
            jednostka=jednostka,
            podstawowe_miejsce_pracy=True,
        )

    with CaptureQueriesContext(connection) as ctx:
        res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))

    assert res.status_code == 200

    # bpp_autor — PRZED: 9, PO: 4 (kierownik jednostki, PK aktualnych
    # autorów, lista pracowników, lista współpracowników).
    autorzy = _queries(ctx, 'FROM "bpp_autor"')
    assert len(autorzy) <= 4, f"{len(autorzy)} zapytań o autorów:\n" + "\n".join(
        autorzy
    )

    # aktualna_funkcja ma być dociągnięta przez select_related, nie N+1
    # (strażnik na wypadek, gdyby ktoś usunął select_related z pracownicy())
    funkcje = _queries(ctx, 'FROM "bpp_funkcja_autora"')
    assert len(funkcje) == 0, f"N+1 na aktualna_funkcja:\n" + "\n".join(funkcje)

    # PRZED: 4 (aktualni_autorzy() liczone od nowa dla pracownicy()
    # i wspolpracowali(), każde po 3 wywołania z szablonu). PO: 1.
    aj = _queries(ctx, 'FROM "bpp_autor_jednostka"')
    assert len(aj) == 1, f"{len(aj)} zapytań o Autor_Jednostka:\n" + "\n".join(aj)


@pytest.mark.django_db
def test_strona_jednostki_podjednostki_bez_powtorzen(client, uczelnia):
    """Podjednostki (aktualne / koła / historyczne) — po jednym zapytaniu."""
    # rodzaj z 'pokazuj_strukture_podjednostek' => strona w stylu wydziałowym,
    # czyli ta z sekcjami podjednostek
    rodzaj = baker.make(RodzajJednostki, pokazuj_strukture_podjednostek=True)
    jednostka = baker.make(
        Jednostka,
        uczelnia=uczelnia,
        rodzaj=rodzaj,
        skupia_pracownikow=True,
        widoczna=True,
    )
    for i in range(4):
        baker.make(
            Jednostka,
            uczelnia=uczelnia,
            parent=jednostka,
            wydzial=jednostka,
            widoczna=True,
            aktualna=True,
            zarzadzaj_automatycznie=False,
        )

    assert jednostka.aktualne_podjednostki().count() == 4

    with CaptureQueriesContext(connection) as ctx:
        res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))

    assert res.status_code == 200

    # {% with %} nie może "zgubić" danych — sekcja z podjednostkami i jej
    # licznik mają się nadal renderować.
    tresc = res.content.decode()
    assert "Jednostki aktualne" in tresc
    assert ">4<" in tresc

    # Trzy kategorie podjednostek (aktualne / koła / historyczne) — po jednym
    # zapytaniu na kategorię. PRZED: 16 (widok liczył je raz, a szablon jeszcze
    # trzy razy każdą: nawigacja, licznik w nagłówku, pętla — plus 3 EXISTS-y
    # z wymaga_nawigacji()). PO: 5.
    podjednostki = _queries(ctx, 'FROM "bpp_jednostka"')
    assert len(podjednostki) <= 5, (
        f"{len(podjednostki)} zapytań o podjednostki:\n" + "\n".join(podjednostki)
    )


@pytest.mark.django_db
def test_strona_autora_agregaty_liczone_raz(
    client, uczelnia, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    """``liczba_cytowan`` i ``jednostki_gdzie_ma_publikacje`` — po jednym
    zapytaniu, a ``metryki.count`` nie może być liczone w pętli."""
    from ewaluacja_metryki.models import MetrykaAutora

    uczelnia.pokazuj_liczbe_cytowan_na_stronie_autora = (
        OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    )
    uczelnia.save()

    # realistyczne dane: kilka prac z cytowaniami + kilka metryk
    for rok in (2020, 2021, 2022):
        praca = any_ciagle(rok=rok, liczba_cytowan=10)
        praca.dodaj_autora(autor_jan_kowalski, jednostka)

    for _ in range(3):
        baker.make(MetrykaAutora, autor=autor_jan_kowalski)

    with CaptureQueriesContext(connection) as ctx:
        res = client.get(reverse("bpp:browse_autor", args=(autor_jan_kowalski.slug,)))

    assert res.status_code == 200

    # ciężki agregat SUM(liczba_cytowan) po bpp_rekord_mat — maks. 2 razy
    # (liczba_cytowan + liczba_cytowan_afiliowane), nie 3.
    cytowania = [q for q in _queries(ctx, "bpp_rekord_mat") if "SUM(" in q.upper()]
    assert len(cytowania) <= 2, f"{len(cytowania)} agregatów cytowań:\n" + "\n".join(
        cytowania
    )

    # metryki: 1 EXISTS + 1 SELECT; COUNT w pętli po metrykach = regresja
    # PRZED: 5 (EXISTS + SELECT + COUNT dla każdej z 3 metryk). PO: 1.
    metryki = _queries(ctx, "ewaluacja_metryki_metrykaautora")
    assert len(metryki) == 1, f"{len(metryki)} zapytań o metryki:\n" + "\n".join(
        metryki
    )

    # jednostki_gdzie_ma_publikacje — raz, nie dwa razy
    jgmp = [
        q for q in _queries(ctx, "bpp_autorzy_mat") if 'FROM "bpp_jednostka"' in q
    ]
    assert len(jgmp) == 1, f"{len(jgmp)} zapytań o jednostki autora:\n" + "\n".join(
        jgmp
    )
