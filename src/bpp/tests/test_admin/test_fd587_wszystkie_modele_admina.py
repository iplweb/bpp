"""FD#587: historia wersji dla wszystkich modeli edytowanych w adminie.

Strażnik: każdy model w module redagowania jest albo wersjonowany, albo
świadomie wyłączony (z powodem) — nowy model nie może „przeciec” bez
decyzji. Plus: strona „Historia” działa dla każdego wersjonowanego modelu,
a pola wrażliwe (hasła, tokeny, sekrety) nie trafiają do wersji i nie są
cofane przy przywracaniu.
"""

import uuid

import pytest
import reversion
from django.contrib import admin
from django.contrib.admin.utils import quote
from django.db import models
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.admin.helpers.wersje import HistoriaWersjiMixin
from bpp.admin.helpers.wersje_modele import (
    MODELE_BEZ_HISTORII,
    MODELE_Z_HISTORIA,
    POLA_WRAZLIWE,
)


#: Modele, których model_bakery nie umie utworzyć.
FABRYKI = {
    "siteblog.article": lambda model: model.objects.create(
        title="Artykuł FD587", article_body="Treść"
    ),
    # Klucz główny to ścieżka formularza; baker losuje tekst dłuższy niż
    # 191 znaków ``Version.object_id`` — prawdziwe ścieżki są krótkie.
    "formdefaults.formrepresentation": lambda model: model.objects.create(
        full_name="bpp.tests.FormularzFD587", label="Formularz FD587"
    ),
}


def _modele_admina():
    return {
        model._meta.label_lower: (model, model_admin)
        for model, model_admin in admin.site._registry.items()
        if isinstance(model, type) and issubclass(model, models.Model)
    }


def test_kazdy_model_admina_ma_decyzje_o_historii():
    bez_decyzji = sorted(
        set(_modele_admina()) - MODELE_Z_HISTORIA - set(MODELE_BEZ_HISTORII)
    )
    assert bez_decyzji == [], (
        "Dopisz model do MODELE_Z_HISTORIA albo (z powodem) do "
        "MODELE_BEZ_HISTORII w bpp/admin/helpers/wersje_modele.py"
    )


def test_listy_rozlaczne():
    assert not MODELE_Z_HISTORIA & set(MODELE_BEZ_HISTORII)


@pytest.mark.parametrize("etykieta", sorted(MODELE_Z_HISTORIA))
def test_model_z_historia_ma_wersjonowany_admin(etykieta):
    model, model_admin = _modele_admina()[etykieta]
    assert reversion.is_registered(model)
    if etykieta != "dbtemplates.template":  # własny VersionAdmin dbtemplates
        assert isinstance(model_admin, HistoriaWersjiMixin)


@pytest.mark.django_db
@pytest.mark.parametrize("etykieta", sorted(MODELE_Z_HISTORIA))
def test_strona_historii_dziala(admin_client, etykieta):
    model, model_admin = _modele_admina()[etykieta]
    fabryka = FABRYKI.get(etykieta, baker.make)
    obj = model._default_manager.first() or fabryka(model)
    with reversion.create_revision():
        obj.save()
    opts = model._meta
    url = reverse(
        f"admin:{opts.app_label}_{opts.model_name}_history", args=(quote(obj.pk),)
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert Version.objects.get_for_object(obj).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("etykieta", sorted(POLA_WRAZLIWE))
def test_pola_wrazliwe_poza_wersja(etykieta):
    model, _ = _modele_admina()[etykieta]
    obj = baker.make(model)
    with reversion.create_revision():
        obj.save()
    pola = Version.objects.get_for_object(obj).get().field_dict
    for nazwa in POLA_WRAZLIWE[etykieta]:
        assert nazwa not in pola


@pytest.mark.django_db
def test_przywrocenie_wersji_uzytkownika_nie_zmienia_hasla(
    admin_app, django_user_model
):
    # Hasła losowe — żadnych stałych „sekretów” w repo (ggshield).
    stare_haslo, nowe_haslo = uuid.uuid4().hex, uuid.uuid4().hex
    uzytkownik = baker.make(django_user_model, first_name="Stare")
    uzytkownik.set_password(stare_haslo)
    uzytkownik.save()
    url = reverse("admin:bpp_bppuser_change", args=(uzytkownik.pk,))
    form = admin_app.get(url).forms["bppuser_form"]
    form["first_name"] = "Nowe"
    assert form.submit().status_code == 302

    uzytkownik.set_password(nowe_haslo)
    uzytkownik.save()

    stara = Version.objects.get_for_object(uzytkownik).last()
    assert stara.field_dict["first_name"] == "Stare"
    strona = admin_app.get(
        reverse("admin:bpp_bppuser_revision", args=(uzytkownik.pk, stara.pk))
    )
    assert strona.forms["bppuser_form"].submit().status_code == 302

    uzytkownik.refresh_from_db()
    assert uzytkownik.first_name == "Stare"
    assert uzytkownik.check_password(nowe_haslo)
