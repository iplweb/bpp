from datetime import date

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, models, transaction
from django.db.models import CASCADE, Count, JSONField, Q
from django.urls import reverse
from django_fsm import GET_STATE, FSMField, transition
from model_utils.models import TimeStampedModel

from bpp.fields import YearField
from bpp.models import Autor, Autor_Dyscyplina, Dyscyplina_Naukowa, Jednostka, Wydzial
from django_bpp.settings.base import AUTH_USER_MODEL
from import_common.exceptions import (
    BadNoOfSheetsException,
    HeaderNotFoundException,
    ImproperFileException,
)
from import_common.util import znajdz_naglowek


def obecny_rok():
    return date.today().year


class Kolumna(models.Model):
    parent = models.ForeignKey("import_dyscyplin.Import_Dyscyplin", models.CASCADE)

    class RODZAJ:
        POMIJAJ = "pomiń"

        TYTUL = "tytuł"

        NAZWISKO = "nazwisko"
        IMIE = "imię"
        ORCID = "orcid"
        PBN_ID = "pbn_id"
        NAZWA_JEDNOSTKI = "nazwa jednostki"
        WYDZIAL = "wydział"

        DYSCYPLINA = "dyscyplina"
        KOD_DYSCYPLINY = "kod dyscypliny"
        PROCENT_DYSCYPLINY = "procent dyscypliny"

        SUBDYSCYPLINA = "subdyscyplina"
        KOD_SUBDYSCYPLINY = "kod subdyscypliny"
        PROCENT_SUBDYSCYPLINY = "procent subdyscypliny"

    RODZAJE = [
        RODZAJ.TYTUL,
        RODZAJ.NAZWISKO,
        RODZAJ.IMIE,
        RODZAJ.ORCID,
        RODZAJ.PBN_ID,
        RODZAJ.NAZWA_JEDNOSTKI,
        RODZAJ.WYDZIAL,
        RODZAJ.DYSCYPLINA,
        RODZAJ.KOD_DYSCYPLINY,
        RODZAJ.PROCENT_DYSCYPLINY,
        RODZAJ.SUBDYSCYPLINA,
        RODZAJ.KOD_SUBDYSCYPLINY,
        RODZAJ.PROCENT_SUBDYSCYPLINY,
        RODZAJ.POMIJAJ,
    ]

    kolejnosc = models.PositiveSmallIntegerField()
    nazwa_w_pliku = models.CharField(max_length=250)
    rodzaj_pola = models.CharField(
        max_length=50, choices=zip(RODZAJE, RODZAJE, strict=False)
    )

    class Meta:
        ordering = [
            "kolejnosc",
        ]


# Słownik mapowania nazw kolumn na rodzaje pól - używany przez guess_rodzaj()
_NAZWA_DO_RODZAJU: dict[str, str] = {}


def _zbuduj_mapowanie_nazw():
    """Buduje słownik mapowania nazw na rodzaje pól."""
    mapowania = [
        (
            Kolumna.RODZAJ.TYTUL,
            [
                "tytuł_stopień",
                "tytuł",
                "tytułnaukowy",
                "tytuł/stopień",
                "tytułstopień",
                "stopieńnaukowy",
                "stopień",
                "stopien",
                "tytul",
                "tytulnaukowy",
            ],
        ),
        (Kolumna.RODZAJ.NAZWISKO, ["nazwisko", "nazwiska"]),
        (Kolumna.RODZAJ.IMIE, ["imię", "imie", "imiona"]),
        (Kolumna.RODZAJ.ORCID, ["orcid", "identyfikatororcid", "ident.orcid"]),
        (
            Kolumna.RODZAJ.NAZWA_JEDNOSTKI,
            ["jednostka", "nazwajednostki", "nazwa_jednostki"],
        ),
        (Kolumna.RODZAJ.WYDZIAL, ["wydzial", "wydz.", "wydział"]),
        (
            Kolumna.RODZAJ.DYSCYPLINA,
            ["dyscyplina", "dyscyplina1", "dyscyplinagłówna", "dyscyplinaglowna"],
        ),
        (
            Kolumna.RODZAJ.KOD_DYSCYPLINY,
            [
                "kod_dyscypliny",
                "koddyscypliny",
                "koddyscyplinyglownej",
                "koddyscyplinygłównej",
                "kod1",
                "koddyscypliny1",
            ],
        ),
        (
            Kolumna.RODZAJ.PROCENT_DYSCYPLINY,
            [
                "procent_dyscypliny",
                "procentdyscypliny",
                "procentdyscypliny1",
                "procentdyscyplinygłównej",
                "procentdyscyplinyglownej",
                "udziałprocentowy1",
            ],
        ),
        (
            Kolumna.RODZAJ.SUBDYSCYPLINA,
            ["subdyscyplina", "dyscyplina2", "dyscyplinapoboczna"],
        ),
        (
            Kolumna.RODZAJ.KOD_SUBDYSCYPLINY,
            [
                "kod_subdyscypliny",
                "kodsubdyscypliny",
                "koddyscyplinypoboczej",
                "koddyscyplinydrugiej",
                "kod2",
                "koddyscypliny2",
            ],
        ),
        (
            Kolumna.RODZAJ.PROCENT_SUBDYSCYPLINY,
            [
                "procent_subdyscypliny",
                "procentsubdyscypliny",
                "procentdyscypliny2",
                "procentdyscyplinypobocznej",
                "udziałprocentowy2",
            ],
        ),
        (
            Kolumna.RODZAJ.PBN_ID,
            ["pbn_id", "pbn-id", "pbnid", "pbn*id", "identyfikatorpbn", "ident.pbn"],
        ),
    ]
    for rodzaj, nazwy in mapowania:
        for nazwa in nazwy:
            _NAZWA_DO_RODZAJU[nazwa] = rodzaj


def guess_rodzaj(s):
    """Odgaduje rodzaj kolumny na podstawie nazwy z pliku."""
    if not _NAZWA_DO_RODZAJU:
        _zbuduj_mapowanie_nazw()
    s = s.lower().replace(" ", "")
    return _NAZWA_DO_RODZAJU.get(s, Kolumna.RODZAJ.POMIJAJ)


class Import_Dyscyplin(TimeStampedModel):
    class STAN:
        NOWY = "nowy"
        OKRESLANIE_OPCJI_IMPORTU = "określanie opcji importu"
        OPCJE_IMPORTU_OKRESLONE = "opcje importu określone"
        BLEDNY = "błędny"
        PRZEANALIZOWANY = "przeanalizowany"

        ZINTEGROWANY = "zintegrowany"

    STANY = (
        STAN.NOWY,
        STAN.OKRESLANIE_OPCJI_IMPORTU,
        STAN.OPCJE_IMPORTU_OKRESLONE,
        STAN.PRZEANALIZOWANY,
        STAN.BLEDNY,
        STAN.ZINTEGROWANY,
    )

    owner = models.ForeignKey(AUTH_USER_MODEL, CASCADE)
    web_page_uid = models.CharField(max_length=36, blank=True, default="")
    web_page_uid.__doc__ = (
        "UUID4 strony internetowej która może być używana do notyfikacji. "
    )

    task_id = models.CharField(max_length=36, blank=True, default="")
    task_id.__doc__ = "celery.uuid() z identyfikatorem zadania"

    plik = models.FileField(upload_to="protected/import_dyscyplin/")
    rok = YearField(default=obecny_rok)
    stan = FSMField(
        default=STAN.NOWY, choices=zip(STANY, STANY, strict=False), protected=True
    )

    bledny = models.BooleanField(default=False)
    info = models.TextField(blank=True, default="")

    wiersz_naglowka = models.PositiveSmallIntegerField(null=True, blank=True)

    kolumny = models.ManyToManyField(Kolumna)

    @transition(
        field=stan,
        source=STAN.NOWY,
        target=GET_STATE(
            lambda self: (
                self.STAN.BLEDNY if self.bledny else self.STAN.OKRESLANIE_OPCJI_IMPORTU
            ),
            states=[STAN.BLEDNY, STAN.OKRESLANIE_OPCJI_IMPORTU],
        ),
        on_error=STAN.BLEDNY,
    )
    def stworz_kolumny(self):
        try:
            kolumny, wiersz = znajdz_naglowek(self.plik.path)
        except ImproperFileException as e:
            self.bledny = True
            self.info = f"niepoprawny plik - {e}"
            return
        except BadNoOfSheetsException:
            self.bledny = True
            self.info = "Plik musi zawierać tylko jeden arkusz"
            return
        except HeaderNotFoundException:
            self.bledny = True
            self.info = "Nagłówek nie został znaleziony"
            return

        self.kolumna_set.all().delete()
        for n, kolumna in enumerate(kolumny):
            Kolumna.objects.create(
                parent=self,
                kolejnosc=n,
                nazwa_w_pliku=kolumna,
                rodzaj_pola=guess_rodzaj(kolumna) or Kolumna.RODZAJ.POMIJAJ,
            )
        self.wiersz_naglowka = wiersz
        self.save()

    @transition(
        field=stan,
        source=STAN.OKRESLANIE_OPCJI_IMPORTU,
        target=STAN.OPCJE_IMPORTU_OKRESLONE,
    )
    def zatwierdz_kolumny(self):
        self.save()

    @transition(
        field=stan,
        source=STAN.OPCJE_IMPORTU_OKRESLONE,
        target=GET_STATE(
            lambda self: "błędny" if self.bledny else "przeanalizowany",
            states=[STAN.BLEDNY, STAN.PRZEANALIZOWANY],
        ),
        on_error=STAN.BLEDNY,
    )
    def przeanalizuj(self):
        from import_dyscyplin.core import przeanalizuj_plik_xls

        przeanalizuj_plik_xls(self.plik.path, parent=self)

    def wiersze(self):
        return Import_Dyscyplin_Row.objects.filter(parent=self)

    def poprawne_wiersze_do_integracji(self):
        return (
            self.wiersze()
            .exclude(autor_id=None)
            .exclude(stan=Import_Dyscyplin_Row.STAN.BLEDNY)
            .exclude(stan=Import_Dyscyplin_Row.STAN.ZINTEGROWANY)
        )

    def niepoprawne_wiersze(self):
        return self.wiersze().filter(
            Q(autor_id=None) | Q(stan=Import_Dyscyplin_Row.STAN.BLEDNY)
        )

    def distinct_info_dla_qs(self, qs):
        return (
            qs.order_by("info").values("info").annotate(icount=Count("info")).distinct()
        )

    def niepoprawne_wiersze_przyczyny(self):
        return self.distinct_info_dla_qs(self.niepoprawne_wiersze())

    def zintegrowane_wiersze_przyczyny(self):
        return self.distinct_info_dla_qs(self.zintegrowane_wiersze())

    def zintegrowane_wiersze(self):
        return self.wiersze().filter(stan=Import_Dyscyplin_Row.STAN.ZINTEGROWANY)

    def integruj_dyscypliny(self):
        # order_by jest w poniższym zapytaniu potrzebny, żeby pozbyć się
        # problemu z domyślnym porządkiem sortowania, wywołanym przez
        # Import_Dyscyplin_Row.Meta - wówczas distinct powinien zawierać
        # również kolumny po których sortujemy, a to jest nam zbędne, więc:
        for elem in (
            self.wiersze()
            .order_by("dyscyplina")
            .values(
                "dyscyplina", "kod_dyscypliny", "subdyscyplina", "kod_subdyscypliny"
            )
            .distinct()
        ):
            if not elem["dyscyplina"] or not elem["kod_dyscypliny"]:
                continue

            try:
                d, _c = Dyscyplina_Naukowa.objects.get_or_create(
                    nazwa=elem["dyscyplina"], kod=elem["kod_dyscypliny"]
                )
            except IntegrityError:
                for r in self.wiersze().filter(
                    dyscyplina=elem["dyscyplina"], kod_dyscypliny=elem["kod_dyscypliny"]
                ):
                    r.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                    r.info = (
                        "Nie można zintegrować nazwy i kodu dyscypliny. W bazie danych istnieje "
                        "już rekord o takiej nazwie i innym kodzie lub o takim kodzie ale o innej "
                        "nazwie."
                    )
                    r.save()

                continue

            for r in self.wiersze().filter(
                dyscyplina=elem["dyscyplina"], kod_dyscypliny=elem["kod_dyscypliny"]
            ):
                r.dyscyplina_naukowa = d
                r.save()

            if not elem["subdyscyplina"] or not elem["kod_subdyscypliny"]:
                continue

            try:
                sd, _c = Dyscyplina_Naukowa.objects.get_or_create(
                    nazwa=elem["subdyscyplina"], kod=elem["kod_subdyscypliny"]
                )
            except IntegrityError:
                for r in self.wiersze().filter(
                    subdyscyplina=elem["subdyscyplina"],
                    kod_subdyscypliny=elem["kod_subdyscypliny"],
                ):
                    r.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                    r.info = (
                        "Nie można zintegrować nazwy i kodu subdyscypliny. W bazie danych istnieje "
                        "już rekord o takiej nazwie i innym kodzie lub o takim kodzie ale o innej "
                        "nazwie."
                    )
                    r.save()
                continue

            for r in self.wiersze().filter(
                subdyscyplina=elem["subdyscyplina"],
                kod_subdyscypliny=elem["kod_subdyscypliny"],
            ):
                r.subdyscyplina_naukowa = sd
                r.save()

    def sprawdz_czy_konieczne(self):
        """Sprawdza wszystkie wiersze, po przeanalizowaniu oraz po
        integracji dyscyplin, czy wprowadzanie ich jest konieczne do bazy. To znaczy,
        jeżeli istnieją już takie przypisania do autora i dyscypliny, to oznacz
        takie rekordy adekwatnie.
        """
        for elem in self.poprawne_wiersze_do_integracji().select_related():
            try:
                Autor_Dyscyplina.objects.get(
                    autor=elem.autor,
                    rok=self.rok,
                    dyscyplina_naukowa=elem.subdyscyplina_naukowa,
                    procent_dyscypliny=elem.procent_dyscypliny,
                    subdyscyplina_naukowa=elem.subdyscyplina_naukowa,
                    procent_subdyscypliny=elem.procent_subdyscypliny,
                )
                elem.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                elem.info = "Istnieje identyczne przypisanie"
                elem.save()
                continue
            except Autor_Dyscyplina.DoesNotExist:
                try:
                    Autor_Dyscyplina.objects.get(autor=elem.autor, rok=self.rok)

                except Autor_Dyscyplina.DoesNotExist:
                    if (
                        elem.dyscyplina_naukowa is None
                        and elem.subdyscyplina_naukowa is None
                    ):
                        elem.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                        elem.info = "To przypisanie zostało już usunięte"
                        elem.save()
                        continue

            if elem.dyscyplina_naukowa is None:
                elem.info = "Skasuję przypisanie na ten rok. "
                elem.save()

    def id_zdublowanych_autorow(self):
        return (
            self.poprawne_wiersze_do_integracji()
            .values_list("autor_id", flat=True)
            .order_by("autor_id")
            .annotate(acount=Count("autor_id"))
            .filter(acount__gt=1)
            .distinct()
        )

    def sprawdz_czy_poprawne(self):
        """Sprawdza, czy są wiersze z podwójnym (tym samym) autorem w imporcie"""
        for elem in self.id_zdublowanych_autorow():
            for r in self.poprawne_wiersze_do_integracji().filter(autor_id=elem):
                r.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                r.info = "Więcej, niż jeden wiersz z pliku XLS został dopasowany do tego autora w systemie."
                r.save()

    @transition(
        field=stan,
        source=STAN.PRZEANALIZOWANY,
        target=GET_STATE(
            lambda self: "błędny" if self.bledny else "zintegrowany",
            states=[STAN.BLEDNY, STAN.ZINTEGROWANY],
        ),
        on_error=STAN.BLEDNY,
    )
    def integruj_wiersze(self):
        return self._integruj_wiersze()

    def _integruj_wiersze(self):
        for elem in self.poprawne_wiersze_do_integracji().select_related():
            if elem.dyscyplina_naukowa is None:
                # Kasowanie
                # elem["subdyscyplina_naukowa"] został już wcześniej sprawdzony.
                Autor_Dyscyplina.objects.get(autor=elem.autor, rok=self.rok).delete()
                elem.info = f"Usunięto przypisanie do dyscyplin za rok {self.rok}"
                elem.stan = Import_Dyscyplin_Row.STAN.ZINTEGROWANY
                elem.save()
                continue

            try:
                ad = Autor_Dyscyplina.objects.get(autor=elem.autor, rok=self.rok)

                changed = False
                for attr in [
                    "dyscyplina_naukowa",
                    "procent_dyscypliny",
                    "subdyscyplina_naukowa",
                    "procent_subdyscypliny",
                ]:
                    source = getattr(elem, attr)
                    target = getattr(ad, attr)

                    if source != target:
                        setattr(ad, attr, source)
                        if elem.info is None:
                            elem.info = ""

                        elem.info += (
                            f"Istniejące {attr.replace('_', ' ')} dla roku {self.rok} "
                            f"zmieniono z {target or '[brak]'} na {source or '[brak]'}. "
                        )

                        changed = True

                if changed:
                    ad.save()
                else:
                    elem.info = "stan w bazie zgodny jak w pliku importu"

            except Autor_Dyscyplina.DoesNotExist:
                Autor_Dyscyplina.objects.create(
                    autor=elem.autor,
                    rok=self.rok,
                    dyscyplina_naukowa=elem.dyscyplina_naukowa,
                    procent_dyscypliny=elem.procent_dyscypliny,
                    subdyscyplina_naukowa=elem.subdyscyplina_naukowa,
                    procent_subdyscypliny=elem.procent_subdyscypliny,
                )
                subdyscyplina_str = (
                    f", {elem.subdyscyplina_naukowa}"
                    if elem.subdyscyplina_naukowa
                    else ""
                )
                elem.info = (
                    f"nowe przypisanie dla {self.rok}: "
                    f"{elem.dyscyplina_naukowa}{subdyscyplina_str}."
                )

            elem.stan = Import_Dyscyplin_Row.STAN.ZINTEGROWANY
            elem.save()

        Autor_Dyscyplina.objects.ukryj_nieuzywane()

    def delete(self, *args, **kw):
        transaction.on_commit(lambda instance=self: instance.plik.delete(False))
        return super().delete(*args, **kw)

    class Meta:
        ordering = ("-modified",)


class Import_Dyscyplin_Row(models.Model):
    class STAN:
        NOWY = "nowy"
        BLEDNY = "błędny"
        ZINTEGROWANY = "zintegrowany"

    STANY = (STAN.NOWY, STAN.BLEDNY, STAN.ZINTEGROWANY)

    parent = models.ForeignKey(Import_Dyscyplin, CASCADE)

    stan = models.CharField(
        max_length=50,
        choices=zip(STANY, STANY, strict=False),
        default=STAN.NOWY,
        db_index=True,
    )
    info = models.TextField(blank=True, default="")

    row_no = models.IntegerField()
    original = JSONField(encoder=DjangoJSONEncoder)

    nazwisko = models.CharField(max_length=200)
    imiona = models.CharField(max_length=200)

    autor = models.ForeignKey(Autor, null=True, on_delete=models.SET_NULL)

    nazwa_jednostki = models.CharField(max_length=512, blank=True, default="")
    jednostka = models.ForeignKey(Jednostka, null=True, on_delete=models.SET_NULL)

    nazwa_wydzialu = models.CharField(max_length=512, blank=True, default="")
    wydzial = models.ForeignKey(Wydzial, null=True, on_delete=models.SET_NULL)

    dyscyplina = models.CharField(max_length=200, db_index=True, blank=True, default="")
    kod_dyscypliny = models.CharField(
        max_length=20, db_index=True, blank=True, default=""
    )
    procent_dyscypliny = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    dyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    subdyscyplina = models.CharField(
        max_length=200, blank=True, default="", db_index=True
    )
    kod_subdyscypliny = models.CharField(
        max_length=20, blank=True, default="", db_index=True
    )
    procent_subdyscypliny = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    subdyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ("nazwisko", "imiona")

    def serialize_dict(self):
        ret = {
            "nazwisko": self.nazwisko,
            "imiona": self.imiona,
            "jednostka": self.original.get("nazwa jednostki", ""),
            "wydzial": self.original.get("wydzia", ""),
            "info": self.info,
            "dyscyplina": f"{self.dyscyplina} ({self.kod_dyscypliny})",
            "procent_dyscypliny": self.procent_dyscypliny or "",
            "subdyscyplina": f"{self.subdyscyplina} ({self.kod_subdyscypliny})".replace(
                "None ()", ""
            ),
            "procent_subdyscypliny": self.procent_subdyscypliny or "",
            "dopasowanie_autora": "-",
        }

        for elem in "dyscyplina", "subdyscyplina":
            if ret[elem] == " ()":
                ret[elem] = ""

        if self.autor is not None:
            ret["autor_slug"] = self.autor.slug
            ret["dopasowanie_autora"] = "<a target=_blank href='{}'>{} {}</a>".format(
                reverse("bpp:browse_autor", args=(self.autor.slug,)),
                self.autor.nazwisko,
                self.autor.imiona,
            )

        return ret
