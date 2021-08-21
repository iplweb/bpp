# -*- encoding: utf-8 -*-

from urllib.parse import parse_qs
from urllib.parse import quote as urlquote

from django import forms
from django.db import models
from django.forms import BaseInlineFormSet
from django.forms.widgets import Textarea
from django.urls import reverse

from pbn_api.exceptions import AccessDeniedException, SameDataUploadedRecently
from pbn_api.models import SentData

from django.contrib import messages
from django.contrib.admin.utils import quote
from django.contrib.contenttypes.models import ContentType

from django.utils.html import format_html
from django.utils.safestring import mark_safe

from bpp.models import Status_Korekty
from bpp.models.sloty.core import ISlot
from bpp.models.sloty.exceptions import CannotAdapt

CHARMAP_SINGLE_LINE = forms.TextInput(
    attrs={"class": "charmap", "style": "width: 500px"}
)


# Pomocnik dla klasy ModelZMetryczka


class ZapiszZAdnotacjaMixin:
    readonly_fields = ("ostatnio_zmieniony",)


class AdnotacjeZDatamiMixin:
    readonly_fields = ("utworzono", "ostatnio_zmieniony", "id")


class AdnotacjeZDatamiOrazPBNMixin:
    readonly_fields = (
        "utworzono",
        "ostatnio_zmieniony",
        "id",
        "pbn_id",
    )


ADNOTACJE_FIELDSET = (
    "Adnotacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": (ZapiszZAdnotacjaMixin.readonly_fields + ("adnotacje",)),
    },
)

ADNOTACJE_Z_DATAMI_FIELDSET = (
    "Adnotacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": AdnotacjeZDatamiMixin.readonly_fields + ("adnotacje",),
    },
)

ADNOTACJE_Z_DATAMI_ORAZ_PBN_FIELDSET = (
    "Adnotacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": AdnotacjeZDatamiOrazPBNMixin.readonly_fields + ("adnotacje",),
    },
)

OPENACCESS_FIELDSET = (
    "OpenAccess",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": (
            "openaccess_tryb_dostepu",
            "openaccess_licencja",
            "openaccess_wersja_tekstu",
            "openaccess_czas_publikacji",
            "openaccess_ilosc_miesiecy",
        ),
    },
)

DWA_TYTULY = (
    "tytul_oryginalny",
    "tytul",
)

MODEL_ZE_SZCZEGOLAMI = (
    "informacje",
    "szczegoly",
    "uwagi",
    "slowa_kluczowe",
    "strony",
    "tom",
)

MODEL_Z_ISSN = (
    "issn",
    "e_issn",
)

MODEL_Z_PBN_UID = ("pbn_uid",)

MODEL_Z_ISBN = (
    "isbn",
    "e_isbn",
)

MODEL_Z_WWW = (
    "www",
    "dostep_dnia",
    "public_www",
    "public_dostep_dnia",
)

MODEL_Z_PUBMEDID = ("pubmed_id", "pmc_id")

MODEL_Z_DOI = ("doi",)

MODEL_Z_LICZBA_CYTOWAN = ("liczba_cytowan",)

MODEL_Z_MIEJSCEM_PRZECHOWYWANIA = ("numer_odbitki",)

MODEL_Z_ROKIEM = ("rok",)

MODEL_TYPOWANY = (
    "jezyk",
    "jezyk_alt",
    "jezyk_orig",
    "typ_kbn",
)

MODEL_PUNKTOWANY_BAZA = (
    "punkty_kbn",
    "impact_factor",
    "index_copernicus",
    "punktacja_snip",
    "punktacja_wewnetrzna",
)

MODEL_PUNKTOWANY = MODEL_PUNKTOWANY_BAZA + ("weryfikacja_punktacji",)

MODEL_PUNKTOWANY_KOMISJA_CENTRALNA = (
    "kc_impact_factor",
    "kc_punkty_kbn",
    "kc_index_copernicus",
)

MODEL_Z_INFORMACJA_Z = ("informacja_z",)

MODEL_Z_LICZBA_ZNAKOW_WYDAWNICZYCH = ("liczba_znakow_wydawniczych",)

MODEL_ZE_STATUSEM = ("status_korekty",)

MODEL_RECENZOWANY = ("recenzowana",)

MODEL_TYPOWANY_BEZ_CHARAKTERU_FIELDSET = (
    "Typ",
    {"classes": ("",), "fields": MODEL_TYPOWANY},
)

MODEL_TYPOWANY_FIELDSET = (
    "Typ",
    {"classes": ("",), "fields": ("charakter_formalny",) + MODEL_TYPOWANY},
)

MODEL_PUNKTOWANY_FIELDSET = (
    "Punktacja",
    {"classes": ("",), "fields": MODEL_PUNKTOWANY},
)

MODEL_PUNKTOWANY_WYDAWNICTWO_CIAGLE_FIELDSET = (
    "Punktacja",
    {"classes": ("",), "fields": MODEL_PUNKTOWANY + ("uzupelnij_punktacje",)},
)

MODEL_PUNKTOWANY_KOMISJA_CENTRALNA_FIELDSET = (
    "Punktacja Komisji Centralnej",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": MODEL_PUNKTOWANY_KOMISJA_CENTRALNA,
    },
)

MODEL_OPCJONALNIE_NIE_EKSPORTOWANY_DO_API_FIELDSET = (
    "Eksport do API",
    {"classes": ("grp-collapse grp-closed",), "fields": ("nie_eksportuj_przez_api",)},
)

POZOSTALE_MODELE_FIELDSET = (
    "Pozostałe informacje",
    {
        "classes": ("",),
        "fields": MODEL_Z_INFORMACJA_Z + MODEL_ZE_STATUSEM + MODEL_RECENZOWANY,
    },
)

POZOSTALE_MODELE_WYDAWNICTWO_CIAGLE_FIELDSET = (
    "Pozostałe informacje",
    {
        "classes": ("",),
        "fields": MODEL_Z_LICZBA_ZNAKOW_WYDAWNICZYCH
        + MODEL_Z_INFORMACJA_Z
        + MODEL_ZE_STATUSEM
        + MODEL_RECENZOWANY,
    },
)

POZOSTALE_MODELE_WYDAWNICTWO_ZWARTE_FIELDSET = (
    "Pozostałe informacje",
    {
        "classes": ("",),
        "fields": MODEL_Z_LICZBA_ZNAKOW_WYDAWNICZYCH
        + MODEL_Z_INFORMACJA_Z
        + MODEL_ZE_STATUSEM
        + MODEL_RECENZOWANY,
    },
)

SERIA_WYDAWNICZA_FIELDSET = (
    "Seria wydawnicza",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": ("seria_wydawnicza", "numer_w_serii"),
    },
)

PRACA_WYBITNA_FIELDSET = (
    "Praca wybitna",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": ("praca_wybitna", "uzasadnienie_wybitnosci"),
    },
)

PRZED_PO_LISCIE_AUTOROW_FIELDSET = (
    "Dowolny tekst przed lub po liście autorów",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": ("tekst_przed_pierwszym_autorem", "tekst_po_ostatnim_autorze"),
    },
)

EKSTRA_INFORMACJE_WYDAWNICTWO_CIAGLE_FIELDSET = (
    "Ekstra informacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": MODEL_Z_PBN_UID
        + MODEL_Z_ISSN
        + MODEL_Z_WWW
        + MODEL_Z_PUBMEDID
        + MODEL_Z_DOI
        + MODEL_Z_LICZBA_CYTOWAN
        + MODEL_Z_MIEJSCEM_PRZECHOWYWANIA,
    },
)

EKSTRA_INFORMACJE_WYDAWNICTWO_ZWARTE_FIELDSET = (
    "Ekstra informacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": MODEL_Z_PBN_UID
        + MODEL_Z_ISSN
        + MODEL_Z_WWW
        + MODEL_Z_PUBMEDID
        + MODEL_Z_DOI
        + MODEL_Z_LICZBA_CYTOWAN
        + MODEL_Z_MIEJSCEM_PRZECHOWYWANIA,
    },
)

EKSTRA_INFORMACJE_DOKTORSKA_HABILITACYJNA_FIELDSET = (
    "Ekstra informacje",
    {
        "classes": ("grp-collapse grp-closed",),
        "fields": MODEL_Z_WWW
        + MODEL_Z_PUBMEDID
        + MODEL_Z_DOI
        + MODEL_Z_LICZBA_CYTOWAN
        + MODEL_Z_MIEJSCEM_PRZECHOWYWANIA,
    },
)


def js_openwin(url, handle, options):
    options = ",".join(["%s=%s" % (a, b) for a, b in list(options.items())])
    d = dict(url=url, handle=handle, options=options)
    return "window.open('%(url)s','\\%(handle)s','%(options)s')" % d


NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW = {
    models.TextField: {
        "widget": Textarea(attrs={"rows": 2, "cols": 90, "class": "charmap"})
    },
}


class DomyslnyStatusKorektyMixin:
    status_korekty = forms.ModelChoiceField(
        required=True,
        queryset=Status_Korekty.objects.all(),
        initial=lambda: Status_Korekty.objects.first(),
    )


class Wycinaj_W_z_InformacjiMixin:
    def clean_informacje(self):
        i = self.cleaned_data.get("informacje")
        if i:
            x = i.lower()
            n = 0
            if x.startswith("w:"):
                n = 2
            if x.startswith("w :"):
                n = 3
            if n:
                return i[n:].strip()
        return i


class LimitingFormset(BaseInlineFormSet):
    def get_queryset(self):
        if not hasattr(self, "_queryset_limited"):
            qs = super(LimitingFormset, self).get_queryset()
            self._queryset_limited = qs[:100]
        return self._queryset_limited


def link_do_obiektu(obj, friendly_name=None):
    opts = obj._meta
    obj_url = reverse(
        "admin:%s_%s_change" % (opts.app_label, opts.model_name),
        args=(quote(obj.pk),),
        # current_app=self.admin_site.name,
    )
    # Add a link to the object's change form if the user can edit the obj.
    if friendly_name is None:
        friendly_name = mark_safe(obj)
    return format_html('<a href="{}">{}</a>', urlquote(obj_url), friendly_name)


def sprobuj_policzyc_sloty(request, obj):
    if obj.rok >= 2017 and obj.rok <= 2021:
        try:
            ISlot(obj)
            messages.success(
                request,
                'Punkty dla dyscyplin dla "%s" będą mogły być obliczone.'
                % link_do_obiektu(obj),
            )
        except CannotAdapt as e:
            messages.error(
                request,
                'Nie można obliczyć punktów dla dyscyplin dla "%s": %s'
                % (link_do_obiektu(obj), e),
            )
    else:
        messages.warning(
            request,
            'Punkty dla dyscyplin dla "%s" nie będą liczone - rok poza zakresem (%i)'
            % (link_do_obiektu(obj), obj.rok),
        )


def sprobuj_wgrac_do_pbn(request, obj, force_upload=False, pbn_client=None):
    from bpp.models.uczelnia import Uczelnia

    if obj.charakter_formalny.rodzaj_pbn is None:
        messages.info(
            request,
            'Rekord "%s" nie będzie eksportowany do PBN zgodnie z ustawieniem dla charakteru formalnego.'
            % link_do_obiektu(obj),
        )
        return

    uczelnia = Uczelnia.objects.get_default()
    if uczelnia is None:
        messages.info(
            request,
            'Rekord "%s" nie zostanie wyeksportowany do PBN, ponieważ w systemie brakuje obiektu "Uczelnia", a'
            " co za tym idzie, jakchkolwiek ustawień" % link_do_obiektu(obj),
        )
        return

    if not uczelnia.pbn_integracja or not uczelnia.pbn_aktualizuj_na_biezaco:
        return

    if pbn_client is None:
        pbn_client = uczelnia.pbn_client(request.user.pbn_token)

    try:
        pbn_client.sync_publication(obj, force_upload=force_upload)

    except SameDataUploadedRecently as e:
        link_do_wyslanych = reverse(
            "admin:pbn_api_sentdata_change",
            args=(SentData.objects.get_for_rec(obj).pk,),
        )

        messages.info(
            request,
            f'Identyczne dane rekordu "{link_do_obiektu(obj)}" zostały wgrane do PBN w dniu {e}. '
            f"Nie aktualizuję w PBN API. Jeżeli chcesz wysłać ten rekord do PBN, musisz dokonać jakiejś zmiany "
            f"danych rekodu lub "
            f'usunąć informacje o <a target=_blank href="{link_do_wyslanych}">wcześniej wysłanych danych do PBN</a> '
            f"(Redagowanie -> PBN API -> Wysłane informacje). "
            f'<a target=_blank href="{obj.link_do_pbn()}">Kliknij tutaj, aby otworzyć w PBN</a>. ',
        )
        return

    except AccessDeniedException as e:
        messages.warning(
            request,
            f'Nie można zsynchronizować obiektu "{link_do_obiektu(obj)}" z PBN pod adresem '
            f"API {e}. Brak dostępu -- "
            f'<a target=_blank href="{reverse("pbn_api:authorize")}">kliknij tutaj, aby autoryzować sesję w PBN</a>.',
        )
        return

    except Exception as e:
        messages.warning(
            request,
            'Nie można zsynchronizować obiektu "%s" z PBN. Kod błędu: %r.'
            % (link_do_obiektu(obj), e),
        )
        return

    sent_data = SentData.objects.get(
        content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk
    )

    sent_data_link = link_do_obiektu(
        sent_data, "Kliknij tutaj, aby otworzyć widok wysłanych danych. "
    )
    publication_link = link_do_obiektu(
        sent_data.pbn_uid,
        "Kliknij tutaj, aby otworzyć zwrotnie otrzymane z PBN dane o rekordzie. ",
    )
    messages.success(
        request,
        f"Dane w PBN dla rekordu {link_do_obiektu(obj)} zostały zaktualizowane. "
        f'<a target=_blank href="{obj.link_do_pbn()}">Kliknij tutaj, aby otworzyć w PBN</a>. '
        f"{sent_data_link}{publication_link}",
    )


def get_rekord_id_from_GET_qs(request):
    flt = request.GET.get("_changelist_filters", "?")
    data = parse_qs(flt)  # noqa
    if "rekord__id__exact" in data:
        try:
            return int(data.get("rekord__id__exact")[0])
        except (ValueError, TypeError):
            pass


class OptionalPBNSaveMixin:
    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        from bpp.models import Uczelnia

        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            if uczelnia.pbn_integracja and uczelnia.pbn_aktualizuj_na_biezaco:
                context.update({"show_save_and_pbn": True})

        return super(OptionalPBNSaveMixin, self).render_change_form(
            request, context, add, change, form_url, obj
        )

    def response_post_save_change(self, request, obj):
        if "_continue_and_pbn" in request.POST:
            sprobuj_wgrac_do_pbn(request, obj)

            opts = self.model._meta
            route = f"admin:{opts.app_label}_{opts.model_name}_change"

            post_url = reverse(route, args=(obj.pk,))

            from django.http import HttpResponseRedirect

            return HttpResponseRedirect(post_url)
        else:
            # Otherwise, use default behavior
            return super().response_post_save_change(request, obj)
