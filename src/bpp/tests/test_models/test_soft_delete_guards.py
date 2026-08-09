"""Guardy PROTECT fazy 04 soft-delete.

Dwie warstwy ochrony przed osieroceniem rekordów:

1. FK ``CASCADE`` → ``PROTECT`` na powiązaniach autora i na self-FK rozdziałów
   — obrona przed HARD delete (``hard_delete()``, kaskady ORM).
2. Guard aplikacyjny w miękkim ``delete()`` modeli ``Autor`` i
   ``Wydawnictwo_Zwarte`` — obrona przed SOFT delete, licząca dzieci przez
   ``global_objects``, więc widząca także rekordy w koszu.

Druga warstwa jest konieczna, bo ``on_delete`` żyje wyłącznie w kolektorze
Django dla twardego kasowania — miękkie ``delete()`` w ogóle go nie pyta.
"""

import pytest
from django.db.models import PROTECT, ProtectedError
from model_bakery import baker

from bpp.models import (
    Autor,
    Patent_Autor,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    soft_delete,
)
from bpp.models.soft_delete import raise_if_has_protected_children


@pytest.mark.django_db
def test_raise_if_has_protected_children_przepuszcza_gdy_brak():
    autor = baker.make(Autor)
    # Nie rzuca — brak dzieci w podanych relacjach.
    raise_if_has_protected_children(
        autor,
        [(Wydawnictwo_Ciagle_Autor, "autor"), (Praca_Doktorska, "autor")],
        label="autora",
    )


@pytest.mark.django_db
def test_raise_if_has_protected_children_blokuje_gdy_sa_dzieci():
    autor = baker.make(Autor)
    baker.make(Wydawnictwo_Ciagle_Autor, autor=autor)
    with pytest.raises(ProtectedError):
        raise_if_has_protected_children(
            autor,
            [(Wydawnictwo_Ciagle_Autor, "autor")],
            label="autora",
        )


@pytest.mark.django_db
def test_raise_if_has_protected_children_widzi_dzieci_w_koszu():
    """Sedno guarda: dziecko w koszu NADAL chroni rodzica (spec §3.2).

    Gdyby helper liczył przez ``objects``, autor „cały w koszu" (jego prace
    i autorstwa skasowane kaskadą fazy 02) wyglądałby na pustego i dałby się
    skasować — a wtedy przywrócenie którejkolwiek z tych prac dałoby
    publikację z autorem, którego nie ma.
    """
    autor = baker.make(Autor)
    autorstwo = baker.make(Wydawnictwo_Ciagle_Autor, autor=autor)
    autorstwo.delete()

    assert not Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor).exists()
    assert Wydawnictwo_Ciagle_Autor.global_objects.filter(autor=autor).exists()

    with pytest.raises(ProtectedError):
        raise_if_has_protected_children(
            autor,
            [(Wydawnictwo_Ciagle_Autor, "autor")],
            label="autora",
        )


@pytest.mark.django_db
def test_raise_if_has_protected_children_obsluguje_model_bez_global_objects():
    """Helper musi znosić modele SPOZA soft-delete.

    Lista relacji chronionych obejmuje ``Projekt_Autor`` — zwykły model
    z ``PROTECT``, bez menedżera ``global_objects``. Bez fallbacku na
    ``objects`` helper wywaliłby się ``AttributeError``-em, i to na ścieżce
    kasowania KAŻDEGO autora, nie tylko powiązanego z projektem.
    """
    from bpp.models.projekt import Projekt_Autor

    autor = baker.make(Autor)
    assert not hasattr(Projekt_Autor, "global_objects"), (
        "Projekt_Autor stał się modelem soft-delete — dobierz do tego testu "
        "inny model bez global_objects, inaczej przestaje on czegokolwiek "
        "pilnować"
    )

    # Brak dzieci — helper ma przejść przez model bez global_objects
    # spadając na objects, a nie wywalić się AttributeError-em.
    raise_if_has_protected_children(
        autor,
        [(Projekt_Autor, "autor")],
        label="autora",
    )

    # …a gdy dziecko jest — ma blokować tak samo jak modele soft-delete.
    baker.make(Projekt_Autor, autor=autor)
    with pytest.raises(ProtectedError):
        raise_if_has_protected_children(
            autor,
            [(Projekt_Autor, "autor")],
            label="autora",
        )


@pytest.mark.django_db
def test_raise_if_has_protected_children_komunikat_zawiera_liczbe_i_etykiete(
    monkeypatch,
):
    """Komunikat trafia do operatora — musi mówić, CZEGO nie da się usunąć.

    Liczba w komunikacie idzie z ``count()``, a NIE z długości próbki
    dołączonej do ``ProtectedError``. Próbka jest celowo ograniczona (autor
    z tysiącami prac nie ma ich ładować do pamięci tylko po to, by zgłosić
    błąd), więc gdyby komunikat liczył ją, operator zobaczyłby „20 prac"
    tam, gdzie jest ich pięć tysięcy — i uznałby, że wystarczy odpiąć
    dwadzieścia.

    Limit próbki zbijamy tu do 1, żeby test ROZRÓŻNIAŁ oba źródła liczby.
    Bez tego (3 dzieci, limit 20) obie dają tę samą wartość i test
    przepuszcza podmianę ``ile`` → ``len(probka)``.
    """
    monkeypatch.setattr(soft_delete, "LIMIT_PROBKI_CHRONIONYCH", 1)

    autor = baker.make(Autor, nazwisko="Testowy", imiona="Jan")
    baker.make(Wydawnictwo_Ciagle_Autor, autor=autor, _quantity=3)

    with pytest.raises(ProtectedError) as exc:
        raise_if_has_protected_children(
            autor,
            [(Wydawnictwo_Ciagle_Autor, "autor")],
            label="autora",
        )

    komunikat = str(exc.value)
    assert "autora" in komunikat
    assert "Testowy" in komunikat
    assert "3" in komunikat, (
        "liczba w komunikacie musi pochodzić z count(), nie z uciętej próbki"
    )
    assert len(exc.value.protected_objects) == 1, (
        "próbka dołączona do ProtectedError ma respektować limit"
    )


# --- Warstwa 1: FK CASCADE → PROTECT --------------------------------------
#
# Obrona przed kasowaniem TWARDYM. Miękkie `delete()` tego nie pyta (patrz
# docstring helpera), ale `hard_delete()`, `queryset.hard_delete()` i kaskady
# ORM z innych modeli — owszem. Bez tego flipu twarde skasowanie autora
# zabrałoby ze sobą jego autorstwa i doktorat, a skasowanie książki-matki —
# wszystkie jej rozdziały.


def test_fk_autora_jest_protect():
    for model in (
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
        Patent_Autor,
        Praca_Doktorska,
    ):
        field = model._meta.get_field("autor")
        assert field.remote_field.on_delete is PROTECT, model


def test_fk_autora_habilitacji_nadal_protect():
    """Kontrola: habilitacja była PROTECT już przed fazą 04.

    Faza 03 zamieniła to pole z ``OneToOneField`` na ``ForeignKey``
    (migracja ``bpp/0500`` + warunkowy ``phab_uniq_autor_zywy``) — sam
    ``on_delete`` przetrwał tę zmianę i ma tak zostać.
    """
    field = Praca_Habilitacyjna._meta.get_field("autor")
    assert field.remote_field.on_delete is PROTECT


def test_wydawnictwo_nadrzedne_jest_protect():
    field = Wydawnictwo_Zwarte._meta.get_field("wydawnictwo_nadrzedne")
    assert field.remote_field.on_delete is PROTECT


def test_flip_protect_nie_zmienil_reszty_pola_wydawnictwo_nadrzedne():
    """`related_name`, `null` i `blank` muszą przeżyć flip.

    Zgubienie ``related_name`` przestawiłoby akcesor odwrotny na domyślny
    ``wydawnictwo_zwarte_set`` i po cichu zepsuło każdy kod liczący rozdziały
    — a `on_delete` sam w sobie nadal by się zgadzał, więc test powyżej nic
    by nie zauważył.
    """
    field = Wydawnictwo_Zwarte._meta.get_field("wydawnictwo_nadrzedne")
    assert field.remote_field.related_name == "wydawnictwa_powiazane_set"
    assert field.null is True
    assert field.blank is True
