"""FD#527: w interfejsie nie ma już nazwy „KBN” — jest „MNiSW”.

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
    assert Typ_KBN._meta.verbose_name == "typ MNiSW"
    assert Typ_KBN._meta.verbose_name_plural == "typy MNiSW"


def test_fd527_pole_typ_w_importerze_publikacji():
    pole = ImportSession._meta.get_field("typ_kbn")
    assert pole.verbose_name == "typ MNiSW"


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
    assert "Typy MNiSW" in etykiety
    assert not [e for e in etykiety if "KBN" in e]


def test_fd527_adres_slownika_typow_bez_zmian():
    # Strażnik: zmieniamy etykietę, nie adres ani nazwę modelu w adminie.
    assert ("Typy MNiSW", "/admin/bpp/typ_kbn/") in menu.SYSTEM_MENU_2
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
    assert "MNiSW" in tresc
    assert "KBN" not in tresc

    res = admin_client.get(reverse("admin:bpp_charakter_pbn_changelist"))
    assert res.status_code == 200
    tresc = res.content.decode()
    assert "Typy MNiSW" in tresc
    assert "kbn</" not in tresc.lower()


def test_fd527_kolumna_typow_w_adminie_charakterow_pbn():
    from bpp.models import Charakter_PBN

    model_admin = admin.site._registry[Charakter_PBN]
    assert model_admin.typy_kbn.short_description == "Typy MNiSW"


def test_fd527_seed_raportow_bez_kbn():
    etykiety = [kolumna["label"] for kolumna in definicje.KOLUMNY]
    assert "Typ MNiSW" in etykiety
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
        parent__label=definicje.TABELA_LABEL, label="Typ MNiSW"
    )
    # Stan sprzed FD#527: instalacje mają w bazie „Typ KBN”.
    Column.objects.filter(pk=seedowa.pk).update(label="Typ KBN")
    wlasna = baker.make(Column, parent=seedowa.parent, label="Punkty KBN (suma)")
    obca = baker.make(Column, parent=seedowa.parent, label="Typ pracy")

    migracja.naprzod(apps, None)

    seedowa.refresh_from_db()
    wlasna.refresh_from_db()
    obca.refresh_from_db()
    assert seedowa.label == "Typ MNiSW"
    assert wlasna.label == "Punkty MNiSW (suma)"
    # Strażnik: etykiet bez „KBN” migracja nie rusza.
    assert obca.label == "Typ pracy"

    migracja.wstecz(apps, None)
    seedowa.refresh_from_db()
    assert seedowa.label == "Typ KBN"


def test_fd527_zadne_pole_modelu_nie_ma_mein_w_etykiecie():
    """Jedna forma w całym interfejsie: „MNiSW”, bez „/MEiN”."""
    zle = []
    for model in apps.get_models():
        meta = model._meta
        teksty = [("", meta.verbose_name), ("", meta.verbose_name_plural)]
        for pole in meta.get_fields():
            for atrybut in ("verbose_name", "help_text"):
                teksty.append((f".{pole.name}.{atrybut}", getattr(pole, atrybut, "")))
        for gdzie, tekst in teksty:
            if "mein" in str(tekst or "").lower():
                zle.append(f"{meta.label}{gdzie}: {tekst}")
    assert not zle


def test_fd527_etykiety_wyszukiwarki_i_raportow_bez_mein():
    from bpp.multiseek_registry import registry
    from ranking_autorow.forms import RankingAutorowForm
    from raport_slotow.tables import RaportSlotowAutorTable

    etykiety = [str(pole.label) for pole in registry.fields]
    assert "Punkty MNiSW" in etykiety
    assert "Typ MNiSW" in etykiety
    etykiety += [str(p.label) for p in RankingAutorowForm.base_fields.values()]
    etykiety += [str(k.verbose_name) for k in RaportSlotowAutorTable.base_columns.values()]
    etykiety += [kolumna["label"] for kolumna in definicje.KOLUMNY]
    etykiety += [
        tekst
        for nazwa in dir(menu)
        if nazwa.isupper()
        for tekst in _teksty_menu(getattr(menu, nazwa))
    ]
    assert not [e for e in etykiety if "mein" in e.lower()]


@pytest.mark.django_db
def test_fd527_migracja_skraca_znane_etykiety_z_mein(migracja):
    seed_default_reports()
    tabela = Column.objects.filter(parent__label=definicje.TABELA_LABEL).first().parent
    znane = [
        baker.make(Column, parent=tabela, label=stara) for stara in migracja.DOKLADNE
    ]
    obca = baker.make(Column, parent=tabela, label="Wykaz MEiN 2023")
    podobna = baker.make(Column, parent=tabela, label="Punkty MNiSW/MEiN autora")

    migracja.naprzod(apps, None)

    for kolumna, nowa in zip(znane, migracja.DOKLADNE.values(), strict=True):
        kolumna.refresh_from_db()
        assert kolumna.label == nowa
    obca.refresh_from_db()
    podobna.refresh_from_db()
    # Strażnik: tylko dokładne dopasowania znanych etykiet.
    assert obca.label == "Wykaz MEiN 2023"
    assert podobna.label == "Punkty MNiSW/MEiN autora"


@pytest.fixture
def migracja_bpp():
    return importlib.import_module("bpp.migrations.0533_fd527_etykiety_mnisw")


@pytest.mark.django_db
def test_fd527_uprawnienia_slownika_typow_maja_nowa_nazwe(migracja_bpp):
    from django.contrib.auth.models import Permission

    uprawnienia = Permission.objects.filter(
        content_type__app_label="bpp", content_type__model="typ_kbn"
    )
    dodawanie = uprawnienia.get(codename="add_typ_kbn")
    Permission.objects.filter(pk=dodawanie.pk).update(name="Can add typ MNiSW/MEiN")
    przegladanie = uprawnienia.get(codename="view_typ_kbn")
    Permission.objects.filter(pk=przegladanie.pk).update(name="Can view typ KBN")

    migracja_bpp.popraw_nazwy_uprawnien(apps, None)

    dodawanie.refresh_from_db()
    przegladanie.refresh_from_db()
    assert dodawanie.name == "Can add typ MNiSW"
    assert przegladanie.name == "Can view typ MNiSW"
    # Strażnik: kody uprawnień (po nich działa kontrola dostępu) bez zmian.
    assert dodawanie.codename == "add_typ_kbn"


@pytest.mark.django_db
def test_fd527_zapisany_formularz_wyszukiwania_po_zmianie_etykiet(migracja_bpp):
    """Zapisane formularze pamiętają pola po etykiecie — migracja je poprawia."""
    from django.db import connection
    from multiseek.models import SearchForm

    dane = (
        '{"form_data": [null, {"field": "Punkty MNiSW/MEiN", "operator": "=", '
        '"value": 100}, {"field": "Typ MNiSW/MEiN", "value": "PO"}, '
        '{"field": "Tytuł pracy", "value": "wykaz MNiSW/MEiN"}]}'
    )
    formularz = baker.make(SearchForm, data=dane)
    sql = next(
        op.sql
        for op in migracja_bpp.Migration.operations
        if op.__class__.__name__ == "RunSQL"
    )
    with connection.cursor() as kursor:
        kursor.execute(sql)

    formularz.refresh_from_db()
    assert '"field": "Punkty MNiSW"' in formularz.data
    assert '"field": "Typ MNiSW"' in formularz.data
    # Strażnik: wartość wpisana przez użytkownika zostaje nietknięta.
    assert '"value": "wykaz MNiSW/MEiN"' in formularz.data
