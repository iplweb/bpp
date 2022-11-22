import pytest
from model_bakery import baker

from bpp.models import Praca_Doktorska
from bpp.models.autor import Autor
from bpp.models.cache import Autorzy, Rekord
from bpp.models.openaccess import (
    Czas_Udostepnienia_OpenAccess,
    Licencja_OpenAccess,
    Wersja_Tekstu_OpenAccess,
)
from bpp.models.struktura import Jednostka
from bpp.models.system import Charakter_Formalny, Jezyk, Typ_KBN, Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
from bpp.models.zrodlo import Zrodlo


@pytest.mark.django_db
def test_Autorzy_original(wydawnictwo_ciagle_z_dwoma_autorami):
    assert (
        Autorzy.objects.first().original.pk
        in wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.all().values_list(
            "pk", flat=True
        )
    )


def test_opis_bibliograficzny_wydawnictwo_ciagle(
    transactional_db, standard_data, denorms, autor_jan_kowalski, jednostka
):
    wc = baker.make(Wydawnictwo_Ciagle, szczegoly="Sz", uwagi="U")

    rekord = Rekord.objects.all()[0]

    assert wc.opis_bibliograficzny() == rekord.opis_bibliograficzny_cache

    wc.dodaj_autora(autor_jan_kowalski, jednostka)

    assert wc.opis_bibliograficzny() != rekord.opis_bibliograficzny_cache
    denorms.flush()
    assert wc.opis_bibliograficzny() != rekord.opis_bibliograficzny_cache


def test_opis_bibliograficzny_praca_doktorska(
    standard_data, autor_jan_kowalski, jednostka, denorms
):
    wc = baker.make(
        Praca_Doktorska,
        szczegoly="Sz",
        uwagi="U",
        autor=autor_jan_kowalski,
        jednostka=jednostka,
    )

    rekord_opis = Rekord.objects.all()[0].opis_bibliograficzny_cache
    wc_opis = wc.opis_bibliograficzny()
    assert rekord_opis == wc_opis


def test_kasowanie(db, standard_data):
    assert Rekord.objects.count() == 0

    wc = baker.make(Wydawnictwo_Ciagle)
    assert Rekord.objects.count() == 1

    wc.delete()
    assert Rekord.objects.count() == 0


def test_opis_bibliograficzny_dependent(standard_data, denorms):
    """Stwórz i skasuj Wydawnictwo_Ciagle_Autor i sprawdź, jak to
    wpłynie na opis."""

    c = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Test", szczegoly="sz", uwagi="u"
    )
    assert "KOWALSKI" not in c.opis_bibliograficzny()
    assert "KOWALSKI" not in Rekord.objects.first().opis_bibliograficzny_cache

    a = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    j = baker.make(Jednostka)
    wca = c.dodaj_autora(a, j)

    denorms.flush()

    assert "KOWALSKI" in c.opis_bibliograficzny()
    assert "KOWALSKI" in Rekord.objects.first().opis_bibliograficzny_cache

    wca.delete()

    denorms.flush()

    assert "KOWALSKI" not in c.opis_bibliograficzny()
    assert "KOWALSKI" not in Rekord.objects.first().opis_bibliograficzny_cache


def test_opis_bibliograficzny_zrodlo(standard_data, denorms):
    """Zmień nazwę źródła i sprawdź, jak to wpłynie na opis."""

    z = baker.make(Zrodlo, nazwa="OMG", skrot="wutlolski")
    c = baker.make(Wydawnictwo_Ciagle, szczegoly="SZ", uwagi="U", zrodlo=z)

    assert "wutlolski" in c.opis_bibliograficzny()
    assert "wutlolski" in Rekord.objects.first().opis_bibliograficzny_cache

    z.nazwa = "LOL"
    z.skrot = "FOKA"
    z.save()

    denorms.flush()

    assert "FOKA" in c.opis_bibliograficzny()
    assert "FOKA" in Rekord.objects.first().opis_bibliograficzny_cache

    z.nazwa = "LOL 2"
    z.skrot = "foka 2"
    z.save()

    denorms.flush()

    assert "foka 2" in c.opis_bibliograficzny()
    assert "foka 2" in Rekord.objects.first().opis_bibliograficzny_cache


@pytest.mark.django_db
def test_post_save_cache(doktorat):
    assert Rekord.objects.all().count() == 1

    doktorat.tytul = "zmieniono"
    doktorat.save()

    assert Rekord.objects.get_original(doktorat).tytul == "zmieniono"


def test_deletion_cache(doktorat):
    assert Rekord.objects.all().count() == 1

    doktorat.delete()
    assert Rekord.objects.all().count() == 0


@pytest.mark.django_db
def test_wca_delete_cache(wydawnictwo_ciagle_z_dwoma_autorami, denorms):
    """Czy skasowanie obiektu Wydawnictwo_Ciagle_Autor zmieni opis
    wydawnictwa ciągłego w Rekordy materialized view?"""

    assert Rekord.objects.all().count() == 1
    assert Wydawnictwo_Ciagle_Autor.objects.all().count() == 2

    denorms.flush()

    r = Rekord.objects.all()[0]
    assert "NOWAK" in r.opis_bibliograficzny_cache
    assert "KOWALSKI" in r.opis_bibliograficzny_cache

    Wydawnictwo_Ciagle_Autor.objects.all()[0].delete()
    aca = Wydawnictwo_Ciagle_Autor.objects.all()[0]
    aca.delete()

    denorms.flush()

    assert Autorzy.objects.filter_rekord(aca).count() == 0
    assert Rekord.objects.all().count() == 1

    r = Rekord.objects.all()[0]
    assert "NOWAK" not in r.opis_bibliograficzny_cache
    assert "KOWALSKI" not in r.opis_bibliograficzny_cache


@pytest.mark.django_db
def test_caching_kasowanie_autorow(wydawnictwo_ciagle_z_dwoma_autorami):
    for wca in Wydawnictwo_Ciagle_Autor.objects.all().only("autor"):
        wca.autor.delete()

    assert Wydawnictwo_Ciagle_Autor.objects.count() == 0
    assert Rekord.objects.all().count() == 1

    r = Rekord.objects.all()[0]
    assert "NOWAK" not in r.opis_bibliograficzny_cache
    assert "KOWALSKI" not in r.opis_bibliograficzny_cache


@pytest.mark.django_db
def test_caching_kasowanie_typu_odpowiedzialnosci_autorow(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    assert (
        Wydawnictwo_Ciagle_Autor.objects.filter(
            rekord=wydawnictwo_ciagle_z_dwoma_autorami
        ).count()
        == 2
    )

    Typ_Odpowiedzialnosci.objects.all().delete()

    assert Wydawnictwo_Ciagle_Autor.objects.count() == 0
    assert Rekord.objects.all().count() == 1

    r = Rekord.objects.all()[0]
    assert "NOWAK" not in r.opis_bibliograficzny_cache
    assert "KOWALSKI" not in r.opis_bibliograficzny_cache


@pytest.mark.django_db
def test_caching_kasowanie_zrodla(
    denorms,
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    assert Zrodlo.objects.all().count() == 1

    z = Zrodlo.objects.all()[0]
    z.delete()  # WCA ma zrodlo.on_delete=SET_NULL

    denorms.flush()
    assert Rekord.objects.all().count() == 1
    assert Wydawnictwo_Ciagle.objects.all().count() == 1

    r = Rekord.objects.all()[0]
    assert "NOWAK" in r.opis_bibliograficzny_cache
    assert "KOWALSKI" in r.opis_bibliograficzny_cache
    assert z.skrot not in r.opis_bibliograficzny_cache
    assert "None" not in r.opis_bibliograficzny_cache


@pytest.mark.django_db
def test_caching_kasowanie_jezyka(wydawnictwo_ciagle_z_dwoma_autorami):
    xng = Jezyk.objects.create(skrot="xng.", nazwa="taki", pk=500)
    wydawnictwo_ciagle_z_dwoma_autorami.jezyk = xng
    wydawnictwo_ciagle_z_dwoma_autorami.save()

    assert Rekord.objects.all().count() == 1
    xng.delete()

    assert Rekord.objects.all().count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "attrname, klass, skrot, ma_zostac",
    [
        ("typ_kbn", Typ_KBN, "PO", 0),
        ("charakter_formalny", Charakter_Formalny, "PAT", 0),
        ("openaccess_wersja_tekstu", Wersja_Tekstu_OpenAccess, "FINAL_AUTHOR", 1),
        ("openaccess_licencja", Licencja_OpenAccess, "CC-BY-ND", 1),
        (
            "openaccess_czas_publikacji",
            Czas_Udostepnienia_OpenAccess,
            "AT_PUBLICATION",
            1,
        ),
    ],
)
def test_usuwanie_powiazanych_vs_rekord(
    wydawnictwo_ciagle_z_dwoma_autorami,
    patent,
    standard_data,
    openaccess_data,
    attrname,
    klass,
    skrot,
    ma_zostac,
):

    o = klass.objects.get(skrot=skrot)
    setattr(wydawnictwo_ciagle_z_dwoma_autorami, attrname, o)
    wydawnictwo_ciagle_z_dwoma_autorami.save()

    setattr(patent, attrname, o)
    patent.save()

    assert Rekord.objects.all().count() == 2
    o.delete()
    assert Rekord.objects.all().count() == ma_zostac


@pytest.mark.django_db
def test_caching_kasowanie_typu_kbn(wydawnictwo_ciagle_z_dwoma_autorami, standard_data):
    tk = Typ_KBN.objects.all().first()

    wydawnictwo_ciagle_z_dwoma_autorami.typ_kbn = tk
    wydawnictwo_ciagle_z_dwoma_autorami.save()

    assert Rekord.objects.all().count() == 1
    tk.delete()

    assert Rekord.objects.all().count() == 0


@pytest.mark.django_db
def test_caching_kasowanie_charakteru_formalnego(
    wydawnictwo_ciagle_z_dwoma_autorami,
    patent,
    autor_jan_kowalski,
    jednostka,
    standard_data,
):
    patent.dodaj_autora(autor_jan_kowalski, jednostka)

    cf = Charakter_Formalny.objects.all().first()

    wydawnictwo_ciagle_z_dwoma_autorami.charakter_formalny = cf
    wydawnictwo_ciagle_z_dwoma_autorami.save()

    assert Rekord.objects.all().count() == 2
    Charakter_Formalny.objects.all().delete()

    assert Rekord.objects.all().count() == 0


@pytest.mark.django_db
def test_caching_kasowanie_wydzialu(
    autor_jan_kowalski, jednostka, wydzial, wydawnictwo_ciagle, typy_odpowiedzialnosci
):
    assert jednostka.wydzial == wydzial

    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    assert Rekord.objects.all().count() == 1
    assert Jednostka.objects.all().count() == 1
    wydzial.delete()

    assert Rekord.objects.all().count() == 1
    assert Rekord.objects.all()[0].original.autorzy.all().count() == 0
    assert Jednostka.objects.all().count() == 0


@pytest.mark.django_db
def test_caching_kasowanie_uczelni(
    autor_jan_kowalski,
    jednostka,
    wydzial,
    uczelnia,
    wydawnictwo_ciagle,
    typy_odpowiedzialnosci,
):
    assert wydzial.uczelnia == uczelnia
    assert jednostka.wydzial == wydzial
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    assert Rekord.objects.all().count() == 1
    assert Jednostka.objects.all().count() == 1
    uczelnia.delete()

    assert Rekord.objects.all().count() == 1
    assert Rekord.objects.all()[0].original.autorzy.all().count() == 0
    assert Jednostka.objects.all().count() == 0


@pytest.mark.django_db
def test_caching_full_refresh(wydawnictwo_ciagle_z_dwoma_autorami, denorms):
    assert Rekord.objects.all().count() == 1
    denorms.rebuildall()
    assert Rekord.objects.all().count() == 1


@pytest.mark.django_db
def test_caching_kolejnosc(wydawnictwo_ciagle_z_dwoma_autorami, denorms):

    a = list(Wydawnictwo_Ciagle_Autor.objects.all().order_by("kolejnosc"))
    assert len(a) == 2

    denorms.flush()

    x = Rekord.objects.get_original(wydawnictwo_ciagle_z_dwoma_autorami)
    assert "[AUT.] KOWALSKI JAN, NOWAK JAN" in x.opis_bibliograficzny_cache

    k = a[0].kolejnosc
    a[0].kolejnosc = a[1].kolejnosc
    a[1].kolejnosc = k

    a[0].save()
    a[1].save()

    denorms.flush()
    x = Rekord.objects.get_original(wydawnictwo_ciagle_z_dwoma_autorami)
    assert "[AUT.] NOWAK JAN, KOWALSKI JAN" in x.opis_bibliograficzny_cache


@pytest.mark.django_db
def test_rekord_describe_content_type(wydawnictwo_zwarte):
    assert "wydawnictwo" in Rekord.objects.first().describe_content_type


@pytest.mark.django_db
def test_Rekord_get_absolute_url(wydawnictwo_zwarte):
    assert Rekord.objects.first().get_absolute_url().startswith("/")


def test_aktualizacja_rekordu_autora(typy_odpowiedzialnosci, denorms):
    w = baker.make(Wydawnictwo_Ciagle)

    a = baker.make(Autor)
    b = baker.make(Autor)

    j = baker.make(Jednostka)
    r = w.dodaj_autora(a, j, zapisany_jako="Test")

    assert b.pk not in Rekord.objects.all().first().autorzy.all().values_list(
        "autor", flat=True
    )

    r.autor = b
    r.save()

    denorms.flush()

    # czy cache jest odświeżone
    assert b.pk in Rekord.objects.all().first().autorzy.all().values_list(
        "autor", flat=True
    )


@pytest.mark.django_db
def test_prace_autora_z_afiliowanych_jednostek(typy_odpowiedzialnosci):
    a1 = baker.make(Autor, nazwisko="X", imiona="X")
    a2 = baker.make(Autor, nazwisko="Y", imiona="Y")

    nasza = baker.make(Jednostka, skupia_pracownikow=True)
    obca = baker.make(Jednostka, skupia_pracownikow=False)

    wc1 = baker.make(Wydawnictwo_Ciagle, impact_factor=10, rok=2017)
    wc2 = baker.make(Wydawnictwo_Ciagle, impact_factor=10, rok=2017)

    wc1.dodaj_autora(a1, nasza)
    wc1.dodaj_autora(a2, nasza)

    wc2.dodaj_autora(a1, obca, afiliuje=False)
    wc2.dodaj_autora(a2, nasza)

    assert Rekord.objects.prace_autora(a1).count() == 2
    assert Rekord.objects.prace_autora(a2).count() == 2

    assert Rekord.objects.prace_autora_z_afiliowanych_jednostek(a1).count() == 1
    assert Rekord.objects.prace_autora_z_afiliowanych_jednostek(a2).count() == 2


@pytest.mark.django_db
def test_rebuild_ciagle(
    django_assert_max_num_queries, wydawnictwo_ciagle_z_dwoma_autorami, denorms
):
    with django_assert_max_num_queries(40):
        denorms.rebuildall("Wydawnictwo_Ciagle")


@pytest.mark.django_db
def test_rebuild_zwarte(
    django_assert_max_num_queries, wydawnictwo_zwarte_z_autorem, denorms
):
    with django_assert_max_num_queries(45):
        denorms.rebuildall("Wydawnictwo_Zwarte")


@pytest.mark.django_db
def test_rebuild_patent(django_assert_max_num_queries, patent, denorms):
    with django_assert_max_num_queries(40):
        denorms.rebuildall("Patent")
