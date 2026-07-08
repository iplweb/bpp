"""Regresja: liczniki filtrów HTMX na adminach BEZ endpointu `_filter_count`.

`BppUserAdmin` dziedziczy po django-owym `UserAdmin`, a NIE po
`DynamicAdminFilterMixin`/`BaseBppAdminMixin`, więc nie rejestruje URL-a
`admin:bpp_bppuser_filter_count`. Wcześniej szablon `admin/change_list.html`
wywoływał `get_selected_filter_count_url` bezwarunkowo (poza `{% if show_counts %}`),
przez co dla każdego filtrowanego changelistu bez tego endpointu leciał
`NoReverseMatch` połykany przez `zaloguj_polkniety_wyjatek` (szum w Rollbarze).
"""

import pytest
from django.urls import NoReverseMatch, reverse


@pytest.mark.django_db
def test_bppuser_admin_nie_ma_endpointu_filter_count():
    """BppUserAdmin nie wystawia endpointu licznika filtrów."""
    with pytest.raises(NoReverseMatch):
        reverse("admin:bpp_bppuser_filter_count")


@pytest.mark.django_db
def test_admin_z_mixinem_ma_endpoint_filter_count():
    """Admin dziedziczący DynamicAdminFilterMixin (Autor) MA endpoint."""
    # Nie powinno rzucić NoReverseMatch:
    assert reverse("admin:bpp_autor_filter_count")


@pytest.mark.django_db
def test_bppuser_changelist_z_filtrem_nie_loguje_polknietego_wyjatku(
    admin_client, mocker
):
    """Filtrowany changelist BppUser nie próbuje reverse nieistniejącego URL-a.

    Zastosowanie filtru `is_staff` zaznacza wybór inny niż "Wszyscy", co
    wcześniej wyzwalało `get_selected_filter_count_url` -> `reverse(...)` ->
    `NoReverseMatch` -> `zaloguj_polkniety_wyjatek`. Po naprawie licznik jest
    liczony wyłącznie gdy admin wystawia endpoint (`show_counts`), więc żaden
    połknięty wyjątek nie powinien zostać zalogowany.
    """
    spy = mocker.patch(
        "bpp.templatetags.admin_filter_helpers.zaloguj_polkniety_wyjatek"
    )

    url = reverse("admin:bpp_bppuser_changelist")
    response = admin_client.get(url, {"is_staff__exact": "1"})

    assert response.status_code == 200
    spy.assert_not_called()
