# Tu skoczyłem
#
# Plan
# 1) zrobić obiekt 'raport uczelnia', zamawianie raportu -> tworzenie go,
# 2) podstrona 'details' to jest:
# - strona po zamowieniu raportu,
# - oczekiwanie na wygenerowanie
# - zamawianie w alternatywnych formatach
# - przejscie do podgladu
#
# 3) listview: raport jest powieszony /rpaort_uczelnia/ID/ i tam jest ListView ewentualnie z filtrami
#
# 4) zadnego progress baru w javie, chociaz nie wiem w sumie
#
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models

from bpp.core import zbieraj_sloty
from bpp.fields import YearField
from bpp.models import Autor, Cache_Punktacja_Autora_Query, Uczelnia
from bpp.util import year_last_month
from long_running.models import Report
from long_running.notification_mixins import ASGINotificationMixin
from raport_slotow.core import autorzy_zerowi


class RaportSlotowUczelnia(ASGINotificationMixin, Report):
    od_roku = YearField(default=year_last_month)
    do_roku = YearField(default=Uczelnia.objects.do_roku_default)

    class Akcje(models.TextChoices):
        SLOTY = "slot", "zbieraj najkorzystniejsze prace do zadanej wielkości slotu"
        WSZYSTKO = "wszystko", "wyeksportuj wszystkie prace"

    akcja = models.CharField(max_length=10, default=Akcje.SLOTY, choices=Akcje.choices)

    slot = models.DecimalField(
        default=Decimal("1"),
        decimal_places=4,
        max_digits=7,
        validators=[MaxValueValidator(20)],
        null=True,
        blank=True,
    )

    minimalny_pk = models.DecimalField(default=0, decimal_places=2, max_digits=5)

    dziel_na_jednostki_i_wydzialy = models.BooleanField(
        verbose_name="Dziel na jednostki i wydziały",
        default=True,
    )

    pokazuj_zerowych = models.BooleanField(
        verbose_name="Dołączaj autorów z zerowymi slotami",
        default=False,
        help_text="""Autor z zerowym slotem to autor, który ma na zadany okres czasu zadeklarowane dyscypliny,
        ale nie posiada żadnych punktowanych prac w tych dyscyplinach. Jeżeli jednoczesnie podasz parametr
         'minimalny PK' dla tego raportu, to prace z PK poniżej tego progu zostaną potraktowane jako "zerowe"
         czyli bez punktacji. """,
    )

    def on_reset(self):
        self.raportslotowuczelniawiersz_set.all().delete()

    def clean(self):
        if self.od_roku > self.do_roku:
            raise ValidationError(
                {
                    "od_roku": ValidationError(
                        'Pole musi być większe lub równe jak pole "Do roku".'
                    )
                }
            )

        if self.akcja == RaportSlotowUczelnia.Akcje.WSZYSTKO:
            if self.slot is not None:
                raise ValidationError(
                    {
                        "slot": ValidationError(
                            "Jeżeli chcesz eksportować wszystkie prace, to wielkość slotu nie "
                            "ma znaczenia. Pozostaw to pole puste. "
                        )
                    }
                )

        if self.akcja == RaportSlotowUczelnia.Akcje.SLOTY:
            if self.slot is None:
                raise ValidationError(
                    {
                        "slot": ValidationError(
                            "Jeżeli chcesz zbierać prace do zadanej wielkości slotu, to musisz "
                            "podać wielkość slotu, do którego zbierać prace. "
                        )
                    }
                )

    def create_report(self):
        # lista wszystkich autorow z punktacja z okresu od-do roku
        lst = "autor_id", "dyscyplina_id"
        if self.dziel_na_jednostki_i_wydzialy:
            lst += ("jednostka_id",)

        kombinacje = (
            Cache_Punktacja_Autora_Query.objects.filter(
                rekord__rok__gte=self.od_roku, rekord__rok__lte=self.do_roku
            )
            .values_list(*lst)
            .distinct()
        )

        total = kombinacje.count()

        for n, res in enumerate(kombinacje):
            if self.dziel_na_jednostki_i_wydzialy:
                autor_id, dyscyplina_id, jednostka_id = res
            else:
                autor_id, dyscyplina_id = res
                jednostka_id = None

            maks_punkty, lista, sloty_sum = zbieraj_sloty(
                autor_id,
                self.slot,
                self.od_roku,
                self.do_roku,
                self.minimalny_pk,
                dyscyplina_id=dyscyplina_id,
                jednostka_id=jednostka_id,
                akcja=self.akcja,
            )

            avg = None
            if sloty_sum != 0:
                avg = maks_punkty / sloty_sum

            self.raportslotowuczelniawiersz_set.create(
                autor_id=autor_id,
                jednostka_id=jednostka_id,
                dyscyplina_id=dyscyplina_id,
                slot=sloty_sum,
                pkd_aut_sum=maks_punkty,
                avg=avg,
            )

            if not n % 10:
                self.send_progress(n * 100.0 / total)

        if self.pokazuj_zerowych:
            zerowi = autorzy_zerowi(
                od_roku=self.od_roku, do_roku=self.do_roku, min_pk=self.minimalny_pk
            )

            # --- Początek --- komentarz dot. buga w Django
            # Z uwagi na bug w django (obecnie 3.0.11) nie mozemy zrobic tutaj
            # zerowi = zerowi.values_list("autor_id", "dyscyplina_naukowa_id").distinct()
            # a ja na ten (29. sty 2021) moment nie mam czasu poprawiać Django, zatem uzyjemy
            # set() aby lokalizować autorów już widzianych
            # --- Koniec --- komentarza dot. buga w Django

            # Jeżeli w raporcie jest włączony podział na jednostki i wydziały, to dla każdego autora zerowego
            # dorzuć rekordy jego jednostek; jeżeli nie - to wrzuć po prostu autorów.

            # Kolejny problem: jezeli autor już istnieje w raporcie jako autor który ma prace,
            # to nie powinien być wyświetlany jako zerowy (w kontekscie dyscypliny, w której
            # ma prace).

            seen = set()

            # Dodaj do listy widzianych autorów, którzy już zostali wyemitowani w raporcie dla danych
            # dyscyplin.

            seen = set(
                self.raportslotowuczelniawiersz_set.values_list(
                    "autor_id", "dyscyplina_id"
                ).distinct()
            )

            for autor_id, rok, dyscyplina_id in zerowi.values_list():
                if (autor_id, dyscyplina_id) in seen:
                    continue

                seen.add((autor_id, dyscyplina_id))

                kw = dict(
                    autor_id=autor_id,
                    jednostka_id=None,
                    dyscyplina_id=dyscyplina_id,
                    slot=0,
                    pkd_aut_sum=0,
                    avg=None,
                )

                if self.dziel_na_jednostki_i_wydzialy:
                    for (jednostka_id,) in (
                        Autor.objects.get(pk=autor_id)
                        .autor_jednostka_set.values_list("jednostka_id")
                        .distinct()
                    ):
                        kw["jednostka_id"] = jednostka_id
                        self.raportslotowuczelniawiersz_set.create(**kw)
                else:
                    self.raportslotowuczelniawiersz_set.create(**kw)

    def get_details_set(self):
        return self.raportslotowuczelniawiersz_set.all().select_related(
            "autor", "autor__tytul", "jednostka", "jednostka__wydzial", "dyscyplina"
        )


class RaportSlotowUczelniaWiersz(models.Model):
    parent = models.ForeignKey(RaportSlotowUczelnia, on_delete=models.CASCADE)
    autor = models.ForeignKey("bpp.Autor", on_delete=models.CASCADE)
    jednostka = models.ForeignKey(
        "bpp.Jednostka", on_delete=models.CASCADE, null=True, blank=True
    )
    dyscyplina = models.ForeignKey("bpp.Dyscyplina_Naukowa", on_delete=models.CASCADE)
    pkd_aut_sum = models.DecimalField(
        "Suma punktów dla autora", max_digits=16, decimal_places=4
    )
    slot = models.DecimalField(max_digits=16, decimal_places=4)
    avg = models.DecimalField(
        "Średnio punktów dla autora na slot",
        max_digits=16,
        decimal_places=4,
        null=True,
        blank=True,
    )
