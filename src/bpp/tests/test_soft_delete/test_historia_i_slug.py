"""Kosz zostawia ślad w historii rekordu; unikalność a kosz.

Historia: model w django-reversion (``Autor``) dostaje rewizję
„Przeniesiono do kosza" / „Przywrócono z kosza" z userem i powodem;
model spoza reversion (publikacje, słowniki) — wpis ``LogEntry`` CHANGE.

Unikalność: rekord w koszu ZACHOWUJE slug i nazwy. Nowy rekord dostaje
kolejny wariant sluga; wpisanie unikalnej wartości trzymanej przez rekord
z kosza to błąd walidacji („przywróć tamten rekord").
"""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker
from reversion.models import Version

from bpp.models import (
    Autor,
    Konferencja,
    Seria_Wydawnicza,
    Wydawca,
    Wydawnictwo_Ciagle,
    Zrodlo,
)


@pytest.mark.django_db
def test_kosz_i_przywrocenie_autora_to_rewizje_reversion(admin_user):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Historyczny")

    autor.delete(user=admin_user, reason="duplikat")
    autor = Autor.global_objects.get(pk=autor.pk)
    autor.restore(user=admin_user)

    komentarze = [
        v.revision.comment for v in Version.objects.get_for_object(autor).order_by("pk")
    ]
    assert komentarze == [
        "Przeniesiono do kosza (powód: duplikat)",
        "Przywrócono z kosza",
    ]
    assert {v.revision.user_id for v in Version.objects.get_for_object(autor)} == {
        admin_user.pk
    }


@pytest.mark.django_db
def test_kosz_publikacji_to_rewizja(admin_user, bez_celery):
    """FD#587: publikacje są w reversion — kosz i przywrócenie to rewizje
    (receiver kosza przełączył się sam), a nie wpisy ``LogEntry``."""
    wc = baker.make(Wydawnictwo_Ciagle)

    wc.delete(user=admin_user, reason="pomyłka")
    wc.restore(user=admin_user)

    assert not LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        object_id=str(wc.pk),
        action_flag=CHANGE,
    ).exists()
    wersje = Version.objects.get_for_object(wc).order_by("pk")
    assert {v.revision.user_id for v in wersje} == {admin_user.pk}
    assert [v.revision.comment for v in wersje] == [
        "Przeniesiono do kosza (powód: pomyłka)",
        "Przywrócono z kosza",
    ]


@pytest.mark.django_db
def test_nowy_autor_o_tym_samym_nazwisku_po_koszu_bez_integrityerror():
    """Regresja: kosz Jana Kowalskiego + nowy Jan Kowalski -> IntegrityError
    na ``bpp_autor_slug_key``. Teraz rekord w koszu ZACHOWUJE slug, a nowy
    dostaje kolejny wariant (autoslug sprawdza unikalność razem z koszem)."""
    stary = Autor.objects.create(imiona="Jan", nazwisko="Kowalski")
    oryginal = stary.slug

    stary.delete()
    stary = Autor.global_objects.get(pk=stary.pk)
    assert stary.slug == oryginal  # link /jan-kowalski/ zostaje

    nowy = Autor.objects.create(imiona="Jan", nazwisko="Kowalski")
    assert nowy.slug != oryginal
    assert nowy.slug.startswith(oryginal)

    # Przywrócenie niczego nie zmienia i nie koliduje.
    stary.restore()
    stary.refresh_from_db()
    assert stary.slug == oryginal
    assert stary.deleted_at is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,pole",
    [(Seria_Wydawnicza, "nazwa"), (Wydawca, "nazwa")],
)
def test_nazwa_rekordu_z_kosza_daje_blad_walidacji(model, pole):
    """Unikalna nazwa zostaje przy rekordzie w koszu; wpisanie jej ponownie
    to błąd WALIDACJI formularza wskazujący rekord do przywrócenia, a nie
    ``IntegrityError``."""
    from django import forms

    obj = baker.make(model, **{pole: "Taka sama"})
    obj.delete()
    obj = model.global_objects.get(pk=obj.pk)
    assert getattr(obj, pole) == "Taka sama"

    F = forms.modelform_factory(model, fields=[pole])
    form = F(data={pole: "Taka sama"})
    assert not form.is_valid()
    assert "przywróć tamten rekord" in str(form.errors[pole])


@pytest.mark.django_db
def test_zrodlo_w_koszu_zachowuje_slug_nowe_dostaje_inny():
    z = baker.make(Zrodlo, nazwa="Czasopismo Testowe", slug="")
    oryginal = z.slug
    z.delete()
    nowe = baker.make(Zrodlo, nazwa="Czasopismo Testowe", slug="")
    assert nowe.slug != oryginal
    assert Zrodlo.global_objects.get(pk=z.pk).slug == oryginal


@pytest.mark.django_db
def test_konferencja_coroczna_przywrocenie_bez_konfliktu():
    """Regresja (recenzja #6): ``unique_together(nazwa, rozpoczecie)`` —
    edycja 2023 w koszu i żywa edycja 2024 o tej samej nazwie: przywrócenie
    2023 nie może być konfliktem."""
    import datetime

    k23 = Konferencja.objects.create(
        nazwa="Konf X", rozpoczecie=datetime.date(2023, 5, 1)
    )
    Konferencja.objects.create(nazwa="Konf X", rozpoczecie=datetime.date(2024, 5, 1))
    k23.delete()
    k23 = Konferencja.global_objects.get(pk=k23.pk)
    k23.restore()
    assert Konferencja.objects.filter(pk=k23.pk).exists()
