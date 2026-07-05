"""Repro FD#390 — strona autora w trybie multi-homed.

Trzy defekty na stronie autora (``/bpp/autor/<pk>/``), gdy w instalacji
jest WIĘCEJ NIŻ JEDNA uczelnia (multi-homed):

A. Link "PBN UID" / "Naukowiec z POL-on" nie linkuje — szablon woła
   ``autor.link_do_pbn`` bez uczelni, więc w multi-install
   ``get_single_uczelnia_or_none()`` zwraca ``None`` i link jest pusty.
   Powinien użyć uczelni z hosta requestu.

Pozostałe defekty FD#390 mają repro-testy obok:
- ``src/bpp/tests/test_models/test_repro_fd390.py`` — trigger wyboru
  ``aktualna_jednostka`` (realna jednostka bije obcą),
- ``src/bpp/tests/test_admin/test_repro_fd390.py`` — edycja/usuwanie autora
  w adminie multi-homed (scope + cross-tenant delete).
"""

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse

import pytest
from model_bakery import baker

from bpp.models import Autor, Uczelnia


@pytest.fixture
def dwie_uczelnie(db):
    """Multi-homed: dwie uczelnie → get_single_uczelnia_or_none() == None.

    Zwraca uczelnię "A" z ustawioną domeną i pbn_api_root.
    """
    uczelnia_a = baker.make(Uczelnia, pbn_api_root="https://pbn-a.example.com")
    uczelnia_a.site.domain = "uczelnia-a.example.com"
    uczelnia_a.site.save()

    baker.make(Uczelnia)  # druga → single==None (multi-homed)
    return uczelnia_a


@pytest.mark.django_db
def test_repro_fd390_a_link_pbn_uid_uzywa_uczelni_z_hosta(
    client, settings, dwie_uczelnie
):
    """A: link PBN UID na stronie autora ma wskazywać na PBN uczelni z hosta,
    a nie degradować do pustego linku w multi-homed."""
    settings.ALLOWED_HOSTS = ["*"]

    from pbn_api.models import Scientist

    scientist = baker.make(Scientist)
    autor = baker.make(Autor, pbn_uid=scientist)

    url = reverse("bpp:browse_autor", args=(autor.pk,))
    resp = client.get(url, HTTP_HOST="uczelnia-a.example.com")
    assert resp.status_code == 200

    content = resp.content.decode("utf-8")
    oczekiwany = (
        f"https://pbn-a.example.com/core/#/person/view/{autor.pbn_uid_id}/current"
    )
    assert oczekiwany in content, (
        "Link PBN UID powinien używać pbn_api_root uczelni z hosta; "
        "zamiast tego link jest pusty/None (bug multi-homed)."
    )
    # I NIE ma zdegradowanego, pustego linku.
    assert 'href="None"' not in content
    assert 'href=""' not in content
