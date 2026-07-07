"""Walidacja formsetu inline Autor_Jednostka w adminie Autora.

Sprawdza, ze:
- zaznaczenie DWoch podstawowych miejsc pracy naraz daje przyjazny blad
  formularza (a nie 500 z bazy),
- legalne PRZELACZENIE domyslnego miejsca (odznacz A, zaznacz B) przechodzi —
  mimo ze przejsciowo w bazie istnialyby dwa True.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from model_bakery import baker

from bpp.admin.autor import Autor_JednostkaInline
from bpp.models import Autor
from bpp.models.autor import Autor_Jednostka

PREFIX = "Autor_jednostka_set"


def _formset(request_factory, user, autor, data):
    inline = Autor_JednostkaInline(Autor, AdminSite())
    request = request_factory.post("/")
    request.user = user
    formset_cls = inline.get_formset(request)
    return formset_cls(data, instance=autor, prefix=PREFIX)


def _row(idx, aj, *, autor, podstawowe):
    return {
        f"{PREFIX}-{idx}-id": str(aj.pk),
        f"{PREFIX}-{idx}-autor": str(autor.pk),
        f"{PREFIX}-{idx}-jednostka": str(aj.jednostka_id),
        f"{PREFIX}-{idx}-podstawowe_miejsce_pracy": podstawowe,
    }


def _management(total):
    return {
        f"{PREFIX}-TOTAL_FORMS": str(total),
        f"{PREFIX}-INITIAL_FORMS": str(total),
        f"{PREFIX}-MIN_NUM_FORMS": "0",
        f"{PREFIX}-MAX_NUM_FORMS": "1000",
    }


@pytest.mark.django_db
def test_inline_dwa_podstawowe_blad_formularza(
    autor_jan_kowalski, jednostka, druga_jednostka, rf, admin_user
):
    a = baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        podstawowe_miejsce_pracy=True,
    )
    b = baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=druga_jednostka,
        podstawowe_miejsce_pracy=False,
    )

    data = _management(2)
    # Oba zaznaczone jako podstawowe -> stan koncowy niepoprawny.
    data.update(_row(0, a, autor=autor_jan_kowalski, podstawowe="true"))
    data.update(_row(1, b, autor=autor_jan_kowalski, podstawowe="true"))

    formset = _formset(rf, admin_user, autor_jan_kowalski, data)

    assert not formset.is_valid()
    assert "tylko jedno podstawowe miejsce pracy" in str(formset.non_form_errors())


@pytest.mark.django_db
def test_inline_przelaczenie_podstawowego_przechodzi(
    autor_jan_kowalski, jednostka, druga_jednostka, rf, admin_user
):
    a = baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        podstawowe_miejsce_pracy=True,
    )
    b = baker.make(
        Autor_Jednostka,
        autor=autor_jan_kowalski,
        jednostka=druga_jednostka,
        podstawowe_miejsce_pracy=False,
    )

    data = _management(2)
    # Przelaczenie: A -> nie, B -> tak. Stan koncowy = jeden True.
    data.update(_row(0, a, autor=autor_jan_kowalski, podstawowe="false"))
    data.update(_row(1, b, autor=autor_jan_kowalski, podstawowe="true"))

    formset = _formset(rf, admin_user, autor_jan_kowalski, data)

    assert formset.is_valid(), formset.errors or formset.non_form_errors()
