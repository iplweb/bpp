from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from liveops.models import LiveOperation

from bpp.fields import YearField
from bpp.models import Zrodlo

RODZAJ_JCR = "jcr"
RODZAJ_SCOPUS = "scopus"

#: Wartość w ``ImportPunktacjiZrodel.wybory`` oznaczająca „pomiń ten wiersz”.
WYBOR_POMIN = 0


class ImportPunktacjiZrodel(LiveOperation):
    rodzaj_pliku = models.CharField(
        "rodzaj pliku",
        max_length=10,
        choices=[
            (RODZAJ_JCR, "JCR (Impact Factor, kwartyl WoS)"),
            (RODZAJ_SCOPUS, "Scopus (CiteScore)"),
        ],
        default=RODZAJ_JCR,
    )
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

    # Pola importu CiteScore z pliku Scopus (FD#370); dla JCR bez znaczenia.
    importuj_citescore = models.BooleanField(
        "Importuj CiteScore i najwyższy percentyl", default=True
    )
    importuj_snip = models.BooleanField(
        "Importuj SNIP",
        default=False,
        help_text="Zapisuje kolumnę SNIP pliku do pola „Punktacja SNIP”.",
    )
    nadpisz_istniejace = models.BooleanField(
        "Nadpisz istniejące",
        default=False,
        help_text="Gdy odznaczone — wartość już wpisana przy źródle za dany "
        "rok zostaje, nawet jeśli w pliku jest inna.",
    )
    # {"<nr_wiersza>": <pk źródła> | WYBOR_POMIN} — decyzje użytkownika dla
    # wierszy niejednoznacznych. Trzymane przy imporcie (nie przy wierszach),
    # bo zatwierdzenie kasuje wiersze podglądu i przelicza plik od nowa.
    wybory = models.JSONField(default=dict, blank=True)

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
        if self.rodzaj_pliku == RODZAJ_SCOPUS:
            from import_punktacji_zrodel.core_scopus import analyze_scopus_file

            analyze_scopus_file(self.plik.path, self, p)
        else:
            from import_punktacji_zrodel.core import analyze_jcr_file

            analyze_jcr_file(self.plik.path, self, p)

        wiersze = self.get_details_set()
        p.result(
            {
                "total": wiersze.count(),
                "do_aktualizacji": wiersze.filter(wymaga_zmian=True).count(),
                "niedopasowane": self.niedopasowane().count(),
                "do_rozstrzygniecia": wiersze.filter(do_rozstrzygniecia=True).count(),
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

    def niedopasowane(self):
        """Wiersze, dla których w BPP nie ma żadnego pasującego źródła.

        Warunek na ``kandydaci`` odróżnia je od wierszy importu Scopus
        czekających na wybór albo pominiętych decyzją użytkownika (te też
        nie mają ``zrodlo``, ale kandydatów mają)."""
        return self.get_details_set().filter(zrodlo__isnull=True, kandydaci=[])

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

    # Import Scopus (FD#370): pk źródeł pasujących do wiersza oraz znacznik
    # „użytkownik musi wybrać” (kilka źródeł albo kilka wierszy na źródło).
    kandydaci = models.JSONField(default=list, blank=True)
    do_rozstrzygniecia = models.BooleanField(default=False)

    class Meta:
        ordering = ("nr_wiersza",)
