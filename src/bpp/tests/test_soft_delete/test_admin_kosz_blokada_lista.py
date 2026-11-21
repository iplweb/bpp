"""Strona „Nie można przenieść do kosza": lista blokujących rekordów
(grupy per relacja, limit, oznaczenie rekordów z kosza, linki) oraz wygląd
stron kosza w markupie Grappelli."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db.models import ProtectedError
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Jednostka,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Zrodlo,
)
from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna
from bpp.models.soft_delete import (
    LIMIT_POZYCJI_BLOKADY,
    BlokadaKosza,
    grupa_blokady,
)
from pbn_export_queue.models import PBN_Export_Queue

ZNACZNIK_KOSZA = "🗑️ w koszu</strong>"


def _url(obj):
    return reverse(
        f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
        args=[obj.pk],
    )


@pytest.fixture
def autor_z_pracami(bez_celery):
    """Autor z 20 artykułami (3 w koszu) i doktoratem, którego jest
    promotorem."""
    autor = baker.make(Autor, nazwisko="Blokowany", imiona="Jan")
    prace = [
        baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=f"Artykuł {i:02d}")
        for i in range(20)
    ]
    for praca in prace:
        baker.make(Wydawnictwo_Ciagle_Autor, autor=autor, rekord=praca)
    for praca in prace[:3]:
        praca.delete()
    doktorat = baker.make(
        Praca_Doktorska, tytul_oryginalny="Doktorat promowany", promotor=autor
    )
    return autor, prace, doktorat


@pytest.mark.django_db
def test_strona_blokady_listuje_powiazania_z_linkami(superuser_client, autor_z_pracami):
    autor, prace, doktorat = autor_z_pracami
    resp = superuser_client.get(reverse("admin:bpp_autor_delete", args=[autor.pk]))
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")

    assert "Nie można przenieść" in tresc
    assert "Tak, przenieś do kosza" not in tresc
    assert "Autorstwa w wydawnictwach ciągłych: 20" in tresc
    assert "w tym 🗑️ 3 w koszu" in tresc
    assert "Doktoraty (promotor): 1" in tresc
    assert f'href="{_url(doktorat)}"' in tresc

    # Autorstwa linkują do publikacji-rodzica, najwyżej LIMIT na grupę,
    # najpierw te w koszu.
    linkowane = [p for p in prace if f'href="{_url(p)}"' in tresc]
    assert len(linkowane) == LIMIT_POZYCJI_BLOKADY
    assert set(prace[:3]) <= set(linkowane)
    assert f"…i jeszcze {20 - LIMIT_POZYCJI_BLOKADY}" in tresc

    # Rekordy z kosza są oznaczone — konkretna liczba zamiast ogólnika.
    assert tresc.count(ZNACZNIK_KOSZA) == 3
    assert "3 z nich są w koszu" in tresc
    assert "także tych w koszu" not in tresc


@pytest.mark.django_db
def test_grupa_blokady_jedno_zapytanie_na_relacje(
    autor_z_pracami, django_assert_num_queries
):
    autor, prace, _ = autor_z_pracami
    with django_assert_num_queries(1):
        grupa = grupa_blokady(autor, Wydawnictwo_Ciagle_Autor, "autor", limit=4)
        pozycje = [(p.obj.pk, p.w_koszu, p.tekst) for p in grupa.pozycje]
    assert grupa.liczba == 20
    assert grupa.w_koszu == 3
    assert grupa.reszta == 16
    assert len(pozycje) == 4
    assert [w_koszu for _, w_koszu, _ in pozycje] == [True, True, True, False]
    assert grupa_blokady(autor, Praca_Habilitacyjna, "autor") is None


@pytest.mark.django_db
def test_guard_rzuca_blokada_kosza_z_grupami(autor_z_pracami):
    autor, _, _ = autor_z_pracami
    with pytest.raises(BlokadaKosza) as exc:
        autor.sprawdz_czy_mozna_do_kosza()
    assert isinstance(exc.value, ProtectedError)
    assert "w tym 3 w koszu" in str(exc.value)
    etykiety = {g.etykieta: g.liczba for g in exc.value.grupy}
    assert etykiety["Autorstwa w wydawnictwach ciągłych"] == 20
    assert etykiety["Doktoraty (promotor)"] == 1


@pytest.mark.django_db
def test_strona_blokady_slownika(superuser_client, bez_celery):
    zrodlo = baker.make(Zrodlo, nazwa="Źródło używane")
    artykul = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo, tytul_oryginalny="Art")
    resp = superuser_client.get(reverse("admin:bpp_zrodlo_delete", args=[zrodlo.pk]))
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert "Artykuły w tym źródle: 1" in tresc
    assert f'href="{_url(artykul)}"' in tresc
    assert ZNACZNIK_KOSZA not in tresc


@pytest.mark.django_db
def test_strona_blokady_kolejki_pbn_linkuje_wpis(
    superuser, superuser_client, bez_celery
):
    wc = baker.make(Wydawnictwo_Ciagle)
    wpis = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wc,
        zamowil=superuser,
        operacja=PBN_Export_Queue.Operacja.WYSYLKA,
        wysylke_zakonczono=None,
    )
    tresc = superuser_client.get(
        reverse("admin:bpp_wydawnictwo_ciagle_delete", args=[wc.pk])
    ).content.decode("utf-8")
    assert "Rekordy w kolejce PBN: 1" in tresc
    assert f'href="{_url(wpis)}"' in tresc
    assert "Wysyłka — zlecono" in tresc


@pytest.mark.django_db
def test_blokada_kilku_uczelni_grupuje_autorow_per_uczelnia(bez_celery):
    wc = baker.make(Wydawnictwo_Ciagle)
    autorzy = {}
    for kolejnosc, nazwa in enumerate(("Uczelnia A", "Uczelnia B")):
        uczelnia = baker.make(Uczelnia, nazwa=nazwa)
        jednostka = baker.make(Jednostka, uczelnia=uczelnia)
        autor = baker.make(Autor, nazwisko=f"Autor {nazwa}")
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=wc,
            autor=autor,
            jednostka=jednostka,
            kolejnosc=kolejnosc,
        )
        autorzy[nazwa] = autor

    with pytest.raises(BlokadaKosza) as exc:
        wc.sprawdz_czy_mozna_do_kosza()
    grupy = {g.etykieta: [p.obj for p in g.pozycje] for g in exc.value.grupy}
    assert grupy == {
        "Autorzy z uczelni: Uczelnia A": [autorzy["Uczelnia A"]],
        "Autorzy z uczelni: Uczelnia B": [autorzy["Uczelnia B"]],
    }


@pytest.mark.django_db
def test_blokada_habilitacji_linkuje_habilitacje(bez_celery):
    wc = baker.make(Wydawnictwo_Ciagle)
    habilitacja = baker.make(Praca_Habilitacyjna)
    baker.make(Publikacja_Habilitacyjna, praca_habilitacyjna=habilitacja, publikacja=wc)
    with pytest.raises(BlokadaKosza) as exc:
        wc.sprawdz_czy_mozna_do_kosza()
    (grupa,) = exc.value.grupy
    assert grupa.liczba == 1
    assert grupa.pozycje[0].obj == habilitacja
    assert grupa.pozycje[0].url == _url(habilitacja)


@pytest.mark.django_db
def test_potwierdzenie_kosza_w_markupie_grappelli(superuser_client):
    autor = baker.make(Autor, nazwisko="Pusty")
    resp = superuser_client.get(reverse("admin:bpp_autor_delete", args=[autor.pk]))
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert 'class="module grp-module"' in tresc
    assert 'class="form-row grp-row grp-cells-1 powod"' in tresc
    assert 'name="powod"' in tresc
    assert "grp-submit-row" in tresc
    assert "Tak, przenieś do kosza" in tresc


@pytest.mark.django_db
def test_akcja_usun_do_kosza_strona_posrednia_w_markupie_grappelli(
    superuser_client,
):
    autor = baker.make(Autor, nazwisko="Pusty")
    resp = superuser_client.post(
        reverse("admin:bpp_autor_changelist"),
        {"action": "usun_do_kosza", "_selected_action": [str(autor.pk)]},
    )
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert "grp-delete-confirmation" in tresc
    assert 'class="module grp-module"' in tresc
    assert 'name="powod"' in tresc
    assert "grp-submit-row" in tresc
    assert "Pusty" in tresc


# --- przycisk „♻️ Przywróć" na stronie rekordu z kosza ---------------------


def _url_przywroc(obj):
    return reverse("admin:bpp_wydawnictwo_ciagle_przywroc", args=[obj.pk])


@pytest.mark.django_db
def test_rekord_z_kosza_ma_przycisk_przywroc(superuser_client, bez_celery):
    wc = baker.make(Wydawnictwo_Ciagle)
    tresc = superuser_client.get(_url(wc)).content.decode("utf-8")
    assert 'name="_przywroc"' not in tresc

    wc.delete()
    tresc = superuser_client.get(_url(wc)).content.decode("utf-8")
    assert 'value="♻️ Przywróć"' in tresc
    assert "przyciskiem „♻️ Przywróć” na dole strony" in tresc
    assert f'formaction="{_url_przywroc(wc)}"' in tresc


@pytest.mark.django_db
def test_przycisk_przywroc_przywraca_rekord(superuser_client, bez_celery):
    wc = baker.make(Wydawnictwo_Ciagle)
    wc.delete()
    resp = superuser_client.post(_url_przywroc(wc), follow=True)
    assert resp.redirect_chain[0][0] == _url(wc)
    assert Wydawnictwo_Ciagle.objects.filter(pk=wc.pk).exists()
    assert "Przywrócono z kosza" in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_przycisk_przywroc_tylko_post(superuser_client, bez_celery):
    wc = baker.make(Wydawnictwo_Ciagle)
    wc.delete()
    assert superuser_client.get(_url_przywroc(wc)).status_code == 405
    assert not Wydawnictwo_Ciagle.objects.filter(pk=wc.pk).exists()


@pytest.mark.django_db
def test_przycisk_przywroc_respektuje_kolejke_pbn(
    superuser, superuser_client, bez_celery
):
    from pbn_export_queue.operacje import KOMUNIKAT_REKORD_W_KOLEJCE

    wc = baker.make(Wydawnictwo_Ciagle)
    wc.delete()
    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wc,
        zamowil=superuser,
        operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
        wysylke_zakonczono=None,
    )
    resp = superuser_client.post(_url_przywroc(wc), follow=True)
    assert KOMUNIKAT_REKORD_W_KOLEJCE in resp.content.decode("utf-8")
    assert not Wydawnictwo_Ciagle.objects.filter(pk=wc.pk).exists()


@pytest.mark.django_db
def test_przycisk_przywroc_wymaga_uprawnien(client, bez_celery):
    from django.contrib.auth.models import Permission

    from bpp.models.profile import BppUser

    wc = baker.make(Wydawnictwo_Ciagle)
    wc.delete()
    user = baker.make(BppUser, is_staff=True, is_active=True)
    user.user_permissions.add(
        Permission.objects.get(codename="view_wydawnictwo_ciagle"),
        Permission.objects.get(codename="change_wydawnictwo_ciagle"),
    )
    client.force_login(user)

    tresc = client.get(_url(wc)).content.decode("utf-8")
    assert 'name="_przywroc"' not in tresc
    assert client.post(_url_przywroc(wc)).status_code == 403
    assert not Wydawnictwo_Ciagle.objects.filter(pk=wc.pk).exists()


# --- filtr „♻️ Kosz" zawsze ostatni ----------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("model", [Wydawnictwo_Ciagle, Autor, Zrodlo])
def test_filtr_kosza_jest_ostatni(model, rf, superuser):
    from django.contrib import admin

    from bpp.admin.helpers.mixins import PokazSkasowaneFilter

    model_admin = admin.site._registry[model]
    request = rf.get("/")
    request.user = superuser
    filtry = list(model_admin.get_list_filter(request))
    assert filtry[-1] is PokazSkasowaneFilter
    assert filtry.count(PokazSkasowaneFilter) == 1
    assert PokazSkasowaneFilter.title == "♻️ Kosz"


# --- „Pokaż na stronie" tylko dla żywych rekordów ---------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("model", [Wydawnictwo_Ciagle, Autor])
def test_rekord_z_kosza_bez_linku_na_strone(model, superuser_client, bez_celery):
    obj = baker.make(model)
    view_on_site = reverse(
        "admin:view_on_site",
        args=[ContentType.objects.get_for_model(model).pk, obj.pk],
    )
    assert view_on_site in superuser_client.get(_url(obj)).content.decode()

    obj.delete()
    assert view_on_site not in superuser_client.get(_url(obj)).content.decode()
