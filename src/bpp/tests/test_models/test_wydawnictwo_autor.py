import pytest
from django.core.exceptions import ValidationError


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
