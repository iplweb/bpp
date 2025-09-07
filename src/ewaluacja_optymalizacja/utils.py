from itertools import product
from typing import Iterator, List, Union

from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Zrodla,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)


def wersje_dyscyplin(
    wzca: Union[Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor],
) -> Iterator[Union[Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor]]:
    """
    Generuje iteracje rekordu autora z różnymi wariantami przypisania dyscyplin.

    Logika:
    1. Jeśli rekord ma dyscyplina_naukowa i autor ma status "N" lub "D" w danym roku:
       - Zwraca iterację z oryginalną dyscypliną (przypieta=True)
       - Zwraca iterację BEZ dyscypliny (przypieta=False)

    2. Sprawdza czy autor ma inne dyscypliny (subdyscypliny) w tym roku
    3. Dla wydawnictw zwartych: zwraca wszystkie dodatkowe dyscypliny
    4. Dla wydawnictw ciągłych: zwraca tylko te dyscypliny, które są w Zrodlo.dyscypliny_zrodla

    Args:
        wzca: Instancja Wydawnictwo_Zwarte_Autor lub Wydawnictwo_Ciagle_Autor

    Yields:
        Kopie rekordu z różnymi wariantami przypisania dyscyplin
    """
    from copy import deepcopy

    # Pobierz rok z rekordu wydawnictwa
    rok = wzca.rekord.rok

    # Sprawdź czy rekord ma dyscyplina_naukowa
    if not wzca.dyscyplina_naukowa:
        return

    # Sprawdź status autora w danym roku (N lub D)
    try:
        autor_dyscyplina = Autor_Dyscyplina.objects.get(autor=wzca.autor, rok=rok)
    except Autor_Dyscyplina.DoesNotExist:
        return

    # Jeśli autor ma status "N" lub "D"
    if autor_dyscyplina.rodzaj_autora in ["N", "D"]:
        # 1. Zwróć rekord z oryginalną dyscypliną (przypieta=True)
        rekord_z_dyscyplina = deepcopy(wzca)
        rekord_z_dyscyplina.przypieta = True
        yield rekord_z_dyscyplina

        # 2. Zwróć rekord BEZ dyscypliny (przypieta=False)
        rekord_bez_dyscypliny = deepcopy(wzca)
        rekord_bez_dyscypliny.dyscyplina_naukowa = None
        rekord_bez_dyscypliny.przypieta = False
        yield rekord_bez_dyscypliny

        # 3. Sprawdź czy autor ma inne dyscypliny/subdyscypliny w tym roku
        inne_dyscypliny = set()

        # Główna dyscyplina
        if (
            autor_dyscyplina.dyscyplina_naukowa
            and autor_dyscyplina.dyscyplina_naukowa != wzca.dyscyplina_naukowa
        ):
            inne_dyscypliny.add(autor_dyscyplina.dyscyplina_naukowa)

        # Subdyscyplina
        if (
            autor_dyscyplina.subdyscyplina_naukowa
            and autor_dyscyplina.subdyscyplina_naukowa != wzca.dyscyplina_naukowa
        ):
            inne_dyscypliny.add(autor_dyscyplina.subdyscyplina_naukowa)

        # Dla każdej innej dyscypliny
        for inna_dyscyplina in inne_dyscypliny:
            if isinstance(wzca, Wydawnictwo_Zwarte_Autor):
                # Dla wydawnictw zwartych: zwróć wszystkie dodatkowe dyscypliny
                rekord_z_inna_dyscyplina = deepcopy(wzca)
                rekord_z_inna_dyscyplina.dyscyplina_naukowa = inna_dyscyplina
                rekord_z_inna_dyscyplina.przypieta = True
                yield rekord_z_inna_dyscyplina

            elif isinstance(wzca, Wydawnictwo_Ciagle_Autor):
                # Dla wydawnictw ciągłych: sprawdź czy dyscyplina jest w Zrodlo.dyscypliny_zrodla
                zrodlo = wzca.rekord.zrodlo
                if (
                    zrodlo
                    and Dyscyplina_Zrodla.objects.filter(
                        zrodlo=zrodlo, dyscyplina=inna_dyscyplina, rok=rok
                    ).exists()
                ):
                    rekord_z_inna_dyscyplina = deepcopy(wzca)
                    rekord_z_inna_dyscyplina.dyscyplina_naukowa = inna_dyscyplina
                    rekord_z_inna_dyscyplina.przypieta = True
                    yield rekord_z_inna_dyscyplina


def kombinacje_autorow_dyscyplin(
    rekord: Union[Wydawnictwo_Zwarte, Wydawnictwo_Ciagle],
) -> Iterator[List[Union[Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor]]]:
    """
    Generuje wszystkie możliwe kombinacje autorów z dyscyplinami dla danego rekordu.

    Funkcja:
    1. Pobiera wszystkich autorów danego rekordu
    2. Dla każdego autora wykorzystuje funkcję wersje_dyscyplin aby uzyskać wszystkie warianty
    3. Usuwa puste elementy z wyników
    4. Używa kombinatoryki (itertools.product) aby wygenerować wszystkie możliwe kombinacje

    Args:
        rekord: Instancja Wydawnictwo_Zwarte lub Wydawnictwo_Ciagle

    Yields:
        Lista reprezentująca jedną kombinację wszystkich autorów z przypisanymi dyscyplinami.
        Każda lista zawiera po jednym wariancie każdego autora z różnymi przypisaniami dyscyplin.
    """
    # Pobierz wszystkich autorów rekordu
    try:
        autorzy = rekord.autorzy_set.all()
    except AttributeError:
        # Rekord nie ma atrybutu autorzy_set (nieprawidłowy typ)
        return

    # Dla każdego autora pobierz wszystkie wersje dyscyplin
    wersje_dla_autorow = []

    for autor in autorzy:
        # Pobierz wszystkie wersje dyscyplin dla tego autora
        wersje_autora = list(wersje_dyscyplin(autor))

        # Usuń puste elementy (choć wersje_dyscyplin nie powinno ich zwracać)
        wersje_autora = [wersja for wersja in wersje_autora if wersja is not None]

        # Jeśli autor ma jakieś wersje, dodaj do listy
        if wersje_autora:
            wersje_dla_autorow.append(wersje_autora)

    # Jeśli nie ma żadnych wersji, zwróć pustą iterację
    if not wersje_dla_autorow:
        return

    # Użyj itertools.product do wygenerowania wszystkich kombinacji
    # product(*wersje_dla_autorow) generuje kartezjański iloczyn wszystkich list wersji
    for kombinacja in product(*wersje_dla_autorow):
        yield list(kombinacja)
