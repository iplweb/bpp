from typing import Iterator, Union

from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Zrodla,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)


def generate_disciplinary_iterations(
    rekord: Union[Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor],
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
        rekord: Instancja Wydawnictwo_Zwarte_Autor lub Wydawnictwo_Ciagle_Autor

    Yields:
        Kopie rekordu z różnymi wariantami przypisania dyscyplin
    """
    from copy import deepcopy

    # Pobierz rok z rekordu wydawnictwa
    if hasattr(rekord, "rekord"):
        rok = rekord.rekord.rok
    else:
        # Fallback - spróbuj przez related field
        rok = getattr(rekord.wydawnictwo_ciagle, "rok", None) or getattr(
            rekord.wydawnictwo_zwarte, "rok", None
        )

    if not rok:
        # Jeśli nie możemy określić roku, zwróć oryginalny rekord
        yield rekord
        return

    # Sprawdź czy rekord ma dyscyplina_naukowa
    if not rekord.dyscyplina_naukowa:
        yield rekord
        return

    # Sprawdź status autora w danym roku (N lub D)
    try:
        autor_dyscyplina = Autor_Dyscyplina.objects.get(autor=rekord.autor, rok=rok)

        # Jeśli autor ma status "N" lub "D"
        if autor_dyscyplina.rodzaj_autora in ["N", "D"]:
            # 1. Zwróć rekord z oryginalną dyscypliną (przypieta=True)
            rekord_z_dyscyplina = deepcopy(rekord)
            rekord_z_dyscyplina.przypieta = True
            yield rekord_z_dyscyplina

            # 2. Zwróć rekord BEZ dyscypliny (przypieta=False)
            rekord_bez_dyscypliny = deepcopy(rekord)
            rekord_bez_dyscypliny.dyscyplina_naukowa = None
            rekord_bez_dyscypliny.przypieta = False
            yield rekord_bez_dyscypliny

            # 3. Sprawdź czy autor ma inne dyscypliny/subdyscypliny w tym roku
            inne_dyscypliny = set()

            # Główna dyscyplina
            if (
                autor_dyscyplina.dyscyplina_naukowa
                and autor_dyscyplina.dyscyplina_naukowa != rekord.dyscyplina_naukowa
            ):
                inne_dyscypliny.add(autor_dyscyplina.dyscyplina_naukowa)

            # Subdyscyplina
            if (
                autor_dyscyplina.subdyscyplina_naukowa
                and autor_dyscyplina.subdyscyplina_naukowa != rekord.dyscyplina_naukowa
            ):
                inne_dyscypliny.add(autor_dyscyplina.subdyscyplina_naukowa)

            # Dla każdej innej dyscypliny
            for inna_dyscyplina in inne_dyscypliny:
                if isinstance(rekord, Wydawnictwo_Zwarte_Autor):
                    # Dla wydawnictw zwartych: zwróć wszystkie dodatkowe dyscypliny
                    rekord_z_inna_dyscyplina = deepcopy(rekord)
                    rekord_z_inna_dyscyplina.dyscyplina_naukowa = inna_dyscyplina
                    rekord_z_inna_dyscyplina.przypieta = True
                    yield rekord_z_inna_dyscyplina

                elif isinstance(rekord, Wydawnictwo_Ciagle_Autor):
                    # Dla wydawnictw ciągłych: sprawdź czy dyscyplina jest w Zrodlo.dyscypliny_zrodla
                    zrodlo = rekord.wydawnictwo_ciagle.zrodlo
                    if (
                        zrodlo
                        and Dyscyplina_Zrodla.objects.filter(
                            zrodlo=zrodlo, dyscyplina=inna_dyscyplina, rok=rok
                        ).exists()
                    ):
                        rekord_z_inna_dyscyplina = deepcopy(rekord)
                        rekord_z_inna_dyscyplina.dyscyplina_naukowa = inna_dyscyplina
                        rekord_z_inna_dyscyplina.przypieta = True
                        yield rekord_z_inna_dyscyplina
        else:
            # Jeśli autor nie ma statusu "N" lub "D", zwróć oryginalny rekord
            yield rekord

    except Autor_Dyscyplina.DoesNotExist:
        # Jeśli brak danych o autorze w danym roku, zwróć oryginalny rekord
        yield rekord
