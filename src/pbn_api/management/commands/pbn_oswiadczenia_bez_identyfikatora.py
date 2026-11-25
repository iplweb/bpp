"""Zestawienie prac, których wysyłka do PBN jest zatrzymana z powodu autora
bez odpowiednika w PBN i bez ORCID (FD#509).

Tylko do odczytu: niczego nie zmienia i z PBN się nie łączy. Służy do oceny
skali przed aktualizacją i po niej oraz do ustalenia, których autorów
uzupełnić w pierwszej kolejności.
"""

from collections import Counter

from django.core.management import BaseCommand

from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor
from pbn_api.adapters.wydawnictwo_autor import powiazania_bez_identyfikatora_osoby


def powiazania_blokujace_wysylke(rok_od=None, rok_do=None, uczelnia_id=None):
    """Powiązania autor–rekord blokujące wysyłkę, osobno dla każdego modelu.

    Ograniczone do prac, których charakter formalny jest w ogóle wysyłany
    do PBN — pozostałych blokada nie dotyczy.
    """
    for model in (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor):
        qs = powiazania_bez_identyfikatora_osoby(
            model.objects.filter(rekord__charakter_formalny__rodzaj_pbn__isnull=False)
        )
        if rok_od is not None:
            qs = qs.filter(rekord__rok__gte=rok_od)
        if rok_do is not None:
            qs = qs.filter(rekord__rok__lte=rok_do)
        if uczelnia_id is not None:
            qs = qs.filter(jednostka__uczelnia_id=uczelnia_id)
        yield qs.select_related("rekord").order_by("rekord__rok", "rekord_id")


class Command(BaseCommand):
    help = (
        "Pokazuje prace, których wysyłka do PBN jest zatrzymana, bo autor "
        "z przypiętą dyscypliną nie ma ani odpowiednika w PBN, ani ORCID. "
        "Tylko do odczytu."
    )

    def add_arguments(self, parser):
        parser.add_argument("--rok-od", type=int, default=None)
        parser.add_argument("--rok-do", type=int, default=None)
        parser.add_argument(
            "--uczelnia-id",
            type=int,
            default=None,
            help="Tylko autorzy afiliujący w jednostkach tej uczelni.",
        )
        parser.add_argument(
            "--szczegoly",
            action="store_true",
            help=(
                "Wypisz każde powiązanie w wierszu rozdzielanym średnikami: "
                "rodzaj;ID pracy;rok;tytuł;ID autora;autor;dyscyplina."
            ),
        )
        parser.add_argument(
            "--top",
            type=int,
            default=20,
            help="Ilu autorów (z największą liczbą prac) pokazać (domyślnie 20).",
        )

    def handle(self, rok_od, rok_do, uczelnia_id, szczegoly, top, *args, **options):
        prace = set()
        prace_na_rok = Counter()
        prace_autora = Counter()
        autorzy = {}

        for qs in powiazania_blokujace_wysylke(rok_od, rok_do, uczelnia_id):
            rodzaj = qs.model.rekord.field.related_model._meta.model_name
            for wa in qs.iterator():
                klucz = (rodzaj, wa.rekord_id)
                if klucz not in prace:
                    prace.add(klucz)
                    prace_na_rok[wa.rekord.rok] += 1
                prace_autora[wa.autor_id] += 1
                autorzy[wa.autor_id] = str(wa.autor)
                if szczegoly:
                    self.stdout.write(
                        ";".join(
                            str(x)
                            for x in (
                                rodzaj,
                                wa.rekord_id,
                                wa.rekord.rok,
                                wa.rekord.tytul_oryginalny,
                                wa.autor_id,
                                wa.autor,
                                wa.dyscyplina_naukowa,
                            )
                        )
                    )

        self.stdout.write(
            f"Prace z zatrzymaną wysyłką do PBN: {len(prace)}; "
            f"autorzy do uzupełnienia: {len(autorzy)}."
        )
        if not prace:
            return

        self.stdout.write("Prace wg roku:")
        for rok in sorted(prace_na_rok):
            self.stdout.write(f"  {rok}: {prace_na_rok[rok]}")

        self.stdout.write(
            f"Autorzy bez odpowiednika w PBN i bez ORCID (pierwszych {top}, "
            "wg liczby prac; ID autora;autor;liczba prac):"
        )
        for autor_id, ile in prace_autora.most_common(top):
            self.stdout.write(f"  {autor_id};{autorzy[autor_id]};{ile}")
