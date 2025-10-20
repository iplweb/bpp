"""
Logika biznesowa dla modułu dwudyscyplinowców.
Wyodrębniona z management command dla reużywalności.
"""

from collections import defaultdict
from decimal import Decimal

from bpp.models import Autor_Dyscyplina, Wydawnictwo_Ciagle_Autor
from bpp.models.sloty.core import CannotAdapt, ISlot


def pobierz_autorow_z_dwiema_dyscyplinami(lata=None):
    """
    Pobiera autorów z dokładnie dwiema dyscyplinami dla podanych lat.

    Args:
        lata: Lista lat do sprawdzenia. Domyślnie 2022-2025.

    Returns:
        Słownik {autor_id: {
            'autor': Autor,
            'lata': {
                rok: {
                    'dyscyplina_glowna': Dyscyplina_Naukowa,
                    'subdyscyplina': Dyscyplina_Naukowa,
                    'autor_dyscyplina': Autor_Dyscyplina
                },
                ...
            }
        }}
    """
    if lata is None:
        lata = range(2022, 2026)  # 2022-2025

    autorzy_dict = defaultdict(lambda: {"autor": None, "lata": {}})

    for rok in lata:
        # Znajdź wszystkich autorów z dokładnie dwiema dyscyplinami w danym roku
        autorzy_dyscypliny = Autor_Dyscyplina.objects.filter(rok=rok).select_related(
            "autor", "dyscyplina_naukowa", "subdyscyplina_naukowa"
        )

        for ad in autorzy_dyscypliny:
            if not ad.dwie_dyscypliny():
                continue

            autor_id = ad.autor.pk

            if autorzy_dict[autor_id]["autor"] is None:
                autorzy_dict[autor_id]["autor"] = ad.autor

            autorzy_dict[autor_id]["lata"][rok] = {
                "dyscyplina_glowna": ad.dyscyplina_naukowa,
                "subdyscyplina": ad.subdyscyplina_naukowa,
                "autor_dyscyplina": ad,
            }

    return dict(autorzy_dict)


def _oblicz_sloty_dla_publikacji(publikacja, subdyscyplina):
    """
    Oblicza sloty dla danej publikacji i subdyscypliny.

    Args:
        publikacja: Obiekt Wydawnictwo_Ciagle
        subdyscyplina: Obiekt Dyscyplina_Naukowa

    Returns:
        Decimal lub None - liczba slotów dla tej subdyscypliny
    """
    try:
        slot_kalkulator = ISlot(publikacja)
        authors_with_discipline = sum(
            1
            for wa in publikacja.autorzy_set.all()
            if (
                wa.afiliuje
                and wa.jednostka.skupia_pracownikow
                and wa.dyscyplina_naukowa == subdyscyplina
                and wa.rodzaj_autora_uwzgledniany_w_kalkulacjach_slotow()
            )
        )

        if authors_with_discipline > 0:
            autorzy_z_dyscypliny = slot_kalkulator.autorzy_z_dyscypliny(subdyscyplina)
            sloty = 1 / Decimal(1 + len(autorzy_z_dyscypliny))

            if sloty is None:
                sloty = Decimal("1") / Decimal(authors_with_discipline + 1)

            return sloty
    except (CannotAdapt, Exception):
        pass

    return None


def pobierz_publikacje_autora(autor, subdyscyplina, rok):
    """
    Pobiera publikacje ciągłe autora dla danego roku i sprawdza zgodność z subdyscypliną.

    Args:
        autor: Obiekt Autor
        subdyscyplina: Obiekt Dyscyplina_Naukowa (subdyscyplina autora)
        rok: Rok publikacji

    Returns:
        Lista słowników:
        [{
            'rekord': Wydawnictwo_Ciagle,
            'rok': int,
            'zgodna': bool,  # czy subdyscyplina jest w dyscyplinach źródła
            'sloty': Decimal lub None,  # liczba slotów dla subdyscypliny
        }, ...]
    """
    publikacje_autora = Wydawnictwo_Ciagle_Autor.objects.filter(
        autor=autor, rekord__rok=rok
    ).select_related("rekord", "rekord__zrodlo")

    wynik = []

    for pub_autor in publikacje_autora:
        publikacja = pub_autor.rekord
        zrodlo = publikacja.zrodlo

        zgodna = False

        if zrodlo:
            # Sprawdź czy subdyscyplina autora jest w dyscyplinach źródła dla tego roku
            dyscypliny_zrodla = zrodlo.dyscyplina_zrodla_set.filter(
                rok=rok, dyscyplina=subdyscyplina
            )
            zgodna = dyscypliny_zrodla.exists()

        # Oblicz sloty dla subdyscypliny
        sloty = _oblicz_sloty_dla_publikacji(publikacja, subdyscyplina)

        wynik.append(
            {
                "rekord": publikacja,
                "rok": rok,
                "zgodna": zgodna,
                "sloty": sloty,
            }
        )

    return wynik


def pobierz_publikacje_dla_wszystkich_lat(autor_data):
    """
    Pobiera wszystkie publikacje autora z wszystkich lat, w których ma dwie dyscypliny.

    Args:
        autor_data: Słownik z danymi autora z pobierz_autorow_z_dwiema_dyscyplinami

    Returns:
        Lista słowników z publikacjami (jak w pobierz_publikacje_autora)
    """
    wszystkie_publikacje = []

    for rok, dane_roku in autor_data["lata"].items():
        subdyscyplina = dane_roku["subdyscyplina"]
        publikacje = pobierz_publikacje_autora(autor_data["autor"], subdyscyplina, rok)
        wszystkie_publikacje.extend(publikacje)

    # Posortuj według roku i tytułu
    wszystkie_publikacje.sort(key=lambda p: (p["rok"], p["rekord"].tytul_oryginalny))

    return wszystkie_publikacje
