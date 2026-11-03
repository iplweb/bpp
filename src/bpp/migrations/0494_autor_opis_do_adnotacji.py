"""Usunięcie pola ``Autor.opis`` (+ ``pokazuj_opis``) na rzecz biogramu.

Pole „Opis” (HTML z TinyMCE) pokazywało się na stronie autora tylko z flagą
``pokazuj_opis``. Zastąpił je biogram (sanityzowany Markdown/HTML). Przegląd
dumpów produkcyjnych (2026-10): opis wypełniony tylko w APOŻ (14 autorów),
nigdzie niepokazywany — to wewnętrzne notatki. Dlatego niepusty opis trafia
do ``adnotacje`` (pole wewnętrzne, niewidoczne na WWW) jako zwykły tekst, a
NIE do biogramu, który by go opublikował.

Przy okazji usuwamy ``Uczelnia.szerokosc_lewej_kolumny`` — układ strony
autora w pasy (pół / cała) zastąpił dwie kolumny o konfigurowalnej szerokości.
"""

import html
import re

from django.db import migrations
from django.utils.html import strip_tags

NAGLOWEK_OPISU = "Dawne pole „Opis” (przeniesione do adnotacji):"

# Znaczniki kończące linię / akapit → nowa linia przed zdjęciem tagów.
_KONIEC_LINII = re.compile(r"<br\s*/?>|</(p|div|li|h[1-6])>", re.IGNORECASE)


def _opis_jako_tekst(opis):
    tekst = _KONIEC_LINII.sub("\n", opis or "")
    tekst = html.unescape(strip_tags(tekst)).replace("\xa0", " ")
    linie = (re.sub(r"[ \t]+", " ", linia).strip() for linia in tekst.splitlines())
    return "\n".join(linia for linia in linie if linia)


def polacz_adnotacje_z_opisem(adnotacje, opis):
    """Dołącz opis (jako tekst) pod adnotacjami. Pusty opis → bez zmian.

    Idempotentne: gdy ten sam blok już jest w adnotacjach, nie dubluje go.
    """
    tekst = _opis_jako_tekst(opis)
    adnotacje = adnotacje or ""
    if not tekst:
        return adnotacje
    blok = f"{NAGLOWEK_OPISU}\n{tekst}"
    if blok in adnotacje:
        return adnotacje
    return f"{adnotacje}\n\n{blok}" if adnotacje else blok


def przenies_opis_do_adnotacji(apps, schema_editor):
    Autor = apps.get_model("bpp", "Autor")
    for pk, adnotacje, opis in (
        Autor.objects.exclude(opis__isnull=True)
        .exclude(opis="")
        .values_list("pk", "adnotacje", "opis")
    ):
        nowe = polacz_adnotacje_z_opisem(adnotacje, opis)
        if nowe != adnotacje:
            # update() zamiast save(): nie ruszamy ``ostatnio_zmieniony``
            # (auto_now) — to porządki schematu, nie edycja autora.
            Autor.objects.filter(pk=pk).update(adnotacje=nowe)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0493_merge_20261024_0915"),
    ]

    operations = [
        # Odwrotnie: no-op — tekst zostaje w adnotacjach, a przywrócone
        # (puste) pole opis nie wymaga danych.
        migrations.RunPython(przenies_opis_do_adnotacji, migrations.RunPython.noop),
        migrations.RemoveField(model_name="autor", name="opis"),
        migrations.RemoveField(model_name="autor", name="pokazuj_opis"),
        migrations.RemoveField(model_name="uczelnia", name="szerokosc_lewej_kolumny"),
    ]
