"""Regresje z finalnych recenzji (runda 5: Codex, GLM, Fable).

Część przypadków to przerobione testy-reprodukcje Fable'a.
"""

from contextlib import contextmanager
from unittest import mock

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Jednostka,
    Uczelnia,
    Wydawca,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from pbn_export_queue.models import (
    PBN_Export_Queue,
    SendStatus,
    WpisWTrakcieWysylki,
    WycofanieZablokowane,
)

pytestmark = pytest.mark.django_db


# -- 1. Jednostki nie kasuje się wcale ----------------------------------


def test_jednostki_nie_da_sie_usunac(uczelnia):
    from bpp.models.jednostka import JednostkaNieDoUsuniecia

    jednostka = baker.make(Jednostka, uczelnia=uczelnia)

    with pytest.raises(JednostkaNieDoUsuniecia):
        jednostka.delete()
    with pytest.raises(JednostkaNieDoUsuniecia):
        Jednostka.objects.filter(pk=jednostka.pk).delete()
    assert Jednostka.objects.filter(pk=jednostka.pk).exists()


def test_admin_jednostki_bez_usuwania(admin_client, uczelnia):
    jednostka = baker.make(Jednostka, uczelnia=uczelnia)

    res = admin_client.post(
        reverse("admin:bpp_jednostka_delete", args=[jednostka.pk]), {"post": "yes"}
    )

    assert res.status_code == 403
    assert Jednostka.objects.filter(pk=jednostka.pk).exists()


def test_drzewo_jednostek_przebudowuje_sie(uczelnia):
    """Fable #1: zamrożona (skasowana) jednostka w drzewie MPTT blokowała
    przeliczanie ``lft``/``rght`` sąsiadów. Bez kosza jednostek drzewo
    przebudowuje się bez przeszkód."""
    root = baker.make(Jednostka, nazwa="Root", skrot="R", uczelnia=uczelnia)
    a = baker.make(Jednostka, nazwa="A", skrot="A", uczelnia=uczelnia, parent=root)
    c = baker.make(Jednostka, nazwa="C", skrot="C", uczelnia=uczelnia, parent=a)
    c.refresh_from_db()
    c.parent = root
    c.save()
    Jednostka._tree_manager.rebuild()


# -- 2. Import nie wywraca się na unikalnej wartości z kosza -----------


def test_import_wydawcy_pomija_nazwe_z_kosza():
    from pbn_api.models import Publisher
    from pbn_integrator.importer.publishers import _utworz_nowego_wydawce
    from pbn_integrator.models import RekordWKoszuPominietyPrzezImport

    w_koszu = baker.make(Wydawca, nazwa="Springer")
    w_koszu.delete()
    publisher = baker.make(
        Publisher,
        publisherName="Springer",
        versions=[
            {"current": True, "object": {"publisherName": "Springer", "points": {}}}
        ],
    )

    _utworz_nowego_wydawce(publisher, {}, 0)

    assert Wydawca.global_objects.filter(nazwa="Springer").count() == 1
    assert Wydawca.deleted_objects.filter(pk=w_koszu.pk).exists()
    assert RekordWKoszuPominietyPrzezImport.objects.filter(
        object_id=w_koszu.pk
    ).exists()


def test_import_autora_pomija_orcid_z_kosza():
    from pbn_api.models import Scientist
    from pbn_integrator.utils import utworz_wpis_dla_jednego_autora

    orcid = "0000-0002-1825-0097"
    naukowiec = baker.make(
        Scientist,
        versions=[
            {
                "current": True,
                "object": {"name": "Jan", "lastName": "Kowalsky", "orcid": orcid},
            }
        ],
    )
    w_koszu = baker.make(Autor, nazwisko="Kowalski", imiona="Jan", orcid=orcid)
    w_koszu.delete()

    assert utworz_wpis_dla_jednego_autora(naukowiec) is None
    assert Autor.global_objects.filter(orcid=orcid).count() == 1


# -- 3. „Usuń istniejące publikacje PBN" z rozdziałami ------------------


def test_usuwanie_publikacji_pbn_odpina_rozdzialy(wydawnictwo_zwarte):
    from pbn_api.models import Publication
    from pbn_import.utils.publication_import import PublicationImporter

    wydawnictwo_zwarte.pbn_uid = baker.make(Publication)
    wydawnictwo_zwarte.save()
    rozdzial = baker.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wydawnictwo_zwarte,
        pbn_uid=baker.make(Publication),
    )
    rozdzial_bez_pbn = baker.make(
        Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=wydawnictwo_zwarte
    )
    rozdzial_bez_pbn.delete()  # rozdział z kosza też trzeba odpiąć

    importer = PublicationImporter.__new__(PublicationImporter)
    importer.check_cancelled = lambda: False
    importer.update_progress = mock.Mock()
    importer.log = mock.Mock()

    importer._delete_existing_publications(0, 1)

    assert not Wydawnictwo_Zwarte.global_objects.filter(
        pk__in=[wydawnictwo_zwarte.pk, rozdzial.pk]
    ).exists()
    zostal = Wydawnictwo_Zwarte.global_objects.get(pk=rozdzial_bez_pbn.pk)
    assert zostal.wydawnictwo_nadrzedne_id is None
    assert zostal.deleted_at is not None


# -- 4. Autor z kosza nie trafia do raportów ewaluacji ------------------


@pytest.fixture
def autor_w_koszu(dyscyplina1, dyscyplina2):
    autor = baker.make(Autor, nazwisko="Koszowski", imiona="Tajny")
    Autor_Dyscyplina.objects.create(
        autor=autor,
        dyscyplina_naukowa=dyscyplina1,
        rok=2023,
        procent_dyscypliny=50,
        subdyscyplina_naukowa=dyscyplina2,
        procent_subdyscypliny=50,
    )
    autor.delete()
    return autor


def test_raport_zerowy_bez_autora_z_kosza(autor_w_koszu):
    from raport_slotow.core import autorzy_z_dyscyplinami, autorzy_zerowi

    assert autor_w_koszu.pk not in {
        wiersz["autor_id"] for wiersz in autorzy_z_dyscyplinami(2022, 2025)
    }
    assert autor_w_koszu.pk not in {
        wiersz[0] if isinstance(wiersz, tuple) else wiersz["autor_id"]
        for wiersz in autorzy_zerowi(od_roku=2022, do_roku=2025)
    }


def test_dwudyscyplinowcy_bez_autora_z_kosza(autor_w_koszu):
    from ewaluacja_dwudyscyplinowcy.core import pobierz_autorow_z_dwiema_dyscyplinami

    assert autor_w_koszu.pk not in pobierz_autorow_z_dwiema_dyscyplinami(lata=[2023])
    # Dane kadrowe zostają przy autorze w koszu (wrócą z nim).
    assert Autor_Dyscyplina.all_objects.filter(autor=autor_w_koszu).exists()


# -- 6. Sprzątaczka kolejki zachowuje historię rekordów z kosza ---------


def test_sprzataczka_zachowuje_historie_rekordu_z_kosza(admin_user):
    from pbn_export_queue.tasks import kolejka_wyczysc_wpisy_bez_rekordow

    rekord = baker.make(Wydawnictwo_Ciagle)
    historia = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=rekord,
        zamowil=admin_user,
        wysylke_zakonczono="2026-01-01T00:00:00Z",
        zakonczono_pomyslnie=True,
    )
    rekord.delete()
    sierota = baker.make(
        PBN_Export_Queue,
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        object_id=999_999_999,
        zamowil=admin_user,
    )

    kolejka_wyczysc_wpisy_bez_rekordow()

    assert PBN_Export_Queue.objects.filter(pk=historia.pk).exists()
    assert not PBN_Export_Queue.objects.filter(pk=sierota.pk).exists()


# -- 8. Ręczne operacje na kolejce ---------------------------------------


def _wycofanie(rekord, user, **kw):
    return baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=rekord,
        zamowil=user,
        operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
        **kw,
    )


def test_zakonczonego_wycofania_nie_da_sie_usunac(admin_user):
    rekord = baker.make(Wydawnictwo_Ciagle)
    wpis = _wycofanie(rekord, admin_user, wysylke_zakonczono="2026-01-01T00:00:00Z")

    with pytest.raises(WycofanieZablokowane):
        wpis.delete()


def test_try_send_odmawia_dla_wycofania(admin_client, admin_user):
    rekord = baker.make(Wydawnictwo_Ciagle)
    wpis = _wycofanie(rekord, admin_user)

    with mock.patch.object(PBN_Export_Queue, "sprobuj_wyslac_do_pbn") as wyslij:
        admin_client.post(
            reverse("pbn_export_queue:export-queue-try-send", args=[wpis.pk])
        )

    wyslij.assert_not_called()


@contextmanager
def _worker_trzyma_blokade(rekord):
    """Sesyjna blokada workera na rekordzie, z OSOBNEGO połączenia."""
    import psycopg2
    from django.db import connection

    from pbn_export_queue.models import klucz_blokady_rekordu

    ustawienia = connection.settings_dict
    inne = psycopg2.connect(
        dbname=ustawienia["NAME"],
        user=ustawienia["USER"],
        password=ustawienia["PASSWORD"],
        host=ustawienia["HOST"],
        port=ustawienia["PORT"],
    )
    klucz = klucz_blokady_rekordu(
        ContentType.objects.get_for_model(rekord).pk, rekord.pk
    )
    try:
        with inne.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", [klucz])
            assert cur.fetchone()[0]
        yield
        # Release the lock explicitly instead of relying on ``close()``:
        # closing only sends a Terminate message, and the server backend
        # drops its session locks asynchronously while exiting. The test's
        # next ``pg_try_advisory_xact_lock`` could still see the lock held
        # (flaky ``WpisWTrakcieWysylki``). ``pg_advisory_unlock`` returns
        # only after the lock is gone.
        with inne.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", [klucz])
            assert cur.fetchone()[0]
    finally:
        inne.close()


def test_wpisu_wysylanego_przez_workera_nie_da_sie_usunac(admin_user):
    rekord = baker.make(Wydawnictwo_Ciagle)
    wpis = baker.make(PBN_Export_Queue, rekord_do_wysylki=rekord, zamowil=admin_user)

    with _worker_trzyma_blokade(rekord):
        with pytest.raises(WpisWTrakcieWysylki):
            wpis.delete()
    wpis.delete()


# -- 9. Wycofanie nigdy nie kończy się błędem ----------------------------


@pytest.mark.parametrize(
    "blad",
    ["token", "http"],
)
def test_wycofanie_czeka_zamiast_konczyc_sie_bledem(admin_user, blad):
    from pbn_api.exceptions import HttpException, WillNotExportError

    rekord = baker.make(Wydawnictwo_Ciagle)
    wpis = _wycofanie(rekord, admin_user)
    wyjatek = {
        "token": WillNotExportError("konto bez tokenu PBN"),
        "http": HttpException(500, "/x", "PBN padł"),
    }[blad]

    with mock.patch.object(
        PBN_Export_Queue, "_pozyskaj_klienta_pbn", side_effect=wyjatek
    ):
        status = wpis.withdraw_from_pbn()

    wpis.refresh_from_db()
    assert wpis.wysylke_zakonczono is None
    if blad == "token":
        assert status == SendStatus.RETRY_AFTER_USER_AUTHORISED
        assert wpis.retry_after_user_authorised
    else:
        assert status == SendStatus.RETRY_LATER


def test_wycofanie_publikacji_nieznanej_w_pbn_to_sukces():
    from pbn_api.exceptions import HttpException
    from pbn_api.models import Publication
    from pbn_api.wycofanie import StatusWycofania, wycofaj_oswiadczenia

    rekord = baker.make(Wydawnictwo_Ciagle, pbn_uid=baker.make(Publication))
    klient = mock.Mock()
    klient.delete_all_publication_statements.side_effect = HttpException(
        404, "/x", "nie ma"
    )

    assert wycofaj_oswiadczenia(rekord, klient).status == (
        StatusWycofania.BRAK_OSWIADCZEN
    )


# -- 10. Drobne poprawki ---------------------------------------------------


def test_publikacja_wskazana_w_habilitacji_nie_idzie_do_kosza():
    from django.db.models import ProtectedError

    from bpp.models import Praca_Habilitacyjna
    from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna

    publikacja = baker.make(Wydawnictwo_Ciagle)
    baker.make(
        Publikacja_Habilitacyjna,
        praca_habilitacyjna=baker.make(Praca_Habilitacyjna),
        publikacja=publikacja,
    )

    with pytest.raises(ProtectedError):
        publikacja.delete()


def test_scalanie_nie_nadpisuje_pracy_z_kosza(admin_user):
    from bpp.models import Praca_Doktorska
    from deduplikator_autorow.utils.merge import _transfer_simple_authorship

    glowny = baker.make(Autor)
    duplikat = baker.make(Autor)
    praca = baker.make(Praca_Doktorska, autor=duplikat, tytul_oryginalny="Stary")
    praca.delete()
    nieaktualna = Praca_Doktorska.global_objects.get(pk=praca.pk)
    nieaktualna.tytul_oryginalny = "Zmieniony w pamięci"

    with mock.patch(
        "deduplikator_autorow.utils.merge.wiersze_do_transferu",
        return_value=[nieaktualna],
    ):
        wyniki = {"updated_records": [], "total_updated": 0}
        _transfer_simple_authorship(
            Praca_Doktorska,
            "Praca doktorska",
            glowny,
            duplikat,
            admin_user,
            True,
            wyniki,
        )

    w_bazie = Praca_Doktorska.global_objects.get(pk=praca.pk)
    assert w_bazie.autor_id == glowny.pk
    assert w_bazie.deleted_at is not None
    assert w_bazie.tytul_oryginalny == "Stary"


def test_autocomplete_admina_nie_podsuwa_kosza(admin_client):
    autor = baker.make(Autor, nazwisko="Koszowski", imiona="Tajny")
    autor.delete()

    res = admin_client.get(
        "/admin/autocomplete/",
        {
            "app_label": "bpp",
            "model_name": "projekt_autor",
            "field_name": "autor",
            "term": "Koszowski",
        },
    )

    assert res.status_code == 200
    assert b"Koszowski" not in res.content


def test_global_nav_410_dla_rekordu_z_kosza(client):
    """Bez przekierowania (zdradziłoby slug) — od razu 410, jak strona
    publiczna rekordu z kosza (``bpp.rekord_usuniety``)."""
    autor = baker.make(Autor, nazwisko="Koszowski", imiona="Tajny")
    autor.delete()
    ct = ContentType.objects.get_for_model(Autor)

    res = client.get(f"/global-nav-redir/{ct.pk}-{autor.pk}/")

    assert res.status_code == 410
    assert b"Koszowski" not in res.content
    assert autor.slug.encode() not in res.content


def test_wersja_uczelni_bez_pol_kosza(uczelnia):
    import reversion
    from reversion.models import Version

    with reversion.create_revision():
        uczelnia.save()

    pola = Version.objects.get_for_object(uczelnia).first().field_dict
    for nazwa in ("deleted_at", "restored_at", "transaction_id"):
        assert nazwa not in pola
    assert isinstance(uczelnia, Uczelnia)


def test_pusty_napis_podlega_unikalnosci_z_koszem():
    """Jak Django na PostgreSQL: unikalność omija tylko NULL, nie ``""``."""
    from django.core.exceptions import ValidationError

    w_koszu = baker.make(Wydawca, nazwa="")
    w_koszu.delete()

    with pytest.raises(ValidationError):
        Wydawca(nazwa="").validate_unique()
