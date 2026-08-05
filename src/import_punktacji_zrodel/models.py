from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from liveops.models import LiveOperation

from bpp.fields import YearField
from bpp.models import Zrodlo


class ImportPunktacjiZrodel(LiveOperation):
    rok = YearField(null=True, blank=True)
    plik = models.FileField(upload_to="protected/import_punktacji_zrodel/")
    zapisz_zmiany_do_bazy = models.BooleanField(
        default=False,
        help_text="Gdy odznaczone — tylko podgląd, bez zapisu do bazy.",
    )
    importuj_impact_factor = models.BooleanField(default=True)
    importuj_kwartyl_wos = models.BooleanField(default=True)
    ignoruj_zrodla_bez_odpowiednika = models.BooleanField(default=False)
    nie_porownuj_po_tytulach = models.BooleanField(
        default=False,
        help_text="Dopasowuj wyłącznie po ISSN/eISSN, pomijając tytuły.",
    )

    class Meta:
        verbose_name = "import punktacji źródeł"
        verbose_name_plural = "importy punktacji źródeł"
        ordering = ("-created_on",)

    def run(self, p):
        # Punkt wejścia liveops (dawniej Operation.perform()). `p` to obiekt
        # Progress — przekazujemy go do rdzenia, który raportuje postęp
        # (p.track) i loguje błędy (p.log). Na końcu finalizujemy operację
        # przez p.result(...) z podsumowaniem — trafia ono do result_context
        # i jest renderowane w szablonie wyniku (import_punktacji_zrodel_result).
        from import_punktacji_zrodel.core import analyze_jcr_file

        analyze_jcr_file(self.plik.path, self, p)

        wiersze = self.get_details_set()
        p.result(
            {
                "total": wiersze.count(),
                "do_aktualizacji": wiersze.filter(wymaga_zmian=True).count(),
                "niedopasowane": wiersze.filter(zrodlo__isnull=True).count(),
                "duplikaty": wiersze.filter(is_duplicate=True).count(),
                "byl_dry_run": not self.zapisz_zmiany_do_bazy,
                "rok": self.rok,
            }
        )

    def on_restart(self):
        # Hook liveops: wołany przez RestartView (oraz ZatwierdzImportView)
        # przed resetem stanu i ponownym zakolejkowaniem — odpowiednik dawnego
        # long_running on_reset(). Kasuje wiersze poprzedniego przebiegu.
        self.get_details_set().delete()

    def get_details_set(self):
        return self.wierszimportupunktacjizrodel_set.all().select_related("zrodlo")


class WierszImportuPunktacjiZrodel(models.Model):
    parent = models.ForeignKey(ImportPunktacjiZrodel, on_delete=models.CASCADE)
    dane_z_xls = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    nr_wiersza = models.PositiveIntegerField()
    zrodlo = models.ForeignKey(Zrodlo, on_delete=models.SET_NULL, null=True, blank=True)
    rezultat = models.TextField(blank=True, default="")
    wymaga_zmian = models.BooleanField(default=False)

    is_duplicate = models.BooleanField(default=False)
    duplicate_of_row = models.PositiveIntegerField(null=True, blank=True)
    duplicate_reason = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ("nr_wiersza",)
