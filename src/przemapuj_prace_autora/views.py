import sys

import rollbar
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from bpp.models import Autor, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

from .forms import PrzemapoaniePracAutoraForm
from .models import PrzemapoaniePracAutora


@login_required
def wybierz_autora(request):
    """Widok do wyszukiwania i wyboru autora do przemapowania prac"""
    autorzy = None
    search_query = request.GET.get("q", "")

    if search_query:
        # Wyszukaj autorów po nazwisku lub imieniu
        autorzy = Autor.objects.filter(
            Q(nazwisko__icontains=search_query) | Q(imiona__icontains=search_query)
        ).order_by("nazwisko", "imiona")[:50]  # Ogranicz do 50 wyników

    context = {
        "search_query": search_query,
        "autorzy": autorzy,
    }
    return render(request, "przemapuj_prace_autora/wybierz_autora.html", context)


def _accumulate_jednostka_stats(stats_dict, stat, field):
    """Wrzuć licznik prac danego typu (``field``) do agregatu per-jednostka."""
    entry = stats_dict.setdefault(
        stat["jednostka__id"],
        {
            "jednostka_nazwa": stat["jednostka__nazwa"],
            "jednostka_skrot": stat["jednostka__skrot"],
            "prace_ciagle": 0,
            "prace_zwarte": 0,
        },
    )
    entry[field] = stat["liczba"]


def _build_jednostki_stats(autor):
    """Zbuduj posortowaną listę statystyk prac autora per jednostka."""
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

    stats_dict = {}
    for stat in prace_ciagle_stats:
        _accumulate_jednostka_stats(stats_dict, stat, "prace_ciagle")
    for stat in prace_zwarte_stats:
        _accumulate_jednostka_stats(stats_dict, stat, "prace_zwarte")

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
    return jednostki_stats


def _historia_prac_ciaglych(prace_ciagle):
    """Zbuduj historię prac ciągłych przed przemapowaniem."""
    historia = []
    for praca_autor in prace_ciagle:
        rekord = praca_autor.rekord
        historia.append(
            {
                "id": rekord.id,
                "tytul": rekord.tytul_oryginalny,
                "rok": rekord.rok,
                "zrodlo": (
                    str(rekord.zrodlo)
                    if hasattr(rekord, "zrodlo") and rekord.zrodlo
                    else None
                ),
            }
        )
    return historia


def _historia_prac_zwartych(prace_zwarte):
    """Zbuduj historię prac zwartych przed przemapowaniem."""
    historia = []
    for praca_autor in prace_zwarte:
        rekord = praca_autor.rekord
        historia.append(
            {
                "id": rekord.id,
                "tytul": rekord.tytul_oryginalny,
                "rok": rekord.rok,
                "isbn": (rekord.isbn if hasattr(rekord, "isbn") else None),
                "wydawnictwo": (
                    rekord.wydawnictwo if hasattr(rekord, "wydawnictwo") else None
                ),
            }
        )
    return historia


def _wykonaj_przemapowanie(request, autor, form):
    """Wykonaj potwierdzone przemapowanie. Zwraca redirect lub ``None``.

    ``None`` oznacza, że wystąpił błąd (komunikat już ustawiony) i widok ma
    spaść do dolnego renderu.
    """
    jednostka_z = form.cleaned_data["jednostka_z"]
    jednostka_do = form.cleaned_data["jednostka_do"]

    try:
        with transaction.atomic():
            prace_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(
                autor=autor, jednostka=jednostka_z
            ).select_related("rekord")
            prace_ciagle_historia = _historia_prac_ciaglych(prace_ciagle)
            liczba_prac_ciaglych = len(prace_ciagle_historia)
            prace_ciagle.update(jednostka=jednostka_do)

            prace_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(
                autor=autor, jednostka=jednostka_z
            ).select_related("rekord")
            prace_zwarte_historia = _historia_prac_zwartych(prace_zwarte)
            liczba_prac_zwartych = len(prace_zwarte_historia)
            prace_zwarte.update(jednostka=jednostka_do)

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

            return redirect("przemapuj_prace_autora:przemapuj_prace", autor_id=autor.pk)

    except Exception as e:
        rollbar.report_exc_info(sys.exc_info())
        messages.error(request, f"Wystąpił błąd podczas przemapowania prac: {str(e)}")
    return None


def _render_preview(request, autor, form, jednostki_stats):
    """Wyrenderuj podgląd przemapowania dla poprawnego formularza."""
    jednostka_z = form.cleaned_data["jednostka_z"]
    jednostka_do = form.cleaned_data["jednostka_do"]

    prace_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(
        autor=autor, jednostka=jednostka_z
    ).select_related("rekord")[:10]  # Pokaż pierwsze 10 jako przykład

    prace_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(
        autor=autor, jednostka=jednostka_z
    ).select_related("rekord")[:10]  # Pokaż pierwsze 10 jako przykład

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
    return render(request, "przemapuj_prace_autora/przemapuj_prace.html", context)


@login_required
def przemapuj_prace(request, autor_id):
    """Główny widok do przemapowania prac autora między jednostkami"""
    autor = get_object_or_404(Autor, pk=autor_id)
    jednostki_stats = _build_jednostki_stats(autor)

    if request.method == "POST":
        form = PrzemapoaniePracAutoraForm(request.POST, autor=autor)

        if "confirm" in request.POST and form.is_valid():
            response = _wykonaj_przemapowanie(request, autor, form)
            if response is not None:
                return response
        elif "preview" in request.POST and form.is_valid():
            return _render_preview(request, autor, form, jednostki_stats)
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
