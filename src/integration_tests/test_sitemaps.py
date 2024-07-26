import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.models.autor import Autor
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.struktura import Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte


@pytest.mark.xfail(reasons="testowanie static siteamps")
@pytest.mark.django_db
def test_sitemaps(client, settings):
    baker.make(Wydzial)
    baker.make(Autor, nazwisko="Alan")
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="A case of")
    baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="A case of")
    baker.make(Praca_Doktorska, tytul_oryginalny="A case of")
    baker.make(Praca_Habilitacyjna, tytul_oryginalny="A case of")
    baker.make(Patent, tytul_oryginalny="A case of")

    call_command("refresh_sitemap")

    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    assert b"example.com" in res.content

    for page in [
        "-jednostka",
        "-autor-a",
        "-uczelnia",
        "-wydawnictwo-ciagle-a",
        "-wydawnictwo-zwarte-a",
        "-praca-doktorska-a",
        "-praca-habilitacyjna-a",
        "-patent-a",
        "-wydzial",
    ]:
        res = client.get("/static/sitemap%s-1.xml" % page)
        assert res.status_code == 200
        assert b"example.com" in res.content
