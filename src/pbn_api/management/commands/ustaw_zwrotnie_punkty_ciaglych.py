from tqdm import tqdm

from bpp.models import Punktacja_Zrodla, Wydawnictwo_Ciagle
from pbn_api.management.commands.util import PBNBaseCommand, komunikat_bledu


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--min-rok", type=int, default=2022)
        parser.add_argument(
            "--overwrite",
            action="store_true",
            default=False,
            help="Overwrite existing punkty_kbn values (default: skip records with punkty_kbn > 0)",
        )
        parser.add_argument(
            "--ignore-errors",
            action="store_true",
            default=False,
            help=(
                "Nie przerywaj na pierwszym błędnym rekordzie — wypisz błąd "
                "(z pełnym tracebackiem) i przejdź do następnego rekordu."
            ),
        )

    def handle(self, min_rok, overwrite=False, ignore_errors=False, *args, **kw):
        seen = set()

        # Build queryset based on overwrite option
        queryset = Wydawnictwo_Ciagle.objects.filter(rok__gte=min_rok)
        if not overwrite:
            # Exclude records that already have points
            queryset = queryset.exclude(punkty_kbn__gt=0)

        # disable=None → tqdm sam wyłącza pasek, gdy wyjście nie jest TTY
        # (np. pipe do pliku / grep). Interaktywnie pasek jest, w pipie znika.
        for elem in tqdm(queryset, disable=None):
            try:
                self._przetworz(elem, seen)
            except Exception as exc:
                # Bez --ignore-errors zachowujemy stare zachowanie: błąd
                # jednego rekordu wywala całą komendę (z pełnym tracebackiem).
                if not ignore_errors:
                    raise
                # Z flagą: rekord pomijamy, ale błąd MUSI być widoczny —
                # nigdy go nie zjadamy po cichu (patrz CLAUDE.md). Sam
                # komunikat, bez tracebacku; tqdm.write wypisuje PONAD paskiem.
                tqdm.write(f"POMINIĘTO pk={elem.pk} ({elem}): {komunikat_bledu(exc)}")

    def _przetworz(self, elem, seen):
        try:
            elem.punkty_kbn = elem.zrodlo.punktacja_zrodla_set.get(
                rok=elem.rok
            ).punkty_kbn
        except Punktacja_Zrodla.DoesNotExist:
            zrodlo_rok = (elem.zrodlo.pk, elem.rok)
            if zrodlo_rok not in seen:
                print(
                    f"Brak punktacji dla {elem.zrodlo} za {elem.rok}, przyznaję 5 punktów"
                )
                seen.add(zrodlo_rok)
            elem.punkty_kbn = 5

        elem.save()
