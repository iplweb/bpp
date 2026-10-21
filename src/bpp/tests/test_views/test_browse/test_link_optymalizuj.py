"""Rollbar #5364: link „Optymalizuj" na stronie rekordu był pokazywany
każdemu zalogowanemu, a widok optymalizacji wymaga uprawnień redaktorskich
(``moze_wprowadzac_dane``) — zwykły użytkownik dostawał 403.
"""

import pytest
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Cache_Punktacja_Autora


@pytest.fixture
def strona_rekordu_z_tabela_slotow(
    uczelnia, wydawnictwo_ciagle, autor_jan_kowalski, jednostka, dyscyplina1
):
    uczelnia.pokazuj_tabele_slotow_na_stronie_rekordu = "always"
    uczelnia.save()

    ct = ContentType.objects.get_for_model(wydawnictwo_ciagle)
    Cache_Punktacja_Autora.objects.create(
        rekord_id=[ct.pk, wydawnictwo_ciagle.pk],
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        dyscyplina=dyscyplina1,
        pkdaut=50,
        slot=1,
    )
    return (
        reverse("bpp:browse_praca", args=(ct.pk, wydawnictwo_ciagle.pk)),
        reverse(
            "ewaluacja_optymalizuj_publikacje:optymalizuj",
            args=(wydawnictwo_ciagle.slug,),
        ),
    )


def _link_widoczny(client, strona):
    url_rekordu, url_optymalizuj = strona
    res = client.get(url_rekordu, follow=True)
    assert res.status_code == 200
    tresc = res.content.decode()
    # Bezpiecznik: tabela slotów musi się wyrenderować, inaczej asercje
    # o braku linku przechodziłyby na pusto.
    assert "Punkty i sloty autorów" in tresc
    return url_optymalizuj in tresc


@pytest.mark.django_db
def test_anonim_nie_widzi_linku_optymalizuj(client, strona_rekordu_z_tabela_slotow):
    assert not _link_widoczny(client, strona_rekordu_z_tabela_slotow)


@pytest.mark.django_db
def test_zwykly_zalogowany_nie_widzi_linku_optymalizuj(
    client, strona_rekordu_z_tabela_slotow
):
    client.force_login(baker.make("bpp.BppUser", is_superuser=False))
    assert not _link_widoczny(client, strona_rekordu_z_tabela_slotow)


@pytest.mark.django_db
def test_redaktor_widzi_link_optymalizuj(client, strona_rekordu_z_tabela_slotow):
    user = baker.make("bpp.BppUser", is_superuser=False)
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grupa)
    client.force_login(user)
    assert _link_widoczny(client, strona_rekordu_z_tabela_slotow)


@pytest.mark.django_db
def test_superuser_widzi_link_optymalizuj(admin_client, strona_rekordu_z_tabela_slotow):
    assert _link_widoczny(admin_client, strona_rekordu_z_tabela_slotow)
