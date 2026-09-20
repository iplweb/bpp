"""``ostatnio_zmieniony`` przy soft-delete (kontrakt PINNED, faza 01).

Soft-delete JEST modyfikacją rekordu i tak musi wyglądać dla każdego
konsumenta przyrostowego (OAI-PMH, CERIF, REST API). Pakiet
``django-soft-delete`` zapisuje przez
``save(update_fields=['deleted_at','restored_at','transaction_id'])``,
a Django woła ``Field.pre_save()`` WYŁĄCZNIE dla pól obecnych w
``update_fields`` — więc bez naszej interwencji ``auto_now`` na
``ostatnio_zmieniony`` się nie odpala i znacznik czasu stoi w miejscu.

Praktyczny zysk z bumpa: lista nagrobków „co skasowano od daty X" to
``Model.deleted_objects.filter(ostatnio_zmieniony__gte=X)`` — bez
czekania na ``SoftDeleteLog`` z fazy 06.
"""

import datetime

import pytest
from django.utils import timezone

from bpp.models.soft_delete import dopisz_znacznik_zmiany
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor


def _znacznik(pk):
    """Wartość ``ostatnio_zmieniony`` PROSTO Z BAZY (nie z instancji w
    pamięci) — inaczej test mógłby przejść na zaktualizowanym atrybucie
    Pythona przy niezapisanej kolumnie."""
    return Wydawnictwo_Ciagle_Autor.global_objects.values_list(
        "ostatnio_zmieniony", flat=True
    ).get(pk=pk)


def _cofnij_znacznik(pk, o_ile=datetime.timedelta(hours=1)):
    """Cofa ``ostatnio_zmieniony`` w bazie o zadany czas, omijając
    ``auto_now`` (bulk ``update()`` nie woła ``pre_save``). Dzięki temu
    asercja „wzrósł" nie zależy od rozdzielczości zegara."""
    stary = timezone.now() - o_ile
    # Gate z BppSoftDeleteQuerySet blokuje wyłącznie deleted_at/restored_at.
    Wydawnictwo_Ciagle_Autor.global_objects.filter(pk=pk).update(
        ostatnio_zmieniony=stary
    )
    return stary


@pytest.mark.django_db
def test_soft_delete_bumpuje_ostatnio_zmieniony(wydawnictwo_ciagle_z_autorem):
    """delete() (soft) MUSI podbić ``ostatnio_zmieniony`` wiersza.

    Wyrocznia: gdyby override ``save()`` w ``BppAutorstwoSoftDeleteMixin``
    zniknął, ``update_fields`` pakietu nie zawierałoby
    ``ostatnio_zmieniony``, ``auto_now`` by nie wystrzeliło i znacznik
    zostałby na cofniętej wartości.
    """
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    stary = _cofnij_znacznik(wca.pk)

    Wydawnictwo_Ciagle_Autor.objects.get(pk=wca.pk).delete()

    assert _znacznik(wca.pk) > stary


@pytest.mark.django_db
def test_restore_bumpuje_ostatnio_zmieniony(wydawnictwo_ciagle_z_autorem):
    """restore() też jest modyfikacją — i też MUSI podbić znacznik."""
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    Wydawnictwo_Ciagle_Autor.objects.get(pk=wca.pk).delete()

    po_delete = _cofnij_znacznik(wca.pk)

    Wydawnictwo_Ciagle_Autor.global_objects.get(pk=wca.pk).restore()

    assert _znacznik(wca.pk) > po_delete


@pytest.mark.django_db
def test_nagrobki_odpytywalne_po_ostatnio_zmieniony(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    """Podstawa nagrobków dla harvestu przyrostowego:
    ``deleted_objects.filter(ostatnio_zmieniony__gte=okno)`` zwraca to, co
    skasowano W OKNIE — i nic więcej.

    Wyrocznia: bez bumpa skasowany wiersz miałby znacznik sprzed okna i
    wypadłby z wyniku (pierwsza asercja). Gdyby z kolei bump wyciekał na
    wiersze nietknięte, upadłaby asercja o liczności.
    """
    wc = wydawnictwo_ciagle_z_dwoma_autorami
    pierwszy, drugi = wc.autorzy_set.all()[:2]

    # Oba wiersze „stare"; skasowany dostanie świeży znacznik od delete().
    _cofnij_znacznik(pierwszy.pk)
    _cofnij_znacznik(drugi.pk)

    okno_od = timezone.now()
    Wydawnictwo_Ciagle_Autor.objects.get(pk=pierwszy.pk).delete()

    nagrobki = Wydawnictwo_Ciagle_Autor.deleted_objects.filter(
        ostatnio_zmieniony__gte=okno_od
    )
    assert list(nagrobki.values_list("pk", flat=True)) == [pierwszy.pk]

    # Nietknięty wiersz nie udaje nagrobka ani nie dostał bumpa.
    assert not Wydawnictwo_Ciagle_Autor.deleted_objects.filter(pk=drugi.pk).exists()
    assert _znacznik(drugi.pk) < okno_od


def test_dopisz_znacznik_zmiany_model_bez_pola():
    """Faza 04 obejmie ``Autor``; helper nie może zakładać, że pole
    ``ostatnio_zmieniony`` w ogóle istnieje na modelu.

    ``Element_Repozytorium`` jest ``SoftDeleteModel`` i NIE ma tego pola —
    helper musi oddać ``update_fields`` bez zmian (a nie rzucić
    ``FieldDoesNotExist`` ani dopisać nieistniejącej kolumny, co
    wywaliłoby ``save()`` na ``ValueError``).
    """
    from bpp.models.repozytorium import Element_Repozytorium

    obj = Element_Repozytorium()
    pola = ["deleted_at", "restored_at", "transaction_id"]
    assert dopisz_znacznik_zmiany(obj, pola) == pola


def test_dopisz_znacznik_zmiany_nie_rusza_zwyklego_zapisu():
    """Zwykły ``save(update_fields=['kolejnosc'])`` NIE jest soft-deletem —
    helper nie ma prawa dokładać tam znacznika (auto_now i tak zadziała
    dopiero gdy pole jest w update_fields; podbijanie go przy KAŻDYM
    częściowym zapisie zmieniłoby semantykę poza soft-deletem)."""
    obj = Wydawnictwo_Ciagle_Autor()
    assert dopisz_znacznik_zmiany(obj, ["kolejnosc"]) == ["kolejnosc"]
    # ... a pełny zapis (update_fields=None) auto_now obsługuje sam.
    assert dopisz_znacznik_zmiany(obj, None) is None


@pytest.mark.django_db
def test_a2_soft_delete_autorstwa_a_znacznik_publikacji(
    denorms, wydawnictwo_ciagle_z_dwoma_autorami
):
    """ZADANIE A2 — stan PRZYPIĘTY, nie postulat.

    Pytanie: czy soft-delete *autorstwa* podbija ``ostatnio_zmieniony``
    PUBLIKACJI (pośrednio, przez przeliczenie denormem
    ``opis_bibliograficzny_cache``)?

    Odpowiedź: NIE. BPP ma ``DENORM_DISABLE_AUTOTIME_DURING_FLUSH = True``
    (``src/django_bpp/settings/base.py``), przez co
    ``denorm.denorms._build_save_kwargs()`` buduje ``update_fields``
    JAWNIE WYKLUCZAJĄCE pola ``auto_now``. Flush denorma nigdy nie
    dotyka ``ostatnio_zmieniony`` publikacji.

    To NIE jest regresja fazy 01 — dokładnie tak samo zachowuje się
    hard-delete autorstwa na ``dev``. Test przypina fakt, żeby zmiana
    (celowa albo przypadkowa) była widoczna.
    """
    wc = wydawnictwo_ciagle_z_dwoma_autorami
    denorms.flush()

    def _stan_publikacji():
        return Wydawnictwo_Ciagle.objects.values_list(
            "ostatnio_zmieniony",
            "opis_bibliograficzny_zapisani_autorzy_cache",
        ).get(pk=wc.pk)

    stary = timezone.now() - datetime.timedelta(hours=1)
    Wydawnictwo_Ciagle.objects.filter(pk=wc.pk).update(ostatnio_zmieniony=stary)
    _, opis_przed = _stan_publikacji()

    wca = wc.autorzy_set.first()
    Wydawnictwo_Ciagle_Autor.objects.get(pk=wca.pk).delete()
    denorms.flush()

    znacznik_po, opis_po = _stan_publikacji()

    # Kontrola pozytywna: denorm NAPRAWDĘ przeliczył publikację (skasowany
    # autor wypadł z opisu). Bez tej asercji test przechodziłby także w
    # scenariuszu „denorm w ogóle nie zauważył soft-delete", a to byłoby
    # zupełnie inne (i groźniejsze) znalezisko.
    assert opis_po != opis_przed, (
        "Denorm nie przeliczył publikacji po soft-delete autorstwa — "
        "to inny problem niż A2, patrz denorm_always_only na *_Autor."
    )

    # ... a mimo zapisu publikacji znacznik NIE drgnął.
    assert znacznik_po == stary, (
        "Znacznik publikacji zmienił się — zachowanie denorma/auto_now "
        "uległo zmianie; zweryfikuj wnioski A2 przed zmianą tego testu."
    )
