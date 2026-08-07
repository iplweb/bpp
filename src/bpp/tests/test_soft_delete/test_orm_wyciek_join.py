"""Wyciek soft-delete o warstwę wyżej niż widoki SQL: JOIN w ORM-ie.

Faza 01 uczyniła ``Wydawnictwo_Ciagle_Autor`` / ``Wydawnictwo_Zwarte_Autor`` /
``Patent_Autor`` soft-delete. Domyślny manager ``objects`` odcina skasowane —
ale **wyłącznie gdy pytamy o sam through-model**. Kiedy filtrujemy publikację
*przez* relację (``Wydawnictwo_Ciagle.objects.filter(autorzy_set__…)``,
``annotate(Count("autorzy_set"))``, ``Autor.objects.annotate(Count(
"wydawnictwo_ciagle_autor"))``), Django buduje JOIN po SUROWEJ tabeli i
managera **w ogóle nie pyta** — dokładnie ta sama klasa błędu, co widoki SQL
naprawione migracjami 0494/0495/rozbieznosci-0022, tylko w Pythonie.

Moduł ma dwie części:

1. **Kanarki semantyki Django** — przypinają, CO w ogóle przecieka, a co nie.
   Dostęp instancyjny (``wc.autorzy_set``) i ``prefetch_related`` idą przez
   ``_default_manager`` i są bezpieczne; JOIN nie jest. Gdyby Django kiedyś
   zmieniło którekolwiek z tych zachowań, te trzy testy zapalą się pierwsze
   i powiedzą, czy reszta naprawek stała się zbędna, czy niewystarczająca.
2. **Regresje konkretnych miejsc produkcyjnych** — po jednym teście na
   naprawione zapytanie.
"""

import pytest
from django.db.models import Count, Q

from bpp.models import (
    Autor,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)

# --------------------------------------------------------------------------
# 1. Kanarki semantyki Django
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_dostep_instancyjny_autorzy_set_odcina_skasowane(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    """``wc.autorzy_set`` (RelatedManager) dziedziczy po ``_default_manager``.

    Django buduje klasę RelatedManagera z ``related_model._default_manager.
    __class__`` — czyli z ``BppSoftDeleteManager``. Dostęp instancyjny jest
    więc BEZPIECZNY: ~70 wywołań ``obj.autorzy_set.…`` w kodzie produkcyjnym
    nie wymaga żadnych poprawek.
    """
    wc = wydawnictwo_ciagle_z_dwoma_autorami
    assert wc.autorzy_set.count() == 2

    wc.autorzy_set.first().delete()

    assert wc.autorzy_set.count() == 1
    assert wc.autorzy_set.all().count() == 1


@pytest.mark.django_db
def test_prefetch_related_autorzy_set_odcina_skasowane(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    """``prefetch_related("autorzy_set…")`` też idzie przez ``_default_manager``.

    ``RelatedManager.get_prefetch_querysets()`` woła ``super().get_queryset()``
    — czyli manager z filtrem soft-delete. Dlatego ``prefetch_related`` z
    ``autorzy_set__`` w ścieżce (m.in. ``ewaluacja_optymalizacja/tasks/
    discipline_swap/analysis.py``, viewsety ``api_v1``, ``cerif_export``)
    NIE jest wyciekiem, mimo że wygląda jak lookup przez relację.
    """
    wc = wydawnictwo_ciagle_z_dwoma_autorami
    wc.autorzy_set.first().delete()

    pobrany = Wydawnictwo_Ciagle.objects.prefetch_related("autorzy_set__autor").get(
        pk=wc.pk
    )
    assert len(pobrany.autorzy_set.all()) == 1


@pytest.mark.django_db
def test_join_przez_relacje_WIDZI_skasowane_bez_jawnego_filtra(
    wydawnictwo_ciagle_z_autorem,
):
    """Kanarek NEGATYWNY: goły JOIN po ``autorzy_set__`` przecieka.

    To opis stanu faktycznego Django, nie bug do naprawienia — test pilnuje,
    że PRZYCZYNA wszystkich poprawek niżej nadal istnieje. Gdyby kiedyś
    przestała (np. Django nauczyłoby się pytać manager przy JOIN-ie), ten
    test padnie i będzie sygnałem, że jawne ``deleted_at__isnull=True``
    w kodzie produkcyjnym można wycofać.
    """
    wc = wydawnictwo_ciagle_z_autorem
    autor = wc.autorzy_set.first().autor
    wc.autorzy_set.first().delete()

    assert not Wydawnictwo_Ciagle_Autor.objects.filter(rekord=wc).exists()
    # ...a mimo to JOIN nadal łapie publikację:
    assert Wydawnictwo_Ciagle.objects.filter(autorzy_set__autor=autor).exists()
    # ...i predykat na TYM SAMYM joinie ją odcina:
    assert not Wydawnictwo_Ciagle.objects.filter(
        autorzy_set__autor=autor,
        autorzy_set__deleted_at__isnull=True,
    ).exists()


# --------------------------------------------------------------------------
# 2. Regresje konkretnych miejsc produkcyjnych
# --------------------------------------------------------------------------


def _ustaw_dyscypline(autorstwo, dyscyplina, rodzaj_autora, **reszta):
    """Ustawia dyscyplinę na autorstwie razem z wymaganym ``Autor_Dyscyplina``.

    ``BazaModeluOdpowiedzialnosciAutorow`` waliduje przy KAŻDYM ``save()``, że
    autor ma na dany rok przypisanie do tej dyscypliny — a soft-delete też
    idzie przez ``save()``, więc bez tego przypisania wywaliłby się już sam
    ``delete()``. Stąd tworzymy ``Autor_Dyscyplina``, zamiast obchodzić
    walidację ``.update()``-em.
    """
    from bpp.models import Autor_Dyscyplina

    Autor_Dyscyplina.objects.get_or_create(
        autor=autorstwo.autor,
        rok=autorstwo.rekord.rok,
        defaults=dict(
            dyscyplina_naukowa=dyscyplina,
            rodzaj_autora=rodzaj_autora,
        ),
    )
    autorstwo.dyscyplina_naukowa = dyscyplina
    for k, v in reszta.items():
        setattr(autorstwo, k, v)
    autorstwo.save()


@pytest.mark.django_db
def test_import_common_liczba_publikacji_kandydata_pomija_skasowane(
    wydawnictwo_ciagle_z_autorem,
):
    """``import_common.core.autor._publikacji_counts_bulk`` (deduplikator).

    Licznik po ``Count("wydawnictwo_ciagle_autor")`` liczył także autorstwa
    skasowane, więc husk autora pokazywał się w deduplikatorze jako autor
    z dorobkiem.
    """
    from import_common.core.autor import _publikacji_counts_bulk

    autor = wydawnictwo_ciagle_z_autorem.autorzy_set.first().autor
    assert _publikacji_counts_bulk([autor.pk]) == {autor.pk: 1}

    wydawnictwo_ciagle_z_autorem.autorzy_set.first().delete()

    assert _publikacji_counts_bulk([autor.pk]).get(autor.pk, 0) == 0


@pytest.mark.django_db
def test_admin_filter_bez_dyscyplin_nie_liczy_skasowanych(
    wydawnictwo_ciagle_z_dwoma_autorami, dyscyplina1, rodzaj_autora_n
):
    """``bpp.admin.filters.BezJakichkolwiekDyscyplinFilter``.

    Filtr porównuje ``Count("autorzy_set")`` z liczbą autorstw bez
    dyscypliny. Skasowane autorstwo Z dyscypliną podbijało tylko licznik
    ogólny → rekord, w którym WSZYSCY żywi autorzy są bez dyscypliny,
    wypadał z wyników.
    """
    from bpp.admin.filters import BezJakichkolwiekDyscyplinFilter

    wc = wydawnictwo_ciagle_z_dwoma_autorami
    pierwsze = wc.autorzy_set.first()
    _ustaw_dyscypline(pierwsze, dyscyplina1, rodzaj_autora_n)
    pierwsze.delete()
    # Zostało jedno ŻYWE autorstwo, BEZ dyscypliny → rekord ma być złapany.

    f = BezJakichkolwiekDyscyplinFilter(
        request=None,
        params={"_bjkd_": ["tak"]},
        model=Wydawnictwo_Ciagle,
        model_admin=None,
    )
    qs = f.queryset(None, Wydawnictwo_Ciagle.objects.all())
    assert list(qs.values_list("pk", flat=True)) == [wc.pk]


@pytest.mark.django_db
def test_pbn_wysylka_liczniki_oswiadczen_pomijaja_skasowane(
    wydawnictwo_ciagle_z_dwoma_autorami, dyscyplina1, rodzaj_autora_n
):
    """``pbn_wysylka_oswiadczen.queries.get_publications_queryset``.

    Skasowane oświadczenie liczyło się do ``liczba_oswiadczen``, więc filtr
    ``tylko_odpiete`` (oswiadczen > 0 AND przypietych = 0) wskazywał do
    wycofania z PBN rekordy, na których nie ma już żywego autorstwa.
    """
    from pbn_api.models import Publication
    from pbn_wysylka_oswiadczen.queries import get_publications_queryset

    wc = wydawnictwo_ciagle_z_dwoma_autorami
    for wca in wc.autorzy_set.all():
        _ustaw_dyscypline(wca, dyscyplina1, rodzaj_autora_n, przypieta=False)

    wc.pbn_uid = Publication.objects.create(mongoId="x" * 24, status="ACTIVE")
    wc.save()

    wc.autorzy_set.first().delete()

    ciagle_qs, _zwarte = get_publications_queryset(
        rok_od=wc.rok, rok_do=wc.rok, with_annotations=True
    )
    obiekt = ciagle_qs.get(pk=wc.pk)
    assert obiekt.liczba_oswiadczen == 1
    assert obiekt.liczba_przypietych == 0


@pytest.mark.django_db
def test_ewaluacja_verification_licznik_pomija_skasowane(
    wydawnictwo_ciagle_z_dwoma_autorami, dyscyplina1, rodzaj_autora_n, admin_client
):
    """``ewaluacja_optymalizacja.views.verification`` — licznik „brak
    oświadczenia" nie może liczyć publikacji po skasowanym autorstwie."""
    from django.urls import reverse

    wc = wydawnictwo_ciagle_z_dwoma_autorami
    Wydawnictwo_Ciagle.objects.filter(pk=wc.pk).update(rok=2023)
    for wca in wc.autorzy_set.all():
        _ustaw_dyscypline(wca, dyscyplina1, rodzaj_autora_n, data_oswiadczenia=None)

    url = reverse("ewaluacja_optymalizacja:database-verification")
    assert admin_client.get(url).context["brak_oswiadczenia_ciagle_count"] == 1

    for wca in wc.autorzy_set.all():
        wca.delete()

    assert admin_client.get(url).context["brak_oswiadczenia_ciagle_count"] == 0


@pytest.mark.django_db
def test_pbn_wyslij_oswiadczenia_pomija_publikacje_bez_zywego_autorstwa(
    wydawnictwo_ciagle_z_autorem, dyscyplina1, rodzaj_autora_n
):
    """``pbn_wyslij_oswiadczenia_instytucji._get_publications_by_year``."""
    from pbn_api.management.commands.pbn_wyslij_oswiadczenia_instytucji import (
        Command,
    )
    from pbn_api.models import Publication

    wc = wydawnictwo_ciagle_z_autorem
    _ustaw_dyscypline(wc.autorzy_set.first(), dyscyplina1, rodzaj_autora_n)
    wc.pbn_uid = Publication.objects.create(mongoId="y" * 24, status="ACTIVE")
    wc.save()

    def _znalezione():
        return {p.pk for p in Command()._get_publications_by_year(wc.rok)}

    assert wc.pk in _znalezione()

    wc.autorzy_set.first().delete()

    assert wc.pk not in _znalezione()


@pytest.mark.django_db
def test_rozbieznosci_scope_do_uczelni_ignoruje_skasowane(
    settings, site1, jednostka_uczelnia1, jednostka_uczelnia2, typy_odpowiedzialnosci
):
    """``rozbieznosci.views._scope_do_uczelni`` — atrybucja multi-host.

    Skasowane autorstwo nie może przypisywać rekordu do uczelni; inaczej
    rekord wycieka na cudzy host. Test wymaga DWÓCH uczelni — przy jednej
    helper jest no-opem (guard ``tylko_jedna_uczelnia``).
    """
    from model_bakery import baker

    from fixtures.conftest_multisite import make_request_for_site
    from rozbieznosci.views import _scope_do_uczelni

    settings.ALLOWED_HOSTS = ["*"]
    wc = baker.make("bpp.Wydawnictwo_Ciagle", rok=2023)
    baker.make(
        "bpp.Wydawnictwo_Ciagle_Autor",
        rekord=wc,
        autor=baker.make("bpp.Autor"),
        jednostka=jednostka_uczelnia1,
    )
    request = make_request_for_site(site1, path="/rozbieznosci/if/")

    qs_przed = _scope_do_uczelni(Wydawnictwo_Ciagle.objects.all(), request)
    assert wc.pk in set(qs_przed.values_list("pk", flat=True))

    wc.autorzy_set.first().delete()

    qs_po = _scope_do_uczelni(Wydawnictwo_Ciagle.objects.all(), request)
    assert wc.pk not in set(qs_po.values_list("pk", flat=True))


@pytest.mark.django_db
def test_export_bibtex_filtr_po_autorze_pomija_skasowane(
    wydawnictwo_ciagle_z_autorem, capsys
):
    """``bpp.management.commands.export_bibtex`` — ``--author``.

    Filtr szedł po M2M ``autorzy__nazwisko``; skasowane autorstwo dalej
    wciągało publikację do eksportu. (``capsys``, bo komenda drukuje rekordy
    zwykłym ``print()``, a nie przez ``self.stdout``.)
    """
    from django.core.management import call_command
    from django.core.management.base import CommandError

    wc = wydawnictwo_ciagle_z_autorem
    nazwisko = wc.autorzy_set.first().autor.nazwisko

    call_command("export_bibtex", author=nazwisko)
    assert "Exporting 1 publications" in capsys.readouterr().out

    wc.autorzy_set.first().delete()

    # Komenda kończy się CommandError-em, gdy nic nie pasuje — to jest tu
    # POŻĄDANY wynik: po skasowaniu autorstwa nie ma czego eksportować.
    with pytest.raises(CommandError, match="No publications found"):
        call_command("export_bibtex", author=nazwisko)


@pytest.mark.django_db
def test_ranking_autora_w_wyszukiwarce_nie_liczy_skasowanych(
    wydawnictwo_ciagle_z_autorem,
):
    """``AutorManager.fulltext_annotate`` — ``search__rank`` husku autora.

    Ranking podpowiedzi autora to liczba jego autorstw. Bez predykatu husk
    (wszystkie autorstwa skasowane) trzymał swoją pozycję w podpowiedziach.
    """
    autor = wydawnictwo_ciagle_z_autorem.autorzy_set.first().autor

    def _rank():
        return (
            Autor.objects.filter(pk=autor.pk)
            .annotate(**Autor.objects.fulltext_annotate(None, None))
            .values_list("search__rank", flat=True)[0]
        )

    assert _rank() == 1

    wydawnictwo_ciagle_z_autorem.autorzy_set.first().delete()

    assert _rank() == 0


@pytest.mark.django_db
def test_djangoql_deleted_at_jest_wyrazalne_w_zapytaniu(
    wydawnictwo_ciagle_z_autorem,
):
    """Deduplikator otwiera changelist zapytaniem DjangoQL — musi dać się
    w nim wyrazić ``autorzy_set.deleted_at = None``.

    Bez tego (a) składnia sypie się na nieznanym polu, albo (b) — gorzej —
    zapytanie przechodzi, ale JOIN pokazuje skasowane autorstwa, czyli
    dokładnie husk, który deduplikator ma pomagać usuwać.
    """
    from djangoql.queryset import apply_search

    from bpp.djangoql_schema import BppQLSchema

    wc = wydawnictwo_ciagle_z_autorem
    autor_id = wc.autorzy_set.first().autor_id
    zapytanie = f"autorzy_set.autor.id = {autor_id} and autorzy_set.deleted_at = None"

    qs = apply_search(Wydawnictwo_Ciagle.objects.all(), zapytanie, schema=BppQLSchema)
    assert wc.pk in set(qs.values_list("pk", flat=True))

    wc.autorzy_set.first().delete()

    qs = apply_search(Wydawnictwo_Ciagle.objects.all(), zapytanie, schema=BppQLSchema)
    assert wc.pk not in set(qs.values_list("pk", flat=True))


@pytest.mark.django_db
def test_denorm_rebuild_CELOWO_widzi_skasowane(wydawnictwo_ciagle_z_autorem):
    """``bpp.models.dyscyplina_naukowa`` — jedyny ŚWIADOMY brak predykatu.

    ``rebuild_instances_of(klass, rok=…, autorzy_set__autor_id=…)`` wybiera
    publikacje DO PRZELICZENIA. Publikacja, której autorstwo skasowano,
    potrzebuje przeliczenia tak samo (a nawet bardziej) niż ta z autorstwem
    żywym — dodanie ``deleted_at__isnull=True`` wycięłoby ją ze zbioru
    i zostawiło nieaktualne punkty do nocnej rekalkulacji. Ten test przypina
    tę decyzję, żeby nikt jej „nie naprawił" hurtem.
    """
    wc = wydawnictwo_ciagle_z_autorem
    autor_id = wc.autorzy_set.first().autor_id
    wc.autorzy_set.first().delete()

    assert Wydawnictwo_Ciagle.objects.filter(
        rok=wc.rok, autorzy_set__autor_id=autor_id
    ).exists(), "rebuild_instances_of musi nadal widzieć tę publikację"


@pytest.mark.django_db
def test_kanarek_agregat_bez_predykatu_zawyza(wydawnictwo_ciagle_z_autorem):
    """Kanarek negatywny dla agregatów (symetryczny do tego dla ``filter``)."""
    wc = wydawnictwo_ciagle_z_autorem
    wc.autorzy_set.first().delete()

    zawyzony = (
        Wydawnictwo_Ciagle.objects.filter(pk=wc.pk)
        .annotate(n=Count("autorzy_set"))
        .values_list("n", flat=True)[0]
    )
    poprawny = (
        Wydawnictwo_Ciagle.objects.filter(pk=wc.pk)
        .annotate(
            n=Count("autorzy_set", filter=Q(autorzy_set__deleted_at__isnull=True))
        )
        .values_list("n", flat=True)[0]
    )
    assert zawyzony == 1
    assert poprawny == 0
