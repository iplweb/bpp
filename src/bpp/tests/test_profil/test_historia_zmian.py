"""Historia zmian autora (django-reversion) — także edycji profilu przez stronę.

Samodzielna edycja profilu (biogram, zdjęcie, profile zewnętrzne, wyróżnione
prace) musi zostawiać w adminie ten sam ślad co edycja w adminie: kto, kiedy
i co zmienił — oraz pozwalać wrócić do poprzedniej wersji.
"""

import json

import pytest
import reversion
from django.contrib import admin as djadmin
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.urls import reverse
from model_bakery import baker
from reversion import is_registered
from reversion.models import Version
from reversion.revisions import _get_options

from bpp.admin.autor import AutorAdmin
from bpp.models import Autor, Autor_Jednostka, Rekord, Uczelnia
from bpp.models.wybrana_publikacja import WybranaPublikacjaAutora
from bpp.wersjonowanie import KOMENTARZ_WERSJI_POCZATKOWEJ

pytestmark = pytest.mark.django_db


def _zaloguj_jako_autora(client, django_user_model, autor, username="hist-user"):
    user = django_user_model.objects.create_user(username=username, password="x")
    user.autor = autor
    user.save(update_fields=["autor"])
    client.force_login(user)
    return user


def _wersje(autor):
    return list(Version.objects.get_for_object(autor).order_by("pk"))


def test_rejestracja_autora_w_reversion():
    assert is_registered(Autor)
    opcje = _get_options(Autor)
    assert "search" not in opcje.fields
    assert "biogram" in opcje.fields
    # Zatrudnienie/dyscypliny/absencje NIE są przywracane razem z autorem
    # (cudze uczelnie, ewaluacja); dane wyliczane też nie.
    assert opcje.follow == ("wybrane_publikacje",)


def test_edycja_profilu_przez_strone_tworzy_wersje_i_logentry(
    client, django_user_model
):
    autor = baker.make(Autor, biogram="Stary biogram")
    user = _zaloguj_jako_autora(client, django_user_model, autor)

    resp = client.post(
        reverse("bpp:profil-edycja"),
        {"biogram": "Nowy biogram", "biogram_format": "md"},
    )
    assert resp.status_code == 302

    poczatkowa, po_zmianie = _wersje(autor)
    assert poczatkowa.revision.user is None
    assert poczatkowa.revision.comment == KOMENTARZ_WERSJI_POCZATKOWEJ
    assert poczatkowa.field_dict["biogram"] == "Stary biogram"

    assert po_zmianie.revision.user == user
    assert "Samodzielna edycja profilu" in po_zmianie.revision.comment
    assert "Biogram" in po_zmianie.revision.comment
    assert po_zmianie.field_dict["biogram"] == "Nowy biogram"

    wpis = LogEntry.objects.get(
        content_type=ContentType.objects.get_for_model(Autor),
        object_id=str(autor.pk),
    )
    assert wpis.user == user
    assert wpis.action_flag == CHANGE
    assert "Biogram" in wpis.get_change_message()


def test_druga_edycja_nie_dubluje_wersji_poczatkowej(client, django_user_model):
    autor = baker.make(Autor, biogram="v1")
    _zaloguj_jako_autora(client, django_user_model, autor)
    url = reverse("bpp:profil-edycja")
    client.post(url, {"biogram": "v2", "biogram_format": "md"})
    client.post(url, {"biogram": "v3", "biogram_format": "md"})
    assert [w.field_dict["biogram"] for w in _wersje(autor)] == ["v1", "v2", "v3"]


def test_zapis_bez_zmian_nie_tworzy_wersji(client, django_user_model):
    autor = baker.make(Autor, biogram="Bez zmian", biogram_format="md")
    _zaloguj_jako_autora(client, django_user_model, autor)
    resp = client.post(
        reverse("bpp:profil-edycja"),
        {"biogram": "Bez zmian", "biogram_format": "md"},
    )
    assert resp.status_code == 302
    assert _wersje(autor) == []


def test_przywrocenie_wersji_sprzed_edycji_przez_strone(client, django_user_model):
    autor = baker.make(Autor, biogram="Oryginał")
    _zaloguj_jako_autora(client, django_user_model, autor)
    client.post(
        reverse("bpp:profil-edycja"),
        {"biogram": "Zepsute", "biogram_format": "md"},
    )

    _wersje(autor)[0].revision.revert()

    autor.refresh_from_db()
    assert autor.biogram == "Oryginał"
    # ``search`` nie jest w wersji — trigger musi go przeliczyć, nie wyzerować.
    assert Autor.objects.filter(pk=autor.pk, search__isnull=False).exists()


def test_historia_w_adminie_pokazuje_edycje_ze_strony(
    client, admin_client, django_user_model
):
    autor = baker.make(Autor, biogram="a")
    _zaloguj_jako_autora(client, django_user_model, autor, username="jan-hist")
    client.post(reverse("bpp:profil-edycja"), {"biogram": "b", "biogram_format": "md"})

    resp = admin_client.get(reverse("admin:bpp_autor_history", args=[autor.pk]))
    assert resp.status_code == 200
    tresc = resp.content.decode()
    assert "jan-hist" in tresc
    assert "Samodzielna edycja profilu" in tresc

    wersja = _wersje(autor)[0]
    resp = admin_client.get(
        reverse("admin:bpp_autor_revision", args=[autor.pk, wersja.pk])
    )
    assert resp.status_code == 200


def test_historia_w_adminie_pokazuje_logentry_sprzed_wersjonowania(
    admin_client, admin_user
):
    autor = baker.make(Autor)
    LogEntry.objects.log_actions(
        admin_user.pk,
        [autor],
        ADDITION,
        change_message="Dodano dawno temu",
        single_object=True,
    )
    resp = admin_client.get(reverse("admin:bpp_autor_history", args=[autor.pk]))
    assert resp.status_code == 200
    tresc = resp.content.decode()
    assert "Wcześniejsza historia" in tresc
    assert "Dodano dawno temu" in tresc


def _dane_formularza_admina(response):
    """Dane POST odtworzone z formularza autora w adminie (bez inline'ów)."""
    form = response.context["adminform"].form
    dane = {}
    for nazwa, pole in form.fields.items():
        wartosc = form.initial.get(nazwa, pole.initial)
        if wartosc is None or nazwa == "zdjecie":
            continue
        dane[nazwa] = wartosc
    for prefix in (
        "autor_jednostka_set",
        "autor_dyscyplina_set",
        "autor_absencja_set",
        "iloscudzialowdlaautorazarok_set",
        "wybrane_publikacje",
    ):
        dane[f"{prefix}-TOTAL_FORMS"] = "0"
        dane[f"{prefix}-INITIAL_FORMS"] = "0"
    return dane


def test_edycja_w_adminie_tworzy_wersje_poczatkowa_i_wersje(admin_client, admin_user):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Przedzmianowy")
    url = reverse("admin:bpp_autor_change", args=[autor.pk])
    dane = _dane_formularza_admina(admin_client.get(url))
    dane["nazwisko"] = "Pozmianowy"
    resp = admin_client.post(url, dane)
    assert resp.status_code == 302, resp.context["adminform"].form.errors

    poczatkowa, po_zmianie = _wersje(autor)
    assert poczatkowa.field_dict["nazwisko"] == "Przedzmianowy"
    assert po_zmianie.field_dict["nazwisko"] == "Pozmianowy"
    assert po_zmianie.revision.user == admin_user


def test_przywrocenie_w_adminie_przelicza_aktualna_jednostke(
    client, admin_client, django_user_model, jednostka
):
    autor = baker.make(Autor, biogram="Przed")
    assert autor.aktualna_jednostka is None
    _zaloguj_jako_autora(client, django_user_model, autor)
    client.post(reverse("bpp:profil-edycja"), {"biogram": "Po", "biogram_format": "md"})
    poczatkowa = _wersje(autor)[0]

    # Autor dostaje zatrudnienie PO zapisaniu wersji początkowej.
    baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
    autor.refresh_from_db()
    assert autor.aktualna_jednostka == jednostka

    url = reverse("admin:bpp_autor_revision", args=[autor.pk, poczatkowa.pk])
    resp = admin_client.post(url, _dane_formularza_admina(admin_client.get(url)))
    assert resp.status_code == 302

    autor.refresh_from_db()
    assert autor.biogram == "Przed"
    # Wersja niosła aktualna_jednostka=None; zatrudnienie nie jest cofane,
    # więc aktualna jednostka musi zostać przeliczona z bieżących wpisów.
    assert autor.aktualna_jednostka == jednostka


def test_wersja_innego_modelu_w_url_autora_to_404(admin_client):
    autor = baker.make(Autor)
    uczelnia = baker.make(Uczelnia)
    with reversion.create_revision():
        reversion.add_to_revision(uczelnia)
    wersja_uczelni = Version.objects.get_for_object(uczelnia).get()
    # Ten sam object_id co autor — reversion sam typu modelu nie sprawdza.
    wersja_uczelni.object_id = str(autor.pk)
    wersja_uczelni.save()

    resp = admin_client.get(
        reverse("admin:bpp_autor_revision", args=[autor.pk, wersja_uczelni.pk])
    )
    assert resp.status_code == 404


def _wiersz_wyroznienia(autor, wydawnictwo, jednostka, denorms):
    wydawnictwo.dodaj_autora(autor, jednostka)
    denorms.flush()
    rekord = Rekord.objects.prace_autora(autor).first()
    return rekord, f"{rekord.content_type.id}-{rekord.object_id}"


def test_wyroznienie_i_usuniecie_pracy_trafia_do_historii(
    client,
    django_user_model,
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    _, ident = _wiersz_wyroznienia(
        autor_jan_nowak, wydawnictwo_zwarte, jednostka, denorms
    )
    user = _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    url = reverse("bpp:profil-wybrane-publikacje-akcja")

    resp = client.post(url, {"akcja": "dodaj", "rekord": ident})
    pk = json.loads(resp.content)["pk"]
    resp = client.post(url, {"akcja": "usun", "pk": pk})
    assert json.loads(resp.content)["ok"] is True

    poczatkowa, dodanie, usuniecie = _wersje(autor_jan_nowak)
    assert poczatkowa.revision.comment == KOMENTARZ_WERSJI_POCZATKOWEJ
    assert dodanie.revision.user == user
    assert "wyróżniono pracę" in dodanie.revision.comment
    assert wydawnictwo_zwarte.tytul_oryginalny in dodanie.revision.comment
    assert dodanie.revision.version_set.filter(
        content_type=ContentType.objects.get_for_model(WybranaPublikacjaAutora)
    ).exists()
    assert "usunięto wyróżnienie" in usuniecie.revision.comment

    # Cofnięcie do wersji po dodaniu przywraca usunięte wyróżnienie.
    dodanie.revision.revert(delete=True)
    assert autor_jan_nowak.wybrane_publikacje.filter(pk=pk).exists()


def test_przesun_bez_zmiany_kolejnosci_nie_tworzy_wersji(
    client, django_user_model, transactional_db, standard_data, autor_jan_nowak
):
    _zaloguj_jako_autora(client, django_user_model, autor_jan_nowak)
    resp = client.post(
        reverse("bpp:profil-wybrane-publikacje-akcja"),
        {"akcja": "przesun", "kolejnosc": []},
    )
    assert json.loads(resp.content)["ok"] is True
    assert _wersje(autor_jan_nowak) == []


def test_podglad_wersji_poza_zakresem_uczelni_to_404(rf, admin_user, monkeypatch):
    autor = baker.make(Autor)
    aa = AutorAdmin(Autor, djadmin.site)
    monkeypatch.setattr(aa, "get_object", lambda request, object_id: None)
    request = rf.post("/")
    request.user = admin_user
    with pytest.raises(Http404):
        aa.revision_view(request, str(autor.pk), "1")


def test_odzyskiwanie_usunietych_tylko_dla_superusera(rf, django_user_model):
    staff = django_user_model.objects.create_user(
        username="staff-hist", password="x", is_staff=True
    )
    aa = AutorAdmin(Autor, djadmin.site)
    request = rf.get("/")
    request.user = staff
    with pytest.raises(PermissionDenied):
        aa.recoverlist_view(request)
    with pytest.raises(PermissionDenied):
        aa.recover_view(request, "1")
