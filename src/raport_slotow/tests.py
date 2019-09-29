from django.urls import reverse

from bpp.models import Cache_Punktacja_Autora, Cache_Punktacja_Autora_Query, Rekord


def test_raport_slotow_formularz(admin_client):
    res = admin_client.get(reverse("raport_slotow:index"))
    assert res.status_code == 200


def test_raport_slotow_autor_brak_danych(admin_client, autor_jan_kowalski, rok):
    res = admin_client.get(reverse(
        "raport_slotow:raport",
        kwargs={"autor": autor_jan_kowalski.slug,
                "od_roku": rok,
                "do_roku": rok,
                }
    ))
    assert res.status_code == 200
    assert "Brak danych" in res.rendered_content

def test_raport_slotow_autor_sa_dane(admin_client, autor_jan_kowalski, dyscyplina1, wydawnictwo_ciagle_z_autorem, rok):
    Cache_Punktacja_Autora_Query.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina=dyscyplina1,
        pkdaut=50,
        slot=20,
        rekord=Rekord.objects.first()
    )

    res = admin_client.get(reverse(
        "raport_slotow:raport",
        kwargs={"autor": autor_jan_kowalski.slug,
                "od_roku": rok,
                "do_roku": rok,
                }
    ))
    assert res.status_code == 200
    assert "Brak danych" not in res.rendered_content

