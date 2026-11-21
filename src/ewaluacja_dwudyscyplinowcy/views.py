from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ewaluacja_common.okres import okres_dla_request

from .core import (
    pobierz_autorow_z_dwiema_dyscyplinami,
    pobierz_publikacje_dla_wszystkich_lat,
)


@login_required
def index(request):
    """
    Widok główny modułu dwudyscyplinowców.
    Pokazuje listę autorów z dwiema dyscyplinami i ich publikacje w okresie ewaluacji wybranym
    na pasku okresu (domyślnie: okres obejmujący bieżący rok).
    """
    # Pobierz wszystkich autorów z dwiema dyscyplinami
    okres = okres_dla_request(request)
    autorzy_dict = pobierz_autorow_z_dwiema_dyscyplinami(
        lata=okres.lata if okres is not None else []
    )

    # Przygotuj dane dla template
    autorzy_dane = []

    for autor_data in autorzy_dict.values():
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
        "lata": str(okres) if okres is not None else "—",
    }

    return render(request, "ewaluacja_dwudyscyplinowcy/index.html", context)
