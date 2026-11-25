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
from bpp.util.text import strip_html

# Powyżej tylu rekordów link „pokaż wszystkie” miałby zbyt długi adres
# (identyfikatory idą w query stringu).
MAX_REKORDOW_W_LINKU = 500


ZYWY, W_KOSZU, USUNIETY, BEZ_ID = "zywy", "w_koszu", "usuniety", "bez_id"


def _wiersz(pk, tytul, rok, stan):
    # Tytuły publikacji bywają zapisane ze znacznikami (``<i>in vitro</i>``);
    # na liście pokazujemy sam tekst (escapowanie robi ``format_html``).
    tytul = strip_html(tytul) or ""
    opis = f"{tytul} ({rok})" if rok else tytul
    if stan == BEZ_ID:
        return format_html("<li>{}</li>", opis)
    if stan == USUNIETY:
        return format_html("<li>{} — rekord usunięty trwale</li>", opis)
    zmiana = reverse("admin:bpp_wydawnictwo_ciagle_change", args=[pk])
    historia = reverse("admin:bpp_wydawnictwo_ciagle_history", args=[pk])
    if stan == W_KOSZU:
        # Rekord z kosza otwiera się w adminie tylko do odczytu i da się go
        # stamtąd przywrócić.
        return format_html(
            '<li>{} — ♻️ w koszu (można przywrócić) — <a href="{}">👁️ pokaż</a>'
            ' · <a href="{}">🕘 historia</a></li>',
            opis,
            zmiana,
            historia,
        )
    return format_html(
        '<li>{} — <a href="{}">✏️ edytuj</a> · <a href="{}">🕘 historia</a></li>',
        opis,
        zmiana,
        historia,
    )


def _stan(stany, pk):
    if pk is None:
        return BEZ_ID
    return stany.get(pk, USUNIETY)


def przemapowane_publikacje_html(pozycje):
    """HTML z listą przemapowanych wydawnictw ciągłych.

    ``pozycje`` — lista krotek ``(pk, tytuł, rok)`` w kolejności z logu
    operacji. Rekordy przeniesione później do kosza są oznaczone i mają
    linki (kosz jest odwracalny); usunięte trwale oraz pozycje logu bez
    identyfikatora (``pk`` równe ``None``) zostają na liście bez linków.
    """
    pozycje = list(pozycje)
    if not pozycje:
        return "—"

    pks = [pk for pk, _tytul, _rok in pozycje if pk is not None]
    # ``global_objects`` — żywe i kosz; domyślny menedżer kosza nie widzi.
    stany = {
        pk: W_KOSZU if deleted_at else ZYWY
        for pk, deleted_at in Wydawnictwo_Ciagle.global_objects.filter(
            pk__in=pks
        ).values_list("pk", "deleted_at")
    }
    lista = format_html(
        "<ol>{}</ol>",
        format_html_join(
            "",
            "{}",
            (
                (_wiersz(pk, tytul, rok, _stan(stany, pk)),)
                for pk, tytul, rok in pozycje
            ),
        ),
    )

    # Lista w module redagowania domyślnie chowa kosz — link obejmuje tylko
    # żywe rekordy. Posortowane: kolejność w logu bywa dowolna (``Rekord``).
    do_linku = sorted(pk for pk in pks if stany.get(pk) == ZYWY)
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
