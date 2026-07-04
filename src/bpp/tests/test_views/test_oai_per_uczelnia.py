import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
def test_oai_listrecords_wyklucza_obca_uczelnie(
    uczelnia1,
    uczelnia2,
    site1,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    autor_uczelnia1,
    autor_uczelnia2,
    typ_odpowiedzialnosci_autor,
    client,
    settings,
):
    # ``dodaj_autora`` domyślnie szuka Typ_Odpowiedzialnosci "aut." — nie
    # polegaj na ambientowych danych referencyjnych (inne testy, np. z
    # ``typy_odpowiedzialnosci`` / transaction=True, potrafią wyczyścić tę
    # tabelę), tylko zapewnij "aut." jawnie tym idempotentnym fixture.
    settings.ALLOWED_HOSTS = ["*"]  # pozwól na HTTP_HOST domeny uczelni
    chf = baker.make("bpp.Charakter_Formalny", skrot="OAI-TST", nazwa_w_primo="Artykuł")
    w1 = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="PRACA-MOJA",
        rok=2020,
        charakter_formalny=chf,
    )
    w1.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    w2 = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="PRACA-OBCA",
        rok=2020,
        charakter_formalny=chf,
    )
    w2.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)

    url = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    body = client.get(url, HTTP_HOST=site1.domain).content.decode("utf-8")
    assert "PRACA-MOJA" in body
    assert "PRACA-OBCA" not in body
