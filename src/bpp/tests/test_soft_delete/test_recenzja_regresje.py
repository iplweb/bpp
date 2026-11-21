"""Regresje z niezależnych recenzji PR kosza (listopad 2026).

Każdy test odwraca repro błędu: asercja opisuje zachowanie poprawione.
"""

import pytest
from denorm import denorms
from django import forms
from django.db.models import ProtectedError
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APIClient

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Jednostka,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawca,
    Wydawnictwo_Ciagle,
    Zrodlo,
)
from bpp.models.soft_delete import KonfliktPrzywracania, relacje_przychodzace

# --- 4: przywrócenie nie kończy się 500 ----------------------------------


@pytest.mark.django_db
def test_przywrocenie_drugiej_habilitacji_to_konflikt_nie_500(
    autor_jan_kowalski, jednostka
):
    h1 = baker.make(Praca_Habilitacyjna, autor=autor_jan_kowalski, jednostka=jednostka)
    h1.delete()
    baker.make(Praca_Habilitacyjna, autor=autor_jan_kowalski, jednostka=jednostka)
    h1 = Praca_Habilitacyjna.global_objects.get(pk=h1.pk)

    with pytest.raises(KonfliktPrzywracania, match="autor ma już habilitację"):
        h1.restore()

    assert Praca_Habilitacyjna.deleted_objects.filter(pk=h1.pk).exists()
    assert h1.deleted_at is not None


# --- 5: guard z relacji przychodzących -----------------------------------


@pytest.mark.django_db
def test_wydawca_doktoratu_nie_trafia_do_kosza(autor_jan_kowalski, jednostka):
    w = baker.make(Wydawca, nazwa="Wyd X")
    baker.make(
        Praca_Doktorska, autor=autor_jan_kowalski, jednostka=jednostka, wydawca=w
    )
    with pytest.raises(ProtectedError):
        w.delete()


@pytest.mark.django_db
def test_promotor_nie_trafia_do_kosza(autor_jan_kowalski, jednostka):
    promotor = baker.make(Autor, nazwisko="Promotor", imiona="Pan")
    baker.make(
        Praca_Doktorska,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        promotor=promotor,
    )
    with pytest.raises(ProtectedError):
        promotor.delete()


@pytest.mark.django_db
def test_redaktor_zrodla_nie_trafia_do_kosza():
    redaktor = baker.make(Autor)
    baker.make("bpp.Redakcja_Zrodla", redaktor=redaktor, od_roku=2020)
    with pytest.raises(ProtectedError):
        redaktor.delete()


def test_generyczny_guard_obejmuje_wymagane_relacje():
    from bpp.models.autor import POMIJANE_RELACJE_KOSZA_AUTORA

    def etykiety(model, pomijane):
        return {
            f"{m._meta.label}.{pole}"
            for m, pole in relacje_przychodzace(model, pomijane)
        }

    autor = etykiety(Autor, POMIJANE_RELACJE_KOSZA_AUTORA)
    assert {
        "bpp.Praca_Doktorska.promotor",
        "bpp.Praca_Doktorska.autor",
        "bpp.Praca_Habilitacyjna.autor",
        "bpp.Redakcja_Zrodla.redaktor",
        "bpp.Wydawnictwo_Ciagle_Autor.autor",
        "zglos_publikacje.Zgloszenie_Publikacji_Autor.autor",
        "bpp.Projekt_Autor.autor",
    } <= autor
    assert "bpp.Autor_Jednostka.autor" not in autor

    wydawca = etykiety(Wydawca, Wydawca.pomijane_relacje_kosza)
    assert {
        "bpp.Praca_Doktorska.wydawca",
        "bpp.Praca_Habilitacyjna.wydawca",
        "bpp.Wydawnictwo_Zwarte.wydawca",
    } <= wydawca
    assert "bpp.Poziom_Wydawcy.wydawca" not in wydawca


# --- 3: unikalne identyfikatory zostają przy rekordzie z kosza -----------


@pytest.mark.django_db
def test_orcid_autora_z_kosza_daje_blad_walidacji_nie_500():
    a = baker.make(Autor, nazwisko="A", imiona="B", orcid="0000-0001-2345-6789")
    a.delete()

    F = forms.modelform_factory(Autor, fields=["nazwisko", "imiona", "orcid"])
    f = F(data={"nazwisko": "A", "imiona": "B", "orcid": "0000-0001-2345-6789"})

    assert not f.is_valid()
    blad = str(f.errors["orcid"])
    assert "rekordu w koszu" in blad
    assert reverse("admin:bpp_autor_change", args=[a.pk]) in blad


@pytest.mark.django_db
def test_pbn_uid_publikacji_z_kosza_daje_blad_walidacji_nie_500(
    wydawnictwo_ciagle, pbn_publication
):
    wydawnictwo_ciagle.pbn_uid = pbn_publication
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete()
    drugi = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Drugi", rok=2020)

    F = forms.modelform_factory(Wydawnictwo_Ciagle, fields=["pbn_uid"])
    f = F(data={"pbn_uid": pbn_publication.pk}, instance=drugi)

    assert not f.is_valid()
    assert "przywróć tamten rekord" in str(f.errors["pbn_uid"])


@pytest.mark.django_db
def test_ustaw_pbn_uid_pomija_uid_rekordu_z_kosza(pbn_publication):
    from bpp.models import Rekord
    from pbn_integrator.models import RekordWKoszuPominietyPrzezImport
    from pbn_integrator.utils.integration import ustaw_pbn_uid_jesli_brak

    w_koszu = baker.make(Wydawnictwo_Ciagle, pbn_uid=pbn_publication)
    w_koszu.delete()
    zywy = baker.make(Wydawnictwo_Ciagle)
    denorms.flush()
    rekord = (
        Rekord.objects.get_original(zywy)
        if hasattr(Rekord.objects, "get_original")
        else Rekord.objects.get(tytul_oryginalny=zywy.tytul_oryginalny)
    )

    ustaw_pbn_uid_jesli_brak(pbn_publication, rekord)  # bez IntegrityError

    zywy.refresh_from_db()
    assert zywy.pbn_uid_id is None
    assert RekordWKoszuPominietyPrzezImport.objects.filter(
        object_id=w_koszu.pk
    ).exists()


# --- 9: API nie pokazuje dzieci rodzica z kosza --------------------------


@pytest.mark.django_db
def test_api_autor_jednostka_pomija_autorow_z_kosza(uczelnia):
    jednostka = baker.make(Jednostka, uczelnia=uczelnia)
    autor = baker.make(Autor)
    baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
    url = reverse("api_v1:autor_jednostka-list")
    assert APIClient().get(url).json()["count"] == 1

    autor.delete()  # Autor_Jednostka jest pomijane przez guard

    assert APIClient().get(url).json()["count"] == 0


# --- 10: zbiorcze kasowanie jednostek idzie do kosza ---------------------


@pytest.mark.django_db
def test_zbiorcze_kasowanie_jednostek_idzie_do_kosza(uczelnia):
    j1 = baker.make(Jednostka, uczelnia=uczelnia)
    j2 = baker.make(Jednostka, uczelnia=uczelnia)

    Jednostka.objects.filter(pk__in=[j1.pk, j2.pk]).delete()

    assert Jednostka.deleted_objects.filter(pk__in=[j1.pk, j2.pk]).count() == 2
    with pytest.raises(RuntimeError):
        Jednostka.objects.filter(pk=j1.pk).update(deleted_at=None)


# --- 12: liczba N po przywróceniu autora ---------------------------------


@pytest.mark.django_db
def test_przeliczenie_n_kasuje_ukryte_udzialy_autora_z_kosza(
    uczelnia, jednostka, dyscyplina1, rodzaj_autora_n
):
    from bpp.models import Autor_Dyscyplina
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok
    from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025

    jednostka.skupia_pracownikow = True
    jednostka.save()
    autor = baker.make(Autor, aktualna_jednostka=jednostka)
    Autor_Dyscyplina.objects.create(
        autor=autor,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=1,
        procent_dyscypliny=100,
        rodzaj_autora=rodzaj_autora_n,
        rok=2022,
    )
    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)
    autor.delete()
    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)

    # Stare (ukryte) wiersze autora z kosza zostały skasowane przeliczeniem.
    assert not IloscUdzialowDlaAutoraZaRok._base_manager.filter(autor=autor).exists()


# --- A: twarde skasowanie doktoratu czyści bpp_autorzy_mat ---------------


@pytest.mark.django_db
def test_twarde_skasowanie_doktoratu_czysci_autorzy_mat(autor_jan_kowalski, jednostka):
    from bpp.models.cache import Autorzy

    pd = baker.make(Praca_Doktorska, autor=autor_jan_kowalski, jednostka=jednostka)
    assert Autorzy.objects.filter(autor=autor_jan_kowalski).exists()

    pd.delete()
    Praca_Doktorska.global_objects.get(pk=pd.pk).hard_delete()

    assert not Autorzy.objects.filter(autor=autor_jan_kowalski).exists()
    assert autor_jan_kowalski not in jednostka.wspolpracowali()


# --- denorm po przywróceniu ----------------------------------------------


@pytest.mark.django_db
def test_opis_bibliograficzny_aktualny_po_przywroceniu(zrodlo, wydawnictwo_ciagle):
    """Zmiana źródła w czasie, gdy publikacja leży w koszu, musi być
    widoczna w opisie po przywróceniu."""
    wydawnictwo_ciagle.zrodlo = zrodlo
    wydawnictwo_ciagle.save()
    denorms.flush()
    wydawnictwo_ciagle.delete()
    zrodlo.nazwa = "ZUPELNIE NOWA NAZWA"
    zrodlo.skrot = "ZNN"
    zrodlo.save()
    denorms.flush()

    w = Wydawnictwo_Ciagle.global_objects.get(pk=wydawnictwo_ciagle.pk)
    w.restore()
    denorms.flush()
    w.refresh_from_db()

    assert "ZNN" in w.opis_bibliograficzny_cache or (
        "ZUPELNIE" in w.opis_bibliograficzny_cache
    )


# --- 11: przemapuj_zrodla_pbn — źródło z publikacjami w koszu ------------


@pytest.mark.django_db
def test_usun_zrodlo_z_publikacjami_w_koszu_czytelny_komunikat(admin_client):
    from pbn_client.const import DELETED

    from pbn_api.models import Journal

    journal = baker.make(Journal, status=DELETED)
    z = baker.make(Zrodlo, pbn_uid=journal)
    wc = baker.make(Wydawnictwo_Ciagle, zrodlo=z)
    wc.delete()

    res = admin_client.post(
        reverse("przemapuj_zrodla_pbn:usun_zrodlo", args=[z.pk]), follow=True
    )

    tresc = res.content.decode("utf-8")
    assert "publikacji w koszu" in tresc
    assert Zrodlo.objects.filter(pk=z.pk).exists()
