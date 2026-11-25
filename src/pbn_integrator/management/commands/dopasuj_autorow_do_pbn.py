"""Dopasowanie autorów BPP bez odpowiednika w PBN do osób z PBN (FD#510).

Domyślnie TYLKO podgląd: komenda bada autorów, wypisuje podsumowanie
i zapisuje raport do pliku. Zmiany w bazie robi dopiero ``--zapisz`` —
i wyłącznie dla wskazań ocenionych jako „pewne”.
"""

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError
from django.db import transaction

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from bpp.wersjonowanie import jako_uzytkownik
from pbn_api.models import Scientist
from pbn_integrator.utils.dopasowanie_autorow import (
    KOLEJNOSC_POZIOMOW,
    zbadaj_autorow,
)
from pbn_integrator.utils.scientists import _powiaz_autora_z_pbn

NAGLOWKI = [
    "ID autora",
    "Nazwisko",
    "Imiona",
    "ORCID",
    "Aktualna jednostka",
    "Poziom pewności",
    "Proponowany PBN UID",
    "Osoba w PBN",
    "Źródła dowodu",
    "Liczba zgodnych prac",
    "Uwagi",
    "Zapisano",
]


class Command(BaseCommand):
    help = (
        "Dopasowuje autorów bez odpowiednika w PBN (pusty PBN UID) do osób "
        "z lokalnej kopii danych PBN: po ORCID, po imieniu i nazwisku wśród "
        "osób z instytucji oraz po autorach publikacji powiązanych z PBN. "
        "Domyślnie tylko podgląd; zapis wymaga --zapisz."
    )

    def add_arguments(self, parser):
        tryb = parser.add_mutually_exclusive_group()
        tryb.add_argument(
            "--dry-run",
            action="store_true",
            help="Tylko podgląd, bez zmian w bazie (zachowanie domyślne).",
        )
        tryb.add_argument(
            "--zapisz",
            action="store_true",
            help="Zapisz PBN UID autorom ze wskazaniem „pewne”.",
        )
        parser.add_argument(
            "--uczelnia",
            type=int,
            default=None,
            help="ID uczelni (wymagane, gdy w systemie jest więcej niż jedna).",
        )
        parser.add_argument(
            "--rok-od", type=int, default=None, help="Tylko autorzy z pracami od roku."
        )
        parser.add_argument(
            "--rok-do", type=int, default=None, help="Tylko autorzy z pracami do roku."
        )
        parser.add_argument(
            "--limit", type=int, default=None, help="Zbadaj najwyżej tylu autorów."
        )
        parser.add_argument(
            "--pewne-od-prac",
            type=int,
            default=0,
            help=(
                "Uznaj za „pewne” także wskazanie wyłącznie z publikacji, jeśli "
                "ta sama osoba PBN wynika zgodnie z co najmniej tylu prac "
                "(domyślnie wyłączone)."
            ),
        )
        parser.add_argument(
            "--raport",
            default=None,
            help=(
                "Plik raportu (.xlsx albo .csv). Domyślnie "
                "dopasowanie_autorow_pbn_<data>.xlsx w bieżącym katalogu."
            ),
        )
        parser.add_argument(
            "--uzytkownik",
            default=None,
            help=(
                "Login użytkownika, któremu przypisać zmiany w historii "
                "autorów (domyślnie konto systemowe)."
            ),
        )

    def _uczelnia(self, uczelnia_id):
        if uczelnia_id is not None:
            try:
                return Uczelnia.objects.get(pk=uczelnia_id)
            except Uczelnia.DoesNotExist as e:
                raise CommandError(f"Brak uczelni o id={uczelnia_id}.") from e
        liczba = Uczelnia.objects.count()
        if liczba == 1:
            return Uczelnia.objects.get()
        if liczba == 0:
            return None
        raise CommandError(
            "W systemie jest więcej niż jedna uczelnia — podaj --uczelnia."
        )

    def _uzytkownik(self, login):
        if not login:
            return None
        User = get_user_model()
        try:
            return User.objects.get(username=login)
        except User.DoesNotExist as e:
            raise CommandError(f"Brak użytkownika o loginie „{login}”.") from e

    def _autorzy(self, uczelnia, wiele_uczelni, rok_od, rok_do, limit):
        autorzy = Autor.objects.filter(pbn_uid_id__isnull=True)
        if wiele_uczelni:
            autorzy = autorzy.filter(
                pk__in=Autor_Jednostka.objects.filter(
                    jednostka__uczelnia=uczelnia
                ).values("autor_id")
            )
        if rok_od is not None or rok_do is not None:
            z_pracami = set()
            for model in (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor):
                powiazania = model.objects.all()
                if rok_od is not None:
                    powiazania = powiazania.filter(rekord__rok__gte=rok_od)
                if rok_do is not None:
                    powiazania = powiazania.filter(rekord__rok__lte=rok_do)
                z_pracami.update(
                    powiazania.values_list("autor_id", flat=True).distinct()
                )
            autorzy = autorzy.filter(pk__in=z_pracami)
        autorzy = autorzy.select_related("aktualna_jednostka").order_by(
            "nazwisko", "imiona", "pk"
        )
        if limit is not None:
            autorzy = autorzy[:limit]
        return list(autorzy)

    def _zapisz(self, propozycje, uzytkownik):
        """Zapisz wskazania „pewne”. Każdy autor w osobnej transakcji,
        z ponownym sprawdzeniem pod blokadą — PBN UID, który pojawił się
        w międzyczasie, nigdy nie jest nadpisywany."""
        with jako_uzytkownik(uzytkownik):
            for propozycja in propozycje:
                if not propozycja.do_zapisu:
                    continue
                with transaction.atomic():
                    autor = Autor.objects.select_for_update().get(
                        pk=propozycja.autor.pk
                    )
                    if autor.pbn_uid_id is not None:
                        propozycja.uwagi.append(
                            "nie zapisano: autor dostał PBN UID w międzyczasie"
                        )
                        continue
                    if (
                        Autor.objects.filter(pbn_uid_id=propozycja.scientist_id)
                        .exclude(pk=autor.pk)
                        .exists()
                    ):
                        propozycja.uwagi.append(
                            "nie zapisano: osoba PBN została w międzyczasie "
                            "przypisana do innego autora"
                        )
                        continue
                    _powiaz_autora_z_pbn(
                        autor,
                        propozycja.scientist_id,
                        "dopasowanie autorów bez odpowiednika w PBN: "
                        + "; ".join(propozycja.zrodla),
                    )
                    propozycja.zapisano = True

    def _wiersze(self, propozycje):
        osoby = {
            osoba.pk: osoba
            for osoba in Scientist.objects.filter(
                pk__in=[p.scientist_id for p in propozycje if p.scientist_id]
            )
        }
        kolejnosc = {poziom: i for i, poziom in enumerate(KOLEJNOSC_POZIOMOW)}
        for propozycja in sorted(propozycje, key=lambda p: kolejnosc[p.poziom]):
            autor = propozycja.autor
            osoba = osoby.get(propozycja.scientist_id)
            yield [
                autor.pk,
                autor.nazwisko,
                autor.imiona,
                autor.orcid or "",
                str(autor.aktualna_jednostka or ""),
                propozycja.poziom,
                propozycja.scientist_id or "",
                f"{osoba.lastName} {osoba.name}".strip() if osoba else "",
                "; ".join(propozycja.zrodla),
                propozycja.liczba_prac or "",
                "; ".join(propozycja.uwagi),
                "tak" if propozycja.zapisano else "nie",
            ]

    def _zapisz_raport(self, sciezka, wiersze):
        if sciezka.suffix.lower() == ".csv":
            with sciezka.open("w", newline="", encoding="utf-8-sig") as plik:
                pisarz = csv.writer(plik, delimiter=";")
                pisarz.writerow(NAGLOWKI)
                pisarz.writerows(wiersze)
            return
        if sciezka.suffix.lower() != ".xlsx":
            raise CommandError("Raport musi mieć rozszerzenie .xlsx albo .csv.")
        from openpyxl import Workbook

        skoroszyt = Workbook()
        arkusz = skoroszyt.active
        arkusz.title = "Dopasowanie autorów do PBN"
        arkusz.append(NAGLOWKI)
        for wiersz in wiersze:
            arkusz.append(wiersz)
        arkusz.freeze_panes = "A2"
        skoroszyt.save(sciezka)

    def handle(self, *args, **options):
        uczelnia = self._uczelnia(options["uczelnia"])
        uzytkownik = self._uzytkownik(options["uzytkownik"])
        sciezka = Path(
            options["raport"]
            or f"dopasowanie_autorow_pbn_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        )
        if sciezka.suffix.lower() not in (".xlsx", ".csv"):
            raise CommandError("Raport musi mieć rozszerzenie .xlsx albo .csv.")

        autorzy = self._autorzy(
            uczelnia,
            Uczelnia.objects.count() > 1,
            options["rok_od"],
            options["rok_do"],
            options["limit"],
        )
        propozycje = zbadaj_autorow(
            autorzy, uczelnia=uczelnia, pewne_od_prac=options["pewne_od_prac"]
        )

        if options["zapisz"]:
            self._zapisz(propozycje, uzytkownik)

        self._zapisz_raport(sciezka, list(self._wiersze(propozycje)))

        poziomy = Counter(p.poziom for p in propozycje)
        self.stdout.write(f"Autorów bez PBN UID zbadano: {len(propozycje)}")
        for poziom in KOLEJNOSC_POZIOMOW:
            self.stdout.write(f"  {poziom}: {poziomy.get(poziom, 0)}")
        zapisano = sum(1 for p in propozycje if p.zapisano)
        if options["zapisz"]:
            self.stdout.write(self.style.SUCCESS(f"Zapisano PBN UID: {zapisano}"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "TRYB PODGLĄDU — niczego nie zapisano. Aby zapisać wskazania "
                    "„pewne”, uruchom ponownie z --zapisz."
                )
            )
        self.stdout.write(f"Raport: {sciezka.resolve()}")
