import pytest
from django.core.validators import validate_email
from django.db import transaction
from django.urls import reverse
from model_bakery import baker

from zglos_publikacje.models import Zgloszenie_Publikacji

EMAIL = '"<b>x</b>"@example.com'


@pytest.mark.django_db
def test_zwroc_zgloszenie_komunikat_z_emailem_escapowany(
    admin_client, uczelnia, mailoutbox, monkeypatch
):
    validate_email(EMAIL)  # adres jest formalnie poprawny

    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Zgłoszenie",
        email=EMAIL,
        rok=2024,
        status=Zgloszenie_Publikacji.Statusy.NOWY,
    )
    url = reverse(
        "admin:zglos_publikacje_zgloszenie_publikacji_zwroc",
        args=[zgloszenie.pk],
    )

    # Callback ``on_commit`` (wysyłka maila + komunikat) musi wykonać się
    # jeszcze w trakcie żądania, tak jak po COMMIT na produkcji.
    monkeypatch.setattr(transaction, "on_commit", lambda func, *a, **kw: func())
    res = admin_client.post(url, {"przyczyna_zwrotu": "Popraw dane"})
    assert res.status_code == 302
    assert len(mailoutbox) == 1

    res = admin_client.get(
        reverse("admin:zglos_publikacje_zgloszenie_publikacji_changelist")
    )
    html = res.content.decode()
    assert "został powiadomiony o zwróceniu zgłoszenia" in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<b>x</b>" not in html
