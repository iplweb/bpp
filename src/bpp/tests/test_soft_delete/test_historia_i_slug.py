"""Kosz zostawia ślad w historii rekordu; kosz zwalnia unikalne pola.

Historia: model w django-reversion (``Autor``) dostaje rewizję
„Przeniesiono do kosza" / „Przywrócono z kosza" z userem i powodem;
model spoza reversion (publikacje, słowniki) — wpis ``LogEntry`` CHANGE.

Slug: rekord w koszu fizycznie zostaje, a ``slug`` ma bezwarunkowe UNIQUE.
Kosz zmienia go na ``…-unexistent-N``; przywrócenie oddaje oryginał albo
generuje nowy, gdy oryginał zajęto.
"""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker
from reversion.models import Version

from bpp.models import (
    Autor,
    Jednostka,
    Konferencja,
    Seria_Wydawnicza,
    Wydawca,
    Wydawnictwo_Ciagle,
    Zrodlo,
)
from bpp.models.soft_delete import KonfliktPrzywracania


@pytest.mark.django_db
def test_kosz_i_przywrocenie_autora_to_rewizje_reversion(admin_user):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Historyczny")

    autor.delete(user=admin_user, reason="duplikat")
    autor = Autor.global_objects.get(pk=autor.pk)
    autor.restore(user=admin_user)

    komentarze = [
        v.revision.comment
        for v in Version.objects.get_for_object(autor).order_by("pk")
    ]
    assert komentarze == [
        "Przeniesiono do kosza (powód: duplikat)",
        "Przywrócono z kosza",
    ]
    assert {
        v.revision.user_id for v in Version.objects.get_for_object(autor)
    } == {admin_user.pk}


@pytest.mark.django_db
def test_kosz_publikacji_to_logentry(admin_user, bez_celery):
    wc = baker.make(Wydawnictwo_Ciagle)

    wc.delete(user=admin_user, reason="pomyłka")
    wc.restore(user=admin_user)

    wpisy = LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        object_id=str(wc.pk),
        action_flag=CHANGE,
    ).order_by("pk")
    assert [w.change_message for w in wpisy] == [
        "Przeniesiono do kosza (powód: pomyłka)",
        "Przywrócono z kosza",
    ]


@pytest.mark.django_db
def test_nowy_autor_o_tym_samym_nazwisku_po_koszu_bez_integrityerror():
    """Regresja: kosz Jana Kowalskiego + nowy Jan Kowalski -> IntegrityError
    na ``bpp_autor_slug_key`` (autoslug sprawdza unikalność przez domyślny
    menedżer, który kosza nie widzi)."""
    stary = Autor.objects.create(imiona="Jan", nazwisko="Kowalski")
    oryginal = stary.slug

    stary.delete()
    stary = Autor.global_objects.get(pk=stary.pk)
    assert stary.slug == f"{oryginal}-unexistent-1"

    nowy = Autor.objects.create(imiona="Jan", nazwisko="Kowalski")
    assert nowy.slug == oryginal

    # Przywrócenie: oryginał zajęty -> nowy, wolny slug; bez kolizji.
    stary.restore()
    stary.refresh_from_db()
    assert stary.slug != oryginal
    assert "unexistent" not in stary.slug


@pytest.mark.django_db
def test_kolejne_kosze_dostaja_kolejne_numery_i_oryginal_wraca():
    a1 = Autor.objects.create(imiona="Anna", nazwisko="Nowak")
    oryginal = a1.slug
    a1.delete()
    a2 = Autor.objects.create(imiona="Anna", nazwisko="Nowak")
    a2.delete()

    sl = set(
        Autor.global_objects.filter(pk__in=[a1.pk, a2.pk]).values_list(
            "slug", flat=True
        )
    )
    assert sl == {f"{oryginal}-unexistent-1", f"{oryginal}-unexistent-2"}

    a1 = Autor.global_objects.get(pk=a1.pk)
    a1.restore()
    a1.refresh_from_db()
    assert a1.slug == oryginal


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,pole",
    [(Seria_Wydawnicza, "nazwa"), (Wydawca, "nazwa"), (Konferencja, "nazwa")],
)
def test_slownik_w_koszu_zwalnia_nazwe(model, pole):
    obj = baker.make(model, **{pole: "Taka sama"})
    obj.delete()
    obj = model.global_objects.get(pk=obj.pk)
    assert getattr(obj, pole) == "Taka sama [kosz-1]"

    baker.make(model, **{pole: "Taka sama"})  # bez IntegrityError

    with pytest.raises(KonfliktPrzywracania):
        obj.restore()


@pytest.mark.django_db
def test_zrodlo_w_koszu_zwalnia_slug():
    z = baker.make(Zrodlo, nazwa="Czasopismo Testowe", slug="")
    oryginal = z.slug
    z.delete()
    nowe = baker.make(Zrodlo, nazwa="Czasopismo Testowe", slug="")
    assert nowe.slug == oryginal


@pytest.mark.django_db
def test_jednostka_pusta_do_kosza_i_z_powrotem(uczelnia):
    j = baker.make(Jednostka, nazwa="Katedra Pusta", skrot="KP", uczelnia=uczelnia)
    j.delete()
    assert not Jednostka.objects.filter(pk=j.pk).exists()
    baker.make(Jednostka, nazwa="Katedra Pusta", skrot="KP", uczelnia=uczelnia)
    j = Jednostka.global_objects.get(pk=j.pk)
    with pytest.raises(KonfliktPrzywracania):
        j.restore()
