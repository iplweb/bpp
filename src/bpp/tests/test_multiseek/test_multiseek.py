from django.urls import reverse
from model_bakery import baker as mommy

from bpp.models import Wydawnictwo_Ciagle


def test_multiseek_status_korekty_ukrywanie(
    uczelnia,
    client,
    wydawnictwo_zwarte_przed_korekta,
    wydawnictwo_zwarte_po_korekcie,
    wydawnictwo_zwarte_w_trakcie_korekty,
    statusy_korekt,
    admin_client,
):
    res = client.get(reverse("multiseek:results"))
    assert b"Rezultaty wyszukiwania (3" in res.content

    for elem in ["przed korektą", "w trakcie korekty"]:
        uczelnia.ukryj_status_korekty_set.create(status_korekty=statusy_korekt[elem])

    res = client.get(reverse("multiseek:results"))
    assert b"Rezultaty wyszukiwania (1" in res.content

    res = admin_client.get(reverse("multiseek:results"))
    assert b"Rezultaty wyszukiwania (3" in res.content


def test_multiseek_paging_template(
    uczelnia,
    client,
    admin_client,
):
    for _ in range(100):
        mommy.make(Wydawnictwo_Ciagle)

    res = client.get(reverse("multiseek:results"))
    assert res.status_code == 200
