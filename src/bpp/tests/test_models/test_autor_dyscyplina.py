import pytest
from django.core.exceptions import ValidationError

from bpp.models import Autor_Dyscyplina


def test_autor_dyscyplina_save_ta_sama(autor_jan_kowalski, dyscyplina1, rok):
    ad = Autor_Dyscyplina.objects.create(
        rok=rok,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina1
    )

    with pytest.raises(ValidationError):
        ad.clean()


def test_autor_dyscyplina_procent_ponad(autor_jan_kowalski, dyscyplina1, dyscyplina2, rok):
    ad = Autor_Dyscyplina.objects.create(
        rok=rok,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        procent_dyscypliny=100,
        subdyscyplina_naukowa=dyscyplina2,
        procent_subdyscypliny=1)

    with pytest.raises(ValidationError):
        ad.clean()
