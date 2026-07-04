"""Kontrakt konstruktora kroków importu PBN.

Regresja dla błędu: ``SourceScoringImporter.__init__() got an unexpected
keyword argument 'uczelnia'``.

``ImportManager._execute_step`` tworzy KAŻDY krok zawsze tak samo::

    step_class(session=..., client=..., uczelnia=..., **step_config["args"])

Każda klasa kroku zarejestrowana w ``ALL_STEP_DEFINITIONS`` MUSI dać się
zainstancjonować dokładnie tym kontraktem. Kroki które nadpisują ``__init__``
bez przyjęcia ``uczelnia`` wysadzają cały import zanim jakikolwiek
``try/except`` (a więc i Rollbar) zdąży go złapać kontekstowo.
"""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_import.models import ImportSession
from pbn_import.utils.step_definitions import ALL_STEP_DEFINITIONS, get_step_definitions

# Parametryzujemy po nazwie kroku, żeby przy regresji od razu było widać
# KTÓRY krok łamie kontrakt (zamiast gołego indeksu).
STEP_PARAMS = [
    pytest.param(step_def, id=step_def["name"]) for step_def in ALL_STEP_DEFINITIONS
]


@pytest.mark.django_db
@pytest.mark.parametrize("step_def", STEP_PARAMS)
def test_step_class_accepts_manager_constructor_contract(step_def):
    """Każdy krok daje się stworzyć kwargami których używa ImportManager."""
    session = baker.make(ImportSession)
    uczelnia = baker.make(Uczelnia)

    # Dokładnie te same argumenty co ImportManager._execute_step.
    args = get_step_definitions(config={})
    step_args = next(s["args"] for s in args if s["name"] == step_def["name"])

    step = step_def["class"](
        session=session,
        client=None,
        uczelnia=uczelnia,
        **step_args,
    )

    # Kontekst uczelni MUSI dotrzeć do kroku (multi-hosted) — inaczej krok
    # zgadnie złą uczelnię przez get_default()/get().
    assert step.uczelnia == uczelnia
