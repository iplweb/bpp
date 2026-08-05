from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from liveops.testing import MockProgress
from model_bakery import baker

from import_punktacji_zrodel.models import ImportPunktacjiZrodel


@pytest.mark.django_db
def test_index_wymaga_grupy(client, django_user_model):
    user = django_user_model.objects.create_user(username="u1", password="x")
    client.force_login(user)
    resp = client.get(reverse("import_punktacji_zrodel:index"))
    assert resp.status_code in (403, 302)  # brak grupy


@pytest.mark.django_db
def test_index_dostepny_dla_grupy(client, django_user_model):
    user = django_user_model.objects.create_user(username="u2", password="x")
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    user.groups.add(grupa)
    client.force_login(user)
    resp = client.get(reverse("import_punktacji_zrodel:index"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_formularz_nowego_importu_get(client, django_user_model):
    user = django_user_model.objects.create_user(username="u3", password="x")
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    user.groups.add(grupa)
    client.force_login(user)
    resp = client.get(reverse("import_punktacji_zrodel:new"))
    assert resp.status_code == 200
    assert b"plik" in resp.content.lower()


def _user_w_grupie(django_user_model, username):
    user = django_user_model.objects.create_user(username=username, password="x")
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    user.groups.add(grupa)
    return user


@pytest.mark.django_db
def test_run_finalizuje_operacje_z_result_context(admin_user):
    """Integracja liveops: run() → core → p.result() finalizuje operację.

    Używa liveops.testing.MockProgress, żeby zweryfikować, że po przejściu
    run(): powstają wiersze importu, operacja jest oznaczona jako zakończona
    sukcesem, a result_context zawiera podsumowanie (total/do_aktualizacji/…).
    """
    from bpp.models import Zrodlo

    zrodlo = baker.make(Zrodlo, nazwa="RUN JOURNAL", issn="1234-5678")

    op = baker.make(
        ImportPunktacjiZrodel,
        owner=admin_user,
        rok=2025,
        zapisz_zmiany_do_bazy=False,
        importuj_impact_factor=True,
        importuj_kwartyl_wos=True,
        ignoruj_zrodla_bez_odpowiednika=False,
        nie_porownuj_po_tytulach=False,
    )
    # run() czyta self.plik.path; wczytaj_plik_jcr jest patchowane, więc plik
    # nie jest realnie otwierany — wystarczy nadać name, by .path nie rzucił.
    op.plik.name = "protected/import_punktacji_zrodel/dummy.xlsx"

    parsed = SimpleNamespace(
        rok=2025,
        czasopisma=[
            SimpleNamespace(
                nazwa="RUN JOURNAL",
                issn="1234-5678",
                e_issn=None,
                impact_factor=Decimal("5.5"),
                kwartyl_wos=1,
            )
        ],
    )
    with patch("import_punktacji_zrodel.core.wczytaj_plik_jcr", return_value=parsed):
        op.run(MockProgress(op))

    op.refresh_from_db()
    assert op.finished_on is not None
    assert op.finished_successfully is True
    assert op.result_context["total"] == 1
    assert op.result_context["do_aktualizacji"] == 1
    assert op.result_context["niedopasowane"] == 0
    assert op.get_details_set().count() == 1
    assert op.get_details_set().first().zrodlo == zrodlo


@pytest.mark.django_db
def test_strona_live_renderuje_host_page(admin_client, admin_user):
    """Generyczny liveops:live (op_type) renderuje host-page importu.

    Waliduje integrację z django-liveops: get_absolute_url() zawiera op_type
    (<app_label>.<model_name>), centralny widok rozwiązuje konkretny model
    jednym zapytaniem, renderuje host-template z kontenerem live-operacji
    (data-liveop-channel/token dla liveops.js), a superuser przechodzi bramkę
    REQUIRED_GROUP.
    """
    op = baker.make(ImportPunktacjiZrodel, owner=admin_user, rok=2025)
    op.plik.name = "protected/import_punktacji_zrodel/dummy.xlsx"
    op.save(update_fields=["plik"])

    url = op.get_absolute_url()
    assert url == f"/live/import_punktacji_zrodel.importpunktacjizrodel/{op.pk}/"

    response = admin_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "data-liveop-channel" in content
    assert "data-liveop-token" in content
    assert str(op.pk) in content


@pytest.mark.django_db
def test_zakonczona_operacja_pokazuje_wynik_inline(admin_client, admin_user):
    """Regresja FD#431: strona live zakończonej operacji pokazuje wynik
    inline PRZY KAŻDYM wczytaniu strony — bez zależności od jednorazowego
    push-a przez WebSocket.

    Stary long_running wysyłał sygnał zakończenia raz przez WS; gdy przepadł,
    strona wisiała ze starym statusem. liveops renderuje panel wyniku z
    result_context bezpośrednio w host-page dla stanu FINISHED_OK, więc
    odświeżenie/deep-link zawsze pokazuje prawdę.
    """
    from django.utils import timezone

    teraz = timezone.now()
    op = baker.make(
        ImportPunktacjiZrodel,
        owner=admin_user,
        rok=2025,
        started_on=teraz,
        finished_on=teraz,
        finished_successfully=True,
        result_context={
            "total": 7,
            "do_aktualizacji": 3,
            "niedopasowane": 2,
            "duplikaty": 0,
            "byl_dry_run": True,
            "rok": 2025,
        },
    )
    op.plik.name = "protected/import_punktacji_zrodel/dummy.xlsx"
    op.save(update_fields=["plik"])

    response = admin_client.get(op.get_absolute_url())
    assert response.status_code == 200
    content = response.content.decode()
    # Panel wyniku wyrenderowany inline (nie czeka na WS push):
    assert "Zobacz pełne wyniki importu" in content
    # Link prowadzi do pełnej tabeli wyników:
    results_url = reverse(
        "import_punktacji_zrodel:importpunktacjizrodel-results", args=[op.pk]
    )
    assert results_url in content


@pytest.mark.django_db
def test_zatwierdz_wlacza_zapis_i_przekierowuje_na_live(admin_client, admin_user):
    """ZatwierdzImportView: dry-run → commit. Ustawia zapisz_zmiany_do_bazy
    i deleguje do liveops RestartView (reset + re-enqueue), przekierowując na
    stronę live. run() zamockowane, by nie odpalać realnego importu."""
    imp = baker.make(
        ImportPunktacjiZrodel,
        owner=admin_user,
        rok=2025,
        zapisz_zmiany_do_bazy=False,
    )
    imp.plik.name = "protected/import_punktacji_zrodel/dummy.xlsx"
    imp.save(update_fields=["plik"])
    url = reverse("import_punktacji_zrodel:zatwierdz", args=[imp.pk])

    with patch.object(ImportPunktacjiZrodel, "run", lambda self, p: None):
        resp = admin_client.post(url)

    imp.refresh_from_db()
    assert imp.zapisz_zmiany_do_bazy is True
    assert resp.status_code == 302
    assert resp.url == imp.get_absolute_url()


@pytest.mark.django_db
def test_zatwierdz_get_zwraca_405(client, django_user_model):
    user = _user_w_grupie(django_user_model, "u4")
    client.force_login(user)
    imp = baker.make(ImportPunktacjiZrodel, owner=user)
    url = reverse("import_punktacji_zrodel:zatwierdz", args=[imp.pk])
    resp = client.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_zatwierdz_wymaga_grupy(client, django_user_model):
    user = django_user_model.objects.create_user(username="u5", password="x")
    client.force_login(user)
    imp = baker.make(ImportPunktacjiZrodel, owner=user)
    url = reverse("import_punktacji_zrodel:zatwierdz", args=[imp.pk])
    resp = client.post(url)
    assert resp.status_code in (403, 302)
