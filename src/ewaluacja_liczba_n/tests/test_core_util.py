from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Cache_Punktacja_Autora_Query,
    Charakter_Formalny,
    Wydawnictwo_Ciagle,
)
from ewaluacja_common.utils import get_lista_prac
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok, LiczbaNDlaUczelni


def test_get_lista_prac_zakres_lat(
    autor_jan_nowak,
    dyscyplina1,
    jednostka,
    uczelnia,
    denorms,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    rodzaj_autora_n,
):
    """Sprawdza, czy lista prac odrzuca prace spoza zakresu 2022-2026"""

    # Dane testowe 2020-2026: dwa lata przed zakresem wystarczą, żeby
    # sprawdzić odcięcie dolnej granicy (wcześniej od 2015).

    LiczbaNDlaUczelni.objects.create(
        dyscyplina_naukowa=dyscyplina1, uczelnia=uczelnia, liczba_n=100
    )

    # Get a proper charakter_formalny with non-null charakter_ogolny
    charakter_formalny = Charakter_Formalny.objects.filter(
        charakter_ogolny__isnull=False
    ).first()

    for ROK in range(2020, 2027):
        # ``rodzaj_autora`` z ``licz_sloty=True`` jest niezbędny: bez niego
        # autor nie wchodzi do kalkulacji slotów, ``IPunktacjaCacher`` nie
        # zapisuje ``Cache_Punktacja_Autora`` i ``get_lista_prac`` nie ma
        # czego zwrócić.
        Autor_Dyscyplina.objects.create(
            autor=autor_jan_nowak,
            rok=ROK,
            dyscyplina_naukowa=dyscyplina1,
            rodzaj_autora=rodzaj_autora_n,
        )

        # Create IloscUdzialowDlaAutoraZaRok only for years 2022-2026
        if 2022 <= ROK <= 2026:
            IloscUdzialowDlaAutoraZaRok.objects.create(
                autor=autor_jan_nowak,
                rok=ROK,
                ilosc_udzialow=1,
                ilosc_udzialow_monografie=1,
                dyscyplina_naukowa=dyscyplina1,
            )

        wc: Wydawnictwo_Ciagle = baker.make(
            Wydawnictwo_Ciagle,
            rok=ROK,
            punkty_kbn=5,
            tytul_oryginalny=f"Test 123 - praca za rok {ROK}",
            charakter_formalny=charakter_formalny,
        )
        wc.dodaj_autora(autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1)

    denorms.flush()

    # Cache musi obejmować WSZYSTKIE lata 2020-2026 — inaczej test nie
    # sprawdzałby odcięcia zakresu, bo prac spoza zakresu i tak by nie było.
    lata_w_cache = set(
        Cache_Punktacja_Autora_Query.objects.filter(
            dyscyplina=dyscyplina1, autor=autor_jan_nowak
        ).values_list("rekord__rok", flat=True)
    )
    assert lata_w_cache == set(range(2020, 2027))

    lista = list(get_lista_prac(dyscyplina1.nazwa))
    assert sorted(praca.rok for praca in lista) == [2022, 2023, 2024, 2025, 2026]
