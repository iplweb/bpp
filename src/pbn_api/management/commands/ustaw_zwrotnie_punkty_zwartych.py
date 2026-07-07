from tqdm import tqdm

from bpp.models import Wydawnictwo_Zwarte
from pbn_api.management.commands.util import PBNBaseCommand, komunikat_bledu


class RekordBezPunktowalnegoAutorstwa(Exception):
    """Rekord nie ma ani autorstwa, ani redakcji — nie ma czego punktować.

    To anomalia DANYCH (np. książka bez przypiętych autorów), nie luka w
    logice punktacji: skoro brak slotu autorskiego, żadna „szufladka" punktowa
    nie ma zastosowania. Taki rekord pomijamy i raportujemy ZAWSZE, niezależnie
    od ``--ignore-errors`` — w odróżnieniu od ``NotImplementedError``, które
    sygnalizuje realnie nieobsłużoną kombinację typu i bez flagi nadal wywala
    komendę.
    """


class RekordBezWydawcy(Exception):
    """Rekord zwarty bez wydawcy — nie ma podstawy do tieru punktacji.

    Import PBN świadomie tworzy wydawnictwa zwarte bez wydawcy (PBN bywa
    niekompletny; ``wydawca`` jest nullable — redagowane/self-published wchodzą
    bez wydawcy). Punktacja zwartych opiera się na ``wydawca.get_tier(rok)`` —
    bez wydawcy nie ma z czego policzyć tieru (Rollbar #436: ``'NoneType'
    object has no attribute 'get_tier'``). To anomalia DANYCH, nie luka w
    logice: pomijamy i raportujemy ZAWSZE (jak brak autorstwa), niezależnie od
    ``--ignore-errors``.
    """


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
        punkty_dct = [
            {"KS": 20, "RED": 5, "ROZ": 5},
            {"KS": 80, "RED": 20, "ROZ": 20},
            {"KS": 200, "RED": 100, "ROZ": 50},
        ]

        # Build queryset based on overwrite option
        queryset = Wydawnictwo_Zwarte.objects.filter(rok__gte=min_rok)
        if not overwrite:
            # Exclude records that already have points
            queryset = queryset.exclude(punkty_kbn__gt=0)

        # disable=None → tqdm sam wyłącza pasek, gdy wyjście nie jest TTY
        # (np. pipe do pliku / grep). Interaktywnie pasek jest, w pipie znika.
        for elem in tqdm(queryset, disable=None):
            try:
                self._przetworz(elem, punkty_dct)
            except (RekordBezPunktowalnegoAutorstwa, RekordBezWydawcy) as exc:
                # Anomalie danych (rekord bez slotu autorskiego albo bez
                # wydawcy), nie luki w logice: pomijamy i raportujemy ZAWSZE,
                # niezależnie od --ignore-errors. Komenda leci dalej.
                tqdm.write(f"POMINIĘTO pk={elem.pk} ({elem}): {komunikat_bledu(exc)}")
            except Exception as exc:
                # Bez --ignore-errors zachowujemy stare zachowanie: błąd
                # jednego rekordu wywala całą komendę (z pełnym tracebackiem).
                if not ignore_errors:
                    raise
                # Z flagą: rekord pomijamy, ale błąd MUSI być widoczny —
                # nigdy go nie zjadamy po cichu (patrz CLAUDE.md). Sam
                # komunikat, bez tracebacku; tqdm.write wypisuje PONAD paskiem.
                tqdm.write(f"POMINIĘTO pk={elem.pk} ({elem}): {komunikat_bledu(exc)}")

    def _przetworz(self, elem, punkty_dct):
        if elem.wydawca is None:
            # Bez wydawcy nie ma podstawy do tieru punktacji (patrz
            # RekordBezWydawcy). Handle łapie ten wyjątek osobno i pomija rekord.
            raise RekordBezWydawcy(
                f"rekord zwarty bez wydawcy — brak podstawy do tieru "
                f"punktacji (rok={elem.rok})",
                elem,
            )

        poziom_wydawcy = elem.wydawca.get_tier(elem.rok)
        if poziom_wydawcy == -1:
            poziom_wydawcy = 0

        values = punkty_dct[poziom_wydawcy]

        rozdzial = elem.warunek_rozdzial()
        ksiazka = elem.warunek_ksiazka()

        if ksiazka and rozdzial:
            raise NotImplementedError("To sie nie powinno wydarzyc)")

        autorstwo = elem.warunek_autorstwo()
        redakcja = elem.warunek_redakcja()

        if ksiazka and autorstwo:
            punkty_pk = values["KS"]
        elif ksiazka and redakcja:
            punkty_pk = values["RED"]
        elif rozdzial and autorstwo:
            punkty_pk = values["ROZ"]
        elif not autorstwo and not redakcja:
            # Rekord nie ma ani autorstwa, ani redakcji — pusty (lub
            # pozbawiony ról AUTOR/REDAKTOR) slot autorski. Nie ma czego
            # punktować: to anomalia danych, nie nieobsłużony typ. Pomijamy
            # i raportujemy ZAWSZE (handle łapie ten wyjątek osobno).
            raise RekordBezPunktowalnegoAutorstwa(
                f"brak punktowalnego autorstwa/redakcji "
                f"({ksiazka=} {rozdzial=} {redakcja=} {autorstwo=})",
                elem,
                elem.autorzy_set.all(),
            )
        else:
            raise NotImplementedError(
                f"NIE ZAIMPLEMENTOWANO  {ksiazka=} {rozdzial=} {redakcja=} {autorstwo=}",
                elem,
                elem.autorzy_set.all(),
            )

        elem.punkty_kbn = punkty_pk
        elem.save()
