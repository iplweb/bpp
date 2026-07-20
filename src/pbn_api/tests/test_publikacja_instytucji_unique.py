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

import pytest
from django.db import IntegrityError, connection, transaction
from model_bakery import baker

from pbn_api.models import Institution, Publication, Scientist
from pbn_api.models.publikacja_instytucji import PublikacjaInstytucji

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
