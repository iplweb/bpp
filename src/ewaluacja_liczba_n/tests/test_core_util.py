from model_bakery import baker

from bpp.models import Autor_Dyscyplina, Wydawnictwo_Ciagle
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
    """Sprawdza, czy lista prac odrzuca prace spoza okresu ewaluacji 2022-2025"""
    from bpp.models import Charakter_Formalny

    # Dane testowe od 2015 do 2026 — z zapasem po OBU stronach okresu
    # ewaluacji, żeby test wyłapał zjechanie zarówno dolnej, jak i górnej
    # granicy zakresu.

    LiczbaNDlaUczelni.objects.create(
        dyscyplina_naukowa=dyscyplina1, uczelnia=uczelnia, liczba_n=100
    )

    # Get a proper charakter_formalny with non-null charakter_ogolny
    charakter_formalny = Charakter_Formalny.objects.filter(
        charakter_ogolny__isnull=False
    ).first()

    for ROK in range(2015, 2027):
        # rodzaj_autora jest OBOWIĄZKOWY: bez rodzaju z ``licz_sloty=True``
        # ``SlotMixin.autorzy_z_dyscypliny`` pomija autora, przez co rekord
        # nie trafia do ``Cache_Punktacja_Autora`` i test nie ma czego badać.
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
            # 5 pkt wpada w próg 3 kalkulatora slotów, ale DOPIERO od 2017 r.
            # (patrz ``bpp.models.sloty.core._dopasuj_kalkulator``); lata
            # 2015-2016 nie dają się przeliczyć i cache ich nie zawiera —
            # to nie szkodzi, bo i tak są poza okresem ewaluacji.
            punkty_kbn=5,
            tytul_oryginalny=f"Test 123 - praca za rok {ROK}",
            charakter_formalny=charakter_formalny,
        )
        wc.dodaj_autora(autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1)

    denorms.flush()

    # Bez wpisów w cache test nie badałby niczego — sprawdzamy to JAWNIE,
    # zamiast (jak dawniej) po cichu robić ``pytest.skip``, przez co asercja
    # niżej nigdy się nie wykonywała.
    from bpp.models import Cache_Punktacja_Autora_Query

    assert Cache_Punktacja_Autora_Query.objects.filter(
        dyscyplina__nazwa=dyscyplina1.nazwa, autor=autor_jan_nowak
    ).exists(), "Cache_Punktacja_Autora_Query pusty — test nie ma czego sprawdzać"

    # Asercja na KONKRETNYCH latach, nie na samej ich liczbie: gdyby zakres
    # zjechał o rok w którąkolwiek stronę (np. 2023-2026), sama liczba prac
    # nadal wynosiłaby 4 i test by tego nie zauważył.
    lata = sorted(praca.rok for praca in get_lista_prac(dyscyplina1.nazwa))
    assert lata == [2022, 2023, 2024, 2025]
