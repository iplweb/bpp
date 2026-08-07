"""Wyszukiwanie po podłańcuchu w ``opis_bibliograficzny_cache``.

Trzy miejsca w kolejce PBN filtrują rekordy przez ``fraza in opis.lower()``
na SUROWYM HTML-u. Po dodaniu ``<span lang="…">`` (WCAG 3.1.2) sprawdzamy,
że fraza niesąsiadująca ze znacznikiem nadal znajduje rekord.

UWAGA na kształt gałęzi: w ``list_views`` i ``action_views`` opis jest
sprawdzany w ``elif`` — wyłącznie gdy rekord NIE ma ``tytul_oryginalny``.
Test tworzący rekord z tytułem nigdy w tę gałąź nie trafi i przechodziłby
fałszywie.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_export_queue.models import PBN_Export_Queue
from pbn_export_queue.views.action_views import _get_ids_matching_title
from pbn_export_queue.views.utils import get_record_title

OPIS_ZE_ZNACZNIKIEM = (
    'Kowalski Jan. <span lang="en">Effects of X on Y</span>. '
    "Postępy Higieny 2024, t. 78, s. 112-119."
)


@pytest.mark.django_db
def test_get_record_title_zwraca_opis_ze_znacznikiem(wydawnictwo_ciagle):
    wydawnictwo_ciagle.tytul_oryginalny = ""
    wydawnictwo_ciagle.opis_bibliograficzny_cache = OPIS_ZE_ZNACZNIKIEM

    assert get_record_title(wydawnictwo_ciagle) == OPIS_ZE_ZNACZNIKIEM


@pytest.mark.django_db
def test_get_record_title_woli_tytul_nad_opisem(wydawnictwo_ciagle):
    # Gałąź elif: opis czytany WYŁĄCZNIE gdy brak tytułu oryginalnego.
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł wprost"
    wydawnictwo_ciagle.opis_bibliograficzny_cache = OPIS_ZE_ZNACZNIKIEM

    assert get_record_title(wydawnictwo_ciagle) == "Tytuł wprost"


@pytest.mark.django_db
def test_lista_kolejki_znajduje_rekord_po_opisie(
    admin_client, admin_user, wydawnictwo_ciagle
):
    # Realny filtr widoku (list_views.py: _apply_search_filter /
    # _find_matching_record_ids_by_title) na rekordzie BEZ tytułu
    # oryginalnego — inaczej dopasowanie nigdy nie sięgnie opisu.
    wydawnictwo_ciagle.tytul_oryginalny = ""
    wydawnictwo_ciagle.save()

    # opis_bibliograficzny_cache to pole @denormalized (django-denorm) —
    # zwykłe przypisanie atrybutu + .save() zostaje nadpisane przelicze-
    # niem z szablonu przy save(). .update() na queryset omija sygnał
    # denorm i wymusza rzeczywistą wartość w bazie, dokładnie tę, którą
    # przeczyta widok przez świeży SELECT (item.rekord_do_wysylki).
    Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).update(
        opis_bibliograficzny_cache=OPIS_ZE_ZNACZNIKIEM
    )

    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
    )

    url = reverse("pbn_export_queue:export-queue-list")
    res = admin_client.get(url, {"q": "postępy higieny"})

    assert res.status_code == 200
    assert queue_item in res.context["export_queue_items"]


@pytest.mark.django_db
def test_akcje_kolejki_znajduja_rekord_po_opisie(wydawnictwo_ciagle, admin_user):
    # action_views._get_ids_matching_title (ok. linii 370-396) powiela ten
    # sam wzorzec `fraza in opis.lower()` co list_views, ale zasila widok
    # POST /resend-filtered/ (masowe wznowienie), a nie GET listy. Test
    # bezpośrednio na funkcji filtrującej — przejście przez pełny widok
    # resend_filtered wymagałoby mockowania wywołań PBN dla rekordu, co jest
    # niezwiązane z logiką wyszukiwania po opisie i tylko dublowałoby
    # pokrycie z test_views_actions.py.
    wydawnictwo_ciagle.tytul_oryginalny = ""
    wydawnictwo_ciagle.save()

    Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).update(
        opis_bibliograficzny_cache=OPIS_ZE_ZNACZNIKIEM
    )

    queue_item = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
    )

    ids = _get_ids_matching_title(PBN_Export_Queue.objects.all(), "postępy higieny")

    assert queue_item.pk in ids
