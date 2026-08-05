"""Przegląd i ustawianie identyfikatorów ROR uczelni na potrzeby CERIF/OpenAIRE.

``Uczelnia.ror_id`` trafia do eksportu jako element ``RORID`` encji ``OrgUnit``.
Puste pole oznacza, że OpenAIRE Explore nie sklei wyeksportowanych publikacji
z profilem instytucji — a wpisanie ROR-a „na oko” jest jeszcze gorsze, bo
rekord wygląda na uzupełniony, a wskazuje w próżnię albo na cudzą instytucję.

Komenda robi trzy rzeczy naraz: pokazuje stan, waliduje to, co już jest
(format + suma kontrolna ISO 7064), i podpowiada kandydatów z publicznego API
ROR wyszukanych po nazwie uczelni. Zapis jest zawsze świadomą decyzją operatora
(``--uczelnia`` + ``--ustaw``) — komenda nigdy nie zapisuje niczego sama.
"""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from bpp.models import Uczelnia
from bpp.util import ror

SZEROKOSC_PODSUMOWANIA = 42

STATUS_OK = "ok"
STATUS_BRAK = "brak"
STATUS_BLAD = "blad"


def znajdz_uczelnie(wskaznik):
    """Uczelnia wskazana kluczem głównym albo skrótem/nazwą.

    Skrót jest w praktyce wygodniejszy od PK, ale nie ma na nim ograniczenia
    unikalności — stąd jawny błąd przy niejednoznaczności zamiast cichego
    ``.first()``, który potrafiłby zapisać ROR nie tej uczelni, co trzeba.
    """
    wskaznik = (wskaznik or "").strip()
    if not wskaznik:
        raise CommandError("Pusty wskaźnik uczelni.")

    if wskaznik.isdigit():
        try:
            return Uczelnia.objects.get(pk=int(wskaznik))
        except Uczelnia.DoesNotExist as exc:
            raise CommandError(f"Nie ma uczelni o kluczu głównym {wskaznik}.") from exc

    znalezione = list(
        Uczelnia.objects.filter(skrot__iexact=wskaznik)
        | Uczelnia.objects.filter(nazwa__iexact=wskaznik)
    )

    if not znalezione:
        raise CommandError(
            f"Nie ma uczelni o skrócie ani nazwie „{wskaznik}”. Proszę podać "
            f"klucz główny albo uruchomić komendę bez argumentów, żeby "
            f"zobaczyć listę."
        )

    if len(znalezione) > 1:
        klucze = ", ".join(str(obj.pk) for obj in znalezione)
        raise CommandError(
            f"Wskaźnik „{wskaznik}” pasuje do więcej niż jednej uczelni "
            f"(klucze główne: {klucze}). Proszę podać klucz główny."
        )

    return znalezione[0]


def zbadaj(uczelnia):
    """Zwróć ``(status, komunikat)`` dla ``uczelnia.ror_id``."""
    wartosc = (uczelnia.ror_id or "").strip()
    if not wartosc:
        return STATUS_BRAK, "pole puste — instytucja nie zostanie wyeksportowana"

    try:
        ror.waliduj(wartosc)
    except ValidationError as exc:
        return STATUS_BLAD, " ".join(exc.messages)

    kanoniczny = ror.normalizuj(wartosc)
    if kanoniczny != wartosc:
        return STATUS_OK, f"poprawny (postać kanoniczna: {kanoniczny})"
    return STATUS_OK, "poprawny"


class Command(BaseCommand):
    help = (
        "Pokazuje i pomaga ustawić identyfikatory ROR uczelni używane "
        "w eksporcie CERIF/OpenAIRE."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--uczelnia",
            help=(
                "Zawęź do jednej uczelni — klucz główny, skrót albo nazwa. "
                "Wymagane razem z --ustaw."
            ),
        )
        parser.add_argument(
            "--ustaw",
            help=(
                "Zapisz podany identyfikator ROR (pełny adres albo sam "
                "identyfikator) po walidacji. Wymaga --uczelnia."
            ),
        )
        parser.add_argument(
            "--offline",
            action="store_true",
            help=(
                "Nie odpytuj API ROR — pokaż wyłącznie stan obecny i wynik walidacji."
            ),
        )

    def handle(self, *args, **options):
        if options["ustaw"] and not options["uczelnia"]:
            raise CommandError(
                "--ustaw wymaga wskazania uczelni przez --uczelnia (żeby nie "
                "dało się przypadkiem nadpisać ROR-a wszystkim naraz)."
            )

        if options["uczelnia"]:
            uczelnie = [znajdz_uczelnie(options["uczelnia"])]
        else:
            uczelnie = list(Uczelnia.objects.order_by("pk"))

        if options["ustaw"]:
            self._ustaw(uczelnie[0], options["ustaw"])
            return

        if not uczelnie:
            self.stdout.write(self.style.WARNING("W bazie nie ma ani jednej uczelni."))
            return

        self._naglowek()

        statusy = []
        for uczelnia in uczelnie:
            status = self._wypisz_uczelnie(uczelnia, offline=options["offline"])
            statusy.append(status)

        self._podsumowanie(statusy)

    def _ustaw(self, uczelnia, wartosc):
        """Zapisz zwalidowany, znormalizowany ROR dla jednej uczelni."""
        try:
            ror.waliduj(wartosc)
        except ValidationError as exc:
            raise CommandError(
                "Nie zapisano — podana wartość nie jest poprawnym "
                "identyfikatorem ROR. " + " ".join(exc.messages)
            ) from exc

        kanoniczny = ror.normalizuj(wartosc)
        poprzedni = (uczelnia.ror_id or "").strip()

        if poprzedni == kanoniczny:
            self.stdout.write(
                f"{self._etykieta(uczelnia)}: ROR bez zmian ({kanoniczny})."
            )
            return

        uczelnia.ror_id = kanoniczny
        uczelnia.save(update_fields=["ror_id"])

        if poprzedni:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{self._etykieta(uczelnia)}: ROR zmieniony "
                    f"z {poprzedni} na {kanoniczny}."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{self._etykieta(uczelnia)}: ROR ustawiony na {kanoniczny}."
                )
            )

    def _naglowek(self):
        tytul = "Identyfikatory ROR uczelni (eksport CERIF / OpenAIRE)"
        self.stdout.write(tytul)
        self.stdout.write("=" * len(tytul))

    @staticmethod
    def _etykieta(uczelnia):
        skrot = (uczelnia.skrot or "").strip()
        if skrot:
            return f"{uczelnia.nazwa} [{skrot}] (pk={uczelnia.pk})"
        return f"{uczelnia.nazwa} (pk={uczelnia.pk})"

    def _wypisz_uczelnie(self, uczelnia, offline):
        status, komunikat = zbadaj(uczelnia)

        self.stdout.write("")
        self.stdout.write(self._etykieta(uczelnia))
        self.stdout.write(f"  ROR ....... {(uczelnia.ror_id or '').strip() or 'BRAK'}")

        if status == STATUS_OK:
            styl = self.style.SUCCESS
        elif status == STATUS_BRAK:
            styl = self.style.WARNING
        else:
            styl = self.style.ERROR
        self.stdout.write(f"  Status .... {styl(komunikat)}")

        # Kandydatów proponujemy też przy błędnej wartości — literówka w ROR-ze
        # wymaga dokładnie tej samej pomocy co pusty rekord.
        if status != STATUS_OK and not offline:
            self._wypisz_kandydatow(uczelnia)

        return status

    def _wypisz_kandydatow(self, uczelnia):
        nazwa = (uczelnia.nazwa or "").strip()
        if not nazwa:
            return

        try:
            kandydaci = ror.szukaj(nazwa)
        except ror.BladWyszukiwania as exc:
            # Brak sieci nie może przerwać przeglądu pozostałych uczelni —
            # raport stanu (i walidacja) działa też bez API.
            self.stdout.write(
                self.style.WARNING(
                    f"  Kandydaci . niedostępni: {exc} "
                    f"(--offline pomija odpytywanie API)"
                )
            )
            return

        if not kandydaci:
            self.stdout.write(
                f"  Kandydaci . API ROR nie zwróciło nic dla nazwy „{nazwa}”."
            )
            return

        self.stdout.write(f"  Kandydaci z API ROR dla nazwy „{nazwa}”:")
        for numer, kandydat in enumerate(kandydaci, start=1):
            opis = kandydat["nazwa"] or "(bez nazwy)"
            if kandydat["kraj"]:
                opis = f"{opis}, {kandydat['kraj']}"
            self.stdout.write(f"    {numer}. {kandydat['id']} — {opis}")

        self.stdout.write(
            f"    Aby ustawić: manage.py cerif_ustaw_ror "
            f"--uczelnia {uczelnia.pk} --ustaw {kandydaci[0]['id']}"
        )

    def _podsumowanie(self, statusy):
        self.stdout.write("")
        self.stdout.write("Podsumowanie")
        self.stdout.write("------------")

        pozycje = [
            ("uczelnie razem", len(statusy)),
            ("z poprawnym ROR", statusy.count(STATUS_OK)),
            ("bez ROR", statusy.count(STATUS_BRAK)),
            ("z błędnym ROR", statusy.count(STATUS_BLAD)),
        ]

        for etykieta, ile in pozycje:
            kropki = "." * max(1, SZEROKOSC_PODSUMOWANIA - len(etykieta) - 2)
            self.stdout.write(f"  {etykieta} {kropki} {ile}")

        do_zrobienia = statusy.count(STATUS_BRAK) + statusy.count(STATUS_BLAD)
        self.stdout.write("")
        if do_zrobienia:
            self.stdout.write(
                self.style.WARNING(
                    f"Uczelni wymagających uwagi: {do_zrobienia}. Bez poprawnego "
                    f"ROR-a OpenAIRE nie połączy wyeksportowanych publikacji "
                    f"z profilem instytucji."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("Wszystkie uczelnie mają poprawny ROR.")
            )
