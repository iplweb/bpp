"""#508 F4: destrukcyjne wyzwalacze fazy integracji (Zatwierdź / Restart
analizy) muszą być za bramką grupy „wprowadzanie danych", nie za samym
``login_required``.

``ZatwierdzImportView``/``RestartAnalizaView`` dziedziczą po liveops
``RestartView`` (``BaseLiveOperationMixin``), którego bramka grupy zależy od
ustawienia ``LIVEOPS["REQUIRED_GROUP"]`` — a to w BPP jest NIEUSTAWIONE
(``get_setting`` zwraca ``None`` → gałąź gatingu to no-op). Reszta widoków
importu gejtuje się przez braces ``GroupRequiredMixin`` (konwencja projektu,
np. ``import_punktacji_zrodel``); te dwa widoki jej nie miały, więc dowolny
zalogowany user mógł odpalić integrację / restart cudzego-schematu importu.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_zatwierdz_bez_grupy_nie_zmienia_stanu(client, django_user_model):
    u = django_user_model.objects.create_user(username="plain", password="pass")
    client.force_login(u)
    imp = baker.make(
        ImportPracownikow, owner=u, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    client.post(url)
    imp.refresh_from_db()
    # Bramka zablokowała POST — stan NIE ruszył na „zatwierdzony"/„zintegrowany".
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY


@pytest.mark.django_db
def test_restart_analiza_bez_grupy_nie_zmienia_stanu(client, django_user_model):
    u = django_user_model.objects.create_user(username="plain2", password="pass")
    client.force_login(u)
    imp = baker.make(
        ImportPracownikow, owner=u, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
    )
    url = reverse("import_pracownikow:restart-analiza", kwargs={"pk": imp.pk})
    client.post(url)
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY


@pytest.mark.django_db
def test_zatwierdz_z_grupa_przechodzi(client, django_user_model):
    u = django_user_model.objects.create_user(username="entry", password="pass")
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grupa)
    client.force_login(u)
    imp = baker.make(
        ImportPracownikow, owner=u, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    # Z podglądu wolno zapisać strukturę (Krok 1) — to ruszy stan.
    client.post(url, {"zakres": "jednostki"})
    imp.refresh_from_db()
    # Członek grupy przechodzi bramkę — POST wykonał się (stan ruszył dalej).
    assert imp.stan != ImportPracownikow.STAN_PRZEANALIZOWANY
