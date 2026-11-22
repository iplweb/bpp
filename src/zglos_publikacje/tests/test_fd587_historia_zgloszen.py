"""FD#587: zgłoszenia publikacji mają historię wersji także dla zmian spoza
formularza admina — zgłoszenie z formularza na stronie, „Zwróć do autora”
i oznaczenie jako zaimportowane (importer)."""

import pytest
from django.db import transaction
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from zglos_publikacje.models import Zgloszenie_Publikacji
from zglos_publikacje.tests.tests_zglos_publikacje import (
    _zrob_submit_calego_formularza,
)


@pytest.mark.django_db
def test_zgloszenie_z_formularza_na_stronie_ma_wersje(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_jan_kowalski,
    jednostka,
):
    _zrob_submit_calego_formularza(
        webtest_app,
        django_capture_on_commit_callbacks,
        rodzaj="POZOSTALE",
        oczekuj_platnosci=False,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
    )
    zgloszenie = Zgloszenie_Publikacji.objects.get()
    wersja = Version.objects.get_for_object(zgloszenie).get()
    assert wersja.revision.comment.startswith(
        "Zgłoszono publikację przez formularz na stronie"
    )
    assert wersja.revision.zrodlo_zmiany.zrodlo == "strona"
    modele = {v.content_type.model for v in wersja.revision.version_set.all()}
    assert "zgloszenie_publikacji_autor" in modele


@pytest.mark.django_db
def test_zwrot_do_autora_ma_wersje_z_przyczyna(
    admin_client, uczelnia, mailoutbox, monkeypatch
):
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Zgłoszenie",
        email="autor@example.com",
        rok=2024,
        status=Zgloszenie_Publikacji.Statusy.NOWY,
    )
    monkeypatch.setattr(transaction, "on_commit", lambda func, *a, **kw: func())
    res = admin_client.post(
        reverse(
            "admin:zglos_publikacje_zgloszenie_publikacji_zwroc",
            args=[zgloszenie.pk],
        ),
        {"przyczyna_zwrotu": "Popraw dane autorów"},
    )
    assert res.status_code == 302

    po, przed = Version.objects.get_for_object(zgloszenie)
    assert "Popraw dane autorów" in po.revision.comment
    assert po.field_dict["status"] == Zgloszenie_Publikacji.Statusy.WYMAGA_ZMIAN
    assert przed.field_dict["status"] == Zgloszenie_Publikacji.Statusy.NOWY


@pytest.mark.django_db
def test_zwrot_do_autora_wymaga_uprawnienia(client, django_user_model, uczelnia):
    """Sam dostęp do panelu nie wystarcza: zwrot zmienia zgłoszenie i wysyła
    zgłaszającemu nowy link do edycji (wcześniej każdy z personelu mógł)."""
    from django.contrib.auth.models import Permission

    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Zgłoszenie",
        email="autor@example.com",
        rok=2024,
        status=Zgloszenie_Publikacji.Statusy.NOWY,
    )
    personel = baker.make(django_user_model, is_staff=True)
    personel.user_permissions.add(
        Permission.objects.get(codename="view_zgloszenie_publikacji")
    )
    client.force_login(personel)
    url = reverse(
        "admin:zglos_publikacje_zgloszenie_publikacji_zwroc", args=[zgloszenie.pk]
    )
    assert client.post(url, {"przyczyna_zwrotu": "x"}).status_code == 403
    zgloszenie.refresh_from_db()
    assert zgloszenie.status == Zgloszenie_Publikacji.Statusy.NOWY

    strona = client.get(
        reverse(
            "admin:zglos_publikacje_zgloszenie_publikacji_change",
            args=[zgloszenie.pk],
        )
    ).content.decode()
    assert "Zwróć do autora" not in strona
