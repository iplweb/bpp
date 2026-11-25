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

    # Cofnięcie niczego nie zmienia: „Typ MNiSW” mógł wpisać redaktor.
    migracja.wstecz(apps, None)
    seedowa.refresh_from_db()
    assert seedowa.label == "Typ MNiSW"


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
    etykiety += [
        str(k.verbose_name) for k in RaportSlotowAutorTable.base_columns.values()
    ]
    etykiety += [kolumna["label"] for kolumna in definicje.KOLUMNY]
    etykiety += [
        tekst
        for nazwa in dir(menu)
        if nazwa.isupper()
        for tekst in _teksty_menu(getattr(menu, nazwa))
    ]
    assert not [e for e in etykiety if "mein" in e.lower()]


@pytest.fixture
def migracja_bpp():
    return importlib.import_module("bpp.migrations.0533_fd527_etykiety_mnisw")


@pytest.mark.django_db
def test_fd527_uprawnienia_slownika_typow_maja_nowa_nazwe(migracja_bpp):
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    typ = ContentType.objects.get(app_label="bpp", model="typ_kbn")
    uprawnienia = Permission.objects.filter(content_type=typ)
    dodawanie = uprawnienia.get(codename="add_typ_kbn")
    Permission.objects.filter(pk=dodawanie.pk).update(name="Can add typ MNiSW/MEiN")
    przegladanie = uprawnienia.get(codename="view_typ_kbn")
    Permission.objects.filter(pk=przegladanie.pk).update(name="Can view typ KBN")
    wlasne = Permission.objects.create(
        content_type=typ, codename="scalaj_typ_kbn", name="Może scalać typ KBN"
    )

    migracja_bpp.popraw_nazwy_uprawnien(apps, None)

    dodawanie.refresh_from_db()
    przegladanie.refresh_from_db()
    wlasne.refresh_from_db()
    assert dodawanie.name == "Can add typ MNiSW"
    assert przegladanie.name == "Can view typ MNiSW"
    # Strażnicy: kody uprawnień (po nich działa kontrola dostępu) bez zmian,
    # a uprawnienia spoza czterech standardowych nie są dotykane.
    assert dodawanie.codename == "add_typ_kbn"
    assert wlasne.name == "Może scalać typ KBN"


@pytest.mark.django_db
def test_fd527_zapisane_formularze_wyszukiwania(migracja_bpp):
    """Migracja zmienia wyłącznie klucz pola — nie wartości filtrów."""
    import json

    from multiseek.models import SearchForm

    warunki = [
        None,
        {"field": "Punkty MNiSW/MEiN", "operator": "=", "value": 100},
        # wartość równa dawnej etykiecie — to tekst użytkownika, zostaje
        {"field": "Tytuł pracy", "operator": "~", "value": "Punkty MNiSW/MEiN"},
        [None, {"field": "Typ KBN", "operator": "=", "value": "Typ MNiSW/MEiN"}],
    ]
    zwykly = baker.make(
        SearchForm,
        name="fd527 zwykly",
        data=json.dumps({"form_data": warunki, "ordering": {"order_0": "6"}}),
    )
    # poprawny JSON z escapowanym ukośnikiem w etykiecie
    escapowany = baker.make(
        SearchForm,
        name="fd527 escapowany",
        data='{"form_data": [null, {"field": "Typ MNiSW\\/MEiN", "value": "PO"}]}',
    )
    assert "\\/" in escapowany.data
    uszkodzony = baker.make(
        SearchForm, name="fd527 zepsuty", data='{"form_data": [null, {"field": '
    )
    aktualny_tekst = '{"form_data": [null, {"field": "Punkty MNiSW", "value": 1}]}'
    aktualny = baker.make(SearchForm, name="fd527 aktualny", data=aktualny_tekst)

    migracja_bpp.popraw_zapisane_formularze(apps, None)

    zwykly.refresh_from_db()
    dane = json.loads(zwykly.data)
    assert dane["form_data"][1] == {
        "field": "Punkty MNiSW",
        "operator": "=",
        "value": 100,
    }
    assert dane["form_data"][2]["value"] == "Punkty MNiSW/MEiN"
    assert dane["form_data"][3][1] == {
        "field": "Typ MNiSW",
        "operator": "=",
        "value": "Typ MNiSW/MEiN",
    }
    assert dane["ordering"] == {"order_0": "6"}

    escapowany.refresh_from_db()
    assert json.loads(escapowany.data)["form_data"][1]["field"] == "Typ MNiSW"

    # Strażnicy: uszkodzony JSON i formularz bez dawnych etykiet — bez zmian.
    uszkodzony.refresh_from_db()
    assert uszkodzony.data == '{"form_data": [null, {"field": '
    aktualny.refresh_from_db()
    assert aktualny.data == aktualny_tekst


def test_fd527_mapa_etykiet_w_migracji_zgodna_z_rejestrem(migracja_bpp):
    from bpp.multiseek_registry.dawne_etykiety import DAWNE_ETYKIETY

    assert migracja_bpp.DAWNE_ETYKIETY_POL == DAWNE_ETYKIETY


@pytest.mark.parametrize(
    "stara,nowa",
    [
        ("Typ KBN", "Typ MNiSW"),
        ("Typ kbn", "Typ MNiSW"),
        ("Punkty KBN (suma)", "Punkty MNiSW (suma)"),
        # bez podwojenia, gdy obie nazwy stały obok siebie
        ("Punkty KBN/MNiSW", "Punkty MNiSW"),
        ("Pkt. MNiSW/KBN", "Pkt. MNiSW"),
        ("Punkty KBN / MNiSW", "Punkty MNiSW"),
        # znane frazy z „/MEiN”, także ze spacją na brzegu i z dopiskiem
        ("Typ MNiSW/MEiN", "Typ MNiSW"),
        ("Typy MNiSW/MEiN", "Typy MNiSW"),
        ("Pkt. MNiSW/MEiN ", "Pkt. MNiSW"),
        ("Punkty MNiSW/MEiN (suma)", "Punkty MNiSW (suma)"),
        ("Punkty MNiSW/MEiN autora", "Punkty MNiSW autora"),
        ("typ mnisw/mein", "typ MNiSW"),
        # strażnicy: tego migracja nie rusza
        ("KBN-owskie", "KBN-owskie"),
        ("punkty_kbn", "punkty_kbn"),
        ("Punkty MNiSW/MEiN/NCN", "Punkty MNiSW/MEiN/NCN"),
        ("Typ MNiSW ", "Typ MNiSW "),
        ("Wykaz MEiN 2023", "Wykaz MEiN 2023"),
        ("Typ MNiSW", "Typ MNiSW"),
        ("Rok", "Rok"),
    ],
)
def test_fd527_migracja_raportow_podmiany(migracja, stara, nowa):
    assert migracja.nowa_etykieta(stara) == nowa


@pytest.mark.django_db
def test_fd527_migracja_raportow_na_bazie(migracja):
    seed_default_reports()
    tabela = Column.objects.filter(parent__label=definicje.TABELA_LABEL).first().parent
    Column.objects.filter(parent=tabela, label__in=["Typ MNiSW", "Pkt. MNiSW"]).delete()
    przypadki = {
        "Punkty KBN/MNiSW": "Punkty MNiSW",
        "Typ kbn": "Typ MNiSW",
        "Pkt. MNiSW/MEiN ": "Pkt. MNiSW",
        "KBN-owskie": "KBN-owskie",
    }
    kolumny = {
        stara: baker.make(Column, parent=tabela, label=stara) for stara in przypadki
    }
    migracja.naprzod(apps, None)
    for stara, nowa in przypadki.items():
        kolumny[stara].refresh_from_db()
        assert kolumny[stara].label == nowa, stara


@pytest.mark.django_db
def test_fd527_kafel_najczesciej_uzywane_bez_typy_kbn(admin_user):
    from admin_dashboard.models import MenuClick

    migracja_menu = importlib.import_module(
        "admin_dashboard.migrations.0002_fd527_menu_typy_mnisw"
    )
    adres = "/admin/bpp/typ_kbn/"
    for etykieta in ("Typy KBN", "Typy KBN", "Typy MNiSW/MEiN", "Typy MNiSW"):
        baker.make(MenuClick, user=admin_user, menu_label=etykieta, menu_url=adres)
    inne = baker.make(
        MenuClick, user=admin_user, menu_label="Tytuły", menu_url="/admin/bpp/tytul/"
    )

    migracja_menu.naprzod(apps, None)

    etykiety = set(
        MenuClick.objects.filter(menu_url=adres).values_list("menu_label", flat=True)
    )
    assert etykiety == {"Typy MNiSW"}
    # Kliknięcia nie znikają — zliczają się teraz pod jedną nazwą.
    assert MenuClick.objects.filter(menu_url=adres).count() == 4
    inne.refresh_from_db()
    assert inne.menu_label == "Tytuły"


def test_fd527_migracja_raportow_plan_kolizji(migracja):
    """Etykieta jest kluczem kolumny w tabeli raportu — dwie takie same
    oznaczałyby, że jedna kolumna znika z raportu."""
    zmiany, kolizje = migracja.zaplanuj_zmiany(
        {
            1: "Typ KBN",
            2: "Typ MNiSW",
            3: "Punkty KBN",
            4: "Punkty MNiSW/MEiN",
            5: "Rok",
        }
    )
    # „Typ MNiSW” już jest → „Typ KBN” zostaje; z dwóch kandydatów na
    # „Punkty MNiSW” zmienia się pierwszy, drugi zostaje.
    assert zmiany == {3: "Punkty MNiSW"}
    assert kolizje == [
        (1, "Typ KBN", "Typ MNiSW"),
        (4, "Punkty MNiSW/MEiN", "Punkty MNiSW"),
    ]


@pytest.mark.django_db
def test_fd527_migracja_raportow_nie_tworzy_duplikatow_w_tabeli(migracja, caplog):
    from flexible_reports.models import Table

    seed_default_reports()
    tabela = Column.objects.filter(parent__label=definicje.TABELA_LABEL).first().parent
    # W tej tabeli „Typ MNiSW” już jest (seed) — dokładamy dawne „Typ KBN”.
    stara = baker.make(Column, parent=tabela, label="Typ KBN")
    # W innej tabeli kolizji nie ma, więc tam zmiana zachodzi.
    inna = baker.make(Table, label="FD527 inna tabela", base_model=tabela.base_model)
    w_innej = baker.make(Column, parent=inna, label="Typ KBN")

    with caplog.at_level("WARNING"):
        migracja.naprzod(apps, None)

    stara.refresh_from_db()
    w_innej.refresh_from_db()
    assert stara.label == "Typ KBN"
    assert w_innej.label == "Typ MNiSW"
    etykiety = list(
        Column.objects.filter(parent=tabela).values_list("label", flat=True)
    )
    assert len(etykiety) == len(set(etykiety))
    assert "zajęta" in caplog.text


def test_fd527_opisy_funkcji_na_stronie_uczelni_bez_mein():
    """Opis narzędzia „Import list ministerialnych” mówi o wykazie MNiSW."""
    from django.template.loader import get_template

    zrodlo = get_template("browse/uczelnia.html").template.source
    assert "wykazu czasopism MNiSW" in zrodlo
    assert "MEiN" not in zrodlo
    assert "KBN" not in zrodlo
