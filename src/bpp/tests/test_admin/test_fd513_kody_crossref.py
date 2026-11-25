"""FD#513: dwuliterowe kody języków dla CrossRef na danych w kształcie PBN.

Języki dociągane z PBN mają skrót i „Kod BCP 47” TRZYLITEROWY (ISO 639-2:
„ukr”, „ces”), a w PBN ten sam język bywa dwa razy (kod bibliograficzny
i terminologiczny: „cze” i „ces”). CrossRef podaje kod dwuliterowy.
"""

from importlib import import_module

import pytest
from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.urls import reverse
from model_bakery import baker

from bpp.admin.jezyk_kody import propozycje_kodow
from bpp.kody_jezykow import KOD_WG_NAZWY, zaproponuj_kody
from bpp.models import Jezyk, Wydawnictwo_Ciagle
from crossref_bpp.core import Komparator
from pbn_api.models import Language

URL = "admin:bpp_jezyk_changelist"
MIGRACJA = import_module("bpp.migrations.0533_jezyk_kody_crossref_fd513")


def _pbn(kod3, kod2=None, pl=None):
    dane = {"en": f"lang {kod3}", "639-2": kod3}
    if kod2:
        dane["639-1"] = kod2
    if pl:
        dane["pl"] = pl
    return Language.objects.update_or_create(code=kod3, defaults={"language": dane})[0]


def _z_pbn(nazwa, kod3, kod2=None, **kw):
    """Język założony przez integrację z PBN: skrót = kod trzyliterowy,
    a „Kod BCP 47” skopiowany ze skrótu przez migrację 0479."""
    Jezyk.objects.filter(skrot=kod3).delete()
    kw.setdefault("kod_bcp47", kod3)
    return baker.make(
        Jezyk,
        nazwa=nazwa,
        skrot=kod3,
        pbn_uid=_pbn(kod3, kod2, nazwa),
        skrot_crossref=None,
        widoczny=kw.pop("widoczny", True),
        **kw,
    )


@pytest.fixture
def slownik_jak_z_pbn(db):
    """Czysty słownik (bez języków baseline) w kształcie bazy klienta."""
    Jezyk.objects.all().delete()
    return {
        "ukr": _z_pbn("t-ukraiński", "ukr", "uk"),
        # Ten sam język dwa razy w PBN (kod T i B) — kolizja kodu „cs”.
        "ces": _z_pbn("t-czeski", "ces", "cs"),
        "cze": _z_pbn("t-czeski (B)", "cze", "cs"),
        # Język bez kodu dwuliterowego.
        "ach": _z_pbn("t-acoli", "ach"),
        # Kod BCP 47 wpisany ręcznie przez redakcję.
        "por": _z_pbn("t-portugalski", "por", "pt", kod_bcp47="pt-BR"),
        # Bez powiązania z PBN — kod z polskiej nazwy.
        "wegierski": baker.make(
            Jezyk, nazwa="węgierski", skrot="t-weg", kod_bcp47="", skrot_crossref=None
        ),
        "nieznany": baker.make(
            Jezyk, nazwa="t-klingoński", skrot="t-kl", kod_bcp47="", skrot_crossref=None
        ),
    }


def _stan(jezyki):
    wynik = {}
    for klucz, jezyk in jezyki.items():
        jezyk.refresh_from_db()
        wynik[klucz] = (jezyk.kod_bcp47, jezyk.skrot_crossref)
    return wynik


OCZEKIWANE = {
    "ukr": ("uk", "uk"),
    # Kolizja: oba dostają kod BCP 47, skrótu CrossRef nie dostaje żaden.
    "ces": ("cs", None),
    "cze": ("cs", None),
    "ach": ("ach", None),
    # Ręcznie wpisany kod BCP 47 zostaje; skrót CrossRef uzupełniony.
    "por": ("pt-BR", "pt"),
    "wegierski": ("hu", "hu"),
    "nieznany": ("", None),
}


def test_przed_uzupelnieniem_jezyk_z_pbn_i_tak_sie_dopasowuje(slownik_jak_z_pbn):
    """Zapas w ``Jezyk.dla_kodu``: kod dwuliterowy z powiązanego języka PBN —
    działa także dla języków dociągniętych z PBN już po migracji."""
    assert Jezyk.dla_kodu("uk") == slownik_jak_z_pbn["ukr"]
    assert Jezyk.dla_kodu("ukr") == slownik_jak_z_pbn["ukr"]
    assert Jezyk.dla_kodu("xx") is None


def test_migracja_na_danych_w_ksztalcie_pbn(slownik_jak_z_pbn):
    MIGRACJA.uzupelnij_kody(apps, None)
    assert _stan(slownik_jak_z_pbn) == OCZEKIWANE

    # Praca po ukraińsku i po czesku z CrossRef dostaje język.
    assert (
        Komparator.porownaj_language("uk").rekord_po_stronie_bpp
        == (slownik_jak_z_pbn["ukr"])
    )
    assert Komparator.porownaj_language("cs").rekord_po_stronie_bpp in (
        slownik_jak_z_pbn["ces"],
        slownik_jak_z_pbn["cze"],
    )
    assert (
        Komparator.porownaj_language("pt").rekord_po_stronie_bpp
        == (slownik_jak_z_pbn["por"])
    )

    # Idempotentna.
    MIGRACJA.uzupelnij_kody(apps, None)
    assert _stan(slownik_jak_z_pbn) == OCZEKIWANE


def test_migracja_kolizje_rozstrzyga_uzycie_potem_widocznosc(slownik_jak_z_pbn):
    # „cs”: używany w publikacji wygrywa.
    baker.make(Wydawnictwo_Ciagle, jezyk=slownik_jak_z_pbn["cze"])
    # „de”: dwa nieużywane, jeden widoczny.
    deu = _z_pbn("t-niemiecki", "deu", "de")
    ger = _z_pbn("t-niemiecki (B)", "ger", "de", widoczny=False)
    # „fr”: kod już zajęty ręcznie — nikt inny go nie dostanie.
    zajety = baker.make(Jezyk, nazwa="t-fr-ręczny", skrot="t-frr", skrot_crossref="fr")
    fra = _z_pbn("t-francuski", "fra", "fr")

    MIGRACJA.uzupelnij_kody(apps, None)

    stan = _stan({**slownik_jak_z_pbn, "deu": deu, "ger": ger, "fra": fra})
    assert stan["cze"] == ("cs", "cs")
    assert stan["ces"] == ("cs", None)
    assert stan["deu"] == ("de", "de")
    assert stan["ger"] == ("de", None)
    assert stan["fra"] == ("fr", None)
    zajety.refresh_from_db()
    assert zajety.skrot_crossref == "fr"


def test_migracja_nie_wywraca_sie_na_dziwnych_danych(db):
    Jezyk.objects.all().delete()
    MIGRACJA.uzupelnij_kody(apps, None)  # pusty słownik

    # JSON języka PBN bez kluczy / nie-słownik / śmieciowy kod.
    for kod, dane in (("xa1", {}), ("xa2", []), ("xa3", {"639-1": 7})):
        Language.objects.update_or_create(code=kod, defaults={"language": dane})
        baker.make(
            Jezyk,
            nazwa=f"t-{kod}",
            skrot=kod,
            kod_bcp47=kod,
            pbn_uid_id=kod,
            skrot_crossref=None,
        )
    Language.objects.update_or_create(
        code="xa4", defaults={"language": {"639-1": "ZZZ"}}
    )
    baker.make(Jezyk, nazwa="t-xa4", skrot="xa4", pbn_uid_id="xa4", kod_bcp47="xa4")
    # Dwa języki o tej samej polskiej nazwie.
    baker.make(Jezyk, nazwa="czeski", skrot="t-c1", kod_bcp47="", _quantity=1)
    baker.make(Jezyk, nazwa="Czeski", skrot="t-c2", kod_bcp47="")

    MIGRACJA.uzupelnij_kody(apps, None)

    assert set(
        Jezyk.objects.filter(skrot__startswith="xa").values_list(
            "kod_bcp47", "skrot_crossref"
        )
    ) == {("xa1", None), ("xa2", None), ("xa3", None), ("xa4", None)}
    assert set(
        Jezyk.objects.filter(skrot__startswith="t-c").values_list(
            "kod_bcp47", "skrot_crossref"
        )
    ) == {("cs", None)}


def test_zamrozona_kopia_w_migracji_zgadza_sie_z_aplikacja():
    """Migracja nie importuje kodu aplikacji; w dniu jej napisania kopia ma
    dawać to samo co ``bpp.kody_jezykow``."""
    assert MIGRACJA.KOD_WG_NAZWY == KOD_WG_NAZWY
    wiersze = [
        dict(pk=1, nazwa="x", skrot="ukr", kod_bcp47="ukr", skrot_crossref=None,
             widoczny=True, pbn_kod="ukr", pbn_jezyk={"639-1": "uk"}),
        dict(pk=2, nazwa="czeski", skrot="ces", kod_bcp47="ces", skrot_crossref=None,
             widoczny=True, pbn_kod=None, pbn_jezyk=None),
        dict(pk=3, nazwa="y", skrot="cze", kod_bcp47="cze", skrot_crossref=None,
             widoczny=False, pbn_kod="cze", pbn_jezyk={"639-1": "cs"}),
    ]  # fmt: skip

    def jako_krotki(propozycje):
        return [(p.pk, p.kod_bcp47, p.skrot_crossref, p.kolizja) for p in propozycje]

    assert jako_krotki(MIGRACJA.zaproponuj_kody(wiersze, {3})) == jako_krotki(
        zaproponuj_kody(wiersze, {3})
    )


# --- akcja w adminie ----------------------------------------------------------


def test_akcja_uzupelnij_kody_podglad_i_zatwierdzenie(admin_client, slownik_jak_z_pbn):
    przed = _stan(slownik_jak_z_pbn)

    # Krok 1: podgląd bez zaznaczania — nic nie zmienia.
    res = admin_client.post(reverse(URL), {"action": "uzupelnij_kody_crossref"})
    assert res.status_code == 200
    assert _stan(slownik_jak_z_pbn) == przed
    zmieniane = {jezyk for jezyk, _p, _z in res.context["zmiany"]}
    assert slownik_jak_z_pbn["ukr"] in zmieniane
    assert slownik_jak_z_pbn["nieznany"] not in zmieniane
    assert {jezyk for jezyk, _p in res.context["kolizje"]} == {
        slownik_jak_z_pbn["ces"],
        slownik_jak_z_pbn["cze"],
    }

    # Krok 2: zatwierdzenie dokładnie tego, co pokazał podgląd.
    res = admin_client.post(
        reverse(URL),
        {
            "action": "uzupelnij_kody_crossref",
            "potwierdzam": "1",
            "zmiana": [znacznik for _j, _p, znacznik in res.context["zmiany"]],
        },
        follow=True,
    )
    assert res.status_code == 200
    assert _stan(slownik_jak_z_pbn) == OCZEKIWANE
    assert LogEntry.objects.filter(
        object_id=str(slownik_jak_z_pbn["ukr"].pk),
        change_message__contains="Uzupełnij kody CrossRef z PBN",
    ).exists()

    # Drugi raz: nic do zrobienia poza kolizjami.
    assert all(not p.zmienia for _j, p in propozycje_kodow())


def test_akcja_bez_listy_z_podgladu_niczego_nie_zmienia(
    admin_client, slownik_jak_z_pbn
):
    przed = _stan(slownik_jak_z_pbn)
    admin_client.post(
        reverse(URL), {"action": "uzupelnij_kody_crossref", "potwierdzam": "1"}
    )
    assert _stan(slownik_jak_z_pbn) == przed


def test_akcja_wymaga_uprawnienia(client, django_user_model, slownik_jak_z_pbn):
    przed = _stan(slownik_jak_z_pbn)
    user = django_user_model.objects.create_user(
        username="bez-uprawnien", password="x", is_staff=True
    )
    client.force_login(user)
    res = client.post(reverse(URL), {"action": "uzupelnij_kody_crossref"})
    assert "zmiany" not in (res.context or {})
    assert _stan(slownik_jak_z_pbn) == przed


def test_filtr_kod_crossref_po_uzupelnieniu(admin_client, slownik_jak_z_pbn):
    """Po uzupełnieniu filtr „nieustawiony” pokazuje tylko języki, których
    naprawdę nie da się dopasować kodem dwuliterowym."""
    MIGRACJA.uzupelnij_kody(apps, None)
    res = admin_client.get(reverse(URL), {"kod_crossref": "nie"})
    assert set(res.context["cl"].result_list) == {
        slownik_jak_z_pbn["ach"],
        slownik_jak_z_pbn["nieznany"],
    }
