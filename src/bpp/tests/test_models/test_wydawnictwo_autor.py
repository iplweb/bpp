import pytest
from django.core.exceptions import ValidationError
from model_mommy import mommy

from bpp.models import (
    Wydawnictwo_Zwarte_Autor,
    Patent_Autor,
    Wydawnictwo_Ciagle_Autor,
    Patent,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "w",
    [
        pytest.lazy_fixture("wydawnictwo_zwarte"),
        pytest.lazy_fixture("wydawnictwo_ciagle"),
        pytest.lazy_fixture("patent"),
    ],
)
def test_autor_jednostka_afiliuje_na_obca(autor_jan_kowalski, obca_jednostka, w):
    with pytest.raises(ValidationError):
        w.dodaj_autora(autor_jan_kowalski, obca_jednostka, afiliuje=True)

    obca_jednostka.skupia_pracownikow = True
    obca_jednostka.save()
    w.dodaj_autora(autor_jan_kowalski, obca_jednostka, afiliuje=True)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "w,r",
    [
        (Wydawnictwo_Zwarte_Autor, Wydawnictwo_Zwarte),
        (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Ciagle),
        (Patent_Autor, Patent),
    ],
)
def test_autor_jednostka_afiliuje_bug(autor_jan_kowalski, obca_jednostka, w, r):
    ri = mommy.make(r)
    wi = w(autor=autor_jan_kowalski, jednostka=None, rekord=ri)
    wi.clean()
