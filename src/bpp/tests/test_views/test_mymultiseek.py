"""Regression tests dla bpp.views.mymultiseek."""

import pytest
from django.urls import reverse
from multiseek.views import MULTISEEK_SESSION_KEY_REMOVED


@pytest.mark.django_db
def test_remove_from_removed_after_json_session_roundtrip(client):
    """Drugie wywołanie remove_from_results nie może zwrócić 500.

    JSONSerializer zamienia tuple → list przy zapisie sesji. Upstream
    multiseek.manually_add_or_remove robi set(data) na odczycie, co
    failuje na listach (unhashable). Poprzednio to powodowało HTTP 500
    przy drugim klinięciu "Wyrzuć" (oryginalna regresja Django 5.2 PW).

    Symulacja: wrzucamy do sesji listę [[3, 1]] (post-JSON format),
    wołamy endpoint i oczekujemy 200.
    """
    session = client.session
    session[MULTISEEK_SESSION_KEY_REMOVED] = [[3, 1]]  # post-JSON roundtrip
    session.save()

    response = client.get(reverse("remove_from_removed_results", kwargs={"pk": "3_1"}))
    assert response.status_code == 200

    # Po wywołaniu session ma zostać bez tego id (usunięte)
    session = client.session
    assert session.get(MULTISEEK_SESSION_KEY_REMOVED) == []


@pytest.mark.django_db
def test_remove_by_hand_twice_does_not_500(client):
    """Dwa kolejne wywołania remove_from_results nie 500-ują.

    Po pierwszym wywołaniu sesja ma [[id1, id2]] (JSON-serialized tuple).
    Drugie wywołanie musi poprawnie odczytać i znormalizować.
    """
    url = reverse("remove_from_results", kwargs={"pk": "3_7"})
    assert client.get(url).status_code == 200
    # Drugie wywołanie (to samo pk) — niech nie wybuchnie
    assert client.get(url).status_code == 200
