"""Testy regresyjne: akcje mutujące stan (usuwanie importu, uruchamianie
zadań Celery) MUSZĄ być dostępne wyłącznie przez POST + CSRF.

Historycznie widoki obsługiwały te akcje na GET (``get = delete``,
``UruchomZadaniePrzetwarzania.get``), co pozwalało wywołać skutki uboczne
zwykłym żądaniem GET (prefetch przeglądarki, skanery, brak ochrony CSRF).
Poniższe testy pilnują, że GET nic nie mutuje, a POST działa jak dawniej.
"""

from django.urls import reverse
from model_bakery import baker

from fixtures.conftest_browser import (
    NORMAL_DJANGO_USER_LOGIN,
    NORMAL_DJANGO_USER_PASSWORD,
    _webtest_login,
)
from import_dyscyplin.models import Import_Dyscyplin
from import_dyscyplin.tasks import przeanalizuj_import_dyscyplin
from import_dyscyplin.tests.test_views import wyslij

# ---------------------------------------------------------------------------
# Usuwanie importu (UsunImport_Dyscyplin)
# ---------------------------------------------------------------------------


def test_usun_get_nie_kasuje(csrf_exempt_wd_app, test1_xlsx, transactional_db):
    """GET na endpoint usuwania NIE może kasować rekordu (405)."""
    wyslij(csrf_exempt_wd_app, test1_xlsx)
    i = Import_Dyscyplin.objects.first()

    res = csrf_exempt_wd_app.get(
        reverse("import_dyscyplin:usun", args=(i.pk,)), expect_errors=True
    )

    assert res.status_code == 405
    assert Import_Dyscyplin.objects.filter(pk=i.pk).exists()


def test_usun_post_kasuje(csrf_exempt_wd_app, test1_xlsx, transactional_db):
    """POST (z CSRF) usuwa rekord jak dawniej."""
    wyslij(csrf_exempt_wd_app, test1_xlsx)
    i = Import_Dyscyplin.objects.first()

    res = csrf_exempt_wd_app.post(
        reverse("import_dyscyplin:usun", args=(i.pk,))
    ).maybe_follow()

    assert res.status_code == 200
    assert not Import_Dyscyplin.objects.filter(pk=i.pk).exists()


def test_usun_post_cudzy_rekord_niewidoczny(
    csrf_exempt_wd_app, django_user_model, transactional_db
):
    """TylkoMojeMixin: cudzy rekord jest niewidoczny (404), nie kasuje się."""
    obcy = django_user_model.objects.create_user(
        username="obcy_wlasciciel", password="x"
    )
    rec = baker.make(Import_Dyscyplin, owner=obcy)

    res = csrf_exempt_wd_app.post(
        reverse("import_dyscyplin:usun", args=(rec.pk,)), expect_errors=True
    )

    assert res.status_code == 404
    assert Import_Dyscyplin.objects.filter(pk=rec.pk).exists()


def test_usun_post_non_member_odmowa(
    django_app_factory, normal_django_user, transactional_db
):
    """Regresja autoryzacji: użytkownik spoza grupy dostaje odmowę."""
    app = django_app_factory(csrf_checks=False)
    app = _webtest_login(app, NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD)
    rec = baker.make(Import_Dyscyplin, owner=normal_django_user)

    res = app.post(reverse("import_dyscyplin:usun", args=(rec.pk,)), expect_errors=True)

    assert res.status_code in (302, 403)
    assert Import_Dyscyplin.objects.filter(pk=rec.pk).exists()


# ---------------------------------------------------------------------------
# Uruchamianie zadań Celery (UruchomZadaniePrzetwarzania i podklasy)
# ---------------------------------------------------------------------------


def _przygotuj_do_przetwarzania(app, plik):
    wyslij(app, plik)
    i = Import_Dyscyplin.objects.first()
    i.stworz_kolumny()
    i.zatwierdz_kolumny()
    i.save()
    return i


def test_przetwarzaj_get_nie_uruchamia(csrf_exempt_wd_app, test1_xlsx, mocker):
    """GET na endpoint uruchamiający zadanie NIE uruchamia go (405)."""
    i = _przygotuj_do_przetwarzania(csrf_exempt_wd_app, test1_xlsx)
    mock = mocker.patch.object(przeanalizuj_import_dyscyplin, "apply_async")

    res = csrf_exempt_wd_app.get(
        reverse("import_dyscyplin:przetwarzaj", args=(i.pk,)), expect_errors=True
    )

    assert res.status_code == 405
    i = Import_Dyscyplin.objects.get(pk=i.pk)
    assert not i.task_id
    mock.assert_not_called()


def test_przetwarzaj_post_uruchamia(
    csrf_exempt_wd_app, test1_xlsx, mocker, django_capture_on_commit_callbacks
):
    """POST (z CSRF) uruchamia zadanie Celery jak dawniej."""
    i = _przygotuj_do_przetwarzania(csrf_exempt_wd_app, test1_xlsx)
    mock = mocker.patch.object(przeanalizuj_import_dyscyplin, "apply_async")

    with django_capture_on_commit_callbacks(execute=True):
        res = csrf_exempt_wd_app.post(
            reverse("import_dyscyplin:przetwarzaj", args=(i.pk,))
        )

    assert res.json["status"] == "ok"
    i = Import_Dyscyplin.objects.get(pk=i.pk)
    assert i.task_id
    mock.assert_called_once()
