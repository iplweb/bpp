"""FD#604: akcje masowe admina zmieniające dane hurtem zostawiają ślad
w „Historii” rekordu (``LogEntry``; dla autorów także wersje reversion)."""

from unittest import mock

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import connection, transaction
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from model_bakery import baker
from reversion.models import Version

from bpp.admin import actions
from bpp.admin.autor import AutorAdmin
from bpp.models import Autor, Praca_Doktorska, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

URL_AUTORA = "/admin/bpp/autor/"

#: (model, URL changelisty) — modele z akcjami „Ustaw status korekty: …”.
PUBLIKACJE = [
    (Wydawnictwo_Ciagle, "/admin/bpp/wydawnictwo_ciagle/"),
    (Wydawnictwo_Zwarte, "/admin/bpp/wydawnictwo_zwarte/"),
    (Praca_Doktorska, "/admin/bpp/praca_doktorska/"),
]

#: akcja → (nazwa statusu, komentarz w historii)
AKCJE_STATUSU = {
    "ustaw_przed_korekta": (
        "przed korektą",
        "Ustawiono status korekty: przed korektą (akcja masowa)",
    ),
    "ustaw_po_korekcie": (
        "po korekcie",
        "Ustawiono status korekty: po korekcie (akcja masowa)",
    ),
    "ustaw_w_trakcie_korekty": (
        "w trakcie korekty",
        "Ustawiono status korekty: w trakcie korekty (akcja masowa)",
    ),
}


def _post_akcji(client, url, akcja, pks):
    return client.post(url, {"action": akcja, "_selected_action": pks, "index": 0})


def _flagi(autor):
    autor.refresh_from_db()
    return (autor.pokazuj_na_stronie_jednostki, autor.pokazuj_w_rankingu)


def _request(user):
    request = RequestFactory().get(URL_AUTORA)
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


# --- Autor: „Ukryj/Pokaż … na stronach jednostek i w rankingu” ---


@pytest.mark.django_db
@pytest.mark.parametrize(
    "akcja,przed,po,komentarz",
    [
        (
            "ustaw_pokazuj_false",
            True,
            False,
            "Ukryto na stronach jednostek i w rankingu (akcja masowa)",
        ),
        (
            "ustaw_pokazuj_true",
            False,
            True,
            "Pokazano na stronach jednostek i w rankingu (akcja masowa)",
        ),
    ],
)
def test_widocznosc_jednostki_ranking_historia_i_przywrocenie(
    admin_client, admin_user, akcja, przed, po, komentarz
):
    flagi = {"pokazuj_na_stronie_jednostki": przed, "pokazuj_w_rankingu": przed}
    autorzy = baker.make(Autor, _quantity=2, **flagi)
    bez_zmian = baker.make(
        Autor, pokazuj_na_stronie_jednostki=po, pokazuj_w_rankingu=po
    )

    res = _post_akcji(
        admin_client,
        URL_AUTORA,
        akcja,
        [a.pk for a in autorzy] + [bez_zmian.pk],
    )
    assert res.status_code == 302

    for autor in autorzy:
        assert _flagi(autor) == (po, po)
        wpis = LogEntry.objects.get(object_id=str(autor.pk))
        assert wpis.action_flag == CHANGE
        assert wpis.user == admin_user
        assert wpis.change_message == komentarz
        assert wpis.object_repr == str(autor)[:200]

        wersje = list(Version.objects.get_for_object(autor))
        assert len(wersje) == 2
        nowa, stara = wersje  # najnowsza pierwsza
        assert stara.field_dict["pokazuj_w_rankingu"] is przed
        assert nowa.field_dict["pokazuj_w_rankingu"] is po
        assert nowa.revision.comment == komentarz
        assert nowa.revision.user == admin_user

    # Rekord, w którym nic się nie zmieniło, nie dostaje wpisów.
    assert not LogEntry.objects.filter(object_id=str(bez_zmian.pk)).exists()
    assert not Version.objects.get_for_object(bez_zmian).exists()

    # Przywrócenie wersji „przed” z „Historii” cofa zmianę.
    Version.objects.get_for_object(autorzy[0]).last().revert()
    assert _flagi(autorzy[0]) == (przed, przed)


@pytest.mark.django_db
def test_widocznosc_jednostki_ranking_strona_historii_pokazuje_wpis(admin_client):
    autor = baker.make(Autor)
    _post_akcji(admin_client, URL_AUTORA, "ustaw_pokazuj_false", [autor.pk])

    res = admin_client.get(f"{URL_AUTORA}{autor.pk}/history/")
    assert "Ukryto na stronach jednostek i w rankingu (akcja masowa)" in (
        res.content.decode()
    )


@pytest.mark.django_db
def test_widocznosc_jednostki_ranking_stala_liczba_zapytan(
    admin_client, django_assert_max_num_queries
):
    tytul = baker.make("bpp.Tytul")

    def zmierz(n):
        autorzy = baker.make(Autor, tytul=tytul, _quantity=n)
        with CaptureQueriesContext(connection) as ctx:
            _post_akcji(
                admin_client, URL_AUTORA, "ustaw_pokazuj_false", [a.pk for a in autorzy]
            )
        assert LogEntry.objects.filter(
            object_id__in=[str(a.pk) for a in autorzy]
        ).count() == n
        return len(ctx.captured_queries)

    zmierz(1)  # rozgrzewka: sesja, cache ContentType itp.
    przy_2 = zmierz(2)
    assert zmierz(40) == przy_2

    autorzy = baker.make(Autor, tytul=tytul, _quantity=60)
    with django_assert_max_num_queries(przy_2):
        _post_akcji(
            admin_client, URL_AUTORA, "ustaw_pokazuj_false", [a.pk for a in autorzy]
        )


@pytest.mark.django_db
def test_widocznosc_jednostki_ranking_odmawia_powyzej_limitu(admin_user):
    autorzy = baker.make(Autor, _quantity=3)
    request = _request(admin_user)

    with mock.patch.object(actions, "MAKS_REKORDOW_AKCJI_MASOWEJ", 2):
        actions.ustaw_pokazuj_false(
            AutorAdmin(Autor, AdminSite()), request, Autor.objects.all()
        )

    for autor in autorzy:
        assert _flagi(autor) == (True, True)
    assert not LogEntry.objects.exists()
    assert not Version.objects.exists()
    (komunikat,) = list(get_messages(request))
    assert "Nic nie zostało zmienione" in str(komunikat)


@pytest.mark.django_db
@pytest.mark.parametrize("akcja", ["ustaw_pokazuj_false", "ustaw_pokazuj_true"])
def test_widocznosc_jednostki_ranking_uniewaznia_cache_raz(
    akcja, admin_user, django_capture_on_commit_callbacks
):
    widoczny = akcja == "ustaw_pokazuj_false"
    autorzy = baker.make(
        Autor,
        _quantity=3,
        pokazuj_na_stronie_jednostki=widoczny,
        pokazuj_w_rankingu=widoczny,
    )

    transaction.get_connection().run_on_commit.clear()
    with (
        mock.patch("bpp.views.cache_publiczny._wykonaj_bump") as bump,
        django_capture_on_commit_callbacks(execute=True),
    ):
        getattr(actions, akcja)(
            AutorAdmin(Autor, AdminSite()),
            _request(admin_user),
            Autor.objects.filter(pk__in=[a.pk for a in autorzy]),
        )

    assert bump.call_count == 1


@pytest.mark.django_db
def test_akcje_widocznosci_wymagaja_uprawnienia_change(django_user_model):
    user = django_user_model.objects.create_user(
        "tylko_podglad", password="x", is_staff=True
    )
    user.user_permissions.add(Permission.objects.get(codename="view_autor"))
    user = django_user_model.objects.get(pk=user.pk)
    request = _request(user)
    request.user.cached_groups = []

    dostepne = AutorAdmin(Autor, AdminSite()).get_actions(request)
    assert "ustaw_pokazuj_true" not in dostepne
    assert "ustaw_pokazuj_false" not in dostepne


# --- Publikacje: „Ustaw status korekty: …” (bez reversion — tylko LogEntry) ---


@pytest.mark.django_db
@pytest.mark.parametrize("model,url", PUBLIKACJE)
@pytest.mark.parametrize("akcja", list(AKCJE_STATUSU))
def test_status_korekty_logentry(
    admin_client, admin_user, statusy_korekt, model, url, akcja
):
    nazwa, komentarz = AKCJE_STATUSU[akcja]
    docelowy = statusy_korekt[nazwa]
    inny = next(s for n, s in statusy_korekt.items() if n != nazwa)

    rekordy = baker.make(model, _quantity=2, status_korekty=inny)
    bez_zmian = baker.make(model, status_korekty=docelowy)

    res = _post_akcji(
        admin_client, url, akcja, [r.pk for r in rekordy] + [bez_zmian.pk]
    )
    assert res.status_code == 302

    for rekord in rekordy:
        rekord.refresh_from_db()
        assert rekord.status_korekty == docelowy
        wpis = LogEntry.objects.get(
            object_id=str(rekord.pk), content_type__model=model._meta.model_name
        )
        assert wpis.action_flag == CHANGE
        assert wpis.user == admin_user
        assert wpis.change_message == komentarz
        assert wpis.object_repr == str(rekord)[:200]

    assert not LogEntry.objects.filter(
        object_id=str(bez_zmian.pk), content_type__model=model._meta.model_name
    ).exists()
    # Publikacje nie są wersjonowane — żadnych wersji.
    assert not Version.objects.exists()


@pytest.mark.django_db
def test_status_korekty_strona_historii_pokazuje_wpis(
    admin_client, przed_korekta, po_korekcie
):
    rekord = baker.make(Wydawnictwo_Ciagle, status_korekty=przed_korekta)
    url = "/admin/bpp/wydawnictwo_ciagle/"
    _post_akcji(admin_client, url, "ustaw_po_korekcie", [rekord.pk])

    res = admin_client.get(f"{url}{rekord.pk}/history/")
    assert "Ustawiono status korekty: po korekcie (akcja masowa)" in (
        res.content.decode()
    )


@pytest.mark.django_db
def test_status_korekty_stala_liczba_zapytan(
    admin_client, przed_korekta, po_korekcie, django_assert_max_num_queries
):
    url = "/admin/bpp/wydawnictwo_ciagle/"

    def zmierz(n):
        rekordy = baker.make(
            Wydawnictwo_Ciagle, status_korekty=przed_korekta, _quantity=n
        )
        with CaptureQueriesContext(connection) as ctx:
            _post_akcji(admin_client, url, "ustaw_po_korekcie", [r.pk for r in rekordy])
        assert LogEntry.objects.filter(
            object_id__in=[str(r.pk) for r in rekordy]
        ).count() == n
        return len(ctx.captured_queries)

    zmierz(1)  # rozgrzewka
    przy_2 = zmierz(2)
    assert zmierz(40) == przy_2

    rekordy = baker.make(Wydawnictwo_Ciagle, status_korekty=przed_korekta, _quantity=60)
    with django_assert_max_num_queries(przy_2):
        _post_akcji(admin_client, url, "ustaw_po_korekcie", [r.pk for r in rekordy])


@pytest.mark.django_db
def test_status_korekty_odmawia_powyzej_limitu(admin_client, przed_korekta):
    rekordy = baker.make(Wydawnictwo_Ciagle, status_korekty=przed_korekta, _quantity=3)

    with mock.patch.object(actions, "MAKS_REKORDOW_AKCJI_MASOWEJ_BEZ_WERSJI", 2):
        res = _post_akcji(
            admin_client,
            "/admin/bpp/wydawnictwo_ciagle/",
            "ustaw_po_korekcie",
            [r.pk for r in rekordy],
        )

    for rekord in rekordy:
        rekord.refresh_from_db()
        assert rekord.status_korekty == przed_korekta
    assert not LogEntry.objects.exists()
    komunikaty = [str(m) for m in get_messages(res.wsgi_request)]
    assert any("Nic nie zostało zmienione" in k for k in komunikaty)


def test_limity_akcji_masowej():
    # Autor (wersje reversion) — niski limit; publikacje (tylko LogEntry)
    # — dużo wyższy, żeby nie blokować redaktorów zmieniających status
    # korekty całego rocznika.
    assert actions.limit_akcji_masowej(Autor) == 2000
    for model, _url in PUBLIKACJE:
        assert actions.limit_akcji_masowej(model) == 20000


@pytest.mark.django_db
def test_status_korekty_powyzej_limitu_autorow_przechodzi_w_partiach(
    admin_client, przed_korekta, po_korekcie
):
    """Limit dla wersjonowanych modeli nie dotyczy publikacji; wpisy
    ``LogEntry`` powstają w partiach (tu: po 2), wszystkie trafiają do bazy."""
    rekordy = baker.make(Wydawnictwo_Ciagle, status_korekty=przed_korekta, _quantity=5)

    with (
        mock.patch.object(actions, "MAKS_REKORDOW_AKCJI_MASOWEJ", 2),
        mock.patch.object(actions, "PARTIA_LOGENTRY", 2),
    ):
        res = _post_akcji(
            admin_client,
            "/admin/bpp/wydawnictwo_ciagle/",
            "ustaw_po_korekcie",
            [r.pk for r in rekordy],
        )
    assert res.status_code == 302

    for rekord in rekordy:
        rekord.refresh_from_db()
        assert rekord.status_korekty == po_korekcie
    assert LogEntry.objects.filter(
        object_id__in=[str(r.pk) for r in rekordy],
        change_message="Ustawiono status korekty: po korekcie (akcja masowa)",
    ).count() == 5
    komunikaty = [str(m) for m in get_messages(res.wsgi_request)]
    assert komunikaty == ["Ustawiono status 'po korekcie' dla 5 rekordów"]
