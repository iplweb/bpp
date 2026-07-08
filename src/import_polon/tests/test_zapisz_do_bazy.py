"""Testy akcji "uruchom ponownie z zapisem do bazy" dla importów POLON i
absencji. Dry-run (``zapisz_zmiany_do_bazy=False``) można domknąć zapisem do
bazy: przestawić flagę na ``True`` i zresetować obiekt do ponownego uruchomienia.
"""

import pytest
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.system import User
from import_polon.models import (
    ImportPlikuAbsencji,
    ImportPlikuPolon,
    WierszImportuPlikuPolon,
)


def _reimport_scheduled(callbacks):
    """Ile spośród callbacków ``on_commit`` to nasze ponowne uruchomienie importu.

    Middleware audytu (django-easy-audit) rejestruje własne callbacki, więc nie
    można liczyć wszystkich — filtrujemy po tym, który pochodzi z
    ``LongRunningTaskCallerMixin.task_on_commit``.
    """
    return sum("task_on_commit" in cb.__qualname__ for cb in callbacks)


def _finished_dry_run(model, owner, **extra):
    """Zakończony pomyślnie dry-run (bez zapisu do bazy)."""
    return baker.make(
        model,
        owner=owner,
        zapisz_zmiany_do_bazy=False,
        started_on=timezone.now(),
        finished_on=timezone.now(),
        finished_successfully=True,
        **extra,
    )


@pytest.mark.django_db
def test_zapisz_do_bazy_polon_get_renders_confirmation(admin_client, admin_user):
    imp = _finished_dry_run(ImportPlikuPolon, admin_user, rok=2023)
    url = reverse("import_polon:importplikupolon-zapisz-do-bazy", args=[imp.pk])

    response = admin_client.get(url)

    assert response.status_code == 200
    assert "import_polon/potwierdz_zapis_do_bazy.html" in [
        t.name for t in response.templates
    ]


@pytest.mark.django_db
def test_zapisz_do_bazy_polon_post_flips_flag_and_resets(
    admin_client, admin_user, django_capture_on_commit_callbacks
):
    imp = _finished_dry_run(ImportPlikuPolon, admin_user, rok=2023)
    url = reverse("import_polon:importplikupolon-zapisz-do-bazy", args=[imp.pk])

    with django_capture_on_commit_callbacks() as callbacks:
        response = admin_client.post(url)

    assert response.status_code == 302
    imp.refresh_from_db()
    assert imp.zapisz_zmiany_do_bazy is True
    assert imp.started_on is None
    assert imp.finished_on is None
    assert imp.finished_successfully is False
    # Ponowne uruchomienie importu zostało zakolejkowane.
    assert _reimport_scheduled(callbacks) == 1


@pytest.mark.django_db
def test_zapisz_do_bazy_polon_guard_already_committed(
    admin_client, admin_user, django_capture_on_commit_callbacks
):
    # Import już zapisany do bazy — ponowny zapis nie może się wykonać.
    imp = baker.make(
        ImportPlikuPolon,
        owner=admin_user,
        zapisz_zmiany_do_bazy=True,
        started_on=timezone.now(),
        finished_on=timezone.now(),
        finished_successfully=True,
        rok=2023,
    )
    url = reverse("import_polon:importplikupolon-zapisz-do-bazy", args=[imp.pk])

    with django_capture_on_commit_callbacks() as callbacks:
        response = admin_client.post(url)

    assert response.status_code == 302
    imp.refresh_from_db()
    # Stan bez zmian — nie zresetowano, nie zakolejkowano ponownego uruchomienia.
    assert imp.finished_on is not None
    assert imp.finished_successfully is True
    assert _reimport_scheduled(callbacks) == 0


@pytest.mark.django_db
def test_zapisz_do_bazy_polon_other_user_404(admin_client):
    other = baker.make(User)
    imp = _finished_dry_run(ImportPlikuPolon, other, rok=2023)
    url = reverse("import_polon:importplikupolon-zapisz-do-bazy", args=[imp.pk])

    assert admin_client.get(url).status_code == 404
    assert admin_client.post(url).status_code == 404


@pytest.mark.django_db
def test_zapisz_do_bazy_polon_guard_errored_dry_run(
    admin_client, admin_user, django_capture_on_commit_callbacks
):
    # Dry-run zakończony BŁĘDEM: użytkownik nigdy nie zobaczył podglądu, więc
    # bezpośredni POST (stara karta / ręcznie wpisany URL) nie może odpalić
    # zapisu do bazy.
    imp = baker.make(
        ImportPlikuPolon,
        owner=admin_user,
        zapisz_zmiany_do_bazy=False,
        started_on=timezone.now(),
        finished_on=timezone.now(),
        finished_successfully=False,
        rok=2023,
    )
    url = reverse("import_polon:importplikupolon-zapisz-do-bazy", args=[imp.pk])

    with django_capture_on_commit_callbacks() as callbacks:
        response = admin_client.post(url)

    assert response.status_code == 302
    imp.refresh_from_db()
    assert imp.zapisz_zmiany_do_bazy is False
    assert _reimport_scheduled(callbacks) == 0


@pytest.mark.django_db
def test_zapisz_do_bazy_polon_guard_in_progress(
    admin_client, admin_user, django_capture_on_commit_callbacks
):
    # Import w trakcie (started, jeszcze nie finished) — nie wolno resetować.
    imp = baker.make(
        ImportPlikuPolon,
        owner=admin_user,
        zapisz_zmiany_do_bazy=False,
        started_on=timezone.now(),
        finished_on=None,
        finished_successfully=False,
        rok=2023,
    )
    url = reverse("import_polon:importplikupolon-zapisz-do-bazy", args=[imp.pk])

    with django_capture_on_commit_callbacks() as callbacks:
        response = admin_client.post(url)

    assert response.status_code == 302
    imp.refresh_from_db()
    assert imp.zapisz_zmiany_do_bazy is False
    assert imp.started_on is not None
    assert _reimport_scheduled(callbacks) == 0


@pytest.mark.django_db
def test_zapisz_do_bazy_polon_post_deletes_child_rows(
    admin_client, admin_user, django_capture_on_commit_callbacks
):
    # Reset musi skasować wiersze-dzieci poprzedniego (dry-run) przebiegu —
    # sedno ochrony przed duplikatami przy ponownym uruchomieniu.
    imp = _finished_dry_run(ImportPlikuPolon, admin_user, rok=2023)
    baker.make(WierszImportuPlikuPolon, parent=imp, nr_wiersza=1)
    baker.make(WierszImportuPlikuPolon, parent=imp, nr_wiersza=2)
    assert imp.wierszimportuplikupolon_set.count() == 2
    url = reverse("import_polon:importplikupolon-zapisz-do-bazy", args=[imp.pk])

    with django_capture_on_commit_callbacks():
        admin_client.post(url)

    assert imp.wierszimportuplikupolon_set.count() == 0


@pytest.mark.django_db
def test_zapisz_do_bazy_absencji_post_flips_flag_and_resets(
    admin_client, admin_user, django_capture_on_commit_callbacks
):
    imp = _finished_dry_run(ImportPlikuAbsencji, admin_user)
    url = reverse("import_polon:importplikuabsencji-zapisz-do-bazy", args=[imp.pk])

    with django_capture_on_commit_callbacks() as callbacks:
        response = admin_client.post(url)

    assert response.status_code == 302
    imp.refresh_from_db()
    assert imp.zapisz_zmiany_do_bazy is True
    assert imp.started_on is None
    assert imp.finished_on is None
    assert _reimport_scheduled(callbacks) == 1


@pytest.mark.django_db
def test_results_page_shows_button_for_dry_run(admin_client, admin_user):
    imp = _finished_dry_run(ImportPlikuPolon, admin_user, rok=2023)
    results_url = reverse("import_polon:importplikupolon-results", args=[imp.pk])
    zapisz_url = reverse("import_polon:importplikupolon-zapisz-do-bazy", args=[imp.pk])

    content = admin_client.get(results_url).content.decode()

    assert zapisz_url in content


@pytest.mark.django_db
def test_results_page_hides_button_when_already_committed(admin_client, admin_user):
    imp = baker.make(
        ImportPlikuPolon,
        owner=admin_user,
        zapisz_zmiany_do_bazy=True,
        started_on=timezone.now(),
        finished_on=timezone.now(),
        finished_successfully=True,
        rok=2023,
    )
    results_url = reverse("import_polon:importplikupolon-results", args=[imp.pk])
    zapisz_url = reverse("import_polon:importplikupolon-zapisz-do-bazy", args=[imp.pk])

    content = admin_client.get(results_url).content.decode()

    assert zapisz_url not in content


@pytest.mark.django_db
def test_zapisz_do_bazy_absencji_guard_already_committed(
    admin_client, admin_user, django_capture_on_commit_callbacks
):
    imp = baker.make(
        ImportPlikuAbsencji,
        owner=admin_user,
        zapisz_zmiany_do_bazy=True,
        started_on=timezone.now(),
        finished_on=timezone.now(),
        finished_successfully=True,
    )
    url = reverse("import_polon:importplikuabsencji-zapisz-do-bazy", args=[imp.pk])

    with django_capture_on_commit_callbacks() as callbacks:
        response = admin_client.post(url)

    assert response.status_code == 302
    imp.refresh_from_db()
    assert imp.finished_on is not None
    assert _reimport_scheduled(callbacks) == 0
