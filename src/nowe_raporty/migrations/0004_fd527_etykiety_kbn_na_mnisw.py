"""FD#527: „KBN” i „MNiSW/MEiN” → „MNiSW” w etykietach kolumn raportów.

Etykiety kolumn ``flexible_reports`` siedzą w bazie (zakładane przez seed
albo przeniesione z dawnych instalacji), więc zmiana w ``seeding`` nie
dotarłaby do istniejących instalacji. Podmiany, w tej kolejności:

1. „KBN/MNiSW” i „MNiSW/KBN” → „MNiSW” (inaczej krok 2 dałby
   „MNiSW/MNiSW”);
2. samodzielne słowo „KBN” — także małymi literami, jak w etykietach
   wyliczonych przez Django z nazwy pola („Typ kbn”) — → „MNiSW”
   (np. „Typ KBN” → „Typ MNiSW”, „Punkty KBN (suma)” → „Punkty MNiSW
   (suma)”). Nie ruszamy „KBN” sklejonego z literą, cyfrą, podkreśleniem
   ani łącznikiem („punkty_kbn”, „KBN-owskie”);
3. znane frazy z „/MEiN” — „Typ”, „Typy”, „Punkty”, „Pkt.” + „MNiSW/MEiN”
   (tak nazywały się pola w BPP, więc redaktorzy przepisywali je do tabel,
   czasem z dopiskiem: „Punkty MNiSW/MEiN (suma)”) → forma bez „/MEiN”.
   Samego „MEiN” w innych etykietach („Wykaz MEiN 2023”) nie ruszamy.

Na końcu odcinamy spacje z brzegów zmienionej etykiety.

KOLIZJE. ``flexible_reports`` używa etykiety jako klucza kolumny tabeli
(``AdHocTable.base_columns[label]``): dwie kolumny o tej samej etykiecie
w jednej tabeli = druga nadpisuje pierwszą, która znika z raportu i eksportu.
Dlatego w obrębie tabeli sprawdzamy to PRZED zmianą — jeśli nowa etykieta
jest już zajęta (przez kolumnę istniejącą albo inną właśnie zmienianą),
tej kolumny nie ruszamy i zostawiamy ostrzeżenie w logu; redaktor rozstrzygnie
to sam („Raporty” → „Tabele” → sekcja „Kolumny”).

Cofnięcie migracji niczego nie zmienia — patrz ``wstecz``.
"""

import logging
import re

from django.db import migrations

logger = logging.getLogger(__name__)

NOWE = "MNiSW"
PARY = re.compile(r"KBN\s*/\s*MNiSW|MNiSW\s*/\s*KBN", re.IGNORECASE)
KBN = re.compile(r"(?<![\w-])KBN(?![\w-])", re.IGNORECASE)
FRAZY_Z_MEIN = re.compile(r"\b(Typy?|Punkty|Pkt\.) MNiSW/MEiN(?![\w/])", re.IGNORECASE)


def nowa_etykieta(etykieta):
    """Etykieta po podmianach (albo ta sama, gdy nic nie pasuje)."""
    wynik = KBN.sub(NOWE, PARY.sub(NOWE, etykieta))
    wynik = FRAZY_Z_MEIN.sub(lambda m: f"{m.group(1)} {NOWE}", wynik)
    return etykieta if wynik == etykieta else wynik.strip()


def zaplanuj_zmiany(etykiety):
    """Dla kolumn JEDNEJ tabeli (``{pk: etykieta}``) zwraca
    ``({pk: nowa etykieta}, [(pk, stara, nowa) pominięte przez kolizję])``."""
    kandydaci = {}
    for pk, etykieta in etykiety.items():
        nowa = nowa_etykieta(etykieta)
        if nowa != etykieta:
            kandydaci[pk] = nowa
    # Etykiety, które na pewno zostają: kolumny, których nie zmieniamy.
    zajete = {e for pk, e in etykiety.items() if pk not in kandydaci}
    zmiany, kolizje = {}, []
    for pk in sorted(kandydaci):
        nowa = kandydaci[pk]
        if nowa in zajete:
            kolizje.append((pk, etykiety[pk], nowa))
            # Niezmieniona kolumna dalej zajmuje swoją dawną etykietę.
            zajete.add(etykiety[pk])
        else:
            zmiany[pk] = nowa
            zajete.add(nowa)
    return zmiany, kolizje


def naprzod(apps, schema_editor):
    Column = apps.get_model("flexible_reports", "Column")
    podejrzane = Column.objects.filter(label__icontains="kbn") | Column.objects.filter(
        label__icontains="/MEiN"
    )
    for tabela_id in sorted(set(podejrzane.values_list("parent_id", flat=True))):
        etykiety = dict(
            Column.objects.filter(parent_id=tabela_id).values_list("pk", "label")
        )
        zmiany, kolizje = zaplanuj_zmiany(etykiety)
        for pk, nowa in zmiany.items():
            Column.objects.filter(pk=pk).update(label=nowa)
        for pk, stara, nowa in kolizje:
            logger.warning(
                "FD#527: tabela raportu %s — kolumna %s zostaje jako %r, bo "
                "etykieta %r jest już w tej tabeli zajęta.",
                tabela_id,
                pk,
                stara,
                nowa,
            )


def wstecz(apps, schema_editor):
    """Celowo nic: po migracji „Typ MNiSW” z dawnego „Typ KBN” jest nie do
    odróżnienia od „Typ MNiSW” wpisanego ręcznie przez redaktora — cofanie
    zamieniałoby cudze etykiety na nazwę nieistniejącego komitetu."""


class Migration(migrations.Migration):
    dependencies = [
        ("nowe_raporty", "0003_opis_bibliograficzny_link"),
        ("flexible_reports", "0014_alter_datasource_sample_context"),
    ]

    operations = [migrations.RunPython(naprzod, wstecz)]
