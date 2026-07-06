import re

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from model_bakery import baker

#: To, czego saveForm() z multiseek.js szuka w stronie, zeby wstawic token
#: CSRF do POST-a na ./save_form/ (pole ``csrfmiddlewaretoken``).
MULTISEEK_CSRF_TOKEN_RE = re.compile(r"multiseekCSRFToken\s*=\s*'([^']*)'")


@pytest.mark.django_db
def test_multiseek_anonymous(client):
    """Test multiseek dla niezalogowanego użytkownika."""
    res = client.get(reverse("multiseek:index"))
    assert res.status_code == 200
    assert b"Adnotacje" not in res.content


@pytest.mark.django_db
def test_multiseek_logged_in(logged_in_client):
    """Test multiseek dla zalogowanego użytkownika."""
    res = logged_in_client.get(reverse("multiseek:index"))
    assert res.status_code == 200
    assert b"Adnotacje" in res.content


@pytest.mark.django_db
def test_multiseek_index_renders_multiseek_csrf_token(logged_in_client):
    """Strona multiseek MUSI ustawiac window.multiseekCSRFToken na realny token.

    Vendorowany multiseek.js (saveForm/submitEvent) czyta
    ``window.multiseekCSRFToken`` i wstawia go jako pole ``csrfmiddlewaretoken``
    do POST-a na ``./save_form/``. Jesli token jest pusty (albo go w ogole nie ma
    w szablonie), Django odrzuca zapis z bledem CSRF. To wprost regresja z
    FreshDesk #378 — nasz override ``multiseek/index.html`` zgubil te linie,
    ktora upstreamowy ``multiseek_head.html`` renderuje.
    """
    res = logged_in_client.get(reverse("multiseek:index"))
    assert res.status_code == 200

    match = MULTISEEK_CSRF_TOKEN_RE.search(res.content.decode("utf-8"))
    assert match is not None, (
        "Strona multiseek nie ustawia window.multiseekCSRFToken — saveForm() "
        "wysle pusty token i zapis formularza padnie na CSRF (FreshDesk #378)."
    )
    assert match.group(1).strip(), (
        "window.multiseekCSRFToken jest pusty — POST do save_form/ dostanie "
        "pusty csrfmiddlewaretoken i Django zwroci 403 (FreshDesk #378)."
    )


@pytest.mark.django_db
def test_save_form_post_using_page_rendered_token_is_allowed():
    """Reprodukcja FreshDesk #378 na poziomie HTTP, tak jak robi to przegladarka.

    Kluczowe: ``CSRF_COOKIE_HTTPONLY = True`` w BPP sprawia, ze JS NIE moze
    odczytac ciasteczka ``csrftoken``. Dlatego saveForm() polega wylacznie na
    tokenie wyrenderowanym server-side w ``window.multiseekCSRFToken`` — i to
    jego tu wyciagamy ze strony (a NIE z ciasteczka, jak robi to test
    upstreamu, ktory wlasnie dlatego nie wykryl tego buga w naszym szablonie).

    Z ``enforce_csrf_checks=True`` (jak prawdziwa przegladarka) brak tokenu
    konczy sie 403. Po naprawie szablonu token jest obecny i zapis przechodzi.
    """
    staff = baker.make(get_user_model(), is_staff=True)
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(staff)

    page = csrf_client.get(reverse("multiseek:index"))
    assert page.status_code == 200
    match = MULTISEEK_CSRF_TOKEN_RE.search(page.content.decode("utf-8"))
    token = match.group(1) if match else ""

    res = csrf_client.post(
        reverse("multiseek:save_form"),
        data={
            "json": '{"form_data": [null]}',
            "name": "formularz testowy #378",
            "csrfmiddlewaretoken": token,
        },
    )

    assert res.status_code != 403, (
        "save_form zwrocil 403 — token CSRF ze strony (window.multiseekCSRFToken) "
        "nie dotarl do POST-a. To bug z FreshDesk #378."
    )
