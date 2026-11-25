"""Akcja „Uzupełnij kody CrossRef z PBN” w słowniku języków (FD#513).

Języki dociągane z PBN mają kod trzyliterowy (ISO 639-2), a CrossRef opisuje
język publikacji kodem dwuliterowym (ISO 639-1). Akcja wylicza kody
(``bpp.kody_jezykow.zaproponuj_kody``), pokazuje podgląd zmian i dopiero po
zatwierdzeniu je zapisuje — można ją uruchamiać wielokrotnie, np. po
dociągnięciu nowych języków z PBN.
"""

from django.contrib import messages
from django.db import transaction
from django.template.response import TemplateResponse

from bpp.admin.actions import zapisuje_historie
from bpp.kody_jezykow import zaproponuj_kody
from bpp.models import (
    Jezyk,
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

AKCJA_KODY = "uzupelnij_kody_crossref"
POLE_ZMIANY = "zmiana"
KOMUNIKAT_HISTORII = "Uzupełniono kody języka (akcja „Uzupełnij kody CrossRef z PBN”)"

# Modele publikacji: kolumna „Liczba publikacji” i rozstrzyganie kolizji kodów.
PUBLIKACJE_Z_JEZYKIEM = (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Patent,
)


def pola_jezyka(model):
    return [
        pole.name for pole in model._meta.concrete_fields if pole.related_model is Jezyk
    ]


def jezyki_uzywane_w_publikacjach():
    """Zbiór ``pk`` języków, na które wskazuje jakakolwiek publikacja."""
    wynik = set()
    for model in PUBLIKACJE_Z_JEZYKIEM:
        for pole in pola_jezyka(model):
            wynik.update(
                model._base_manager.order_by()
                .exclude(**{pole: None})
                .values_list(f"{pole}_id", flat=True)
                .distinct()
            )
    return wynik


def propozycje_kodow():
    """``[(jezyk, PropozycjaKodow), …]`` dla całego słownika języków."""
    jezyki = {j.pk: j for j in Jezyk.objects.select_related("pbn_uid")}
    wiersze = [
        {
            "pk": j.pk,
            "nazwa": j.nazwa,
            "skrot": j.skrot,
            "kod_bcp47": j.kod_bcp47,
            "skrot_crossref": j.skrot_crossref,
            "widoczny": j.widoczny,
            "pbn_kod": j.pbn_uid_id,
            "pbn_jezyk": j.pbn_uid.language if j.pbn_uid_id else None,
        }
        for j in jezyki.values()
    ]
    propozycje = zaproponuj_kody(wiersze, jezyki_uzywane_w_publikacjach())
    return sorted(
        ((jezyki[p.pk], p) for p in propozycje), key=lambda para: para[0].nazwa
    )


def _znacznik(propozycja):
    """Zmiana jako tekst do ukrytego pola — zatwierdzenie stosuje tylko
    zmiany DOKŁADNIE takie, jak pokazał podgląd."""
    return f"{propozycja.pk}:{propozycja.kod_bcp47 or ''}:{propozycja.skrot_crossref or ''}"


@zapisuje_historie
def uzupelnij_kody_crossref(modeladmin, request, queryset):
    """Dla CAŁEGO słownika języków — zaznaczenie na liście jest ignorowane."""
    pary = propozycje_kodow()
    zmiany = [(j, p) for j, p in pary if p.zmienia]
    kolizje = [(j, p) for j, p in pary if p.kolizja]

    if request.POST.get("potwierdzam") != "1":
        context = {
            **modeladmin.admin_site.each_context(request),
            "title": "Uzupełnij kody CrossRef z PBN",
            "opts": Jezyk._meta,
            "zmiany": [(j, p, _znacznik(p)) for j, p in zmiany],
            "kolizje": kolizje,
            "akcja": AKCJA_KODY,
            "pole_zmiany": POLE_ZMIANY,
        }
        return TemplateResponse(request, "admin/bpp/jezyk_kody_podglad.html", context)

    zatwierdzone = set(request.POST.getlist(POLE_ZMIANY))
    zmieniono = 0
    with transaction.atomic():
        for jezyk, propozycja in zmiany:
            if _znacznik(propozycja) not in zatwierdzone:
                # Stan słownika zmienił się od podglądu — tej zmiany
                # użytkownik nie widział, więc jej nie stosujemy.
                continue
            pola = {}
            if propozycja.kod_bcp47 is not None:
                pola["kod_bcp47"] = propozycja.kod_bcp47
            if propozycja.skrot_crossref is not None:
                pola["skrot_crossref"] = propozycja.skrot_crossref
            Jezyk.objects.filter(pk=jezyk.pk).update(**pola)
            modeladmin.log_change(request, jezyk, KOMUNIKAT_HISTORII)
            zmieniono += 1

    pominieto = len(zatwierdzone) - zmieniono
    komunikat = f"Uzupełniono kody w {zmieniono} językach."
    if pominieto > 0:
        komunikat += (
            f" Pominięto {pominieto} — słownik zmienił się od wyświetlenia "
            f"podglądu; uruchom akcję ponownie."
        )
    modeladmin.message_user(request, komunikat, messages.SUCCESS)


uzupelnij_kody_crossref.short_description = (
    "Uzupełnij kody CrossRef z PBN (bez zaznaczania)…"
)
uzupelnij_kody_crossref.allowed_permissions = ("change",)
