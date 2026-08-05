"""H1: sanityzacja pól szczegółów rekordu na wejściu (clean).

Pola ``informacje``/``szczegoly``/``uwagi`` (z ``ModelZeSzczegolami``) są
renderowane w opisie bibliograficznym przez filtr ``|safe`` (i trafiają do
zdenormalizowanego ``opis_bibliograficzny_cache`` renderowanego ``|safe`` na
publicznych stronach oraz w globalnej wyszukiwarce). W przeciwieństwie do
tytułów NIE były sanityzowane — redaktor (grupa wprowadzania danych) mógł
wstrzyknąć stored XSS wykonywany u anonimowych odwiedzających i superuserów
w adminie. Muszą być czyszczone ``safe_html`` w ``clean()``, tak jak tytuły.
"""

import pytest
from django.core.exceptions import ValidationError
from model_bakery import baker

PAYLOAD = '<img src=x onerror="alert(document.cookie)">Uwaga'


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_name",
    ["Wydawnictwo_Ciagle", "Wydawnictwo_Zwarte", "Patent"],
)
@pytest.mark.parametrize("field", ["informacje", "szczegoly", "uwagi"])
def test_szczegoly_field_sanitized_on_clean(model_name, field):
    from bpp import models as m

    model = getattr(m, model_name)
    obj = baker.prepare(model, **{field: PAYLOAD})

    try:
        obj.clean()
    except ValidationError:
        # Walidacja opłat / rekordu nadrzędnego jest nieistotna dla tego
        # testu; sanityzacja pól szczegółów wykonuje się w clean() PRZED
        # tymi walidacjami, więc wartość i tak jest już oczyszczona.
        pass

    value = getattr(obj, field)
    assert "onerror" not in value
    assert "<img" not in value
    assert "Uwaga" in value  # niegroźny tekst zachowany
