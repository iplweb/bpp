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


# --- Warstwa 2: Autor jako model soft-delete + guard ------------------------


@pytest.mark.django_db
def test_autor_bez_prac_soft_delete_ok(autor_jan_nowak):
    """Autor bez prac („husk") kasuje się miękko — to on zostaje po scaleniu."""
    autor_jan_nowak.delete()
    autor_jan_nowak.refresh_from_db()

    assert autor_jan_nowak.deleted_at is not None
    assert not Autor.objects.filter(pk=autor_jan_nowak.pk).exists()
    assert Autor.global_objects.filter(pk=autor_jan_nowak.pk).exists()


@pytest.mark.django_db
def test_autor_soft_delete_nie_kasuje_powiazan_spoza_soft_delete(
    autor_jan_nowak, jednostka
):
    """Miękkie skasowanie autora NIE WOLNO, by cokolwiek fizycznie usunęło.

    ``SoftDeleteModel.delete()`` pakietu przechodzi po WSZYSTKICH relacjach
    odwrotnych i dla dziecka z ``CASCADE``, które nie jest samo modelem
    soft-delete, woła zwykłe ``delete()`` — czyli kasuje TWARDO. ``Autor``
    ma 27 takich dzieci, m.in. ``Autor_Jednostka``, ``Autor_Dyscyplina``
    i ``Autor_Absencja``: delegowanie do ``super().delete()`` wymazałoby
    zatrudnienie i dyscypliny osoby, a husk przestałby dać się sensownie
    przywrócić.

    Sprawdzone mutacją: po podmianie ciała na ``super().delete()`` ten test
    nie tylko pada — samo przejście po relacjach ``Autora`` wywala się
    ``ProgrammingError``-em na tabeli, której w bazie nie ma
    (``raport_slotow_raportzerowyentry``). Refleksyjna kaskada pakietu jest
    dla tego modelu nie tyle ryzykowna, co po prostu nieużywalna.

    Dlatego ``Autor.delete()`` pisze ``deleted_at`` sam — tak samo, jak
    zdecydowała faza 02 dla publikacji (patrz ``BppPublikacjaSoftDelete
    Mixin``). Ten test jest jedynym, który to pilnuje.
    """
    from bpp.models import Autor_Jednostka

    Autor_Jednostka.objects.create(autor=autor_jan_nowak, jednostka=jednostka)
    assert Autor_Jednostka.objects.filter(autor=autor_jan_nowak).count() == 1

    autor_jan_nowak.delete()

    assert Autor_Jednostka.objects.filter(autor=autor_jan_nowak).count() == 1, (
        "miękkie skasowanie autora fizycznie usunęło jego powiązanie "
        "z jednostką — to kaskada pakietu, której NIE WOLNO uruchamiać"
    )


@pytest.mark.django_db
def test_autor_husk_wraca_z_kosza(autor_jan_nowak):
    """``restore()`` musi działać mimo relacji do modeli spoza soft-delete.

    ``SoftDeleteModel.restore()`` pakietu ma domyślnie ``strict=True``
    i sprawdza KAŻDE pole z ``related_model`` — także zwykłe FK w przód.
    ``Autor`` ma FK m.in. do ``Tytul``, więc gołe ``restore()`` rzuciłoby
    ``SoftDeleteException`` i przywrócenie husku byłoby niemożliwe.
    """
    autor_jan_nowak.delete()
    assert not Autor.objects.filter(pk=autor_jan_nowak.pk).exists()

    autor_jan_nowak.restore()
    autor_jan_nowak.refresh_from_db()

    assert autor_jan_nowak.deleted_at is None
    assert Autor.objects.filter(pk=autor_jan_nowak.pk).exists()


@pytest.mark.django_db
def test_husk_autora_znika_z_menedzera_objects_i_z_wyszukiwarki(autor_jan_nowak):
    """``Autor.objects`` musi ukrywać husk — inaczej „usunięty" autor
    dalej wyskakuje w autocomplete, na listach i w wyszukiwarce
    pełnotekstowej.

    ``AutorManager`` nie był przepleciony z filtrem soft-delete (§4c/R4
    handoffu): sam ``SoftDeleteModel`` w bazie klas tego NIE załatwia, bo
    ``objects = AutorManager()`` nadpisuje menedżer pakietu.
    """
    nazwisko = autor_jan_nowak.nazwisko
    autor_jan_nowak.delete()

    assert not Autor.objects.filter(nazwisko=nazwisko).exists()
    assert Autor.objects.all().count() == 0
    assert Autor.deleted_objects.filter(pk=autor_jan_nowak.pk).exists()


@pytest.mark.django_db
def test_queryset_autora_nie_pozwala_na_bulk_update_deleted_at(autor_jan_nowak):
    """Gate z fazy 01 musi obowiązywać też ``AutorQuerySet``.

    Bulk ``update(deleted_at=...)`` omija ``save()``, sygnały, reversion
    i (od fazy 06) ``SoftDeleteLog``. ``AutorQuerySet`` dziedziczy dziś po
    zwykłym ``models.QuerySet``, więc bez przepięcia bazy gate by tu nie
    obowiązywał.
    """
    with pytest.raises(RuntimeError):
        Autor.objects.filter(pk=autor_jan_nowak.pk).update(deleted_at=None)


@pytest.mark.django_db
def test_metody_domenowe_autorquerysetu_przezyly_przepiecie(autor_jan_nowak, uczelnia):
    """Przepięcie bazy ``AutorQuerySet`` nie może zgubić metod zakresów.

    ``aktualnie_zatrudnieni`` / ``kiedykolwiek_zwiazani`` /
    ``kiedykolwiek_zatrudnieni`` są używane przez widoki i API — gdyby
    zniknęły przy zmianie klasy bazowej, padłoby to daleko od tego pliku.
    """
    qs = Autor.objects.all()
    assert qs.aktualnie_zatrudnieni(uczelnia).count() == 0
    assert qs.kiedykolwiek_zwiazani(uczelnia).count() == 0
    assert qs.kiedykolwiek_zatrudnieni(uczelnia).count() == 0


# --- Zadanie 4: guard Autor.delete() dla każdego typu pracy -----------------


@pytest.mark.django_db
def test_autor_z_praca_ciagla_protect(
    wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    with pytest.raises(ProtectedError):
        autor_jan_kowalski.delete()


@pytest.mark.django_db
def test_autor_z_praca_zwarta_protect(
    wydawnictwo_zwarte, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    with pytest.raises(ProtectedError):
        autor_jan_kowalski.delete()


@pytest.mark.django_db
def test_autor_z_patentem_protect(
    patent, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    patent.dodaj_autora(autor_jan_kowalski, jednostka)
    with pytest.raises(ProtectedError):
        autor_jan_kowalski.delete()


@pytest.mark.django_db
def test_autor_z_doktoratem_protect(autor_jan_nowak, jednostka):
    baker.make(Praca_Doktorska, autor=autor_jan_nowak, jednostka=jednostka)
    with pytest.raises(ProtectedError):
        autor_jan_nowak.delete()


@pytest.mark.django_db
def test_autor_z_habilitacja_protect(autor_jan_nowak, jednostka):
    baker.make(Praca_Habilitacyjna, autor=autor_jan_nowak, jednostka=jednostka)
    with pytest.raises(ProtectedError):
        autor_jan_nowak.delete()


@pytest.mark.django_db
def test_autor_w_projekcie_protect(autor_jan_nowak):
    """Uczestnictwo w projekcie chroni autora — tak jak chroniło zawsze.

    ``Projekt_Autor.autor`` ma ``PROTECT`` od dawna, więc TWARDE
    ``autor.delete()`` już przed fazą 04 kończyło się ``ProtectedError``.
    Guard musi to zachować: gdyby liczył wyłącznie prace, miękkie kasowanie
    po cichu obeszłoby istniejącą gwarancję i zostawiło projekt wskazujący
    na husk.
    """
    from bpp.models.projekt import Projekt_Autor

    baker.make(Projekt_Autor, autor=autor_jan_nowak)
    with pytest.raises(ProtectedError):
        autor_jan_nowak.delete()


@pytest.mark.django_db
def test_autor_z_praca_tylko_w_koszu_nadal_protect(
    wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    """Najważniejszy przypadek: autor „cały w koszu" NIE jest pusty.

    Publikacja skasowana miękko zabiera kaskadą fazy 02 swoje autorstwa.
    Przez ``objects`` autor wygląda wtedy na wolnego od zobowiązań — i to
    jest pułapka: przywrócenie tej publikacji dałoby rekord wskazujący na
    autora, którego nie ma. Guard liczy przez ``global_objects``
    (spec §3.2).
    """
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_ciagle.delete()

    assert not Wydawnictwo_Ciagle_Autor.objects.filter(
        autor=autor_jan_kowalski
    ).exists()
    assert Wydawnictwo_Ciagle_Autor.global_objects.filter(
        autor=autor_jan_kowalski
    ).exists()

    with pytest.raises(ProtectedError):
        autor_jan_kowalski.delete()


@pytest.mark.django_db
def test_autor_zablokowany_guardem_nie_trafil_do_kosza(
    wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    """Guard ma ODMÓWIĆ, a nie „odmówić po fakcie".

    Gdyby stał za zapisem ``deleted_at``, autor lądowałby w koszu mimo
    wyjątku — a operator zobaczyłby błąd i zniknięcie naraz.
    """
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    with pytest.raises(ProtectedError):
        autor_jan_kowalski.delete()

    autor_jan_kowalski.refresh_from_db()
    assert autor_jan_kowalski.deleted_at is None
    assert Autor.objects.filter(pk=autor_jan_kowalski.pk).exists()


# --- Zadanie 5: guard Wydawnictwo_Zwarte.delete() na rozdziały --------------


@pytest.mark.django_db
def test_ksiazka_matka_z_rozdzialem_protect(wydawnictwo_zwarte):
    rozdzial = baker.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=wydawnictwo_zwarte)
    assert rozdzial.wydawnictwo_nadrzedne_id == wydawnictwo_zwarte.pk

    with pytest.raises(ProtectedError):
        wydawnictwo_zwarte.delete()

    wydawnictwo_zwarte.refresh_from_db()
    assert wydawnictwo_zwarte.deleted_at is None


@pytest.mark.django_db
def test_ksiazka_bez_rozdzialow_soft_delete_ok(wydawnictwo_zwarte):
    wydawnictwo_zwarte.delete()
    wydawnictwo_zwarte.refresh_from_db()
    assert wydawnictwo_zwarte.deleted_at is not None


@pytest.mark.django_db
def test_ksiazka_matka_z_rozdzialem_w_koszu_nadal_protect(wydawnictwo_zwarte):
    """Rozdział w koszu też blokuje (spec §2.6).

    Inaczej skasowanie książki-matki „przez kosz" (najpierw rozdział, potem
    książka) dałoby się przeprowadzić w dwóch krokach, a przywrócenie
    rozdziału zostawiłoby go bez książki.
    """
    rozdzial = baker.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=wydawnictwo_zwarte)
    rozdzial.delete()

    assert not Wydawnictwo_Zwarte.objects.filter(pk=rozdzial.pk).exists()
    assert Wydawnictwo_Zwarte.global_objects.filter(pk=rozdzial.pk).exists()

    with pytest.raises(ProtectedError):
        wydawnictwo_zwarte.delete()


@pytest.mark.django_db
def test_guard_rozdzialow_nie_dotyka_innych_typow_publikacji(wydawnictwo_ciagle):
    """Guard NIE MOŻE trafić do wspólnego mixinu publikacji (§4c/R3).

    ``BppPublikacjaSoftDeleteMixin`` dzieli pięć modeli. Wstawiony tam guard
    odpytywałby dla ``Wydawnictwo_Ciagle`` czy ``Patent``
    ``Wydawnictwo_Zwarte.global_objects.filter(wydawnictwo_nadrzedne=<obiekt
    innego modelu>)`` — zapytanie międzytypowe, w najlepszym razie zawsze
    puste, w gorszym wyjątek. Dlatego guard siedzi we własnym ``delete()``
    modelu ``Wydawnictwo_Zwarte``.
    """
    wydawnictwo_ciagle.delete()
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.deleted_at is not None


@pytest.mark.django_db
def test_ksiazka_bez_rozdzialow_nadal_kaskaduje_na_autorstwa(
    wydawnictwo_zwarte, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    """Guard wstawiamy PRZED kaskadą fazy 02 — ale jej NIE GUBIMY."""
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    assert Wydawnictwo_Zwarte_Autor.objects.filter(rekord=wydawnictwo_zwarte).exists()

    wydawnictwo_zwarte.delete()

    assert not Wydawnictwo_Zwarte_Autor.objects.filter(
        rekord=wydawnictwo_zwarte
    ).exists()
    assert Wydawnictwo_Zwarte_Autor.global_objects.filter(
        rekord=wydawnictwo_zwarte
    ).exists()


@pytest.mark.django_db
def test_delete_ksiazki_przepuszcza_user_i_reason(wydawnictwo_zwarte, admin_user):
    """Własny ``delete()`` nie może ZAWĘZIĆ sygnatury z mixinu.

    ``delete(user=..., reason=...)`` to kontrakt PINNED faz 06/07: tak woła
    kasowanie z powodem z panelu admina. Override w ``Wydawnictwo_Zwarte``
    przesłania wersję z ``BppPublikacjaSoftDeleteMixin``, więc zawężenie
    sygnatury (np. do samego ``self``) wywaliłoby ``TypeError`` na każdej
    książce — i dopiero w fazie 07, daleko od tej zmiany.

    Zakres tego testu — sprawdzone mutacyjnie: łapie ZAWĘŻENIE sygnatury,
    NIE łapie zgubienia ``user``/``reason`` w wywołaniu ``super()``. To
    drugie jest dziś nieobserwowalne, bo mixin tylko przyjmuje te parametry
    i nic z nimi nie robi (konsumuje je dopiero ``SoftDeleteLog`` z fazy
    06). Przekazujemy je jawnie mimo to — gdy faza 06 zacznie ich używać,
    ta ścieżka ma już działać.
    """
    wydawnictwo_zwarte.delete(user=admin_user, reason="test")
    wydawnictwo_zwarte.refresh_from_db()
    assert wydawnictwo_zwarte.deleted_at is not None


# --- Zadanie 6: guard nie blokuje scalania autorów --------------------------


@pytest.mark.django_db
def test_husk_po_transferze_prac_soft_delete_ok(
    wydawnictwo_ciagle,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    typy_odpowiedzialnosci,
):
    """Po przeniesieniu prac duplikat jest pusty — guard go przepuszcza.

    To jest warunek, żeby faza 04 nie zablokowała scalania duplikatów
    autorów, czyli jedynej operacji, która husków w ogóle produkuje.
    """
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    wca = Wydawnictwo_Ciagle_Autor.global_objects.get(autor=autor_jan_nowak)

    wca.autor = autor_jan_kowalski
    wca.save()

    autor_jan_nowak.delete()
    autor_jan_nowak.refresh_from_db()
    assert autor_jan_nowak.deleted_at is not None


@pytest.mark.django_db
def test_husk_z_autorstwem_zostawionym_w_koszu_JEST_blokowany(
    wydawnictwo_ciagle,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    typy_odpowiedzialnosci,
):
    """Przypadek, którego plan fazy 04 nie przewidywał (§4c/R1 handoffu).

    Symulacja z testu wyżej pokrywa wyłącznie CZYSTY transfer. Scalanie ma
    jednak gałąź „kolizja": gdy główny autor ma już to samo autorstwo,
    wiersza duplikatu nie da się przenieść. Gdyby zostawić go przy
    duplikacie, guard zobaczyłby go przez ``global_objects`` i całe
    scalanie padłoby na ``ProtectedError``.

    Ten test pilnuje, że guard rzeczywiście tak zareaguje — czyli że
    poprawka w ``_transfer_authorship_record`` (przepięcie wiersza na
    głównego autora) jest KONIECZNA, a nie kosmetyczna. Gdyby guard
    przepuszczał autorstwa w koszu, poprawka wyglądałaby na zbędną i ktoś
    by ją usunął, a wtedy w koszu zostałaby sierota wskazująca na autora,
    którego nie ma.
    """
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    wca = Wydawnictwo_Ciagle_Autor.global_objects.get(autor=autor_jan_nowak)
    wca.delete()  # wiersz w koszu, ale NADAL przy duplikacie

    assert not Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor_jan_nowak).exists()

    with pytest.raises(ProtectedError):
        autor_jan_nowak.delete()
