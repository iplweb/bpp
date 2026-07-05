"""Testy rozwiązywania domyślnego języka dla sesji importu PBN.

Domyślny język to ten, którym oznaczamy publikację, gdy PBN nie poda języka
(``mainLanguage``) albo poda kod nieobecny w słowniku ``Jezyk``. Wybór z
formularza nowego importu ląduje w ``config["default_jezyk_id"]``; przy jego
braku spadamy na polski. Języki są globalne (nie per-uczelnia), więc resolver
nie potrzebuje ``Uczelnia``.
"""

import pytest
from model_bakery import baker

from bpp.models import Jezyk
from pbn_import.models import ImportSession
from pbn_import.utils.institution_import import resolve_default_jezyk


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(ImportSession, user=user, config={})


def test_prefers_config_default_jezyk_id(session):
    """``config["default_jezyk_id"]`` (wybór z formularza) ma pierwszeństwo."""
    angielski = Jezyk.objects.get(skrot="ang.")
    session.config = {"default_jezyk_id": angielski.pk}

    assert resolve_default_jezyk(session) == angielski


def test_falls_back_to_polish_when_no_config(session):
    """Brak wyboru w configu → polski (skrot='pol.')."""
    assert resolve_default_jezyk(session) == Jezyk.objects.get(skrot="pol.")


def test_falls_back_to_polish_when_config_id_invalid(session):
    """Niepoprawne id języka w configu → polski (defensywnie, bez wywalenia)."""
    session.config = {"default_jezyk_id": 99999999}

    assert resolve_default_jezyk(session) == Jezyk.objects.get(skrot="pol.")
