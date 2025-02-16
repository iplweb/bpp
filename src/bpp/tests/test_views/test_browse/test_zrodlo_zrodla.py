from django.urls import reverse


def test_zrodlo_browser_pokazuj_zrodla_bez_prac(client, zrodlo, uczelnia):
    uczelnia.pokazuj_zrodla_bez_prac_w_przegladaniu_danych = True
    uczelnia.save()

    res = client.get(reverse("bpp:browse_zrodla"))
    assert zrodlo.nazwa in res.rendered_content


def test_zrodlo_browser_nie_pokazuj_zrodel_bez_prac(client, zrodlo, uczelnia):

    uczelnia.pokazuj_zrodla_bez_prac_w_przegladaniu_danych = False
    uczelnia.save()

    res = client.get(reverse("bpp:browse_zrodla"))
    assert zrodlo.nazwa not in str(res.rendered_content)
