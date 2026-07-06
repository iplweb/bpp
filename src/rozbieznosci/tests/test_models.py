import pytest
from django.db import IntegrityError, transaction
from model_bakery import baker

from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog


@pytest.mark.django_db
def test_ignorowana_rozbieznosc_str():
    wc = baker.make("bpp.Wydawnictwo_Ciagle")
    ign = IgnorowanaRozbieznosc.objects.create(metryka="if", rekord=wc)
    assert str(wc.pk) in str(ign)
    assert "if" in str(ign)


@pytest.mark.django_db
def test_unique_metryka_rekord():
    wc = baker.make("bpp.Wydawnictwo_Ciagle")
    IgnorowanaRozbieznosc.objects.create(metryka="if", rekord=wc)
    # ta sama metryka + rekord => konflikt; atomic() tworzy savepoint,
    # żeby zepsuta transakcja nie blokowała dalszych zapytań (PostgreSQL)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            IgnorowanaRozbieznosc.objects.create(metryka="if", rekord=wc)
    # inna metryka => OK
    IgnorowanaRozbieznosc.objects.create(metryka="mnisw", rekord=wc)
    assert IgnorowanaRozbieznosc.objects.filter(rekord=wc).count() == 2


@pytest.mark.django_db
def test_log_str():
    wc = baker.make("bpp.Wydawnictwo_Ciagle")
    log = RozbieznoscLog.objects.create(
        metryka="if", rekord=wc, wartosc_przed=1, wartosc_po=2
    )
    assert "if" in str(log)
