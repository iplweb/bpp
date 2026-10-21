"""Odroczenie ``cached_punkty_dyscyplin`` przy zapisie z admina.

Admin zapisuje rodzica (``save_model``) PRZED inline'ami autorów
(``save_related``), więc liczenie ``@denormalized cached_punkty_dyscyplin``
w ``pre_save`` szło na STARYCH autorach i zakładało blokady na
``bpp_cache_punktacja_*`` (Rollbar #5363). Teraz admin owija
``changeform_view`` w ``denorm.deferred(...)``: kolumna JSON nie jest liczona
w ``pre_save``, zostaje marker ``DirtyInstance`` i liczy ją flush denorm
(raz, na danych po zapisie inline'ów). Tabele ``bpp_cache_punktacja_*``
przebudowuje ``BaseBppAdminMixin.save_related`` -- już na nowych autorach.
"""

import pytest
from denorm.models import DirtyInstance
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from bpp.models import (
    Jezyk,
    Patent,
    Typ_KBN,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.sloty.core import IPunktacjaCacher
from bpp.tests.test_admin.conftest import ROK_SLOTOW as ROK
from bpp.tests.test_admin.conftest import jako_json as _jako_json
from bpp.tests.test_admin.conftest import wpisy_cache_punktacji

POLE = "cached_punkty_dyscyplin"


MODELE = {
    "wydawnictwo_ciagle": Wydawnictwo_Ciagle,
    "wydawnictwo_zwarte": Wydawnictwo_Zwarte,
    "patent": Patent,
}


def _markery(obj):
    ct = ContentType.objects.get_for_model(obj)
    return DirtyInstance.objects.filter(
        content_type=ct, object_id=obj.pk, func_name=POLE
    )


def _bledy_formularza(res):
    """Komunikaty błędów formularza admina -- do czytelnego asserta."""
    ret = []
    for e in res.html.select(".errorlist, .errornote"):
        label = e.find_previous("label")
        ret.append((label.get_text() if label else "", e.get_text(" ")))
    return ret


@pytest.mark.parametrize("rekord_z_dyscyplinami", list(MODELE), indirect=True)
def test_admin_change_nie_liczy_punktow_dyscyplin_w_pre_save(
    rekord_z_dyscyplinami, admin_app, mocker, denorms
):
    """(a) + (b): edycja z admina nie woła ``przelicz_punkty_dyscyplin``
    (jedyne jego wywołanie przy zapisie pochodzi z ``pre_save`` denorma),
    ale cache przebudowuje ``save_related`` (``IPunktacjaCacher``
    bezpośrednio), a dla kolumny JSON zostaje marker ``DirtyInstance``."""
    obj = rekord_z_dyscyplinami
    model = type(obj)
    nazwa = obj._meta.model_name

    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_change", args=(obj.pk,)))
    form = page.forms[f"{nazwa}_form"]
    form["tytul_oryginalny"].value = "Zmieniony tytuł"

    # Markery z fixtur (triggery na *_Autor przy dodaj_autora) -- precz,
    # żeby marker po POST-cie dało się przypisać do odroczenia.
    DirtyInstance.objects.all().delete()

    przelicz = mocker.spy(model, "przelicz_punkty_dyscyplin")
    przebuduj = mocker.spy(IPunktacjaCacher, "rebuildEntries")

    res = form.submit()
    assert res.status_code == 302, res.text[:2000]

    assert przelicz.call_count == 0
    if nazwa != "patent":
        # Patent nie jest adaptowalny (canAdapt() == False) -> save_related
        # nie przebudowuje cache; dla pozostałych przebudowa MUSI zajść.
        assert przebuduj.call_count >= 1

    obj.refresh_from_db()
    assert obj.tytul_oryginalny == "Zmieniony tytuł"
    assert _markery(obj).count() == 1


@pytest.mark.parametrize(
    "rekord_z_dyscyplinami",
    ["wydawnictwo_ciagle", "wydawnictwo_zwarte"],
    indirect=True,
)
def test_admin_change_cache_na_nowych_autorach_a_json_po_flushu(
    rekord_z_dyscyplinami,
    admin_app,
    denorms,
    autor_jan_nowak,
    dyscyplina1,
):
    """(c) + (d): po zapisie z admina (drugi autor przestaje afiliować)
    tabele ``bpp_cache_punktacja_*`` odpowiadają NOWYM autorom od razu
    (``save_related``), a kolumna JSON -- dopiero po flushu denorm.

    Patent pominięty: nie jest adaptowalny, więc i cache, i JSON są puste
    przed i po zapisie -- test by niczego nie rozróżniał.
    """
    obj = rekord_z_dyscyplinami
    nazwa = obj._meta.model_name
    stary_json = obj.cached_punkty_dyscyplin
    assert stary_json and any(stary_json)

    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_change", args=(obj.pk,)))
    form = page.forms[f"{nazwa}_form"]
    # Kolejność inline'ów wg ``kolejnosc``: [0] Nowak, [1] Kowalski.
    form["autorzy_set-1-afiliuje"].checked = False

    res = form.submit()
    assert res.status_code == 302, res.text[:2000]

    # (c) cache na nowych autorach -- bez żadnego flushu:
    assert wpisy_cache_punktacji(obj) == ({autor_jan_nowak.pk}, {dyscyplina1.pk})

    # Kolumna JSON nietknięta do flushu (UPDATE pisze col = col)...
    obj.refresh_from_db()
    assert obj.cached_punkty_dyscyplin == stary_json
    assert _markery(obj).exists()

    # (d) ...a po flushu aktualna.
    denorms.flush()
    obj.refresh_from_db()
    assert not _markery(obj).exists()
    assert obj.cached_punkty_dyscyplin != stary_json
    assert obj.cached_punkty_dyscyplin == _jako_json(IPunktacjaCacher(obj).serialize())
    assert wpisy_cache_punktacji(obj) == ({autor_jan_nowak.pk}, {dyscyplina1.pk})


@pytest.mark.parametrize("nazwa", list(MODELE))
def test_admin_add_json_none_do_flushu(
    admin_app,
    uczelnia,
    charaktery_formalne,
    jezyki,
    typy_kbn,
    statusy_korekt,
    zrodlo,
    mocker,
    denorms,
    nazwa,
):
    """(e): INSERT z add view -- kolumna JSON = default (None) do flushu,
    marker jest, po flushu kolumna policzona."""
    model = MODELE[nazwa]
    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_add"))
    form = page.forms[f"{nazwa}_form"]
    form["tytul_oryginalny"].value = f"Nowy rekord {nazwa}"
    form["rok"].value = str(ROK)
    wymagane = {
        "zrodlo": zrodlo,
        "charakter_formalny": charaktery_formalne["AC"],
        "jezyk": Jezyk.objects.first(),
        "typ_kbn": Typ_KBN.objects.first(),
    }
    for pole, wartosc in wymagane.items():
        if pole in form.fields:
            form[pole].force_value(str(wartosc.pk))

    przelicz = mocker.spy(model, "przelicz_punkty_dyscyplin")

    res = form.submit()
    assert res.status_code == 302, _bledy_formularza(res)
    assert przelicz.call_count == 0

    obj = model.objects.get(tytul_oryginalny=f"Nowy rekord {nazwa}")
    assert obj.cached_punkty_dyscyplin is None
    assert _markery(obj).count() == 1

    denorms.flush()
    obj.refresh_from_db()
    assert obj.cached_punkty_dyscyplin is not None
    assert obj.cached_punkty_dyscyplin == _jako_json(IPunktacjaCacher(obj).serialize())
