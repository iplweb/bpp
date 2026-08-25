"""Faza 07: kosz w adminie — filtr, przywracanie, trwałe usuwanie, powód.

KONTRAKT PARAMETRU FILTRA: ``?is_deleted=true`` pokazuje WYŁĄCZNIE kosz,
``?is_deleted=all`` żywe razem z koszem, brak parametru — tylko żywe. Ta
sama semantyka, co w pakietowym ``SoftDeleteFilter`` (``'true'`` mapuje
tam na ``deleted_at__isnull=False``), więc parametr w URL-u nie kłamie.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_changelist_domyslnie_ukrywa_kosz(superuser_client):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url)
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Żywa praca" in content
    assert "Praca w koszu" not in content


@pytest.mark.django_db
def test_filtr_pokazuje_wylacznie_kosz(superuser_client):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url, {"is_deleted": "true"})
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Praca w koszu" in content
    assert "Żywa praca" not in content


@pytest.mark.django_db
def test_filtr_wszystkie_pokazuje_zywe_i_kosz(superuser_client):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url, {"is_deleted": "all"})
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Praca w koszu" in content
    assert "Żywa praca" in content


@pytest.mark.django_db
def test_changeform_otwiera_skasowany_rekord(superuser_client):
    """Bez ``global_objects`` w ``get_queryset`` admin dawałby 302/404 —
    a bez otwarcia rekordu nie ma jak go przywrócić ani obejrzeć."""
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=[skasowany.pk])
    resp = superuser_client.get(url)

    assert resp.status_code == 200


def _log(model, pk, akcja):
    """Najnowszy wpis ``SoftDeleteLog`` dla konkretnego rekordu.

    Filtr po ``content_type`` jest istotny: ``object_id`` nie jest unikalne
    globalnie, a kaskada fazy 02 loguje przy okazji wiersze ``*_Autor``,
    ktore z latwoscia trafiaja na te sama wartosc ``pk``.
    """
    from django.contrib.contenttypes.models import ContentType

    from bpp.models import SoftDeleteLog

    return (
        SoftDeleteLog.objects.filter(
            content_type=ContentType.objects.get_for_model(model),
            object_id=pk,
            akcja=akcja,
        )
        .order_by("-timestamp", "-pk")
        .first()
    )


@pytest.mark.django_db
def test_delete_w_adminie_soft_deletuje_i_zapisuje_usera(superuser, superuser_client):
    """Przycisk „Usuń" na changeformie = kosz, nie fizyczne skasowanie."""
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Do kosza")
    pk = obj.pk
    url = reverse("admin:bpp_wydawnictwo_ciagle_delete", args=[pk])

    assert superuser_client.get(url).status_code == 200

    resp = superuser_client.post(url, {"post": "yes"})
    assert resp.status_code == 302

    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    assert Wydawnictwo_Ciagle.global_objects.get(pk=pk).deleted_at is not None

    wpis = _log(Wydawnictwo_Ciagle, pk, "delete")
    assert wpis is not None
    assert wpis.user_id == superuser.pk


@pytest.mark.django_db
def test_akcja_przywroc_dziala_i_zapisuje_usera(superuser, superuser_client):
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Wraca z kosza")
    pk = obj.pk
    obj.delete(reason="test")
    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()

    # Akcja dziala na tym, co widac na liscie — a kosz widac dopiero pod
    # filtrem. Django POST-uje formularz akcji na biezacy URL RAZEM z
    # query stringiem, wiec tak wyglada realny przeplyw operatora.
    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist") + "?is_deleted=true"
    resp = superuser_client.post(
        url,
        {"action": "przywroc_zaznaczone", "_selected_action": [str(pk)]},
    )
    assert resp.status_code in (200, 302)

    assert Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    assert Wydawnictwo_Ciagle.global_objects.get(pk=pk).deleted_at is None

    wpis = _log(Wydawnictwo_Ciagle, pk, "restore")
    assert wpis is not None
    assert wpis.user_id == superuser.pk


@pytest.mark.django_db
def test_usun_trwale_dostepne_dla_superusera(superuser, superuser_client):
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Do trwałego usunięcia")
    pk = obj.pk
    obj.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist") + "?is_deleted=true"
    assert b"usun_trwale_zaznaczone" in superuser_client.get(url).content

    resp = superuser_client.post(
        url,
        {"action": "usun_trwale_zaznaczone", "_selected_action": [str(pk)]},
    )
    assert resp.status_code in (200, 302)
    assert not Wydawnictwo_Ciagle.global_objects.filter(pk=pk).exists()

    # Rekord zniknal fizycznie, wiec wpis audytu jest jedynym sladem, ze
    # istnial — i ma nosic, KTO go skasowal.
    wpis = _log(Wydawnictwo_Ciagle, pk, "hard_delete")
    assert wpis is not None
    assert wpis.user_id == superuser.pk


@pytest.mark.django_db
def test_usun_trwale_niedostepne_dla_staff(staff_client):
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Próba przez staff")
    pk = obj.pk
    obj.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist") + "?is_deleted=true"
    assert b"usun_trwale_zaznaczone" not in staff_client.get(url).content

    # Wymuszony POST tez nie usuwa trwale — akcji nie ma w get_actions,
    # wiec Django odrzuca ja jako niedozwolony wybor.
    resp = staff_client.post(
        url,
        {"action": "usun_trwale_zaznaczone", "_selected_action": [str(pk)]},
    )
    assert resp.status_code in (200, 302, 403)
    assert Wydawnictwo_Ciagle.global_objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_usun_trwale_pomija_rekordy_spoza_kosza(superuser_client):
    """Trwale kasujemy WYLACZNIE z kosza.

    ``Cache_Punktacja_*`` nie ma FK do publikacji, wiec sprzata ja dopiero
    receiver ``post_soft_delete``. Twarde skasowanie rekordu zywego
    zostawiloby wiersze punktacji wskazujace na nieistniejacy rekord.
    """
    zywy = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywy, nie do kosza")
    pk = zywy.pk

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist") + "?is_deleted=all"
    resp = superuser_client.post(
        url,
        {"action": "usun_trwale_zaznaczone", "_selected_action": [str(pk)]},
        follow=True,
    )
    assert resp.status_code == 200
    assert Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    assert "Pominięto rekordów spoza kosza: 1" in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_akcja_usun_do_kosza_z_powodem_trafia_do_logu(superuser, superuser_client):
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Z powodem")
    pk = obj.pk
    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")

    # Krok 1: wybor akcji bez potwierdzenia -> strona posrednia z polem.
    resp1 = superuser_client.post(
        url,
        {"action": "usun_do_kosza", "_selected_action": [str(pk)]},
    )
    assert resp1.status_code == 200
    tresc = resp1.content.decode("utf-8")
    assert 'name="powod"' in tresc
    assert "Z powodem" in tresc
    # Nic sie jeszcze nie stalo:
    assert Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()

    # Krok 2: potwierdzenie z powodem.
    resp2 = superuser_client.post(
        url,
        {
            "action": "usun_do_kosza",
            "_selected_action": [str(pk)],
            "powod_potwierdzony": "1",
            "powod": "Duplikat rekordu",
        },
    )
    assert resp2.status_code in (200, 302)

    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    wpis = _log(Wydawnictwo_Ciagle, pk, "delete")
    assert wpis is not None
    assert wpis.powod == "Duplikat rekordu"
    assert wpis.user_id == superuser.pk


@pytest.mark.django_db
def test_powod_dziedziczy_kaskada_na_autorstwa(superuser, superuser_client):
    """Powod i user maja objac takze wiersze ``*_Autor`` kasowane kaskada.

    Kontekst fazy 06 obejmuje CALE cialo ``delete()``, wiec kaskada
    dziedziczy atrybucje rodzica — bez tego wpisy autorstw byłyby niczyje
    mimo swiadomej decyzji operatora.
    """
    from bpp.models import Wydawnictwo_Ciagle_Autor

    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Z autorem")
    autorstwo = baker.make(Wydawnictwo_Ciagle_Autor, rekord=obj)
    pk_autorstwa = autorstwo.pk

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    superuser_client.post(
        url,
        {
            "action": "usun_do_kosza",
            "_selected_action": [str(obj.pk)],
            "powod_potwierdzony": "1",
            "powod": "Wycofanie calego rekordu",
        },
    )

    wpis = _log(Wydawnictwo_Ciagle_Autor, pk_autorstwa, "delete")
    assert wpis is not None
    assert wpis.powod == "Wycofanie calego rekordu"
    assert wpis.user_id == superuser.pk


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_name,admin_slug",
    [
        ("Wydawnictwo_Zwarte", "wydawnictwo_zwarte"),
        ("Patent", "patent"),
        ("Praca_Doktorska", "praca_doktorska"),
        ("Praca_Habilitacyjna", "praca_habilitacyjna"),
        ("Autor", "autor"),
    ],
)
def test_kosz_w_adminie_dla_kazdego_modelu(model_name, admin_slug, superuser_client):
    import bpp.models

    model = getattr(bpp.models, model_name)
    obj = baker.make(model)
    pk = obj.pk
    obj.delete(reason="test")

    # Changeform otwiera skasowany rekord (global_objects):
    url_change = reverse(f"admin:bpp_{admin_slug}_change", args=[pk])
    assert superuser_client.get(url_change).status_code == 200

    # Filtr kosza pokazuje skasowany, a akcje kosza sa oferowane:
    url_list = reverse(f"admin:bpp_{admin_slug}_changelist") + "?is_deleted=true"
    resp = superuser_client.get(url_list)
    assert resp.status_code == 200
    assert b"przywroc_zaznaczone" in resp.content
    assert b"usun_trwale_zaznaczone" in resp.content
    assert b"usun_do_kosza" in resp.content

    # Przywracanie dziala:
    resp_r = superuser_client.post(
        url_list,
        {"action": "przywroc_zaznaczone", "_selected_action": [str(pk)]},
    )
    assert resp_r.status_code in (200, 302)
    assert model.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_mixin_nie_znosi_zawezenia_do_uczelni_w_autoradmin(staff_user, rf):
    """REGRESJA MRO: kosz nie ma prawa poszerzyc widoku poza wlasna uczelnie.

    Plan fazy 07 kazal wpinac ``BppSoftDeleteAdminMixin`` jako PIERWSZY.
    Jego ``get_queryset`` nie woła ``super()`` (podmienia manager bazowy),
    wiec z pierwszej pozycji uciolby cały łańcuch — w tym
    ``SiteFilteredAdminMixin.get_queryset`` w ``AutorAdmin``, zawezajace
    widok nie-superusera do jego uczelni (FD#390). Personel uczelni A
    zobaczylby (i skasowal) autorow uczelni B.

    Ten test pilnuje, ze mixin stoi na koncu MRO — czyli ze jest PODSTAWA
    lancucha, a nie jego obcieciem.
    """
    from django.contrib.admin.sites import site

    from bpp.models import Autor, Autor_Jednostka, Jednostka, Uczelnia

    uczelnia_a = baker.make(Uczelnia, nazwa="Uczelnia A", skrot="UA")
    uczelnia_b = baker.make(Uczelnia, nazwa="Uczelnia B", skrot="UB")
    jednostka_a = baker.make(Jednostka, uczelnia=uczelnia_a)
    jednostka_b = baker.make(Jednostka, uczelnia=uczelnia_b)

    autor_a = baker.make(Autor)
    baker.make(Autor_Jednostka, autor=autor_a, jednostka=jednostka_a)
    autor_b = baker.make(Autor)
    baker.make(Autor_Jednostka, autor=autor_b, jednostka=jednostka_b)
    autor_b_w_koszu = baker.make(Autor)
    baker.make(Autor_Jednostka, autor=autor_b_w_koszu, jednostka=jednostka_b)
    autor_b_w_koszu.delete(reason="test")

    request = rf.get("/admin/bpp/autor/")
    request.user = staff_user
    request._uczelnia = uczelnia_b

    qs = site._registry[Autor].get_queryset(request)
    widoczne = set(qs.values_list("pk", flat=True))

    assert autor_b.pk in widoczne, "wlasna uczelnia musi byc widoczna"
    assert autor_b_w_koszu.pk in widoczne, "kosz wlasnej uczelni tez (global_objects)"
    assert autor_a.pk not in widoczne, "CUDZA uczelnia NIE MOZE byc widoczna"
