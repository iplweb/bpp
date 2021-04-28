# Create your models here.
from copy import copy
from datetime import date

from django import forms
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DataError, IntegrityError, models, transaction

from import_common.core import (
    matchuj_autora,
    matchuj_funkcja_autora,
    matchuj_grupa_pracownicza,
    matchuj_jednostke,
    matchuj_wymiar_etatu,
)
from import_common.exceptions import (
    BPPDatabaseError,
    BPPDatabaseMismatch,
    XLSMatchError,
    XLSParseError,
)
from import_common.forms import ExcelDateField
from import_common.models import ImportRowMixin
from import_common.normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_nullboleanfield,
    normalize_wymiar_etatu,
)
from import_common.util import XLSImportFile
from long_running.models import Operation
from long_running.notification_mixins import ASGINotificationMixin

from django.contrib.postgres.fields import JSONField

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jednostka,
    Wymiar_Etatu,
)


class JednostkaForm(forms.Form):
    nazwa_jednostki = forms.CharField(max_length=10240)
    wydział = forms.CharField(max_length=500)


class AutorForm(forms.Form):
    nazwisko = forms.CharField(max_length=200)
    imię = forms.CharField(max_length=200)

    numer = forms.IntegerField(required=False)
    orcid = forms.CharField(max_length=19, required=False)
    tytuł_stopień = forms.CharField(max_length=200, required=False)
    pbn_uuid = forms.UUIDField(required=False)
    bpp_id = forms.IntegerField(required=False)

    stanowisko = forms.CharField(max_length=200)
    grupa_pracownicza = forms.CharField(max_length=200)
    data_zatrudnienia = ExcelDateField()
    data_końca_zatrudnienia = ExcelDateField(required=False)
    podstawowe_miejsce_pracy = forms.BooleanField(required=False)
    wymiar_etatu = forms.CharField(max_length=200)


class ImportPracownikow(ASGINotificationMixin, Operation):
    plik_xls = models.FileField()

    performed = models.BooleanField(default=False)
    integrated = models.BooleanField(default=False)

    @transaction.atomic
    def on_reset(self):
        self.performed = self.integrated = False
        self.importpracownikowrow_set.all().delete()
        self.save()

    def perform(self):
        xif = XLSImportFile(self.plik_xls.path)
        total = xif.count()

        for no, elem in enumerate(xif.data()):

            jednostka_form = JednostkaForm(data=elem)
            jednostka_form.full_clean()
            if not jednostka_form.is_valid():
                raise XLSParseError(elem, jednostka_form, "weryfikacja nazwy jednostki")

            try:
                jednostka = matchuj_jednostke(
                    jednostka_form.cleaned_data.get("nazwa_jednostki"),
                    wydzial=jednostka_form.cleaned_data.get("wydział"),
                )
            except Jednostka.MultipleObjectsReturned:
                raise XLSMatchError(
                    elem, "jednostka", "wiele dopasowań w systemie - po nazwie"
                )

            except Jednostka.DoesNotExist:
                raise XLSMatchError(
                    elem, "jednostka", "brak dopasowania w systemie - po nazwie"
                )

            autor_form = AutorForm(data=elem)
            autor_form.full_clean()
            if not autor_form.is_valid():
                raise XLSParseError(elem, autor_form, "weryfikacja danych autora")
            assert isinstance(autor_form.cleaned_data.get("data_zatrudnienia"), date)
            data = autor_form.cleaned_data

            # if data.get("tytuł_stopień"):
            #     try:
            #         matchuj_tytul(data.get("tytuł_stopień"))
            #     except Tytul.DoesNotExist:
            #         raise XLSMatchError(
            #             elem, "tytuł", "brak takiego tytułu w systemie (nazwa, skrót)"
            #         )
            #     except Tytul.MultipleObjectsReturned:
            #         raise XLSMatchError(
            #             elem,
            #             "tytuł",
            #             "liczne dopasowania dla takiego tytułu w systemie",
            #         )

            try:
                funkcja_autora = matchuj_funkcja_autora(data.get("stanowisko"))
            except Funkcja_Autora.DoesNotExist:
                try:
                    funkcja_autora = Funkcja_Autora.objects.create(
                        nazwa=normalize_funkcja_autora(data.get("stanowisko")),
                        skrot=normalize_funkcja_autora(data.get("stanowisko")),
                    )
                except IntegrityError:
                    raise XLSParseError(
                        elem,
                        autor_form,
                        "nie można utworzyć nowego stanowiska na bazie takich danych",
                    )

            except Funkcja_Autora.MultipleObjectsReturned:
                raise XLSMatchError(
                    elem,
                    "stanowisko",
                    "liczne dopasowania dla takiej funkcji autora (stanowiska) w systemie",
                )

            try:
                grupa_pracownicza = matchuj_grupa_pracownicza(
                    data.get("grupa_pracownicza")
                )
            except Grupa_Pracownicza.DoesNotExist:
                grupa_pracownicza = Grupa_Pracownicza.objects.create(
                    nazwa=normalize_grupa_pracownicza(data.get("grupa_pracownicza"))
                )

            try:
                wymiar_etatu = matchuj_wymiar_etatu(data.get("wymiar_etatu"))
            except Wymiar_Etatu.DoesNotExist:
                wymiar_etatu = Wymiar_Etatu.objects.create(
                    nazwa=normalize_wymiar_etatu(data.get("wymiar_etatu"))
                )

            autor = matchuj_autora(  # noqa
                imiona=data.get("imię"),
                nazwisko=data.get("nazwisko"),
                jednostka=jednostka,
                bpp_id=data.get("bpp_id"),
                pbn_uid_id=data.get("pbn_uuid"),
                system_kadrowy_id=data.get("numer"),
                pbn_id=data.get("pbn_id"),
                orcid=data.get("orcid"),
                tytul_str=data.get("tytuł_stopień"),
            )
            if autor is None:
                raise XLSMatchError(
                    elem, "autor", "brak dopasowania - różne kombinacje"
                )

            # Jeżeli w danych jest podane BPP ID, ale zwrócony autor nie zmatchował po podanym BPP ID
            # za to zmatchował po innych danych, sprawdźmy czy zwrócone BPP ID jest identyczne
            if data.get("bpp_id") is not None:
                if data.get("bpp_id") != autor.pk:
                    raise XLSMatchError(
                        elem,
                        "autor",
                        "BPP ID zmatchowanego autora i BPP ID w pliku XLS nie zgadzają się",
                    )

            try:
                aj = Autor_Jednostka.objects.get(autor=autor, jednostka=jednostka)
            except Autor_Jednostka.MultipleObjectsReturned:
                if "data_zatrudnienia" in data:
                    try:
                        aj = Autor_Jednostka.objects.get(
                            autor=autor,
                            jednostka=jednostka,
                            rozpoczal_prace=data.get("data_zatrudnienia"),
                        )
                    except Autor_Jednostka.DoesNotExist:
                        raise BPPDatabaseMismatch(
                            elem,
                            "autor + jednostka",
                            "brak jednoznacznego powiązania autor+jednostka po stronie BPP",
                        )
            except Autor_Jednostka.DoesNotExist:
                aj = Autor_Jednostka.objects.create(
                    autor=autor, jednostka=jednostka, funkcja=funkcja_autora
                )

            res = ImportPracownikowRow(
                parent=self,
                dane_z_xls=elem,
                dane_znormalizowane=copy(autor_form.cleaned_data),
                autor=autor,
                jednostka=jednostka,
                autor_jednostka=aj,
                funkcja_autora=funkcja_autora,
                grupa_pracownicza=grupa_pracownicza,
                wymiar_etatu=wymiar_etatu,
                podstawowe_miejsce_pracy=normalize_nullboleanfield(
                    data.get("podstawowe_miejsce_pracy")
                ),
            )
            res.zmiany_potrzebne = res.check_if_integration_needed()
            res.save()

            if no % 10 == 0:
                self.send_progress(no / total / 2.0)

        self.performed = True
        self.save()

        self.integrate()
        self.integrated = True
        self.save()

    @property
    def zmiany_potrzebne_set(self):
        return self.importpracownikowrow_set.filter(zmiany_potrzebne=True)

    def get_details_set(self):
        return self.importpracownikowrow_set.all().select_related(
            "autor",
            "jednostka",
            "jednostka__wydzial",
            "autor__tytul",
            "grupa_pracownicza",
            "funkcja_autora",
            "wymiar_etatu",
        )

    def on_finished(self):
        self.send_processing_finished()

    def integrate(self):
        total = self.zmiany_potrzebne_set.all().count()
        for no, elem in enumerate(
            self.zmiany_potrzebne_set.all().select_related(
                "autor", "jednostka", "jednostka__wydzial", "autor__tytul"
            )
        ):
            elem.integrate()
            self.send_progress(0.5 + (no / total / 2.0))


class ImportPracownikowRow(ImportRowMixin, models.Model):
    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,  # related_name="row_set"
    )
    dane_z_xls = JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    dane_znormalizowane = JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)

    autor = models.ForeignKey(Autor, on_delete=models.CASCADE)
    jednostka = models.ForeignKey(Jednostka, on_delete=models.CASCADE)
    autor_jednostka = models.ForeignKey(Autor_Jednostka, on_delete=models.CASCADE)

    podstawowe_miejsce_pracy = models.NullBooleanField()
    funkcja_autora = models.ForeignKey(Funkcja_Autora, on_delete=models.CASCADE)
    grupa_pracownicza = models.ForeignKey(Grupa_Pracownicza, on_delete=models.CASCADE)
    wymiar_etatu = models.ForeignKey(Wymiar_Etatu, on_delete=models.CASCADE)

    zmiany_potrzebne = models.BooleanField()

    log_zmian = JSONField(encoder=DjangoJSONEncoder, null=True, blank=True)

    MAPPING_DANE_NA_AUTOR = [
        ("numer", "system_kadrowy_id"),
        ("orcid", "orcid"),
        ("pbn_uuid", "pbn_uuid"),
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

    def check_if_integration_needed(self):
        dane = self.dane_bardziej_znormalizowane

        # aktualizacja Autora
        a = self.autor

        def _spr(klucz_danych, atrybut_autora):
            v = dane.get(klucz_danych)
            if v is None or str(v) == "":
                return

            if getattr(a, atrybut_autora) != v:
                return True

        for klucz_danych, atrybut_autora in self.MAPPING_DANE_NA_AUTOR:
            if _spr(klucz_danych, atrybut_autora):
                return True

        # aktualizacja Autor_Jednostka
        aj = self.autor_jednostka

        if (
            dane.get("data_zatrudnienia") is not None
            and aj.rozpoczal_prace != dane["data_zatrudnienia"]
        ):
            return True

        if (
            dane.get("data_końca_zatrudnienia") is not None
            and aj.zakonczyl_prace != dane["data_końca_zatrudnienia"]
        ):
            return True

        if aj.funkcja != self.funkcja_autora:
            return True

        if aj.grupa_pracownicza != self.grupa_pracownicza:
            return True

        if aj.wymiar_etatu != self.wymiar_etatu:
            return True

        if self.podstawowe_miejsce_pracy != aj.podstawowe_miejsce_pracy:
            return True

        return False

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

        try:
            a.save()
        except DataError as e:
            raise BPPDatabaseError(self.dane_z_xls, self, f"DataError {e}")

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
            aj.ustaw_podstawowe_miejsce_pracy()
            self.log_zmian["autor_jednostka"].append("podstawowe_miejsce_pracy")

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
