from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PrzemapoaniePracAutoraForm
from .models import PrzemapoaniePracAutora

from django.contrib import messages
from django.contrib.auth.decorators import login_required

from bpp.models import Autor, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor


@login_required
def wybierz_autora(request):
    """Widok do wyszukiwania i wyboru autora do przemapowania prac"""
    autorzy = None
    search_query = request.GET.get("q", "")

    if search_query:
        # Wyszukaj autorów po nazwisku lub imieniu
        autorzy = Autor.objects.filter(
            Q(nazwisko__icontains=search_query) | Q(imiona__icontains=search_query)
        ).order_by("nazwisko", "imiona")[
            :50
        ]  # Ogranicz do 50 wyników

    context = {
        "search_query": search_query,
        "autorzy": autorzy,
    }
    return render(request, "przemapuj_prace_autora/wybierz_autora.html", context)


@login_required
def przemapuj_prace(request, autor_id):
    """Główny widok do przemapowania prac autora między jednostkami"""
    autor = get_object_or_404(Autor, pk=autor_id)

    # Zbierz statystyki o pracach autora w różnych jednostkach
    prace_ciagle_stats = (
        Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor)
        .values("jednostka__id", "jednostka__nazwa", "jednostka__skrot")
        .annotate(liczba=Count("id"))
        .order_by("jednostka__nazwa")
    )

    prace_zwarte_stats = (
        Wydawnictwo_Zwarte_Autor.objects.filter(autor=autor)
        .values("jednostka__id", "jednostka__nazwa", "jednostka__skrot")
        .annotate(liczba=Count("id"))
        .order_by("jednostka__nazwa")
    )

    # Połącz statystyki
    stats_dict = {}
    for stat in prace_ciagle_stats:
        jednostka_id = stat["jednostka__id"]
        if jednostka_id not in stats_dict:
            stats_dict[jednostka_id] = {
                "jednostka_nazwa": stat["jednostka__nazwa"],
                "jednostka_skrot": stat["jednostka__skrot"],
                "prace_ciagle": 0,
                "prace_zwarte": 0,
            }
        stats_dict[jednostka_id]["prace_ciagle"] = stat["liczba"]

    for stat in prace_zwarte_stats:
        jednostka_id = stat["jednostka__id"]
        if jednostka_id not in stats_dict:
            stats_dict[jednostka_id] = {
                "jednostka_nazwa": stat["jednostka__nazwa"],
                "jednostka_skrot": stat["jednostka__skrot"],
                "prace_ciagle": 0,
                "prace_zwarte": 0,
            }
        stats_dict[jednostka_id]["prace_zwarte"] = stat["liczba"]

    # Konwertuj na listę dla łatwiejszego użycia w template
    jednostki_stats = [
        {
            "id": jed_id,
            "nazwa": data["jednostka_nazwa"],
            "skrot": data["jednostka_skrot"],
            "prace_ciagle": data["prace_ciagle"],
            "prace_zwarte": data["prace_zwarte"],
            "razem": data["prace_ciagle"] + data["prace_zwarte"],
        }
        for jed_id, data in stats_dict.items()
    ]
    jednostki_stats.sort(key=lambda x: x["nazwa"])

    if request.method == "POST":
        form = PrzemapoaniePracAutoraForm(request.POST, autor=autor)

        if "confirm" in request.POST:
            # Użytkownik potwierdził przemapowanie
            if form.is_valid():
                jednostka_z = form.cleaned_data["jednostka_z"]
                jednostka_do = form.cleaned_data["jednostka_do"]

                try:
                    with transaction.atomic():
                        # Zbierz informacje o pracach ciągłych przed przemapowaniem
                        prace_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(
                            autor=autor, jednostka=jednostka_z
                        ).select_related("rekord")

                        prace_ciagle_historia = []
                        for praca_autor in prace_ciagle:
                            prace_ciagle_historia.append(
                                {
                                    "id": praca_autor.rekord.id,
                                    "tytul": praca_autor.rekord.tytul_oryginalny,
                                    "rok": praca_autor.rekord.rok,
                                    "zrodlo": (
                                        str(praca_autor.rekord.zrodlo)
                                        if hasattr(praca_autor.rekord, "zrodlo")
                                        and praca_autor.rekord.zrodlo
                                        else None
                                    ),
                                }
                            )

                        liczba_prac_ciaglych = len(prace_ciagle_historia)
                        prace_ciagle.update(jednostka=jednostka_do)

                        # Zbierz informacje o pracach zwartych przed przemapowaniem
                        prace_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(
                            autor=autor, jednostka=jednostka_z
                        ).select_related("rekord")

                        prace_zwarte_historia = []
                        for praca_autor in prace_zwarte:
                            prace_zwarte_historia.append(
                                {
                                    "id": praca_autor.rekord.id,
                                    "tytul": praca_autor.rekord.tytul_oryginalny,
                                    "rok": praca_autor.rekord.rok,
                                    "isbn": (
                                        praca_autor.rekord.isbn
                                        if hasattr(praca_autor.rekord, "isbn")
                                        else None
                                    ),
                                    "wydawnictwo": (
                                        praca_autor.rekord.wydawnictwo
                                        if hasattr(praca_autor.rekord, "wydawnictwo")
                                        else None
                                    ),
                                }
                            )

                        liczba_prac_zwartych = len(prace_zwarte_historia)
                        prace_zwarte.update(jednostka=jednostka_do)

                        # Zapisz log operacji z historią
                        PrzemapoaniePracAutora.objects.create(
                            autor=autor,
                            jednostka_z=jednostka_z,
                            jednostka_do=jednostka_do,
                            liczba_prac_ciaglych=liczba_prac_ciaglych,
                            liczba_prac_zwartych=liczba_prac_zwartych,
                            utworzono_przez=request.user,
                            prace_ciagle_historia=prace_ciagle_historia,
                            prace_zwarte_historia=prace_zwarte_historia,
                        )

                        messages.success(
                            request,
                            f"Pomyślnie przemapowano {liczba_prac_ciaglych} prac ciągłych "
                            f"i {liczba_prac_zwartych} prac zwartych "
                            f'z jednostki "{jednostka_z}" do jednostki "{jednostka_do}".',
                        )

                        return redirect(
                            "przemapuj_prace_autora:przemapuj_prace", autor_id=autor.pk
                        )

                except Exception as e:
                    messages.error(
                        request, f"Wystąpił błąd podczas przemapowania prac: {str(e)}"
                    )

        elif "preview" in request.POST:
            # Użytkownik chce zobaczyć podgląd
            if form.is_valid():
                jednostka_z = form.cleaned_data["jednostka_z"]
                jednostka_do = form.cleaned_data["jednostka_do"]

                # Pobierz prace do przemapowania
                prace_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(
                    autor=autor, jednostka=jednostka_z
                ).select_related("rekord")[
                    :10
                ]  # Pokaż pierwsze 10 jako przykład

                prace_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(
                    autor=autor, jednostka=jednostka_z
                ).select_related("rekord")[
                    :10
                ]  # Pokaż pierwsze 10 jako przykład

                liczba_prac_ciaglych = Wydawnictwo_Ciagle_Autor.objects.filter(
                    autor=autor, jednostka=jednostka_z
                ).count()

                liczba_prac_zwartych = Wydawnictwo_Zwarte_Autor.objects.filter(
                    autor=autor, jednostka=jednostka_z
                ).count()

                context = {
                    "autor": autor,
                    "form": form,
                    "jednostki_stats": jednostki_stats,
                    "preview": True,
                    "jednostka_z": jednostka_z,
                    "jednostka_do": jednostka_do,
                    "prace_ciagle": prace_ciagle,
                    "prace_zwarte": prace_zwarte,
                    "liczba_prac_ciaglych": liczba_prac_ciaglych,
                    "liczba_prac_zwartych": liczba_prac_zwartych,
                    "total_count": liczba_prac_ciaglych + liczba_prac_zwartych,
                }
                return render(
                    request, "przemapuj_prace_autora/przemapuj_prace.html", context
                )

    else:
        form = PrzemapoaniePracAutoraForm(autor=autor)

    # Pobierz historię przemapowań dla tego autora
    historia = PrzemapoaniePracAutora.objects.filter(autor=autor).select_related(
        "jednostka_z", "jednostka_do", "utworzono_przez"
    )[:10]

    context = {
        "autor": autor,
        "form": form,
        "jednostki_stats": jednostki_stats,
        "historia": historia,
        "preview": False,
    }
    return render(request, "przemapuj_prace_autora/przemapuj_prace.html", context)
