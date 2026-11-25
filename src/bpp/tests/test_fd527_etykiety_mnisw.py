"""FD#527: w interfejsie nie ma już nazwy „KBN” — jest „MNiSW/MEiN”.

KBN (Komitet Badań Naukowych) nie istnieje od lat. Nazwy pól, tabel, kluczy
API i adresów (``typ_kbn``, ``punkty_kbn``) zostają — tu pilnujemy wyłącznie
tekstów widocznych dla użytkownika.
"""

import importlib

import pytest
from django.apps import apps
from django.contrib import admin
from django.urls import reverse
from flexible_reports.models import Column
from model_bakery import baker

from bpp.models import Typ_KBN, Wydawnictwo_Ciagle
from django_bpp import menu
from importer_publikacji.models import ImportSession
from nowe_raporty.seeding import definicje, seed_default_reports


def test_fd527_nazwy_modelu_typ_mnisw():
    assert Typ_KBN._meta.verbose_name == "typ MNiSW/MEiN"
    assert Typ_KBN._meta.verbose_name_plural == "typy MNiSW/MEiN"


def test_fd527_pole_typ_w_importerze_publikacji():
    pole = ImportSession._meta.get_field("typ_kbn")
    assert pole.verbose_name == "typ MNiSW/MEiN"


def _teksty_menu(wartosc):
    if isinstance(wartosc, str):
        yield wartosc
    elif isinstance(wartosc, (list, tuple)):
        for element in wartosc:
            yield from _teksty_menu(element)


def test_fd527_menu_bez_kbn():
    etykiety = [
        tekst
        for nazwa in dir(menu)
        if nazwa.isupper()
        for tekst in _teksty_menu(getattr(menu, nazwa))
        if not tekst.startswith("/")
    ]
    assert "Typy MNiSW/MEiN" in etykiety
    assert not [e for e in etykiety if "KBN" in e]


def test_fd527_adres_slownika_typow_bez_zmian():
    # Strażnik: zmieniamy etykietę, nie adres ani nazwę modelu w adminie.
    assert ("Typy MNiSW/MEiN", "/admin/bpp/typ_kbn/") in menu.SYSTEM_MENU_2
    assert reverse("admin:bpp_typ_kbn_changelist") == "/admin/bpp/typ_kbn/"


# Pola bez własnej etykiety (Django wylicza „punkty kbn” z nazwy pola),
# których żaden formularz ani widok nie pokazuje użytkownikowi.
ETYKIETY_NIEWIDOCZNE = {("integrator2.ListaMinisterialnaElement", "punkty_kbn")}


def test_fd527_zadne_pole_modelu_nie_ma_kbn_w_etykiecie():
    zle = []
    for model in apps.get_models():
        meta = model._meta
        for tekst in (meta.verbose_name, meta.verbose_name_plural):
            if "kbn" in str(tekst).lower():
                zle.append(f"{meta.label}: {tekst}")
        for pole in meta.get_fields():
            if (meta.label, pole.name) in ETYKIETY_NIEWIDOCZNE:
                continue
            for atrybut in ("verbose_name", "help_text"):
                tekst = str(getattr(pole, atrybut, "") or "")
                if "kbn" in tekst.lower():
                    zle.append(f"{meta.label}.{pole.name}.{atrybut}: {tekst}")
    assert not zle


def test_fd527_nazwy_pol_w_bazie_bez_zmian():
    # Strażnik: FD#527 (etykiety) nie zmienia nazw pól ani kolumn.
    assert Wydawnictwo_Ciagle._meta.get_field("typ_kbn").column == "typ_kbn_id"
    assert Wydawnictwo_Ciagle._meta.get_field("punkty_kbn").column == "punkty_kbn"
    assert Typ_KBN._meta.db_table == "bpp_typ_kbn"


@pytest.mark.django_db
def test_fd527_admin_lista_typow_i_charakterow_pbn(admin_client):
    res = admin_client.get(reverse("admin:bpp_typ_kbn_changelist"))
    assert res.status_code == 200
    tresc = res.content.decode()
    assert "MNiSW/MEiN" in tresc
    assert "KBN" not in tresc

    res = admin_client.get(reverse("admin:bpp_charakter_pbn_changelist"))
    assert res.status_code == 200
    tresc = res.content.decode()
    assert "Typy MNiSW/MEiN" in tresc
    assert "kbn</" not in tresc.lower()


def test_fd527_kolumna_typow_w_adminie_charakterow_pbn():
    from bpp.models import Charakter_PBN

    model_admin = admin.site._registry[Charakter_PBN]
    assert model_admin.typy_kbn.short_description == "Typy MNiSW/MEiN"


def test_fd527_seed_raportow_bez_kbn():
    etykiety = [kolumna["label"] for kolumna in definicje.KOLUMNY]
    assert "Typ MNiSW/MEiN" in etykiety
    assert not [e for e in etykiety if "KBN" in e]


@pytest.fixture
def migracja():
    return importlib.import_module(
        "nowe_raporty.migrations.0004_fd527_etykiety_kbn_na_mnisw"
    )


@pytest.mark.django_db
def test_fd527_migracja_poprawia_etykiety_kolumn_w_bazie(migracja):
    seed_default_reports()
    seedowa = Column.objects.get(
        parent__label=definicje.TABELA_LABEL, label="Typ MNiSW/MEiN"
    )
    # Stan sprzed FD#527: instalacje mają w bazie „Typ KBN”.
    Column.objects.filter(pk=seedowa.pk).update(label="Typ KBN")
    wlasna = baker.make(Column, parent=seedowa.parent, label="Punkty KBN (suma)")
    obca = baker.make(Column, parent=seedowa.parent, label="Typ pracy")

    migracja.naprzod(apps, None)

    seedowa.refresh_from_db()
    wlasna.refresh_from_db()
    obca.refresh_from_db()
    assert seedowa.label == "Typ MNiSW/MEiN"
    assert wlasna.label == "Punkty MNiSW/MEiN (suma)"
    # Strażnik: etykiet bez „KBN” migracja nie rusza.
    assert obca.label == "Typ pracy"

    migracja.wstecz(apps, None)
    seedowa.refresh_from_db()
    assert seedowa.label == "Typ KBN"


def test_fd527_jedna_forma_mnisw_mein_w_importerze_i_raportach():
    from importer_publikacji.forms import PunktacjaForm, VerifyForm
    from nowe_raporty.forms import BaseRaportForm

    assert VerifyForm.base_fields["typ_kbn"].label == "Typ MNiSW/MEiN"
    assert PunktacjaForm.base_fields["punkty_kbn"].label == "Punkty MNiSW/MEiN"
    etykiety = [kolumna["label"] for kolumna in definicje.KOLUMNY]
    assert "Pkt. MNiSW/MEiN" in etykiety
    assert "Pkt. MNiSW" not in etykiety
    etykiety_formularza = [str(p.label) for p in BaseRaportForm.base_fields.values()]
    assert "Tylko prace punktowane (pkt MNiSW/MEiN > 0)" in etykiety_formularza


@pytest.mark.django_db
def test_fd527_migracja_dopisuje_mein_do_krotkich_etykiet():
    migracja = importlib.import_module(
        "nowe_raporty.migrations.0005_fd527_etykiety_mnisw_mein"
    )
    seed_default_reports()
    tabela = Column.objects.filter(parent__label=definicje.TABELA_LABEL).first().parent
    Column.objects.filter(parent=tabela, label="Pkt. MNiSW/MEiN").update(
        label="Pkt. MNiSW"
    )
    reczna = baker.make(Column, parent=tabela, label="Typ MNiSW")
    obca = baker.make(Column, parent=tabela, label="Punkty MNiSW autora")

    migracja.naprzod(apps, None)

    etykiety = set(Column.objects.filter(parent=tabela).values_list("label", flat=True))
    assert "Pkt. MNiSW/MEiN" in etykiety
    assert "Pkt. MNiSW" not in etykiety
    reczna.refresh_from_db()
    obca.refresh_from_db()
    assert reczna.label == "Typ MNiSW/MEiN"
    # Strażnik: etykiety niebędące dokładnie krótką formą zostają.
    assert obca.label == "Punkty MNiSW autora"
