from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .core import (
    pobierz_autorow_z_dwiema_dyscyplinami,
    pobierz_publikacje_dla_wszystkich_lat,
)


@login_required
def index(request):
    """
    Widok główny modułu dwudyscyplinowców.
    Pokazuje listę autorów z dwiema dyscyplinami i ich publikacje (2022-2025).
    """
    # Pobierz wszystkich autorów z dwiema dyscyplinami
    autorzy_dict = pobierz_autorow_z_dwiema_dyscyplinami()

    # Przygotuj dane dla template
    autorzy_dane = []

    for autor_id, autor_data in autorzy_dict.items():
        # Pobierz wszystkie publikacje autora z wszystkich lat
        publikacje = pobierz_publikacje_dla_wszystkich_lat(autor_data)

        # Zlicz statystyki
        liczba_publikacji = len(publikacje)
        liczba_zgodnych = sum(1 for p in publikacje if p["zgodna"])
        liczba_niezgodnych = liczba_publikacji - liczba_zgodnych

        # Pomiń autorów bez publikacji zgodnych z subdyscypliną
        if liczba_zgodnych == 0:
            continue

        # Przygotuj stringi z dyscyplinami dla każdego roku
        dyscypliny_info = []
        for rok in sorted(autor_data["lata"].keys()):
            dane_roku = autor_data["lata"][rok]
            dyscypliny_info.append(
                {
                    "rok": rok,
                    "dyscyplina_glowna": dane_roku["dyscyplina_glowna"],
                    "subdyscyplina": dane_roku["subdyscyplina"],
                }
            )

        autorzy_dane.append(
            {
                "autor": autor_data["autor"],
                "dyscypliny_info": dyscypliny_info,
                "publikacje": publikacje,
                "liczba_publikacji": liczba_publikacji,
                "liczba_zgodnych": liczba_zgodnych,
                "liczba_niezgodnych": liczba_niezgodnych,
            }
        )

    # Posortuj autorów alfabetycznie
    autorzy_dane.sort(key=lambda a: str(a["autor"]))

    # Statystyki ogólne
    context = {
        "autorzy_dane": autorzy_dane,
        "liczba_autorow": len(autorzy_dane),
        "lata": "2022-2025",
    }

    return render(request, "ewaluacja_dwudyscyplinowcy/index.html", context)
