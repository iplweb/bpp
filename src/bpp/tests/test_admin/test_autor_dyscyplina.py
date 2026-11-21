import pytest
from django.urls import reverse

from bpp.admin.autor_dyscyplina import Autor_DyscyplinaResource
from bpp.models import Autor_Dyscyplina


def test_autor_dyscyplina_resource(autor_jan_kowalski, dyscyplina1):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=2020, dyscyplina_naukowa=dyscyplina1
    )
    assert "Kowalski" in str(Autor_DyscyplinaResource().export())


# FD#569: z listy i z formularza Autor_Dyscyplina da się przejść do autora.


@pytest.fixture
def autor_dyscyplina(autor_jan_kowalski, dyscyplina1):
    return Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=2020, dyscyplina_naukowa=dyscyplina1
    )


@pytest.mark.django_db
def test_autor_dyscyplina_changelist_link_do_autora(admin_client, autor_dyscyplina):
    url_autora = reverse("admin:bpp_autor_change", args=[autor_dyscyplina.autor_id])

    res = admin_client.get(reverse("admin:bpp_autor_dyscyplina_changelist"))

    assert res.status_code == 200
    assert f'href="{url_autora}"' in res.content.decode()


@pytest.mark.django_db
def test_autor_dyscyplina_change_form_link_do_autora(admin_client, autor_dyscyplina):
    url_autora = reverse("admin:bpp_autor_change", args=[autor_dyscyplina.autor_id])

    res = admin_client.get(
        reverse("admin:bpp_autor_dyscyplina_change", args=[autor_dyscyplina.pk])
    )

    assert res.status_code == 200
    assert f'href="{url_autora}"' in res.content.decode()


@pytest.mark.django_db
def test_autor_dyscyplina_add_form_bez_linku_i_zapis_dziala(
    admin_client, autor_jan_kowalski, dyscyplina1
):
    """Formularz dodawania nie ma linku (nie ma jeszcze autora), a pole
    tylko-do-odczytu nie psuje zapisu powiązania."""
    url = reverse("admin:bpp_autor_dyscyplina_add")

    res = admin_client.get(url)
    assert res.status_code == 200
    assert "przejdź do autora" not in res.content.decode()

    res = admin_client.post(
        url,
        {
            "rok": 2021,
            "autor": autor_jan_kowalski.pk,
            "dyscyplina_naukowa": dyscyplina1.pk,
            "procent_dyscypliny": "100.00",
        },
    )
    assert res.status_code == 302, res.content.decode()[:3000]
    assert Autor_Dyscyplina.objects.filter(autor=autor_jan_kowalski, rok=2021).exists()
