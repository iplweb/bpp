"""Kontrakt „generuj → wykonaj" dla wyszukiwania AI.

``ai_search`` opisuje LLM-owi schemat przez ``RekordLLMSchema`` (kanoniczny
schemat agent-facing z gałęzi dev — ten sam, którego używa
``/api/v1/zapytanie/``), a następnie przekierowuje wygenerowane zapytanie do
edytora ``/zapytanie/`` (``bpp:zapytanie``), który WALIDUJE i wykonuje je pod
``BppQLSchemaOgraniczony``.

Żeby wygenerowane zapytanie nie było odrzucone przy wykonaniu, powierzchnia
pól ``RekordLLMSchema`` MUSI być podzbiorem ``BppQLSchemaOgraniczony``
(``BppQLSchemaOgraniczony`` = ``RekordLLMSchema`` + pickery ``<fk>__rel`` +
ewentualnie pola, których ``RekordLLMSchema`` świadomie nie pokazuje LLM-owi).
Te testy pilnują tego niezmiennika dla obu modeli, po których pyta ai_search
(``rekord`` i ``autor``).
"""

import pytest

from bpp.djangoql_schema import BppQLSchemaOgraniczony, RekordLLMSchema
from bpp.models import Autor
from bpp.models.cache import Rekord


def _surface(schema_cls, model):
    """Mapa ``{etykieta_modelu: set(pól)}`` dla danego schematu i modelu
    startowego."""
    return {label: set(fields) for label, fields in schema_cls(model).models.items()}


@pytest.mark.django_db
@pytest.mark.parametrize("model", [Rekord, Autor])
def test_llm_schema_models_subset_of_web_editor(model):
    """Każdy model osiągalny w ``RekordLLMSchema`` jest też osiągalny w
    ``BppQLSchemaOgraniczony`` (ten sam allow-list ``SEARCH_ALLOWLIST``)."""
    llm = _surface(RekordLLMSchema, model)
    web = _surface(BppQLSchemaOgraniczony, model)
    brakujace = set(llm) - set(web)
    assert not brakujace, (
        f"RekordLLMSchema({model.__name__}) osiąga modele nieobecne w "
        f"BppQLSchemaOgraniczony: {sorted(brakujace)} — LLM wygenerowałby "
        f"zapytanie odrzucane przez /zapytanie/."
    )


@pytest.mark.django_db
@pytest.mark.parametrize("model", [Rekord, Autor])
def test_llm_schema_fields_subset_of_web_editor(model):
    """Każde pole wyrażalne w ``RekordLLMSchema`` jest też wyrażalne w
    ``BppQLSchemaOgraniczony`` — inaczej wygenerowane przez AI zapytanie
    zostałoby odrzucone przy wykonaniu w edytorze ``/zapytanie/``."""
    llm = _surface(RekordLLMSchema, model)
    web = _surface(BppQLSchemaOgraniczony, model)
    naruszenia = {
        label: sorted(fields - web.get(label, set()))
        for label, fields in llm.items()
        if fields - web.get(label, set())
    }
    assert not naruszenia, (
        f"RekordLLMSchema({model.__name__}) wyraża pola spoza "
        f"BppQLSchemaOgraniczony (odrzucane przez /zapytanie/): {naruszenia}"
    )
