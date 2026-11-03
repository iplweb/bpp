import json

import pytest
from django.contrib.contenttypes.models import ContentType

from bpp.models import (
    Autor_Dyscyplina,
    Cache_Punktacja_Autora,
    Cache_Punktacja_Dyscypliny,
)
from bpp.models.sloty.core import IPunktacjaCacher
from zglos_publikacje.models import Zgloszenie_Publikacji

# Rok z zakresu procedur liczących sloty (bieżący rok bywa poza nim).
ROK_SLOTOW = 2022


def jako_json(wartosc):
    """Krotki z ``serialize()`` -> listy, jak po odczycie z JSONField."""
    return json.loads(json.dumps(wartosc))


def wpisy_cache_punktacji(obj):
    """(autorzy, dyscypliny) z ``bpp_cache_punktacja_*`` dla rekordu."""
    rekord_id = [ContentType.objects.get_for_model(obj).pk, obj.pk]
    autorzy = set(
        Cache_Punktacja_Autora.objects.filter(rekord_id=rekord_id).values_list(
            "autor_id", flat=True
        )
    )
    dyscypliny = set(
        Cache_Punktacja_Dyscypliny.objects.filter(rekord_id=rekord_id).values_list(
            "dyscyplina_id", flat=True
        )
    )
    return autorzy, dyscypliny


@pytest.fixture
def zgloszenie_publikacji(
    typy_odpowiedzialnosci, autor_jan_kowalski, jednostka, rok
) -> Zgloszenie_Publikacji:
    z = Zgloszenie_Publikacji.objects.create(
        tytul_oryginalny="test",
        rok=rok,
        email="foo@bar.pl",
        rodzaj_zglaszanej_publikacji=Zgloszenie_Publikacji.Rodzaje.POZOSTALE,
        strona_www="https://onet.pl/",
    )

    z.zgloszenie_publikacji_autor_set.create(
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        typ_odpowiedzialnosci=typy_odpowiedzialnosci["aut."],
        rok=rok,
    )

    return z


@pytest.fixture
def zgloszenie_publikacji_z_oplata(zgloszenie_publikacji) -> Zgloszenie_Publikacji:
    zgloszenie_publikacji.opl_pub_cost_free = False
    zgloszenie_publikacji.opl_pub_amount = 20000
    zgloszenie_publikacji.opl_pub_research_potential = True
    zgloszenie_publikacji.save()
    return zgloszenie_publikacji


@pytest.fixture
def rekord_z_dyscyplinami(
    request,
    uczelnia,
    jednostka,
    autor_jan_nowak,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    rodzaj_autora_n,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    wydawca,
):
    """Rekord (ciągły/zwarty) z dwoma autorami w dwóch dyscyplinach, dla
    którego sloty DAJĄ się policzyć (``canAdapt()``) -- inaczej testy
    tabel cache przechodziłyby „na pusto"."""
    nazwa = request.param
    obj = request.getfixturevalue(nazwa)

    if nazwa == "patent":
        # Patenty nie mają slotów (ISlot -> CannotAdapt): cache zostaje pusty,
        # ale ścieżka denorm/admin jest ta sama.
        obj.dodaj_autora(autor_jan_nowak, jednostka)
        assert not IPunktacjaCacher(obj).canAdapt()
        return obj

    for autor, dyscyplina in (
        (autor_jan_nowak, dyscyplina1),
        (autor_jan_kowalski, dyscyplina2),
    ):
        Autor_Dyscyplina.objects.create(
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            rok=ROK_SLOTOW,
            rodzaj_autora=rodzaj_autora_n,
        )

    obj.rok = ROK_SLOTOW
    obj.punkty_kbn = 20
    if nazwa == "wydawnictwo_zwarte":
        # książka / autorstwo / wydawca spoza wykazu
        obj.charakter_formalny = charaktery_formalne["KSP"]
        obj.wydawca = wydawca
    obj.save()

    obj.dodaj_autora(autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1)
    obj.dodaj_autora(autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2)

    obj.przelicz_punkty_dyscyplin()
    # Kolumna JSON = stan z dwoma autorami (zapis z pominięciem pre_save
    # innych pól nie jest tu potrzebny -- update() nie woła pre_save).
    type(obj).objects.filter(pk=obj.pk).update(
        **{"cached_punkty_dyscyplin": jako_json(IPunktacjaCacher(obj).serialize())}
    )
    obj.refresh_from_db()

    assert IPunktacjaCacher(obj).canAdapt()
    assert wpisy_cache_punktacji(obj) == (
        {autor_jan_nowak.pk, autor_jan_kowalski.pk},
        {dyscyplina1.pk, dyscyplina2.pk},
    )
    return obj
