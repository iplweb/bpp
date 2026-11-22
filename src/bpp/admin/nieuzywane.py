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
rekord (przy ``limit_choices_to`` takiego rekordu nie dałoby się potem
zapisać w adminie).
"""

import operator
from functools import reduce

from django.contrib import admin, messages
from django.contrib.admin.filters import SimpleListFilter
from django.db.models import BLANK_CHOICE_DASH, Exists, ManyToManyRel, OuterRef, Q
from django.utils.translation import ngettext

from bpp.admin.actions import (
    komunikat_limitu,
    zapisuje_historie,
    zmien_hurtowo_z_historia,
)

KOMUNIKAT_UKRYTO_NIEUZYWANE = "Ukryto nieużywaną pozycję słownika (akcja masowa)"


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


@zapisuje_historie
def ukryj_nieuzywane(modeladmin, request, queryset):
    model = queryset.model
    pole, wartosc = pole_ukrycia(model)
    zaznaczone = queryset.count()
    do_ukrycia = nieuzywane(queryset)
    pominiete_uzywane = zaznaczone - do_ukrycia.count()

    updated = zmien_hurtowo_z_historia(
        request, do_ukrycia, {pole: wartosc}, KOMUNIKAT_UKRYTO_NIEUZYWANE
    )
    if updated is None:
        return komunikat_limitu(modeladmin, request, model)

    komunikat = (
        f"Ukryto {updated} "
        f"{ngettext('nieużywaną pozycję', 'nieużywanych pozycji', updated)}."
    )
    if pominiete_uzywane:
        komunikat += (
            f" Pominięto {pominiete_uzywane} "
            f"{ngettext('używaną', 'używanych', pominiete_uzywane)} — "
            f"wskazują na nie istniejące rekordy."
        )
    modeladmin.message_user(request, komunikat, messages.SUCCESS)


ukryj_nieuzywane.short_description = (
    "Ukryj na listach wyboru zaznaczone pozycje, których nie używa żaden rekord"
)
ukryj_nieuzywane.allowed_permissions = ("change",)


class UkryjNieuzywaneMixin:
    """Dokłada do admina słownika filtr „używane” i akcję „Ukryj nieużywane”.

    Model musi mieć pole ``widoczny`` albo ``ukryty``.
    """

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

    def get_actions(self, request):
        actions = super().get_actions(request)
        if self.has_change_permission(request):
            actions["ukryj_nieuzywane"] = self.get_action(ukryj_nieuzywane)
        return actions
