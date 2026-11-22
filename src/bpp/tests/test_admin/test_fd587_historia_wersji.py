"""FD#587: historia wersji (django-reversion) dla modeli edytowanych w adminie.

Publikacje (z autorami), zgłoszenia, słowniki i jednostki są wersjonowane:
edycja w adminie tworzy wersję, strona „Historia" pozwala porównać dwie
wersje i przywrócić wcześniejszą.
"""

import pytest
import reversion
from django.contrib import admin as djadmin
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.models import (
    Jednostka,
    Konferencja,
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Seria_Wydawnicza,
    Wydawca,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Zrodlo,
)
from bpp.wersjonowanie import POLA_POZA_WERSJA, sledzone_relacje
from zglos_publikacje.models import Zgloszenie_Publikacji

pytestmark = pytest.mark.django_db

#: model → (fixtura albo None = baker, pole tekstowe do zmiany)
MODELE = {
    Wydawnictwo_Ciagle: ("wydawnictwo_ciagle", "tytul_oryginalny"),
    Wydawnictwo_Zwarte: ("wydawnictwo_zwarte", "tytul_oryginalny"),
    Patent: ("patent", "tytul_oryginalny"),
    Praca_Doktorska: ("praca_doktorska", "tytul_oryginalny"),
    Praca_Habilitacyjna: ("praca_habilitacyjna", "tytul_oryginalny"),
    Zgloszenie_Publikacji: ("zgloszenie_publikacji", "tytul_oryginalny"),
    Zrodlo: ("zrodlo", "nazwa"),
    Wydawca: ("wydawca", "nazwa"),
    Konferencja: (None, "nazwa"),
    Seria_Wydawnicza: (None, "nazwa"),
    Jednostka: ("jednostka", "nazwa"),
}


def _obiekt(request, model):
    fixtura, _ = MODELE[model]
    if fixtura is None:
        return baker.make(model)
    return request.getfixturevalue(fixtura)


@pytest.mark.parametrize("model", list(MODELE), ids=lambda m: m.__name__)
def test_model_jest_wersjonowany(model):
    assert reversion.is_registered(model)
    for nazwa in POLA_POZA_WERSJA.get(model, ()):
        # Pole spoza wersji przy przywracaniu dostaje wartość domyślną —
        # nie może to być pole bez wartości domyślnej, którego nie liczy baza.
        assert nazwa in {f.name for f in model._meta.concrete_fields}


@pytest.mark.parametrize(
    "model",
    [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Patent],
    ids=lambda m: m.__name__,
)
def test_publikacja_wersjonowana_razem_z_autorami(model):
    assert "autorzy_set" in sledzone_relacje(model)


@pytest.mark.parametrize("model", list(MODELE), ids=lambda m: m.__name__)
def test_przywrocenie_wersji_przywraca_pole(request, model):
    """Zapis → wersja; przywrócenie najstarszej wersji przywraca pole, nie
    wywala się na polach wyliczanych spoza wersji i nie rusza kosza."""
    obj = _obiekt(request, model)
    _, pole = MODELE[model]
    stara = getattr(obj, pole)

    with reversion.create_revision():
        obj.save()
    setattr(obj, pole, "Wartość po zmianie FD587")
    with reversion.create_revision():
        obj.save()

    wersje = Version.objects.get_for_object(obj)
    assert wersje.count() == 2
    assert wersje.last().field_dict[pole] == stara

    wersje.last().revision.revert(delete=True)

    obj = model._default_manager.get(pk=obj.pk)
    assert getattr(obj, pole) == stara
    if hasattr(model, "deleted_objects"):
        assert obj.deleted_at is None


def test_przywrocenie_wersji_publikacji_usuwa_pozniej_dopisanych_autorow(
    wydawnictwo_ciagle, autor_jan_nowak, autor_jan_kowalski, jednostka
):
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    with reversion.create_revision():
        wydawnictwo_ciagle.save()

    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    with reversion.create_revision():
        wydawnictwo_ciagle.save()

    Version.objects.get_for_object(wydawnictwo_ciagle).last().revision.revert(
        delete=True
    )

    autorzy = Wydawnictwo_Ciagle_Autor.objects.filter(rekord=wydawnictwo_ciagle)
    assert list(autorzy.values_list("autor", flat=True)) == [autor_jan_nowak.pk]


def test_pola_kosza_i_wyliczane_poza_wersja_publikacji(wydawnictwo_ciagle):
    with reversion.create_revision():
        wydawnictwo_ciagle.save()
    pola = Version.objects.get_for_object(wydawnictwo_ciagle).get().field_dict
    for nazwa in (
        "deleted_at",
        "search_index",
        "opis_bibliograficzny_cache",
        "cached_punkty_dyscyplin",
    ):
        assert nazwa not in pola
    assert "tytul_oryginalny" in pola


@pytest.mark.parametrize("rekord_z_dyscyplinami", ["wydawnictwo_ciagle"], indirect=True)
def test_admin_edycja_historia_porownanie_przywrocenie(
    rekord_z_dyscyplinami, admin_app, denorms
):
    """Pełna ścieżka w adminie: edycja → dwie wersje (początkowa + po
    zmianie) → „Historia" z porównaniem → przywrócenie starej wersji razem
    z autorami, z przeliczonym opisem bibliograficznym."""
    obj = rekord_z_dyscyplinami
    nazwa = obj._meta.model_name
    stary_tytul = obj.tytul_oryginalny

    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_change", args=(obj.pk,)))
    form = page.forms[f"{nazwa}_form"]
    form["tytul_oryginalny"].value = "Tytuł po zmianie FD587"
    form["autorzy_set-1-afiliuje"].checked = False
    res = form.submit()
    assert res.status_code == 302, res.text[:2000]

    wersje = Version.objects.get_for_object(obj)
    assert wersje.count() == 2  # stan początkowy + stan po zmianie

    historia = admin_app.get(reverse(f"admin:bpp_{nazwa}_history", args=(obj.pk,)))
    assert "Porównaj wersje" in historia.text

    porownanie = admin_app.get(
        reverse(f"admin:bpp_{nazwa}_compare", args=(obj.pk,)),
        params={
            "version_id1": wersje.last().pk,
            "version_id2": wersje.first().pk,
        },
    )
    # Diff znakowy (reversion-compare) — fragmenty obu tytułów.
    assert "po zmianie FD58" in porownanie.text
    assert "oryginalny Wydawnictwo_Ciagle" in porownanie.text
    # Niezmienione słowniki (FK) nie zaśmiecają porównania.
    assert "Charakter formalny" not in porownanie.text

    strona = admin_app.get(
        reverse(f"admin:bpp_{nazwa}_revision", args=(obj.pk, wersje.last().pk))
    )
    res = strona.forms[f"{nazwa}_form"].submit()
    assert res.status_code == 302, res.text[:2000]

    denorms.flush()
    obj.refresh_from_db()
    assert obj.tytul_oryginalny == stary_tytul
    assert stary_tytul in obj.opis_bibliograficzny_cache
    assert all(obj.autorzy_set.values_list("afiliuje", flat=True))
    assert Version.objects.get_for_object(obj).count() == 3


def test_porownanie_wersji_wymaga_uprawnien(rf, wydawnictwo_ciagle, django_user_model):
    from bpp.admin.wydawnictwo_ciagle import Wydawnictwo_CiagleAdmin

    uzytkownik = django_user_model.objects.create_user(
        username="bez-uprawnien", password="x", is_staff=True
    )
    request = rf.get("/", {"version_id1": "1", "version_id2": "2"})
    request.user = uzytkownik
    ma = Wydawnictwo_CiagleAdmin(Wydawnictwo_Ciagle, djadmin.site)
    with pytest.raises(PermissionDenied):
        ma.compare_view(request, str(wydawnictwo_ciagle.pk))

    uzytkownik.user_permissions.add(
        Permission.objects.get(codename="view_wydawnictwo_ciagle")
    )
    uzytkownik = django_user_model.objects.get(pk=uzytkownik.pk)
    request.user = uzytkownik
    # Z uprawnieniem do podglądu dalej: brak takich wersji → 404, nie 403.
    from django.http import Http404

    with pytest.raises(Http404):
        ma.compare_view(request, str(wydawnictwo_ciagle.pk))


def test_akcja_masowa_nie_laczy_rekordow_w_jedna_rewizje(
    admin_client, wydawnictwo_ciagle
):
    """Kosz dwóch publikacji akcją masową: każda ma WŁASNĄ rewizję —
    przywrócenie wersji jednej nie może cofnąć drugiej."""
    drugi = baker.make(
        Wydawnictwo_Ciagle,
        rok=wydawnictwo_ciagle.rok,
        charakter_formalny=wydawnictwo_ciagle.charakter_formalny,
        jezyk=wydawnictwo_ciagle.jezyk,
        typ_kbn=wydawnictwo_ciagle.typ_kbn,
        status_korekty=wydawnictwo_ciagle.status_korekty,
    )
    res = admin_client.post(
        reverse("admin:bpp_wydawnictwo_ciagle_changelist"),
        {
            "action": "usun_do_kosza",
            "_selected_action": [wydawnictwo_ciagle.pk, drugi.pk],
            "powod": "test FD587",
            "powod_potwierdzony": "1",
        },
    )
    assert res.status_code == 302
    assert (
        Wydawnictwo_Ciagle.deleted_objects.filter(
            pk__in=[wydawnictwo_ciagle.pk, drugi.pk]
        ).count()
        == 2
    )
    rewizje = {
        v.revision_id
        for obj in (wydawnictwo_ciagle, drugi)
        for v in Version.objects.get_for_object_reference(Wydawnictwo_Ciagle, obj.pk)
    }
    assert len(rewizje) == 2
    for rewizja in rewizje:
        assert (
            Version.objects.filter(
                revision_id=rewizja,
                content_type__model="wydawnictwo_ciagle",
            ).count()
            == 1
        )
