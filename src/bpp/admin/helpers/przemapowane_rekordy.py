"""Lista publikacji objętych przemapowaniem źródła — pole tylko do odczytu
na stronie operacji w logu przemapowań (FD#508).

Log przemapowania trzyma listę rekordów w JSON-ie. Samo JSON nie pozwala
przejść do rekordu ani do jego historii, więc admin pokazuje zamiast niego
listę z linkami: do edycji i historii każdej publikacji oraz do gotowej
listy wszystkich w module redagowania.
"""

from django.urls import reverse
from django.utils.html import format_html, format_html_join

from bpp.models import Wydawnictwo_Ciagle

# Powyżej tylu rekordów link „pokaż wszystkie” miałby zbyt długi adres
# (identyfikatory idą w query stringu).
MAX_REKORDOW_W_LINKU = 500


def _wiersz(pk, tytul, rok, istnieje):
    opis = f"{tytul} ({rok})" if rok else f"{tytul}"
    if not istnieje:
        return format_html("<li>{} — rekord usunięty</li>", opis)
    return format_html(
        '<li>{} — <a href="{}">✏️ edytuj</a> · <a href="{}">🕘 historia</a></li>',
        opis,
        reverse("admin:bpp_wydawnictwo_ciagle_change", args=[pk]),
        reverse("admin:bpp_wydawnictwo_ciagle_history", args=[pk]),
    )


def przemapowane_publikacje_html(pozycje):
    """HTML z listą przemapowanych wydawnictw ciągłych.

    ``pozycje`` — lista krotek ``(pk, tytuł, rok)`` w kolejności z logu
    operacji. Rekordy skasowane po przemapowaniu zostają na liście, ale bez
    linków.
    """
    pozycje = list(pozycje)
    if not pozycje:
        return "—"

    pks = [pk for pk, _tytul, _rok in pozycje]
    istniejace = set(
        Wydawnictwo_Ciagle.objects.filter(pk__in=pks).values_list("pk", flat=True)
    )
    lista = format_html(
        "<ol>{}</ol>",
        format_html_join(
            "",
            "{}",
            (
                (_wiersz(pk, tytul, rok, pk in istniejace),)
                for pk, tytul, rok in pozycje
            ),
        ),
    )

    do_linku = [pk for pk in pks if pk in istniejace]
    if not do_linku or len(do_linku) > MAX_REKORDOW_W_LINKU:
        return lista

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    return format_html(
        '<p><a href="{}?id__in={}">📋 Pokaż w module redagowania ({})</a></p>{}',
        url,
        ",".join(str(pk) for pk in do_linku),
        len(do_linku),
        lista,
    )
