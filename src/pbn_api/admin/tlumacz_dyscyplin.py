from pbn_api.models import TlumaczDyscyplin

from django.contrib import admin


@admin.register(TlumaczDyscyplin)
class TlumaczDyscyplinAdmin(admin.ModelAdmin):
    list_display = [
        "dyscyplina_w_bpp",
        "pbn_2017_2021",
        "pbn_2022_2023",
        "pbn_2024_now",
    ]
    list_filter = ["dyscyplina_w_bpp__kod", "dyscyplina_w_bpp__nazwa"]
    search_fields = [
        "dyscyplina_w_bpp__nazwa",
        "dyscyplina_w_bpp__kod",
        "pbn_2017_2021__uuid",
        "pbn_2017_2021__code",
        "pbn_2017_2021__name",
        "pbn_2022_2023__uuid",
        "pbn_2022_2023__code",
        "pbn_2022_2023__name",
        "pbn_2024_now__uuid",
        "pbn_2024_now__code",
        "pbn_2024_now__name",
    ]
