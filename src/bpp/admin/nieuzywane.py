"""Słowniki: filtr „używane / nieużywane” i akcja „Ukryj nieużywane”.

Słowniki (języki, charaktery formalne, typy MNiSW, charaktery PBN) potrafią
mieć setki pozycji, z których uczelnia używa kilkunastu. Filtr pozwala
zobaczyć, które pozycje nie są wskazywane przez żaden rekord, a akcja
chowa je z list wyboru (``widoczny = False`` albo ``ukryty = True``).

„Używana” znaczy: wskazuje na nią **dowolna** relacja w bazie (FK, M2M,
OneToOne) — publikacje, patenty, prace dyplomowe, konfiguracja uczelni,
tabele importów itd. Lista relacji jest liczona z ``_meta``, więc nowy
model wskazujący na słownik jest uwzględniany automatycznie. Pomijamy
tylko relacje modelu do samego siebie (np. ``parent`` w drzewie MPTT
charakterów formalnych) — to, że pozycja ma podrzędne, nie znaczy, że
jakikolwiek rekord jej używa.

Akcja zawsze chowa **wyłącznie** nieużywane spośród zaznaczonych — nawet
przy „zaznacz wszystkie” nie ukryje pozycji, której używa istniejący
rekord.

Obie akcje chowające nieużywane („Ukryj nieużywane” dla zaznaczonych
i „Ukryj wszystkie nieużywane” bez zaznaczania) najpierw pokazują stronę
z podglądem: co zostanie ukryte, a co pominięte jako używane (FD#513).
Zmiana następuje dopiero po potwierdzeniu.
"""

import operator
from functools import reduce

from django.contrib import admin, messages
from django.contrib.admin import helpers as admin_helpers
from django.contrib.admin.filters import SimpleListFilter
from django.db.models import (
    BLANK_CHOICE_DASH,
    BooleanField,
    Exists,
    ExpressionWrapper,
    ManyToManyRel,
    OuterRef,
    Q,
    Value,
)
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils.translation import ngettext

from bpp.admin.actions import (
    komunikat_limitu,
    zapisuje_historie,
    zmien_hurtowo_z_historia,
)

KOMUNIKAT_UKRYTO_NIEUZYWANE = "Ukryto nieużywaną pozycję słownika (akcja masowa)"
KOMUNIKAT_UKRYTO = "Ukryto pozycję słownika (akcja masowa)"
KOMUNIKAT_POKAZANO = "Pokazano pozycję słownika (akcja masowa)"

AKCJA_WSZYSTKIE = "ukryj_wszystkie_nieuzywane"
POLE_POTWIERDZENIA = "potwierdzam"
#: Lista PK pokazana w podglądzie — po zatwierdzeniu zmieniamy NAJWYŻEJ je.
POLE_PK_Z_PODGLADU = "pk_z_podgladu"
SZABLON_PODGLADU = "admin/bpp/ukryj_nieuzywane_podglad.html"


def relacje_wskazujace(model):
    """Relacje odwrotne (FK/M2M/OneToOne) wskazujące na ``model``, łącznie
    z ukrytymi (``related_name="+"``, np. ``jezyk_alt``), bez relacji
    modelu do samego siebie."""
    return [
        pole
        for pole in model._meta.get_fields(include_hidden=True)
        if pole.auto_created
        and not pole.concrete
        and pole.is_relation
        and pole.related_model is not model
    ]


def _exists_dla_relacji(rel):
    zrodlo = rel.related_model._base_manager.order_by()
    if isinstance(rel, ManyToManyRel):
        return Exists(zrodlo.filter(**{rel.field.name: OuterRef("pk")}))
    cel = rel.field.target_field.name
    return Exists(zrodlo.filter(**{f"{rel.field.name}__{cel}": OuterRef(cel)}))


def warunek_uzywane(model):
    """``Q`` prawdziwe dla pozycji, na które wskazuje cokolwiek w bazie,
    albo ``None``, gdy na model nie wskazuje żadna relacja.

    ``_base_manager`` celowo — rekord w koszu (soft-delete) też trzyma
    wartość słownika i po przywróceniu musi dać się zapisać.
    """
    warunki = [Q(_exists_dla_relacji(rel)) for rel in relacje_wskazujace(model)]
    if not warunki:
        return None
    return reduce(operator.or_, warunki)


def nieuzywane(queryset):
    warunek = warunek_uzywane(queryset.model)
    return queryset if warunek is None else queryset.exclude(warunek)


def uzywane(queryset):
    warunek = warunek_uzywane(queryset.model)
    return queryset.none() if warunek is None else queryset.filter(warunek)


class UzywaneFilter(SimpleListFilter):
    title = "używane w rekordach"
    parameter_name = "uzywane"

    def lookups(self, request, model_admin):
        return [("tak", "używane"), ("nie", "nieużywane")]

    def queryset(self, request, queryset):
        if self.value() == "tak":
            return uzywane(queryset)
        if self.value() == "nie":
            return nieuzywane(queryset)
        return queryset


def pole_ukrycia(model):
    """(nazwa pola, wartość oznaczająca „ukryty”) dla modelu słownika."""
    nazwy = {f.name for f in model._meta.concrete_fields}
    if "widoczny" in nazwy:
        return "widoczny", False
    if "ukryty" in nazwy:
        return "ukryty", True
    raise ValueError(f"{model._meta.label} nie ma pola widoczny ani ukryty")


def _widoczne(queryset):
    """Pozycje, które dziś SĄ na listach wyboru (jeszcze nieukryte)."""
    pole, wartosc_ukryty = pole_ukrycia(queryset.model)
    return queryset.exclude(**{pole: wartosc_ukryty})


def _podglad_ukrywania(modeladmin, request, queryset, akcja, tytul):
    """Strona pośrednia: co zostanie ukryte, co pominięte. Nic nie zmienia."""
    do_ukrycia = _widoczne(nieuzywane(queryset))
    pominiete = _widoczne(uzywane(queryset))
    context = {
        **modeladmin.admin_site.each_context(request),
        "title": tytul,
        "opts": queryset.model._meta,
        "do_ukrycia": list(do_ukrycia),
        "pominiete": list(pominiete),
        "akcja": akcja,
        "pole_potwierdzenia": POLE_POTWIERDZENIA,
        "pole_pk_z_podgladu": POLE_PK_Z_PODGLADU,
        "wybrane_pk": request.POST.getlist(admin_helpers.ACTION_CHECKBOX_NAME),
        "action_checkbox_name": admin_helpers.ACTION_CHECKBOX_NAME,
        "select_across": request.POST.get("select_across", "0"),
    }
    return TemplateResponse(request, SZABLON_PODGLADU, context)


def _ukryj_nieuzywane_po_potwierdzeniu(modeladmin, request, queryset):
    model = queryset.model
    pole, wartosc = pole_ukrycia(model)
    # Zatwierdzenie dotyczy dokładnie tej listy, którą pokazał podgląd —
    # pozycja dodana do słownika w międzyczasie nie zostanie ukryta „na
    # ślepo”.
    z_podgladu = [
        pk for pk in request.POST.getlist(POLE_PK_Z_PODGLADU) if str(pk).isdigit()
    ]
    kandydaci = queryset.filter(pk__in=z_podgladu)

    # „Nieużywana” sprawdzamy ponownie w chwili zmiany, pod blokadą wierszy
    # — pozycja, która po podglądzie trafiła do jakiegoś rekordu, zostaje.
    updated = zmien_hurtowo_z_historia(
        request,
        kandydaci,
        {pole: wartosc},
        KOMUNIKAT_UKRYTO_NIEUZYWANE,
        warunek_pod_blokada=nieuzywane,
    )
    if updated is None:
        return komunikat_limitu(modeladmin, request, model)
    pominiete_uzywane = _widoczne(uzywane(kandydaci)).count()

    komunikat = (
        f"Ukryto {updated} "
        f"{ngettext('nieużywaną pozycję', 'nieużywanych pozycji', updated)}."
    )
    if pominiete_uzywane:
        komunikat += (
            f" Pominięto {pominiete_uzywane} "
            f"{ngettext('pozycję, która', 'pozycji, które', pominiete_uzywane)} "
            f"po wyświetleniu podglądu "
            f"{ngettext('zaczęła', 'zaczęły', pominiete_uzywane)} być "
            f"{ngettext('używana', 'używane', pominiete_uzywane)}."
        )
    if updated:
        komunikat += (
            " Aby to cofnąć, wybierz filtr pokazujący ukryte pozycje, zaznacz "
            "je i użyj akcji „Pokaż zaznaczone”."
        )
    modeladmin.message_user(request, komunikat, messages.SUCCESS)


@zapisuje_historie
def ukryj_nieuzywane(modeladmin, request, queryset):
    if request.POST.get(POLE_POTWIERDZENIA) != "1":
        return _podglad_ukrywania(
            modeladmin,
            request,
            queryset,
            "ukryj_nieuzywane",
            "Ukryj nieużywane spośród zaznaczonych",
        )
    return _ukryj_nieuzywane_po_potwierdzeniu(modeladmin, request, queryset)


ukryj_nieuzywane.short_description = "Ukryj nieużywane spośród zaznaczonych…"
ukryj_nieuzywane.allowed_permissions = ("change",)


@zapisuje_historie
def ukryj_wszystkie_nieuzywane(modeladmin, request, queryset):
    """Jak ``ukryj_nieuzywane``, ale dla CAŁEGO słownika — zaznaczenie na
    liście jest ignorowane (akcję można uruchomić bez zaznaczania, patrz
    ``UkryjNieuzywaneMixin.changelist_view``)."""
    queryset = modeladmin.model._default_manager.all()
    if request.POST.get(POLE_POTWIERDZENIA) != "1":
        return _podglad_ukrywania(
            modeladmin, request, queryset, AKCJA_WSZYSTKIE, "Ukryj wszystkie nieużywane"
        )
    return _ukryj_nieuzywane_po_potwierdzeniu(modeladmin, request, queryset)


ukryj_wszystkie_nieuzywane.short_description = (
    "Ukryj wszystkie nieużywane (bez zaznaczania)…"
)
ukryj_wszystkie_nieuzywane.allowed_permissions = ("change",)


def _ustaw_ukrycie(modeladmin, request, queryset, ukryj, komentarz):
    model = queryset.model
    pole, wartosc_ukryty = pole_ukrycia(model)
    wartosc = wartosc_ukryty if ukryj else not wartosc_ukryty
    updated = zmien_hurtowo_z_historia(request, queryset, {pole: wartosc}, komentarz)
    if updated is None:
        komunikat_limitu(modeladmin, request, model)
    return updated


@zapisuje_historie
def ukryj_zaznaczone(modeladmin, request, queryset):
    updated = _ustaw_ukrycie(modeladmin, request, queryset, True, KOMUNIKAT_UKRYTO)
    if updated is None:
        return
    komunikat = f"Ukryto {updated} {ngettext('pozycję', 'pozycji', updated)}."
    uzywanych = uzywane(queryset).count()
    if uzywanych:
        # Rekord z ukrytą wartością słownika może nie dać się zapisać
        # w formularzu (``limit_choices_to``) — warto o tym wiedzieć.
        komunikat += (
            f" Uwaga: {uzywanych} z zaznaczonych "
            f"{ngettext('jest używana', 'jest używanych', uzywanych)} "
            f"w istniejących rekordach."
        )
        poziom = messages.WARNING
    else:
        poziom = messages.SUCCESS
    modeladmin.message_user(request, komunikat, poziom)


ukryj_zaznaczone.short_description = "Ukryj zaznaczone"
ukryj_zaznaczone.allowed_permissions = ("change",)


@zapisuje_historie
def pokaz_zaznaczone(modeladmin, request, queryset):
    updated = _ustaw_ukrycie(modeladmin, request, queryset, False, KOMUNIKAT_POKAZANO)
    if updated is None:
        return
    modeladmin.message_user(
        request,
        f"Pokazano {updated} {ngettext('pozycję', 'pozycji', updated)}.",
        messages.SUCCESS,
    )


pokaz_zaznaczone.short_description = "Pokaż zaznaczone"
pokaz_zaznaczone.allowed_permissions = ("change",)


class UkryjNieuzywaneMixin:
    """Dokłada do admina słownika filtr „używane”, kolumnę „Używane”
    i akcje „Ukryj nieużywane”, „Ukryj wszystkie nieużywane”, „Ukryj
    zaznaczone”, „Pokaż zaznaczone”.

    Model musi mieć pole ``widoczny`` albo ``ukryty``.
    """

    def get_queryset(self, request):
        warunek = warunek_uzywane(self.model)
        wyrazenie = (
            Value(False)
            if warunek is None
            else ExpressionWrapper(warunek, output_field=BooleanField())
        )
        return super().get_queryset(request).annotate(_uzywane=wyrazenie)

    @admin.display(description="Używane", boolean=True, ordering="_uzywane")
    def uzywane_w_rekordach(self, obj):
        return obj._uzywane

    def get_list_display(self, request):
        kolumny = list(super().get_list_display(request))
        if "uzywane_w_rekordach" not in kolumny:
            kolumny.append("uzywane_w_rekordach")
        return kolumny

    def get_list_filter(self, request):
        return (*super().get_list_filter(request), UzywaneFilter)

    def get_action_choices(self, request, default_choices=BLANK_CHOICE_DASH):
        # ``RestrictDeletionToAdministracjaGroupMixin`` / ``PreventDeletionMixin``
        # zwracają tu ``[]`` osobom spoza grupy „administracja”, żeby schować
        # usuwanie — a to chowa też każdą inną akcję (i Django odrzuca ją przy
        # POST). Usuwanie i tak odcina ``has_delete_permission`` (akcja
        # ``delete_selected`` wymaga uprawnienia „delete”), więc bierzemy
        # standardową listę.
        return admin.ModelAdmin.get_action_choices(self, request, default_choices)

    #: Akcje działające na całym słowniku, bez zaznaczania wierszy.
    akcje_bez_zaznaczania = (ukryj_wszystkie_nieuzywane,)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if self.has_change_permission(request):
            for akcja in (
                *self.akcje_bez_zaznaczania,
                ukryj_nieuzywane,
                ukryj_zaznaczone,
                pokaz_zaznaczone,
            ):
                actions[akcja.__name__] = self.get_action(akcja)
        return actions

    def _akcja_bez_zaznaczania(self, request):
        if request.method != "POST":
            return None
        akcje = request.POST.getlist("action")
        try:
            wybrana = akcje[int(request.POST.get("index", 0))]
        except (ValueError, IndexError):
            # Niepoprawny formularz akcji — niech obsłuży go Django.
            return None
        for akcja in self.akcje_bez_zaznaczania:
            if akcja.__name__ == wybrana:
                return akcja
        return None

    def changelist_view(self, request, extra_context=None):
        # Akcje „bez zaznaczania” nie wymagają zaznaczenia czegokolwiek,
        # a Django odrzuca akcję bez zaznaczonych wierszy („Items must be
        # selected”) — dlatego obsługujemy je, zanim trafią do Django.
        akcja = self._akcja_bez_zaznaczania(request)
        if akcja is not None and self.has_change_permission(request):
            odpowiedz = akcja(self, request, self.get_queryset(request))
            return odpowiedz or HttpResponseRedirect(request.get_full_path())
        return super().changelist_view(request, extra_context)
