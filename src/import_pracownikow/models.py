# Create your models here.
from datetime import date, timedelta

from django import forms
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DataError, models, transaction
from django.db.models import JSONField
from django.db.models.expressions import RawSQL
from django.utils import timezone
from liveops.models import LiveOperation

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jednostka,
    Tytul,
    Wymiar_Etatu,
)
from import_common.exceptions import BPPDatabaseError
from import_common.forms import ExcelDateField
from import_common.models import ImportRowMixin


class JednostkaForm(forms.Form):
    nazwa_jednostki = forms.CharField(max_length=10240)
    wydział = forms.CharField(max_length=500)


class AutorForm(forms.Form):
    nazwisko = forms.CharField(max_length=200)
    imię = forms.CharField(max_length=200)

    numer = forms.IntegerField(required=False)
    orcid = forms.CharField(max_length=19, required=False)
    tytuł_stopień = forms.CharField(max_length=200, required=False)
    pbn_uuid = forms.CharField(required=False, max_length=24, min_length=24)
    bpp_id = forms.IntegerField(required=False)

    stanowisko = forms.CharField(max_length=200)
    grupa_pracownicza = forms.CharField(max_length=200)
    data_zatrudnienia = ExcelDateField()
    data_końca_zatrudnienia = ExcelDateField(required=False)
    podstawowe_miejsce_pracy = forms.BooleanField(required=False)
    wymiar_etatu = forms.CharField(max_length=200)


class ImportPracownikow(LiveOperation):
    STAN_UTWORZONY = "utworzony"
    STAN_PRZEANALIZOWANY = "przeanalizowany"
    STAN_ZATWIERDZONY = "zatwierdzony"
    STAN_ZINTEGROWANY = "zintegrowany"
    STAN_PORZUCONY = "porzucony"
    STAN_CHOICES = [
        (STAN_UTWORZONY, "utworzony"),
        (STAN_PRZEANALIZOWANY, "przeanalizowany (dry-run gotowy)"),
        (STAN_ZATWIERDZONY, "zatwierdzony do zapisu"),
        (STAN_ZINTEGROWANY, "zintegrowany"),
        (STAN_PORZUCONY, "porzucony"),
    ]

    plik_xls = models.FileField(upload_to="protected/import_pracownikow/")
    stan = models.CharField(max_length=20, choices=STAN_CHOICES, default=STAN_UTWORZONY)

    stages = ["Wczytywanie", "Integracja"]

    def run(self, p):
        if self.stan == self.STAN_UTWORZONY:
            from import_pracownikow.pipeline.analyze import analizuj

            analizuj(self, p)
        elif self.stan == self.STAN_ZATWIERDZONY:
            from import_pracownikow.pipeline.integrate import integruj

            integruj(self, p)
        else:
            p.log(f"run() w nieoczekiwanym stanie: {self.stan!r} — pomijam")

    def on_restart(self):
        # kasujemy wiersze TYLKO przy ponownej analizie (stan cofnięty do utworzony)
        if self.stan == self.STAN_UTWORZONY:
            self.importpracownikowrow_set.all().delete()

    @property
    def zmiany_potrzebne_set(self):
        return self.importpracownikowrow_set.filter(zmiany_potrzebne=True)

    def get_details_set(self):
        return (
            self.importpracownikowrow_set.all()
            .annotate(
                nr_wiersza=RawSQL("(dane_z_xls->>'__xls_loc_row__')::int+1", []),
                nr_arkusza=RawSQL("(dane_z_xls->>'__xls_loc_sheet__')::int+1", []),
            )
            .order_by("nr_arkusza", "nr_wiersza")
            .select_related(
                "autor",
                "jednostka",
                "jednostka__wydzial",
                "autor__tytul",
                "grupa_pracownicza",
                "funkcja_autora",
                "wymiar_etatu",
            )
        )

    def autorzy_spoza_pliku_set(self, uczelnia=None, today=None):
        """
        Zwraca wszystkie połączenia Autor + Jednostka, gdzie:
        1) połączenie autor + jednostka nie występuje w imporcie danych (self)
        2) jednostka nie jest obca,
        3) jednostka ma pole "zarzadzaj_automatycznie" zaznaczone jako True
        """

        if today is None:
            today = timezone.now().date()

        autorzy_jednostki_z_pliku = self.importpracownikowrow_set.values_list(
            "autor_jednostka"
        ).distinct()

        qry = (
            Autor_Jednostka.objects.exclude(pk__in=autorzy_jednostki_z_pliku)
            .exclude(autor__aktualna_jednostka=None)
            .exclude(jednostka__zarzadzaj_automatycznie=False)
            .exclude(zakonczyl_prace__lte=today)
        )

        if uczelnia is not None and uczelnia.obca_jednostka_id is not None:
            qry = qry.exclude(autor__aktualna_jednostka_id=uczelnia.obca_jednostka_id)

        return qry

    @transaction.atomic
    def odepnij_autorow_spoza_pliku(self, uczelnia=None, today=None, yesterday=None):
        if today is None:
            today = timezone.now().date()

        if yesterday is None:
            yesterday = today - timedelta(days=1)

        for elem in self.autorzy_spoza_pliku_set(uczelnia=uczelnia, today=today):
            elem.zakonczyl_prace = yesterday
            elem.podstawowe_miejsce_pracy = False
            elem.save()

            elem.refresh_from_db()


class ImportPracownikowRow(ImportRowMixin, models.Model):
    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,  # related_name="row_set"
    )
    dane_z_xls = JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    dane_znormalizowane = JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)

    autor = models.ForeignKey(Autor, on_delete=models.CASCADE, null=True, blank=True)
    jednostka = models.ForeignKey(
        Jednostka, on_delete=models.CASCADE, null=True, blank=True
    )
    autor_jednostka = models.ForeignKey(
        Autor_Jednostka, on_delete=models.CASCADE, null=True, blank=True
    )

    podstawowe_miejsce_pracy = models.BooleanField(null=True, blank=True, default=None)
    funkcja_autora = models.ForeignKey(
        Funkcja_Autora, on_delete=models.CASCADE, null=True, blank=True
    )
    grupa_pracownicza = models.ForeignKey(
        Grupa_Pracownicza, on_delete=models.CASCADE, null=True, blank=True
    )
    wymiar_etatu = models.ForeignKey(
        Wymiar_Etatu, on_delete=models.CASCADE, null=True, blank=True
    )
    tytul = models.ForeignKey(Tytul, on_delete=models.SET_NULL, null=True)

    zmiany_potrzebne = models.BooleanField()

    diff_do_utworzenia = models.JSONField(default=dict, blank=True)
    pominiety_bo_nieaktualny = models.BooleanField(default=False)

    log_zmian = JSONField(encoder=DjangoJSONEncoder, null=True, blank=True)

    MAPPING_DANE_NA_AUTOR = [
        ("numer", "system_kadrowy_id"),
        ("orcid", "orcid"),
        ("pbn_uuid", "pbn_uid_id"),
    ]

    @property
    def dane_bardziej_znormalizowane(self):
        """parsuje daty w dwóch polach, bo JSON w PostgreSQL to raz, a JSONDecoder
        w Django nie ma czegos takiego jak dekoder JSON do pól JSON"""
        for fld in ["data_zatrudnienia", "data_końca_zatrudnienia"]:
            if self.dane_znormalizowane.get(fld):
                v = self.dane_znormalizowane.get(fld)
                if v is None or isinstance(v, date) or v == "":
                    continue
                self.dane_znormalizowane[fld] = date.fromisoformat(v)

        return self.dane_znormalizowane

    def _check_autor_needs_update(self, dane):
        """Sprawdza czy autor wymaga aktualizacji."""
        a = self.autor
        for klucz_danych, atrybut_autora in self.MAPPING_DANE_NA_AUTOR:
            v = dane.get(klucz_danych)
            if v is not None and str(v) != "" and getattr(a, atrybut_autora) != v:
                return True
        return self.tytul_id != a.tytul_id

    def _check_autor_jednostka_needs_update(self, dane):
        """Sprawdza czy powiązanie autor-jednostka wymaga aktualizacji."""
        aj = self.autor_jednostka
        checks = [
            dane.get("data_zatrudnienia") is not None
            and aj.rozpoczal_prace != dane["data_zatrudnienia"],
            dane.get("data_końca_zatrudnienia") is not None
            and aj.zakonczyl_prace != dane["data_końca_zatrudnienia"],
            aj.funkcja != self.funkcja_autora,
            aj.grupa_pracownicza != self.grupa_pracownicza,
            aj.wymiar_etatu != self.wymiar_etatu,
            self.podstawowe_miejsce_pracy != aj.podstawowe_miejsce_pracy,
        ]
        return any(checks)

    def check_if_integration_needed(self):
        dane = self.dane_bardziej_znormalizowane
        return self._check_autor_needs_update(
            dane
        ) or self._check_autor_jednostka_needs_update(dane)

    def _integrate_autor(self):
        dane = self.dane_znormalizowane
        a = self.autor

        def _spr(klucz_danych, atrybut_autora):
            v = dane.get(klucz_danych)
            if v is None or (str(v) == ""):
                return

            if getattr(a, atrybut_autora) != v:
                return True

        for klucz_danych, atrybut_autora in self.MAPPING_DANE_NA_AUTOR:
            if _spr(klucz_danych, atrybut_autora):
                self.log_zmian["autor"].append(
                    f"{atrybut_autora} -> {dane.get(klucz_danych)}"
                )
                setattr(a, atrybut_autora, dane.get(klucz_danych))

        if self.tytul_id is not None:
            if a.tytul_id != self.tytul_id:
                a.tytul_id = self.tytul_id
                self.log_zmian["autor"].append(
                    f"tytuł naukowy -> {self.tytul.skrot if self.tytul_id else 'brak'}"
                )

        try:
            a.save()
        except DataError as e:
            raise BPPDatabaseError(self.dane_z_xls, self, f"DataError {e}") from e

    def _integrate_autor_jednostka(self):
        aj = self.autor_jednostka
        dane = self.dane_bardziej_znormalizowane

        if (
            dane.get("data_zatrudnienia") is not None
            and aj.rozpoczal_prace != dane["data_zatrudnienia"]
        ):
            aj.rozpoczal_prace = dane["data_zatrudnienia"]
            self.log_zmian["autor_jednostka"].append(
                f"data zatrudnienia na {dane['data_zatrudnienia']}"
            )

        if (
            dane.get("data_końca_zatrudnienia") is not None
            and aj.zakonczyl_prace != dane["data_końca_zatrudnienia"]
        ):
            aj.zakonczyl_prace = dane["data_końca_zatrudnienia"]
            self.log_zmian["autor_jednostka"].append(
                f"data końca zatrudnienia na {dane['data_końca_zatrudnienia']}"
            )

        if aj.funkcja != self.funkcja_autora:
            aj.funkcja = self.funkcja_autora
            self.log_zmian["autor_jednostka"].append(
                f"funkcja na {self.funkcja_autora}"
            )

        if aj.grupa_pracownicza != self.grupa_pracownicza:
            aj.grupa_pracownicza = self.grupa_pracownicza
            self.log_zmian["autor_jednostka"].append(
                f"grupa_pracownicza na {self.grupa_pracownicza}"
            )

        if aj.wymiar_etatu != self.wymiar_etatu:
            aj.wymiar_etatu = self.wymiar_etatu
            self.log_zmian["autor_jednostka"].append(
                f"wymiar_etatu na {self.wymiar_etatu}"
            )

        if self.podstawowe_miejsce_pracy != aj.podstawowe_miejsce_pracy:
            if not self.podstawowe_miejsce_pracy:
                aj.podstawowe_miejsce_pracy = False
                self.log_zmian["autor_jednostka"].append(
                    "podstawowe_miejsce_pracy -> nie"
                )
            else:
                aj.ustaw_podstawowe_miejsce_pracy()
                self.log_zmian["autor_jednostka"].append(
                    "podstawowe_miejsce_pracy -> tak"
                )

        aj.save()

    @transaction.atomic
    def integrate(self):
        assert self.zmiany_potrzebne
        self.log_zmian = {"autor": [], "autor_jednostka": []}
        self._integrate_autor()
        self._integrate_autor_jednostka()
        self.save()

    def sformatowany_log_zmian(self):
        if self.log_zmian is None:
            return

        if self.log_zmian["autor"]:
            yield "Zmiany obiektu Autor: " + ", ".join(
                [elem for elem in self.log_zmian["autor"]]
            )

        if self.log_zmian["autor_jednostka"]:
            yield "Zmiany obiektu Autor_Jednostka: " + ", ".join(
                [elem for elem in self.log_zmian["autor_jednostka"]]
            )

        if not self.log_zmian:
            return "bez zmian!"
