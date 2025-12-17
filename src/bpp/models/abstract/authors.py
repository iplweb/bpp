"""
Modele abstrakcyjne związane z odpowiedzialnością autorów.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CASCADE, SET_NULL, Q, Sum

from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina, Dyscyplina_Naukowa
from bpp.models.util import dodaj_autora


class BazaModeluOdpowiedzialnosciAutorow(models.Model):
    """Bazowa klasa dla odpowiedzialności autorów (czyli dla przypisania
    autora do czegokolwiek innego). Zawiera wszystkie informacje dla autora,
    czyli: powiązanie ForeignKey, jednostkę, rodzaj zapisu nazwiska, ale
    nie zawiera podstawowej informacji, czyli powiązania"""

    autor = models.ForeignKey("bpp.Autor", CASCADE)
    jednostka = models.ForeignKey("bpp.Jednostka", CASCADE)
    kierunek_studiow = models.ForeignKey(
        "bpp.Kierunek_Studiow", SET_NULL, blank=True, null=True
    )
    kolejnosc = models.IntegerField("Kolejność", default=0)
    typ_odpowiedzialnosci = models.ForeignKey(
        "bpp.Typ_Odpowiedzialnosci", CASCADE, verbose_name="Typ odpowiedzialności"
    )
    zapisany_jako = models.CharField(max_length=512)
    afiliuje = models.BooleanField(
        default=True,
        help_text="""Afiliuje
    się do jednostki podanej w przypisaniu. Jednostka nie może być obcą. """,
    )
    zatrudniony = models.BooleanField(
        default=False,
        help_text="""Pracownik
    jednostki podanej w przypisaniu""",
    )

    procent = models.DecimalField(
        "Udział w opracowaniu (procent)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    dyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa, on_delete=SET_NULL, null=True, blank=True
    )

    przypieta = models.BooleanField(
        default=True,
        db_index=True,
        help_text="""Możesz odznaczyć, żeby "odpiąć" dyscyplinę od tego autora. Dyscyplina "odpięta" nie będzie
        wykazywana do PBN oraz nie będzie używana do liczenia punktów dla danej pracy.""",
    )

    upowaznienie_pbn = models.BooleanField(
        "Upoważnienie PBN",
        default=False,
        help_text='Tik w polu "upoważnienie PBN" oznacza, że dany autor upoważnił '
        "Uczelnię do sprawozdania tej publikacji w ocenie parametrycznej Uczelni",
    )

    oswiadczenie_ken = models.BooleanField(
        "Oświadczenie KEN",
        null=True,
        blank=True,
        default=None,
        help_text="Oświadczenie Komisji Ewaluacji Nauki (Uniwersytet Medyczny w Lublinie)",
    )

    profil_orcid = models.BooleanField(
        "Praca w profilu ORCID autora",
        default=False,
        help_text="Zaznacz, jeżeli praca znajdje się na profilu ORCID autora",
    )

    data_oswiadczenia = models.DateField(
        "Data oświadczenia",
        null=True,
        blank=True,
        help_text="Informacja eksportowana do PBN, gdy uzupełniono",
    )

    ostatnio_zmieniony = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ("kolejnosc", "typ_odpowiedzialnosci__skrot")

    def __str__(self):
        return str(self.autor) + " - " + str(self.jednostka.skrot)

    def save(self, *args, **kw):
        if "__disable_bmoa_clean_method" in kw:
            del kw["__disable_bmoa_clean_method"]
        else:
            self.clean()
        from bpp.models import Autor_Jednostka

        if (
            getattr(settings, "BPP_DODAWAJ_JEDNOSTKE_PRZY_ZAPISIE_PRACY", True)
            and not Autor_Jednostka.objects.filter(
                autor_id=self.autor_id, jednostka_id=self.jednostka_id
            ).exists()
        ):
            Autor_Jednostka.objects.create(
                autor_id=self.autor_id,
                jednostka_id=self.jednostka_id,
            )
            # olewamy refresh_from_db i autor.aktualna_jednostka

        return super().save(*args, **kw)

    def rodzaj_autora_uwzgledniany_w_kalkulacjach_slotow(self):
        from ewaluacja_common.models import Rodzaj_Autora

        return self.autor.autor_dyscyplina_set.filter(
            rok=self.rekord.rok,
            rodzaj_autora__pk__in=Rodzaj_Autora.objects.filter(
                licz_sloty=True
            ).values_list("pk", flat=True),
        ).exists()

    def okresl_dyscypline(self):
        return self.dyscyplina_naukowa

        # Ponizej wykomentowane automatyczne zachowanie, obecne w systemie do wersji 1.0.30-dev2,
        # którego po tej wersji NIE chcemy. Chcemy mieć explicte określoną dyscyplinę naukową.
        # Jednakże, gdyby się okazało, że należy powrócić do jakiejś automatyki w tym temacie,
        # API .okresl_dyscyplinę na ten moment zostaje, jak i resztka z tego kodu, któro
        # zapewniało zachowanie automatyczne:

        # # Jeżeli nie, sprawdź, czy dla danego autora jest określona dyscyplina
        # # na dany rok:
        # try:
        #     ad = Autor_Dyscyplina.objects.get(
        #         autor_id=self.autor_id,
        #         rok=self.rekord.rok,
        #     )
        # except Autor_Dyscyplina.DoesNotExist:
        #     return
        #
        # # Zwróć przypisaną dyscyplinę naukową tylko w sytuacji, gdy jest
        # # określona jedna. Jeżeli są dwie, to nie można określić z automatu
        # if ad.subdyscyplina_naukowa is None:
        #     return ad.dyscyplina_naukowa

    # XXX TODO sprawdzanie, żęby nie było dwóch autorów o tej samej kolejności

    def _waliduj_dyscypline(self):
        """Validate discipline assignment."""
        if self.dyscyplina_naukowa is None:
            return

        if self.rekord_id is None and self.rekord is None:
            raise ValidationError(
                {
                    "dyscyplina_naukowa": "Określono dyscyplinę naukową, ale brak publikacji nadrzędnej. "
                }
            )

        if self.rekord is not None and self.rekord.rok is None:
            raise ValidationError(
                {"dyscyplina_naukowa": "Publikacja nadrzędna nie ma określonego roku."}
            )

        try:
            Autor_Dyscyplina.objects.get(
                Q(dyscyplina_naukowa=self.dyscyplina_naukowa)
                | Q(subdyscyplina_naukowa=self.dyscyplina_naukowa),
                autor=self.autor,
                rok=self.rekord.rok,
            )
        except Autor_Dyscyplina.DoesNotExist:
            raise ValidationError(
                {
                    "dyscyplina_naukowa": "Autor nie ma przypisania na dany rok do takiej dyscypliny."
                }
            ) from None

    def _waliduj_rekord(self):
        """Validate parent record."""
        ValErrRek = ValidationError(
            "Rekord nadrzędny (pole: rekord) musi być ustalone. "
        )
        if hasattr(self, "rekord"):
            if self.rekord is None:
                raise ValErrRek
        else:
            if self.rekord_id is None:
                raise ValErrRek

    def _waliduj_procent(self):
        """Validate percentage doesn't exceed 100."""
        inne = self.__class__.objects.filter(rekord=self.rekord)
        if self.pk:
            inne = inne.exclude(pk=self.pk)
        suma = inne.aggregate(Sum("procent"))["procent__sum"] or Decimal("0.00")
        procent = self.procent or Decimal("0.00")

        if suma + procent > Decimal("100.00"):
            raise ValidationError(
                {
                    "procent": "Suma podanych odpowiedzialności przekracza 100. "
                    "Jeżeli edytujesz rekord, spróbuj zrobić to w dwóch etapach. W pierwszym "
                    "zmniejsz punkty procentowe innym, zapisz, w następnym zwiększ punkty "
                    "procentowe i zapisz ponownie. Rekordy nie zostały zapisane. "
                }
            )

    def _waliduj_afiliacje(self):
        """Validate affiliation - author can't affiliate to foreign unit."""
        if (
            self.afiliuje
            and self.jednostka_id is not None
            and self.jednostka.skupia_pracownikow is False
            and getattr(settings, "BPP_WALIDUJ_AFILIACJE_AUTOROW", True)
        ):
            raise ValidationError(
                {
                    "afiliuje": "Jeżeli autor opracował tą pracę w obcej jednostce, to pole "
                    "'Afiliuje' nie powinno być zaznaczone."
                }
            )

    def _waliduj_oswiadczenia_ken(self):
        """Validate KEN declarations - can't have both PBN authorization and KEN declaration."""
        if self.upowaznienie_pbn and self.oswiadczenie_ken:
            msg = (
                "Pola 'Upoważnienie PBN' oraz 'Oświadczenie KEN' nie mogą być jednocześnie wybrane. "
                "Odznacz jedno lub drugie. "
            )
            raise ValidationError(
                {
                    "upowaznienie_pbn": msg,
                    "oswiadczenie_ken": msg,
                }
            )

    def clean(self):
        self._waliduj_dyscypline()
        self._waliduj_rekord()
        self._waliduj_procent()
        self._waliduj_afiliacje()
        self._waliduj_oswiadczenia_ken()


class MaProcentyMixin:
    def ma_procenty(self):
        for autor in self.autorzy_set.all():
            if autor.procent:
                return True
        return False


class NieMaProcentowMixin:
    def ma_procenty(self):
        return False


class DodajAutoraMixin:
    """Funkcja pomocnicza z dodawaniem autora do rekordu, raczej na 99%
    używana tylko i wyłącznie przez testy. Musisz określić self.autor_rekordu_class
    czyli np dla Wydawnictwo_Zwarte ta zmienna powinna przyjąć wartość
    Wydawnictwo_Zwarte_Autor."""

    autor_rekordu_klass = None

    def dodaj_autora(
        self,
        autor,
        jednostka,
        zapisany_jako=None,
        typ_odpowiedzialnosci_skrot="aut.",
        kolejnosc=None,
        dyscyplina_naukowa=None,
        afiliuje=True,
    ):
        """
        :rtype: bpp.models.abstract.BazaModeluOdpowiedzialnosciAutorow
        """
        return dodaj_autora(
            klass=self.autor_rekordu_klass,
            rekord=self,
            autor=autor,
            jednostka=jednostka,
            zapisany_jako=zapisany_jako,
            typ_odpowiedzialnosci_skrot=typ_odpowiedzialnosci_skrot,
            kolejnosc=kolejnosc,
            dyscyplina_naukowa=dyscyplina_naukowa,
            afiliuje=afiliuje,
        )
