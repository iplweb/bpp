"""Resources -- zasoby -- dla modułu django-import-export

Klasy określające w jaki sposób dane są eksportowane z systemu.
"""
from django.urls import reverse
from import_export import resources
from import_export.fields import Field

from django.contrib.sites.models import Site

from bpp.models import Autor, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

WYDAWNICTWO_TYPOWE_EXCLUDES = [
    "tekst_przed_pierwszym_autorem",
    "tekst_po_ostatnim_autorze",
    "search_index",
    "tytul_oryginalny_sort",
    "legacy_data",
    "cached_punkty_dyscyplin",
    "opis_bibliograficzny_autorzy_cache",
    "slug",
    "autorzy",
]

WYDAWNICTWO_TYPOWY_EXPORT_ORDER = [
    "id",
    "tytul_oryginalny",
    "pbn_url",
    "bpp_strona_url",
    "bpp_admin_url",
    "tytul",
    "rok",
    "ostatnio_zmieniony",
]


class Wydawnictwo_ResourceBase(resources.ModelResource):
    jezyk = Field(attribute="jezyk__skrot")
    jezyk_alt = Field(attribute="jezyk_alt__skrot")
    jezyk_orig = Field(attribute="jezyk_orig__skrot")
    charakter_formalny = Field(attribute="charakter_formalny__nazwa")
    status_korekty = Field(attribute="status_korekty__nazwa")
    typ_kbn = Field(attribute="typ_kbn__nazwa")
    openaccess_wersja_tekstu = Field(attribute="openaccess_wersja_tekstu__nazwa")
    openaccess_licencja = Field(attribute="openaccess_licencja__nazwa")
    openaccess_czas_publikacji = Field(attribute="openaccess_czas_publikacji__nazwa")
    openaccess_tryb_dostepu = Field(attribute="openaccess_tryb_dostepu__nazwa")
    informacja_z = Field(attribute="informacja_z__nazwa")

    pbn_url = Field(attribute="pbn_uid")
    bpp_strona_url = Field(attribute="pk")
    bpp_admin_url = Field(attribute="pk")

    def dehydrate_pbn_url(self, obj):
        pbn_uid_id = getattr(obj, "pbn_uid_id", None)
        if pbn_uid_id:
            return obj.pbn_uid.link_do_pbn()

    def get_site_url(self):
        return "https://" + Site.objects.all().first().domain

    def dehydrate_bpp_strona_url(self, obj):
        return self.get_site_url() + reverse(
            "bpp:browse_praca", args=(obj._meta.model_name, obj.pk)
        )

    def dehydrate_bpp_admin_url(self, obj):
        return self.get_site_url() + reverse(
            "admin:{m.app_label}_{m.model_name}_change".format(m=obj._meta),
            args=[obj.pk],
        )


class Wydawnictwo_ZwarteResource(Wydawnictwo_ResourceBase):
    class Meta:
        model = Wydawnictwo_Zwarte
        exclude = WYDAWNICTWO_TYPOWE_EXCLUDES
        export_order = WYDAWNICTWO_TYPOWY_EXPORT_ORDER


class Wydawnictwo_CiagleResource(Wydawnictwo_ResourceBase):
    zrodlo = Field(attribute="zrodlo__nazwa")

    class Meta:
        model = Wydawnictwo_Ciagle
        exclude = WYDAWNICTWO_TYPOWE_EXCLUDES
        export_order = WYDAWNICTWO_TYPOWY_EXPORT_ORDER


class AutorResource(resources.ModelResource):
    aktualna_jednostka = Field(attribute="aktualna_jednostka__nazwa")
    aktualna_funkcja = Field(attribute="aktualna_funkcja__nazwa")
    tytul = Field(attribute="tytul__skrot")

    def dehydrate_jednostki(self, obj):
        if obj.jednostki.exists():
            return ", ".join(obj.jednostki.values_list("nazwa", flat=True))

    class Meta:
        model = Autor
        export_order = ["nazwisko", "imiona", "poprzednie_nazwiska"]
        exclude = ["search", "slug", "sort", "expertus_id", "pbn_id"]
