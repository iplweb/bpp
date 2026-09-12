"""Rejestr wskrzeszeń musi być DOSTĘPNY, inaczej nie spełnia swojej roli.

Zmiana decyzji #14 planu fazy 03 („POMIŃ + ZARAPORTUJ" → „PRZYWRÓĆ + ODNOTUJ")
została uzasadniona tym, że ryzyko nie znika, tylko zostaje przeniesione:
z „nie róbmy tego" na „róbmy, ale zostaw ślad". Całym uzasadnieniem jest więc
ŚLAD — operator, który znajdzie w bazie rekord skasowany przez siebie tydzień
temu, ma gdzie sprawdzić, że wrócił z importu, kiedy i z którego źródła.

Rejestr osiągalny wyłącznie przez ``manage.py shell`` tego nie spełnia.

Dwie rzeczy, które testujemy:

1. **Widoczność w adminie** — i to jako trwały ślad audytowy, którego nie da
   się dopisać ani zmienić z UI. Rejestr, który operator może edytować,
   przestaje być dowodem.
2. **Indeks pod pytanie „czy TEN rekord wrócił?"** — czyli po
   ``(content_type, object_id)``. Sprawdzamy PRAWDZIWY indeks w ``pg_indexes``,
   a nie deklarację w ``Meta``: interesuje nas, czy migracja go założyła.
   Wzorzec z ``bpp/tests/test_soft_delete/test_autor_rekord_index.py``.
"""

import pytest
from django.contrib import admin as django_admin
from django.db import connection
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_api.models import Publication
from pbn_integrator.models import RekordPrzywroconyPrzezImport

TABELA = RekordPrzywroconyPrzezImport._meta.db_table


def _wpis_rejestru():
    from django.contrib.contenttypes.models import ContentType

    publication = baker.make(Publication)
    wc = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication)
    return RekordPrzywroconyPrzezImport.objects.create(
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        object_id=wc.pk,
        pbn_uid=publication,
        zrodlo_importu="articles",
    )


@pytest.mark.django_db
def test_rejestr_ma_indeks_na_content_type_i_object_id():
    """„Czy TEN rekord wrócił?" nie może być seq scanem.

    To jedyne pytanie, jakie operator zada temu rejestrowi wprost — z poziomu
    konkretnej publikacji. Bez indeksu na parze kolumn generic-FK odpowiedź
    wymaga przejrzenia całej tabeli, która rośnie z każdym importem.
    """
    with connection.cursor() as cur:
        cur.execute("SELECT indexdef FROM pg_indexes WHERE tablename = %s", [TABELA])
        indeksy = [wiersz[0] for wiersz in cur.fetchall()]

    assert any("(content_type_id, object_id)" in indexdef for indexdef in indeksy), (
        f"brak indeksu na (content_type_id, object_id) w {TABELA}; są: {indeksy}"
    )


@pytest.mark.django_db
def test_rejestr_jest_zarejestrowany_w_adminie():
    assert RekordPrzywroconyPrzezImport in django_admin.site._registry, (
        "rejestr wskrzeszen nie jest widoczny w adminie — czyli slad, ktorym "
        "uzasadniono zmiane decyzji #14, jest nieosiagalny dla operatora"
    )


@pytest.mark.django_db
def test_changelist_pokazuje_wpis_ze_zrodlem_importu(admin_client):
    wpis = _wpis_rejestru()

    res = admin_client.get(
        reverse("admin:pbn_integrator_rekordprzywroconyprzezimport_changelist")
    )

    assert res.status_code == 200
    tresc = res.content.decode()

    # Asercje po klasach `field-<nazwa>`, którymi Django oznacza KOMÓRKI
    # tabeli. Samo „articles in tresc" byłoby fałszywie zielone: ten łańcuch
    # pojawia się też w bocznym filtrze `list_filter`, więc przechodziłoby
    # nawet po wyrzuceniu kolumny z `list_display` (sprawdzone mutacyjnie).
    assert 'class="field-zrodlo_importu"' in tresc, (
        "changelista nie ma kolumny ze zrodlem importu"
    )
    assert 'class="field-rekord"' in tresc, (
        "changelista nie pokazuje, KTORY rekord wrocil"
    )
    assert str(wpis.rekord) in tresc
    assert wpis.zrodlo_importu in tresc


@pytest.mark.django_db
def test_rejestru_nie_da_sie_dopisac_ani_zmienic_z_admina(admin_client):
    """Ślad audytowy, który operator może edytować, nie jest dowodem.

    Wpisy powstają wyłącznie w kodzie importu (``pbn_integrator/kosz.py``).
    """
    wpis = _wpis_rejestru()
    model_admin = django_admin.site._registry[RekordPrzywroconyPrzezImport]
    request = admin_client.get(
        reverse("admin:pbn_integrator_rekordprzywroconyprzezimport_changelist")
    ).wsgi_request

    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request, wpis)
    assert not model_admin.has_delete_permission(request, wpis)
