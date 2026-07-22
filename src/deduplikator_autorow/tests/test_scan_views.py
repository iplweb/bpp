import pytest
from django.contrib import messages as django_messages
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from deduplikator_autorow.models import IgnoredScientist


def _login_user_with_group(client):
    user = baker.make("bpp.BppUser", is_active=True)
    user.set_password("xx")
    user.save()
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    client.force_login(user)
    return user


def _messages(response):
    return list(get_messages(response.wsgi_request))


@pytest.mark.django_db
def test_start_scan_warns_but_runs_with_stale_pbn_people_data(client, mocker):
    user = _login_user_with_group(client)
    mocker.patch(
        "deduplikator_autorow.views.scan.is_pbn_people_data_fresh",
        return_value=(False, "Dane autorów PBN nigdy nie były pobrane", None),
    )
    # Widok woła apply_async z własnym task_id (żeby wykryć deduplikację
    # Singletona). Zwracamy AsyncResult o TYM SAMYM id = „realnie
    # wystartowano".
    apply_async = mocker.patch(
        "deduplikator_autorow.tasks.scan_for_duplicates.apply_async",
        side_effect=lambda **kw: mocker.Mock(id=kw["task_id"]),
    )

    response = client.post(reverse("deduplikator_autorow:start_scan"))

    assert response.status_code == 302
    assert response["Location"] == reverse("deduplikator_autorow:duplicate_authors")
    assert apply_async.call_args.kwargs["kwargs"] == {"user_id": user.pk}

    messages = _messages(response)
    assert any(
        msg.level == django_messages.WARNING
        and "Uruchamiasz skanowanie na nieaktualnych danych PBN" in str(msg)
        for msg in messages
    )
    assert any(
        msg.level == django_messages.SUCCESS
        and "Skanowanie duplikatów zostało uruchomione" in str(msg)
        for msg in messages
    )


@pytest.mark.django_db
def test_start_scan_nie_klamie_gdy_singleton_zdeduplikowal_dispatch(client, mocker):
    """Gdy Singleton zdeduplikował wysyłkę (apply_async zwrócił AsyncResult
    ISTNIEJĄCEGO zadania, o innym id niż zadane), widok NIE może meldować
    „uruchomiono" — bo nic się nie uruchomiło."""
    _login_user_with_group(client)
    mocker.patch(
        "deduplikator_autorow.views.scan.is_pbn_people_data_fresh",
        return_value=(True, None, None),
    )
    # Zwracamy id INNE niż zadane = sygnał deduplikacji z celery_singleton.
    mocker.patch(
        "deduplikator_autorow.tasks.scan_for_duplicates.apply_async",
        return_value=mocker.Mock(id="id-juz-trwajacego-zadania"),
    )

    response = client.post(reverse("deduplikator_autorow:start_scan"))

    assert response.status_code == 302
    messages = _messages(response)
    assert any(
        msg.level == django_messages.WARNING and "już trwa" in str(msg)
        for msg in messages
    )
    assert not any(msg.level == django_messages.SUCCESS for msg in messages)


@pytest.mark.django_db
def test_reset_ignored_scientists_warns_but_triggers_rescan_on_stale_pbn(
    client, mocker
):
    user = _login_user_with_group(client)
    IgnoredScientist.objects.create(
        scientist=baker.make("pbn_api.Scientist"),
        created_by=user,
    )
    mocker.patch(
        "deduplikator_autorow.views.ignore.is_pbn_people_data_fresh",
        return_value=(False, "Dane autorów PBN są nieaktualne (8 dni)", None),
    )
    delay = mocker.patch("deduplikator_autorow.tasks.scan_for_duplicates.delay")

    response = client.post(reverse("deduplikator_autorow:reset_ignored_scientists"))

    assert response.status_code == 302
    assert IgnoredScientist.objects.count() == 0
    delay.assert_called_once_with(user_id=user.pk)

    messages = _messages(response)
    assert any(
        msg.level == django_messages.WARNING
        and "Uruchamiasz skanowanie na nieaktualnych danych PBN" in str(msg)
        for msg in messages
    )
    assert any(
        msg.level == django_messages.SUCCESS
        and "Uruchomiono nowe skanowanie duplikatów w tle" in str(msg)
        for msg in messages
    )
