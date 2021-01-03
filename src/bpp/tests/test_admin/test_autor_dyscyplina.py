from bpp.admin.autor_dyscyplina import Autor_DyscyplinaResource
from bpp.models import Autor_Dyscyplina


def test_autor_dyscyplina_resource(autor_jan_kowalski, dyscyplina1):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=2020, dyscyplina_naukowa=dyscyplina1
    )
    assert "Kowalski" in str(Autor_DyscyplinaResource().export())
