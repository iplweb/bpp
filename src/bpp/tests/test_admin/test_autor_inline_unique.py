"""Task 3c — czy zamiana `unique_together` na warunkowy `UniqueConstraint`/
`ExclusionConstraint` (``condition=deleted_at__isnull``) NIE zregresowała
walidacji formularza w adminie.

Dwie osobne pułapki, obie związane z tym, że ``deleted_at`` NIE jest polem
formularza (``generuj_formularz_dla_autorow`` go nie miało):

1. ``Model.validate_unique()`` w ogóle NIE sprawdza ``Meta.constraints``
   (ani warunkowych, ani bezwarunkowych) — to osobny krok,
   ``Model.validate_constraints()`` (Django >=4.1), wołany automatycznie
   przez ``ModelForm._post_clean()`` -> ``instance.full_clean(...)``.
2. ``validate_constraints()`` DZIAŁA dla warunkowych constraintów, ALE tylko
   jeśli pole użyte w ``condition`` (tu: ``deleted_at``) nie jest wykluczone
   z walidacji. Pole spoza ``Meta.fields`` formularza Django automatycznie
   wrzuca do ``exclude`` (``_get_validation_exclusions()``). Skutek:
   - dla ``UniqueConstraint`` — Django CICHO POMIJA walidację (łapie
     ``FieldError`` i nic nie zgłasza — kolizja przechodzi formularz,
     ``IntegrityError`` wyskakuje dopiero przy zapisie do bazy),
   - dla ``ExclusionConstraint`` — Django W OGÓLE NIE ŁAPIE tego
     ``FieldError`` — ``is_valid()`` wywala się niekontrolowanym wyjątkiem
     (HTTP 500) przy KAŻDYM zapisie, nawet bez żadnej kolizji.

Naprawa: ``deleted_at`` jest teraz jawnym, ukrytym/wyłączonym polem
formularza (zawsze ``None`` — formularz operuje tylko na żywych wierszach),
więc oba constrainty widzą je poprawnie i walidują się jak należy, bez
ręcznego ``clean()``.
"""

import pytest
from django.contrib.admin.sites import AdminSite

from bpp.admin.core import generuj_formularz_dla_autorow, generuj_inline_dla_autorow
from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor

PREFIX = "autorzy_set"


def _form_class():
    return generuj_formularz_dla_autorow(Wydawnictwo_Ciagle_Autor, include_rekord=True)


def _inline_formset(rf, admin_user, wc, data):
    inline_cls = generuj_inline_dla_autorow(Wydawnictwo_Ciagle_Autor)
    inline = inline_cls(Wydawnictwo_Ciagle, AdminSite())
    request = rf.post("/")
    request.user = admin_user
    formset_cls = inline.get_formset(request, wc)
    return formset_cls(data, instance=wc, prefix=PREFIX)


def _wca_row(idx, wca):
    return {
        f"{PREFIX}-{idx}-id": str(wca.pk),
        f"{PREFIX}-{idx}-autor": str(wca.autor_id),
        f"{PREFIX}-{idx}-jednostka": str(wca.jednostka_id),
        f"{PREFIX}-{idx}-typ_odpowiedzialnosci": str(wca.typ_odpowiedzialnosci_id),
        f"{PREFIX}-{idx}-zapisany_jako": wca.zapisany_jako,
        f"{PREFIX}-{idx}-kolejnosc": str(wca.kolejnosc),
    }


def _nowy_wiersz(
    idx, *, autor, jednostka, typ_odpowiedzialnosci, zapisany_jako, kolejnosc
):
    return {
        f"{PREFIX}-{idx}-id": "",
        f"{PREFIX}-{idx}-autor": str(autor.pk),
        f"{PREFIX}-{idx}-jednostka": str(jednostka.pk),
        f"{PREFIX}-{idx}-typ_odpowiedzialnosci": str(typ_odpowiedzialnosci.pk),
        f"{PREFIX}-{idx}-zapisany_jako": zapisany_jako,
        f"{PREFIX}-{idx}-kolejnosc": str(kolejnosc),
    }


def _management(total, initial):
    return {
        f"{PREFIX}-TOTAL_FORMS": str(total),
        f"{PREFIX}-INITIAL_FORMS": str(initial),
        f"{PREFIX}-MIN_NUM_FORMS": "0",
        f"{PREFIX}-MAX_NUM_FORMS": "1000",
    }


def _data(wc, wca, **overrides):
    data = {
        "rekord": str(wc.pk),
        "autor": str(wca.autor_id),
        "jednostka": str(wca.jednostka_id),
        "typ_odpowiedzialnosci": str(wca.typ_odpowiedzialnosci_id),
        "zapisany_jako": wca.zapisany_jako,
        "kolejnosc": "1",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_standalone_admin_form_lapie_kolizje_rekord_autor_typ(
    wydawnictwo_ciagle_z_autorem,
):
    """Nowe powiązanie z tym samym (rekord, autor, typ_odpowiedzialnosci), co
    już istniejący ŻYWY wiersz, MUSI dać błąd formularza — nie
    IntegrityError przy zapisie."""
    wc = wydawnictwo_ciagle_z_autorem
    existing = wc.autorzy_set.get()

    # Pozycyjnie, jak robi to prawdziwy Django admin (`ModelForm(request.POST,
    # request.FILES, instance=obj)`) — jako kwarg `data=` włącza w kodzie
    # formularza gałąź oczekującą `kwargs["prefix"]` (dotyczy TYLKO formsetów
    # inline, nie samodzielnego admina).
    form = _form_class()(_data(wc, existing, kolejnosc="1"), None)

    assert not form.is_valid(), "kolizja (rekord, autor, typ) powinna być błędem"


@pytest.mark.django_db
def test_standalone_admin_form_lapie_kolizje_rekord_autor_kolejnosc(
    wydawnictwo_ciagle_z_autorem, autor_jan_nowak
):
    """Nowe powiązanie INNEGO typu odpowiedzialności, ale z tą samą
    (rekord, autor, kolejnosc) — też musi być błędem formularza."""
    wc = wydawnictwo_ciagle_z_autorem
    existing = wc.autorzy_set.get()

    from bpp.models import Typ_Odpowiedzialnosci

    inny_typ = Typ_Odpowiedzialnosci.objects.exclude(
        pk=existing.typ_odpowiedzialnosci_id
    ).first()
    assert inny_typ is not None

    form = _form_class()(
        _data(
            wc,
            existing,
            kolejnosc=str(existing.kolejnosc),
            typ_odpowiedzialnosci=str(inny_typ.pk),
        ),
        None,
    )

    assert not form.is_valid(), "kolizja (rekord, autor, kolejnosc) to błąd"


@pytest.mark.django_db
def test_standalone_admin_form_po_soft_delete_nie_koliduje(
    wydawnictwo_ciagle_z_autorem,
):
    """Po soft-delete starego powiązania to samo (rekord, autor, typ) musi
    dać się zapisać ponownie — formularz nie może uznać skasowanego wiersza
    za kolizję (wzorzec "usuń i wstaw od nowa" w adminie)."""
    wc = wydawnictwo_ciagle_z_autorem
    existing = wc.autorzy_set.get()
    dane = _data(wc, existing, kolejnosc="1")
    existing.delete()  # soft

    form = _form_class()(dane, None)

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_standalone_admin_form_edycja_wlasnego_wiersza_nie_koliduje_sama_ze_soba(
    wydawnictwo_ciagle_z_autorem,
):
    """Edycja ISTNIEJĄCEGO wiersza (te same wartości) nie może wykryć
    kolizji z samym sobą."""
    wc = wydawnictwo_ciagle_z_autorem
    existing = wc.autorzy_set.get()

    form = _form_class()(
        _data(wc, existing, kolejnosc=str(existing.kolejnosc)),
        None,
        instance=existing,
    )

    assert form.is_valid(), form.errors


# --- Formset inline (`generuj_inline_dla_autorow`), realny widok Wydawnictwo_Ciagle ---


@pytest.mark.django_db
def test_inline_nowy_wiersz_koliduje_z_istniejacym_typ(
    wydawnictwo_ciagle_z_autorem, rf, admin_user
):
    """Dodanie NOWEGO wiersza kolidującego (rekord, autor, typ) z ISTNIEJĄCYM
    (widocznym w tym samym formsecie) wierszem musi dać błąd formsetu."""
    wc = wydawnictwo_ciagle_z_autorem
    existing = wc.autorzy_set.get()

    data = _management(total=2, initial=1)
    data.update(_wca_row(0, existing))
    data.update(
        _nowy_wiersz(
            1,
            autor=existing.autor,
            jednostka=existing.jednostka,
            typ_odpowiedzialnosci=existing.typ_odpowiedzialnosci,
            zapisany_jako=existing.zapisany_jako,
            kolejnosc=existing.kolejnosc + 1,
        )
    )

    formset = _inline_formset(rf, admin_user, wc, data)

    assert not formset.is_valid(), formset.errors


@pytest.mark.django_db
def test_inline_nowy_wiersz_koliduje_z_istniejacym_kolejnosc(
    wydawnictwo_ciagle_z_autorem, rf, admin_user, typy_odpowiedzialnosci
):
    """Dodanie NOWEGO wiersza z tą samą (rekord, autor, kolejnosc), co
    ISTNIEJĄCY wiersz (inny typ odpowiedzialności) — też błąd formsetu."""
    wc = wydawnictwo_ciagle_z_autorem
    existing = wc.autorzy_set.get()
    inny_typ = typy_odpowiedzialnosci["red."]

    data = _management(total=2, initial=1)
    data.update(_wca_row(0, existing))
    data.update(
        _nowy_wiersz(
            1,
            autor=existing.autor,
            jednostka=existing.jednostka,
            typ_odpowiedzialnosci=inny_typ,
            zapisany_jako=existing.zapisany_jako,
            kolejnosc=existing.kolejnosc,
        )
    )

    formset = _inline_formset(rf, admin_user, wc, data)

    assert not formset.is_valid(), formset.errors


@pytest.mark.django_db
def test_inline_po_soft_delete_reinsert_przechodzi(
    wydawnictwo_ciagle_z_autorem, rf, admin_user
):
    """Formset MUSI przepuścić wzorzec "usuń stary wiersz (miękko) + dodaj
    nowy o tych samych wartościach" — dokładnie regresja z Taska 3c."""
    wc = wydawnictwo_ciagle_z_autorem
    existing = wc.autorzy_set.get()

    data = _management(total=2, initial=1)
    row0 = _wca_row(0, existing)
    row0[f"{PREFIX}-0-DELETE"] = "on"
    data.update(row0)
    data.update(
        _nowy_wiersz(
            1,
            autor=existing.autor,
            jednostka=existing.jednostka,
            typ_odpowiedzialnosci=existing.typ_odpowiedzialnosci,
            zapisany_jako=existing.zapisany_jako,
            kolejnosc=existing.kolejnosc,
        )
    )

    formset = _inline_formset(rf, admin_user, wc, data)

    assert formset.is_valid(), formset.errors
