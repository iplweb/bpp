"""FD#640: raport dyscyplin i jednostek dopisanych przez formularz zgłaszania
publikacji autorom spoza uczelni.

WYŁĄCZNIE raport — komenda niczego nie zmienia w bazie. Na jego podstawie
człowiek decyduje o ręcznym sprzątaniu w edycji autora. Logika i opis
ostrożności (przypadki niepewne, zmienione przez redakcję, prace tracące
dyscyplinę): ``zglos_publikacje.fd640``.
"""

import csv

from django.core.management.base import BaseCommand

from zglos_publikacje.fd640 import znajdz_jednostki_bez_dyscyplin, znajdz_przypadki

KOLUMNY_CSV = (
    "sekcja",
    "autor_id",
    "autor",
    "rok",
    "dyscyplina",
    "zgloszenie",
    "jednostki_ze_zgloszenia",
    "niepewne",
    "zmienione_przez_redakcje",
    "prace_tracace_dyscypline",
)

UWAGA_NIEPEWNE = (
    "NIEPEWNE: autor wygląda na obcego dopiero po pominięciu powiązań "
    "z jednostkami bez dat i prac, wybranych przy nim w zgłoszeniu — nie da "
    "się ustalić, czy założyło je zgłoszenie"
)
UWAGA_ZMIENIONE = "przypisanie zmieniono później w module redagowania"
UWAGA_PRACE = (
    "usunięcie przypisania wyzerowałoby dyscyplinę w {} autorstwach z tego "
    "roku (trigger zeruje wszystkie autorstwa autora w danym roku)"
)


class Command(BaseCommand):
    help = (
        "FD#640: raport (bez zmian w bazie) dyscyplin dopisanych podczas "
        "zgłaszania prac autorom spoza uczelni oraz powiązań z jednostkami, "
        "które wyglądają na założone przez zgłoszenia."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            action="store_true",
            help="Wypisz raport jako CSV (zamiast tekstu).",
        )

    def handle(self, *args, **options):
        przypadki = znajdz_przypadki()
        tylko_jednostki = znajdz_jednostki_bez_dyscyplin(
            pomin_autorow={p.autor.pk for p in przypadki}
        )
        if options["csv"]:
            self._csv(przypadki, tylko_jednostki)
        else:
            self._tekst(przypadki, tylko_jednostki)

    def _wiersze(self, sekcja, przypadki):
        for p in przypadki:
            ad = p.przypisanie
            yield {
                "sekcja": sekcja,
                "autor_id": p.autor.pk,
                "autor": str(p.autor),
                "rok": ad.rok if ad else "",
                "dyscyplina": str(ad.dyscyplina_naukowa) if ad else "",
                "zgloszenie": p.zgloszenie_id or "",
                "jednostki_ze_zgloszenia": "; ".join(
                    str(aj.jednostka) for aj in p.jednostki_ze_zgloszenia
                ),
                "niepewne": "tak" if p.niepewne else "nie",
                "zmienione_przez_redakcje": "tak" if p.zmienione else "nie",
                "prace_tracace_dyscypline": p.prace_tracace_dyscypline,
            }

    def _csv(self, przypadki, tylko_jednostki):
        pisarz = csv.DictWriter(self.stdout, fieldnames=KOLUMNY_CSV)
        pisarz.writeheader()
        for wiersz in self._wiersze("dyscyplina", przypadki):
            pisarz.writerow(wiersz)
        for wiersz in self._wiersze("tylko_jednostka", tylko_jednostki):
            pisarz.writerow(wiersz)

    def _tekst(self, przypadki, tylko_jednostki):
        w = self.stdout.write
        w("Raport FD#640 — tylko odczyt, nic nie zostało zmienione.")
        w("")
        w("1. Dyscypliny dopisane przez zgłoszenia autorom spoza uczelni")
        w("")
        for p in przypadki:
            ad = p.przypisanie
            w(f"{p.autor} (id {p.autor.pk}): {ad.dyscyplina_naukowa} na rok {ad.rok}")
            w(f"    {p.opis_utworzenia}")
            for aj in p.jednostki_ze_zgloszenia:
                w(f"    jednostka ze zgłoszenia (?): {aj.jednostka}")
            if p.niepewne:
                w(f"    {UWAGA_NIEPEWNE}")
            if p.zmienione:
                w(f"    {UWAGA_ZMIENIONE}")
            if p.prace_tracace_dyscypline:
                w(f"    {UWAGA_PRACE.format(p.prace_tracace_dyscypline)}")
        w(
            f"Przypadków: {len(przypadki)}, w tym niepewnych: "
            f"{sum(p.niepewne for p in przypadki)}, zmienionych przez redakcję: "
            f"{sum(p.zmienione for p in przypadki)}, z pracami tracącymi "
            f"dyscyplinę: {sum(bool(p.prace_tracace_dyscypline) for p in przypadki)}"
        )
        w("")
        w(
            "2. Autorzy, którzy wyglądają na obcych po pominięciu powiązań "
            "z jednostkami ze zgłoszeń (bez dopisanej dyscypliny, np. "
            "zgłoszenia sprzed FD#620) — wszystkie NIEPEWNE"
        )
        w("")
        for p in tylko_jednostki:
            jednostki = ", ".join(str(aj.jednostka) for aj in p.jednostki_ze_zgloszenia)
            w(
                f"{p.autor} (id {p.autor.pk}): {jednostki} "
                f"(zgłoszenie #{p.zgloszenie_id})"
            )
        w(f"Przypadków: {len(tylko_jednostki)}")
