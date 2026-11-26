"""Uzgodnienie BPP z profilem instytucji w PBN z linii poleceń (FD#477)."""

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from bpp.models import Uczelnia
from bpp.models.profile import BppUser
from pbn_uzgadnianie.models import UzgodnienieZPBN
from pbn_uzgadnianie.raport import zbuduj_xlsx
from pbn_uzgadnianie.silnik import KATEGORIE
from pbn_uzgadnianie.swiezosc import linie_opisu, stan_danych
from pbn_uzgadnianie.tasks import wykonaj_uzgodnienie


class Command(BaseCommand):
    help = (
        "Uzgadnia BPP z profilem instytucji w PBN dla podanych lat: tworzy/wiąże "
        "brakujące rekordy i wypisuje raport. Pracuje na danych pobranych "
        "wcześniej (podaje, z kiedy są); --pobierz pobiera je najpierw z PBN. "
        "Z --dry-run pokazuje, co zostałoby zrobione, bez zmian w rekordach BPP."
    )

    def add_arguments(self, parser):
        parser.add_argument("--rok-od", type=int, required=True)
        parser.add_argument("--rok-do", type=int, required=True)
        parser.add_argument(
            "--uzytkownik",
            required=True,
            help="Login użytkownika BPP z ważną autoryzacją w PBN "
            "(jego token jest używany, on trafia do historii zmian).",
        )
        parser.add_argument(
            "--uczelnia",
            type=int,
            default=None,
            help="ID uczelni; wymagane, gdy w systemie jest więcej niż jedna.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Podgląd: nic nie zmienia w rekordach BPP.",
        )
        parser.add_argument(
            "--pobierz",
            action="store_true",
            help="Najpierw pobierz aktualne dane z PBN. Bez tej opcji polecenie "
            "pracuje na danych pobranych wcześniej i podaje, z kiedy są.",
        )
        parser.add_argument("--xlsx", help="Zapisz raport do pliku XLSX.")

    def _uczelnia(self, uczelnia_id):
        if uczelnia_id is not None:
            try:
                return Uczelnia.objects.get(pk=uczelnia_id)
            except Uczelnia.DoesNotExist:
                raise CommandError(f"Nie ma uczelni o ID {uczelnia_id}.") from None
        uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()
        if uczelnia is None:
            raise CommandError(
                "W systemie nie ma dokładnie jednej uczelni — podaj --uczelnia."
            )
        return uczelnia

    @staticmethod
    def _nowy_przebieg(uczelnia, user, opcje, tryb, na_podstawie):
        UzgodnienieZPBN.oznacz_przerwane(uczelnia)
        try:
            with transaction.atomic():
                return UzgodnienieZPBN.objects.create(
                    uczelnia=uczelnia,
                    user=user,
                    rok_od=opcje["rok_od"],
                    rok_do=opcje["rok_do"],
                    tryb=tryb,
                    na_podstawie=na_podstawie,
                )
        except IntegrityError:
            raise CommandError("Uzgadnianie z PBN dla tej uczelni już trwa.") from None

    @staticmethod
    def _dane_z_pbn(uczelnia, opcje, nowy_przebieg):
        """Przebieg-pobranie, na którego danych ma pracować uzgadnianie."""
        if opcje["pobierz"]:
            pobranie = nowy_przebieg(UzgodnienieZPBN.Tryb.POBRANIE)
            wykonaj_uzgodnienie(pobranie)
            if pobranie.status != UzgodnienieZPBN.Status.ZAKONCZONE:
                raise CommandError("Pobieranie danych z PBN nie zakończyło się.")
            return pobranie
        pobranie = UzgodnienieZPBN.ostatnie_pobranie(
            uczelnia, opcje["rok_od"], opcje["rok_do"]
        )
        if pobranie is None:
            raise CommandError(
                f"Nie ma pobranych danych z PBN dla lat {opcje['rok_od']}–"
                f"{opcje['rok_do']}. Uruchom z opcją --pobierz."
            )
        return pobranie

    def handle(self, *args, **opcje):
        if opcje["rok_od"] > opcje["rok_do"]:
            raise CommandError("--rok-od nie może być większy niż --rok-do.")
        uczelnia = self._uczelnia(opcje["uczelnia"])
        try:
            user = BppUser.objects.get(username=opcje["uzytkownik"])
        except BppUser.DoesNotExist:
            raise CommandError(f"Nie ma użytkownika „{opcje['uzytkownik']}”.") from None

        def nowy_przebieg(tryb, na_podstawie=None):
            return self._nowy_przebieg(uczelnia, user, opcje, tryb, na_podstawie)

        pobranie = self._dane_z_pbn(uczelnia, opcje, nowy_przebieg)
        przebieg = nowy_przebieg(
            UzgodnienieZPBN.Tryb.PODGLAD
            if opcje["dry_run"]
            else UzgodnienieZPBN.Tryb.WYKONANIE,
            na_podstawie=pobranie,
        )
        wykonaj_uzgodnienie(przebieg)

        self.stdout.write(
            f"{przebieg.get_tryb_display()}: {przebieg.get_status_display()} "
            f"(przebieg #{przebieg.pk})"
        )
        for linia in linie_opisu(stan_danych(przebieg.zakres)):
            self.stdout.write(linia)
        for kod, etykieta in KATEGORIE.items():
            self.stdout.write(f"  {etykieta}: {przebieg.podsumowanie.get(kod, 0)}")
        if opcje["xlsx"]:
            with open(opcje["xlsx"], "wb") as plik:
                plik.write(zbuduj_xlsx(przebieg))
            self.stdout.write(f"Raport: {opcje['xlsx']}")
