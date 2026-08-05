"""Testy unikalności trójki FK w ``PublikacjaInstytucji``.

Bug: ``zapisz_publikacje_instytucji`` (``pbn_integrator``) robi
``get_or_create`` po (``institutionId``, ``publicationId``, ``insPersonId``),
a na tej trójce nie było żadnego unikalnego constraintu. Import PBN biegnie
wielowątkowo (``pobierz_mongodb(use_threads=True)``), więc dwa wątki na tej
samej trójce **cicho** tworzyły dwa wiersze — bez wyjątku, bez logu. Efekt:
zawyżone liczby powiązań publikacja-instytucja-osoba, narastające z każdym
importem.

Uwaga o nullach: wszystkie trzy FK w trójce są NOT NULL (brak ``null=True``
w modelu), więc zwykły ``UniqueConstraint`` wystarcza — nie ma problemu
„NULL-e są w indeksie unikalnym rozróżnialne", który wymagałby dodatkowego
indeksu częściowego.
"""

import importlib

import pytest
from django.apps import apps as django_apps
from django.db import IntegrityError, connection, transaction
from django.db.models.query import QuerySet
from model_bakery import baker

from pbn_api.models import Institution, Publication, Scientist
from pbn_api.models.publikacja_instytucji import PublikacjaInstytucji

MIGRACJA = importlib.import_module(
    "pbn_api.migrations.0078_deduplikacja_publikacji_instytucji"
)

NAZWA_CONSTRAINTU = "pbn_api_publikacjainstytucji_trojka_unikalna"


@pytest.fixture
def trojka(db):
    return {
        "institutionId": baker.make(Institution),
        "publicationId": baker.make(Publication),
        "insPersonId": baker.make(Scientist),
    }


def _zdejmij_constraint_unikalnosci():
    """Zdejmuje unikalny constraint, żeby dało się WYPRODUKOWAĆ duplikaty.

    PostgreSQL wykonuje DDL transakcyjnie, więc rollback testu przywraca
    constraint — nie zostawiamy po sobie zmienionego schematu.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE pbn_api_publikacjainstytucji "
            f'DROP CONSTRAINT IF EXISTS "{NAZWA_CONSTRAINTU}"'
        )


@pytest.mark.django_db
def test_baza_odrzuca_duplikat_trojki(trojka):
    """Constraint na trójce FK faktycznie działa w bazie."""
    PublikacjaInstytucji.objects.create(**trojka)

    with pytest.raises(IntegrityError), transaction.atomic():
        PublikacjaInstytucji.objects.create(**trojka)


@pytest.mark.django_db
def test_wszystkie_trzy_fk_sa_not_null():
    """Gdyby któryś FK stał się nullowalny, sam UniqueConstraint przestałby
    wystarczać (NULL-e są w indeksie unikalnym wzajemnie rozróżnialne)."""
    for nazwa in ("insPersonId", "institutionId", "publicationId"):
        assert not PublikacjaInstytucji._meta.get_field(nazwa).null, nazwa


@pytest.mark.django_db
def test_ta_sama_publikacja_i_instytucja_ale_inna_osoba_jest_dozwolona(trojka):
    """Constraint obejmuje CAŁĄ trójkę, nie samą parę publikacja+instytucja."""
    PublikacjaInstytucji.objects.create(**trojka)
    PublikacjaInstytucji.objects.create(
        institutionId=trojka["institutionId"],
        publicationId=trojka["publicationId"],
        insPersonId=baker.make(Scientist),
    )

    assert (
        PublikacjaInstytucji.objects.filter(
            publicationId=trojka["publicationId"]
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_get_or_create_przezywa_przegrany_wyscig(trojka, monkeypatch):
    """Constraint NIE wywala importu, gdy równoległy wątek zdążył pierwszy.

    Django ``get_or_create`` sam implementuje wzorzec
    ``_update_or_create_odporne_na_wyscig``: ``create`` idzie w savepoint
    (``transaction.atomic``), a ``IntegrityError`` jest domykany ponownym
    ``get``. Dlatego gorąca ścieżka w ``zapisz_publikacje_instytucji`` NIE
    wymaga własnej obsługi ``IntegrityError`` — ten test tego pilnuje.

    Symulacja przegranego wyścigu: wiersz JUŻ jest w bazie, ale pierwszy
    ``get`` (ten sprzed ``create``) udaje, że go nie widzi.
    """
    istniejacy = PublikacjaInstytucji.objects.create(**trojka)

    prawdziwy_get = QuerySet.get
    wywolania = {"ile": 0}

    def get_slepy_za_pierwszym_razem(self, *args, **kwargs):
        if self.model is PublikacjaInstytucji:
            wywolania["ile"] += 1
            if wywolania["ile"] == 1:
                raise PublikacjaInstytucji.DoesNotExist()
        return prawdziwy_get(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "get", get_slepy_za_pierwszym_razem)

    rec, utworzony = PublikacjaInstytucji.objects.get_or_create(
        institutionId_id=trojka["institutionId"].pk,
        publicationId_id=trojka["publicationId"].pk,
        insPersonId_id=trojka["insPersonId"].pk,
    )

    assert wywolania["ile"] == 2, "IntegrityError nie został domknięty przez get()"
    assert not utworzony
    assert rec.pk == istniejacy.pk
    assert PublikacjaInstytucji.objects.count() == 1


@pytest.mark.django_db
def test_migracja_usuwa_duplikaty_zostawiajac_najnizszy_pk(trojka):
    """Dedup zostawia po jednym wierszu z grupy — ten o najniższym pk."""
    _zdejmij_constraint_unikalnosci()

    zostaje = PublikacjaInstytucji.objects.create(**trojka, publicationYear=2020)
    duplikat_a = PublikacjaInstytucji.objects.create(**trojka, publicationYear=2021)
    duplikat_b = PublikacjaInstytucji.objects.create(**trojka, publicationYear=2022)
    assert duplikat_a.pk > zostaje.pk and duplikat_b.pk > duplikat_a.pk

    # wiersz spoza grupy duplikatów — nie wolno go ruszyć
    nietkniety = PublikacjaInstytucji.objects.create(
        institutionId=trojka["institutionId"],
        publicationId=trojka["publicationId"],
        insPersonId=baker.make(Scientist),
    )

    MIGRACJA.deduplikuj(django_apps, None)

    assert PublikacjaInstytucji.objects.count() == 2
    assert PublikacjaInstytucji.objects.filter(pk=zostaje.pk).exists()
    assert PublikacjaInstytucji.objects.filter(pk=nietkniety.pk).exists()
    assert not PublikacjaInstytucji.objects.filter(
        pk__in=[duplikat_a.pk, duplikat_b.pk]
    ).exists()


@pytest.mark.django_db
def test_migracja_jest_idempotentna_na_bazie_bez_duplikatow(trojka):
    """Dedup na bazie BEZ duplikatów niczego nie rusza."""
    PublikacjaInstytucji.objects.create(**trojka)
    przed = set(PublikacjaInstytucji.objects.values_list("pk", flat=True))

    MIGRACJA.deduplikuj(django_apps, None)

    assert set(PublikacjaInstytucji.objects.values_list("pk", flat=True)) == przed


@pytest.mark.django_db
def test_nic_nie_ma_fk_do_publikacji_instytucji():
    """Dedup kasuje duplikaty wprost — wolno mu, bo model jest liściem grafu.

    Gdyby ktoś dołożył FK do ``PublikacjaInstytucji``, migracja ``0078``
    zaczęłaby kasadowo osierocać/kasować powiązane wiersze. Ten test to
    wykryje i wymusi dopisanie przepinania FK do dedupu.
    """
    powiazania = [
        f"{rel.related_model._meta.label}.{rel.field.name}"
        for rel in PublikacjaInstytucji._meta.related_objects
    ]
    assert powiazania == []
