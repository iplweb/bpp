import sys

import rollbar
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import TrigramSimilarity
from django.db import models, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from bpp.models import Rekord, Rodzaj_Zrodla, Wydawnictwo_Ciagle, Zrodlo
from pbn_api.const import ACTIVE, DELETED
from pbn_api.models import Journal
from pbn_export_queue.models import PBN_Export_Queue

from .forms import PrzeMapowanieZrodlaForm
from .models import PrzeMapowanieZrodla


def find_by_issn(journal_skasowane, exclude_id=None):
    """
    Znajdź źródła w BPP po ISSN lub e-ISSN.
    Zwraca queryset źródeł z aktywnym PBN.
    """
    if not journal_skasowane.issn and not journal_skasowane.eissn:
        return Zrodlo.objects.none()

    q = Q()
    if journal_skasowane.issn:
        # Szukaj po ISSN w obu polach (issn i e_issn)
        q |= Q(issn=journal_skasowane.issn) | Q(e_issn=journal_skasowane.issn)
    if journal_skasowane.eissn:
        # Szukaj po e-ISSN w obu polach
        q |= Q(issn=journal_skasowane.eissn) | Q(e_issn=journal_skasowane.eissn)

    queryset = Zrodlo.objects.filter(q)
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)

    # Filtruj tylko te z aktywnym PBN i posortuj: najpierw z mniswId
    return (
        queryset.filter(pbn_uid__status=ACTIVE)
        .select_related("pbn_uid")
        .order_by(
            models.Case(
                models.When(pbn_uid__mniswId__isnull=False, then=0),
                default=1,
            ),
            "nazwa",
        )
    )


def find_by_name_prefix(title, exclude_id=None):
    """
    Znajdź źródła których nazwa zaczyna się tak samo jak przekazany tytuł.
    Używa ILIKE z % na końcu, np. "Współczesne Zarządzanie%" znajdzie:
    - "Współczesne Zarządzanie"
    - "Współczesne Zarządzanie i Marketing"
    ale NIE znajdzie:
    - "Współczesne Pielęgniarstwo"
    """
    if not title:
        return Zrodlo.objects.none()

    # Użyj całego tytułu jako prefiksu (bez dzielenia na słowa)
    # To znajdzie źródła które zaczynają się dokładnie tak jak szukane
    queryset = Zrodlo.objects.filter(nazwa__istartswith=title)

    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)

    # Filtruj tylko te z aktywnym PBN
    return (
        queryset.filter(pbn_uid__status=ACTIVE)
        .select_related("pbn_uid")
        .order_by(
            models.Case(
                models.When(pbn_uid__mniswId__isnull=False, then=0),
                default=1,
            ),
            "nazwa",
        )
    )


def find_by_trigram(title, exclude_id=None, min_similarity=0.5):
    """
    Znajdź źródła po podobieństwie nazwy używając trigram similarity.
    Szuka bezpośrednio w tabeli Zrodlo.
    """
    if not title:
        return Zrodlo.objects.none()

    queryset = Zrodlo.objects.annotate(
        similarity=TrigramSimilarity("nazwa", title)
    ).filter(similarity__gte=min_similarity)

    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)

    # Filtruj tylko te z aktywnym PBN
    return (
        queryset.filter(pbn_uid__status=ACTIVE)
        .select_related("pbn_uid")
        .order_by(
            "-similarity",
            models.Case(
                models.When(pbn_uid__mniswId__isnull=False, then=0),
                default=1,
            ),
            "nazwa",
        )
    )


def find_journals_by_issn(journal_skasowane, exclude_existing=True):
    """
    Znajdź Journale w PBN po ISSN lub e-ISSN.
    Domyślnie wyklucza te które już mają odpowiedniki w BPP.
    """
    if not journal_skasowane.issn and not journal_skasowane.eissn:
        return Journal.objects.none()

    q = Q()
    if journal_skasowane.issn:
        q |= Q(issn=journal_skasowane.issn) | Q(eissn=journal_skasowane.issn)
    if journal_skasowane.eissn:
        q |= Q(issn=journal_skasowane.eissn) | Q(eissn=journal_skasowane.eissn)

    queryset = (
        Journal.objects.filter(q).filter(status=ACTIVE).exclude(pk=journal_skasowane.pk)
    )

    if exclude_existing:
        # Wyklucz Journale które już mają odpowiedniki w BPP
        existing_pbn_uids = Zrodlo.objects.filter(pbn_uid__isnull=False).values_list(
            "pbn_uid_id", flat=True
        )
        queryset = queryset.exclude(pk__in=existing_pbn_uids)

    # Posortuj: najpierw z mniswId, potem alfabetycznie
    # Lepiej byłoby sortować po podobieństwie do nazwy ale to wymagałoby dodatkowej adnotacji
    return queryset.order_by(
        models.Case(
            models.When(mniswId__isnull=False, then=0),
            default=1,
        ),
        "title",
    )


def find_journals_by_prefix(title, exclude_existing=True):
    """
    Znajdź Journale w PBN których tytuł zaczyna się tak samo jak przekazany tytuł.
    """
    if not title:
        return Journal.objects.none()

    # Użyj całego tytułu jako prefiksu
    queryset = Journal.objects.filter(title__istartswith=title, status=ACTIVE)

    if exclude_existing:
        existing_pbn_uids = Zrodlo.objects.filter(pbn_uid__isnull=False).values_list(
            "pbn_uid_id", flat=True
        )
        queryset = queryset.exclude(pk__in=existing_pbn_uids)

    return queryset.order_by(
        models.Case(
            models.When(mniswId__isnull=False, then=0),
            default=1,
        ),
        "title",
    )


def find_journals_by_trigram(title, exclude_existing=True, min_similarity=0.5):
    """
    Znajdź Journale w PBN po podobieństwie tytułu.
    """
    if not title:
        return Journal.objects.none()

    queryset = Journal.objects.annotate(
        similarity=TrigramSimilarity("title", title)
    ).filter(similarity__gte=min_similarity, status=ACTIVE)

    if exclude_existing:
        existing_pbn_uids = Zrodlo.objects.filter(pbn_uid__isnull=False).values_list(
            "pbn_uid_id", flat=True
        )
        queryset = queryset.exclude(pk__in=existing_pbn_uids)

    return queryset.order_by(
        "-similarity",
        models.Case(
            models.When(mniswId__isnull=False, then=0),
            default=1,
        ),
        "title",
    )


def znajdz_podobne_zrodla(journal_skasowane, max_results=10):  # noqa: C901
    """
    Znajduje podobne źródła dla skasowanego czasopisma w PBN.
    Szuka w DWÓCH tabelach: Zrodlo (źródła w BPP) i Journal (źródła PBN które NIE są w BPP).

    Zwraca słownik z dwoma głównymi kategoriami:
    - zrodla_bpp: źródła które już są w BPP (z tabeli Zrodlo)
    - journale_pbn: źródła z PBN które NIE są w BPP (z tabeli Journal)

    Każda kategoria zawiera podkategorie: najlepsze, dobre, akceptowalne
    """
    results = {
        "zrodla_bpp": {"najlepsze": [], "dobre": [], "akceptowalne": []},
        "journale_pbn": {"najlepsze": [], "dobre": [], "akceptowalne": []},
    }

    # Pobierz źródło skasowane jeśli istnieje w BPP
    zrodlo_skasowane = None
    zrodlo_skasowane_id = None
    nazwa_do_wyszukania = journal_skasowane.title  # domyślnie użyj tytułu z PBN

    try:
        zrodlo_skasowane = Zrodlo.objects.get(pbn_uid=journal_skasowane)
        zrodlo_skasowane_id = zrodlo_skasowane.pk
        # Jeśli mamy źródło w BPP, użyj jego nazwy zamiast tytułu z PBN
        nazwa_do_wyszukania = zrodlo_skasowane.nazwa
    except Zrodlo.DoesNotExist:
        pass

    # CZĘŚĆ 1: SZUKANIE W TABELI ZRODLO (źródła już w BPP)
    znalezione_zrodla_ids = set()

    # 1.1. Szukaj po ISSN/e-ISSN w Zrodlo
    # Pobierz wszystkie aby znaleźć te które mają pasującą nazwę
    issn_matches = find_by_issn(journal_skasowane, exclude_id=zrodlo_skasowane_id)

    # Najpierw zbierz te które mają pasującą nazwę + ISSN
    issn_nazwa_matches_zrodla = []
    issn_only_matches_zrodla = []

    for zrodlo in issn_matches:
        if zrodlo.pk not in znalezione_zrodla_ids:
            # Sprawdź czy nazwa też się zgadza
            if nazwa_do_wyszukania and zrodlo.nazwa.lower().startswith(
                nazwa_do_wyszukania.lower()
            ):
                issn_nazwa_matches_zrodla.append(zrodlo)
            else:
                issn_only_matches_zrodla.append(zrodlo)

    # Dodaj najpierw te z pasującą nazwą (najlepsze dopasowania)
    for zrodlo in issn_nazwa_matches_zrodla[:max_results]:
        znalezione_zrodla_ids.add(zrodlo.pk)
        item = (zrodlo, "ISSN+NAZWA", 1.0)
        if zrodlo.pbn_uid and zrodlo.pbn_uid.mniswId:
            results["zrodla_bpp"]["najlepsze"].append(item)
        else:
            results["zrodla_bpp"]["dobre"].append(item)

    # Potem dodaj te z samym ISSN (dobre dopasowania)
    for zrodlo in issn_only_matches_zrodla[:max_results]:
        znalezione_zrodla_ids.add(zrodlo.pk)
        item = (zrodlo, "ISSN", 0.9)
        results["zrodla_bpp"]["dobre"].append(item)

    # 1.2. Szukaj po prefiksie nazwy w Zrodlo
    if nazwa_do_wyszukania:
        prefix_matches = find_by_name_prefix(
            nazwa_do_wyszukania, exclude_id=zrodlo_skasowane_id
        )[:max_results]

        for zrodlo in prefix_matches:
            if zrodlo.pk not in znalezione_zrodla_ids:
                znalezione_zrodla_ids.add(zrodlo.pk)
                item = (zrodlo, "PREFIX", 0.8)

                # PREFIX może być najlepsze TYLKO jeśli ISSN się zgadza
                issn_match = False
                if zrodlo_skasowane and journal_skasowane:
                    if (
                        journal_skasowane.issn and zrodlo.issn == journal_skasowane.issn
                    ) or (
                        journal_skasowane.eissn
                        and zrodlo.e_issn == journal_skasowane.eissn
                    ):
                        issn_match = True

                if issn_match and zrodlo.pbn_uid and zrodlo.pbn_uid.mniswId:
                    results["zrodla_bpp"]["najlepsze"].append(item)
                else:
                    results["zrodla_bpp"]["dobre"].append(item)

    # 1.3. Szukaj po podobieństwie w Zrodlo
    if nazwa_do_wyszukania:
        similarity_matches = find_by_trigram(
            nazwa_do_wyszukania, exclude_id=zrodlo_skasowane_id, min_similarity=0.5
        )[:max_results]

        for zrodlo in similarity_matches:
            if zrodlo.pk not in znalezione_zrodla_ids:
                znalezione_zrodla_ids.add(zrodlo.pk)
                podobienstwo = getattr(zrodlo, "similarity", 0.5)
                item = (zrodlo, "SIMILARITY", podobienstwo)

                if zrodlo.pbn_uid and zrodlo.pbn_uid.mniswId and podobienstwo > 0.7:
                    results["zrodla_bpp"]["dobre"].append(item)
                else:
                    results["zrodla_bpp"]["akceptowalne"].append(item)

    # CZĘŚĆ 2: SZUKANIE W TABELI JOURNAL (źródła PBN które NIE są w BPP)
    znalezione_journal_ids = set()

    # 2.1. Szukaj po ISSN/e-ISSN w Journal
    # Pobierz wszystkie aby znaleźć te które mają pasującą nazwę
    journal_issn_matches = find_journals_by_issn(journal_skasowane)

    # Najpierw zbierz te które mają pasującą nazwę + ISSN
    issn_nazwa_matches = []
    issn_only_matches = []

    for journal in journal_issn_matches:
        if journal.pk not in znalezione_journal_ids:
            # Sprawdź czy nazwa też się zgadza
            if nazwa_do_wyszukania and journal.title.lower().startswith(
                nazwa_do_wyszukania.lower()
            ):
                issn_nazwa_matches.append(journal)
            else:
                issn_only_matches.append(journal)

    # Dodaj najpierw te z pasującą nazwą (najlepsze dopasowania)
    for journal in issn_nazwa_matches[:max_results]:
        znalezione_journal_ids.add(journal.pk)
        item = (journal, "ISSN+NAZWA", 1.0)
        if journal.mniswId:
            results["journale_pbn"]["najlepsze"].append(item)
        else:
            results["journale_pbn"]["dobre"].append(item)

    # Potem dodaj te z samym ISSN (dobre dopasowania)
    for journal in issn_only_matches[:max_results]:
        znalezione_journal_ids.add(journal.pk)
        item = (journal, "ISSN", 0.9)
        results["journale_pbn"]["dobre"].append(item)

    # 2.2. Szukaj po prefiksie tytułu w Journal
    if nazwa_do_wyszukania:
        journal_prefix_matches = find_journals_by_prefix(nazwa_do_wyszukania)[
            :max_results
        ]

        for journal in journal_prefix_matches:
            if journal.pk not in znalezione_journal_ids:
                znalezione_journal_ids.add(journal.pk)
                item = (journal, "PREFIX", 0.8)

                # PREFIX może być najlepsze TYLKO jeśli ISSN się zgadza
                issn_match = False
                if journal_skasowane:
                    if (
                        journal_skasowane.issn
                        and journal.issn == journal_skasowane.issn
                    ) or (
                        journal_skasowane.eissn
                        and journal.eissn == journal_skasowane.eissn
                    ):
                        issn_match = True

                if issn_match and journal.mniswId:
                    results["journale_pbn"]["najlepsze"].append(item)
                elif journal.mniswId:
                    # Jeśli ma mniswId ale ISSN się nie zgadza - to "dobre" nie "najlepsze"
                    results["journale_pbn"]["dobre"].append(item)
                else:
                    results["journale_pbn"]["dobre"].append(item)

    # 2.3. Szukaj po podobieństwie w Journal
    if nazwa_do_wyszukania:
        journal_similarity_matches = find_journals_by_trigram(nazwa_do_wyszukania)[
            :max_results
        ]

        for journal in journal_similarity_matches:
            if journal.pk not in znalezione_journal_ids:
                znalezione_journal_ids.add(journal.pk)
                podobienstwo = getattr(journal, "similarity", 0.5)
                item = (journal, "SIMILARITY", podobienstwo)

                if journal.mniswId and podobienstwo > 0.7:
                    results["journale_pbn"]["dobre"].append(item)
                else:
                    results["journale_pbn"]["akceptowalne"].append(item)

    # Ogranicz każdą kategorię do max_results i posortuj po podobieństwie
    for main_category in results.values():
        for key in main_category:
            # Sortuj po podobieństwie (trzeci element krotki)
            main_category[key].sort(key=lambda x: x[2], reverse=True)
            main_category[key] = main_category[key][:max_results]

    return results


@login_required
def lista_skasowanych_zrodel(request):
    """Widok listy wszystkich źródeł skasowanych w PBN."""

    # Znajdź wszystkie źródła w BPP, które mają pbn_uid ze statusem DELETED
    zrodla_skasowane = (
        Zrodlo.objects.filter(pbn_uid__status=DELETED)
        .select_related("pbn_uid")
        .annotate(liczba_rekordow=Count("wydawnictwo_ciagle"))
    )

    # Dodaj statystyki
    total_zrodla = zrodla_skasowane.count()
    total_rekordy = sum(z.liczba_rekordow for z in zrodla_skasowane)

    context = {
        "zrodla_skasowane": zrodla_skasowane,
        "total_zrodla": total_zrodla,
        "total_rekordy": total_rekordy,
    }
    return render(
        request, "przemapuj_zrodla_pbn/lista_skasowanych_zrodel.html", context
    )


@login_required
def przemapuj_zrodlo(request, zrodlo_id):  # noqa: C901
    """Główny widok do przemapowania źródła."""
    zrodlo = get_object_or_404(Zrodlo, pk=zrodlo_id)

    # Sprawdź czy źródło jest faktycznie skasowane w PBN
    if not zrodlo.pbn_uid or zrodlo.pbn_uid.status != DELETED:
        messages.error(
            request, "To źródło nie jest skasowane w PBN. Nie można go przemapować."
        )
        return redirect("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")

    # Policz liczbę rekordów
    liczba_rekordow = Rekord.objects.filter(zrodlo=zrodlo).count()

    # Znajdź podobne źródła (w obu tabelach)
    sugerowane = znajdz_podobne_zrodla(zrodlo.pbn_uid)

    # Przygotuj dane dla formularza - tylko źródła z BPP
    wszystkie_zrodla = []
    for kategoria in ["najlepsze", "dobre", "akceptowalne"]:
        wszystkie_zrodla.extend(sugerowane["zrodla_bpp"][kategoria])

    if wszystkie_zrodla:
        # Struktura krotki: (zrodlo, typ_dopasowania, podobienstwo)
        sugerowane_ids = [item[0].pk for item in wszystkie_zrodla]
        sugerowane_queryset = Zrodlo.objects.filter(pk__in=sugerowane_ids)
    else:
        # Brak sugestii - pokaż wszystkie aktywne źródła
        sugerowane_queryset = (
            Zrodlo.objects.filter(pbn_uid__status=ACTIVE)
            .select_related("pbn_uid")
            .order_by(
                models.Case(
                    models.When(pbn_uid__mniswId__isnull=False, then=0),
                    default=1,
                ),
                "nazwa",
            )[:20]
        )

    # Zbierz wszystkie journale z PBN
    wszystkie_journale = []
    for kategoria in ["najlepsze", "dobre", "akceptowalne"]:
        wszystkie_journale.extend(sugerowane["journale_pbn"][kategoria])

    if request.method == "POST":
        form = PrzeMapowanieZrodlaForm(
            request.POST,
            zrodlo_skasowane=zrodlo,
            sugerowane_zrodla=sugerowane_queryset,
            sugerowane_journale=wszystkie_journale,
        )

        if "confirm" in request.POST:
            # Użytkownik potwierdził przemapowanie
            if form.is_valid():
                typ_wyboru = form.cleaned_data.get("typ_wyboru")

                # Określ źródło docelowe
                if typ_wyboru == PrzeMapowanieZrodlaForm.TYP_JOURNAL:
                    # Użytkownik wybrał Journal z PBN - utwórz nowe Zrodlo
                    journal_id = form.cleaned_data["journal_docelowy"]
                    journal_docelowy = Journal.objects.get(pk=journal_id)

                    # Pobierz domyślny rodzaj "czasopismo"
                    rodzaj_czasopismo = Rodzaj_Zrodla.objects.get(nazwa="czasopismo")

                    # Utwórz nowe Zrodlo na podstawie Journal
                    zrodlo_nowe = Zrodlo.objects.create(
                        nazwa=journal_docelowy.title,
                        issn=journal_docelowy.issn,
                        e_issn=journal_docelowy.eissn,
                        pbn_uid=journal_docelowy,
                        rodzaj=rodzaj_czasopismo,
                    )
                    messages.info(
                        request,
                        f'Utworzono nowe źródło "{zrodlo_nowe.nazwa}" na podstawie danych z PBN.',
                    )
                else:
                    # Użytkownik wybrał istniejące Zrodlo
                    zrodlo_nowe = form.cleaned_data["zrodlo_docelowe"]

                # Walidacja: nie można przemapować na źródło również skasowane
                if zrodlo_nowe.pbn_uid and zrodlo_nowe.pbn_uid.status == DELETED:
                    messages.error(
                        request,
                        "Nie można przemapować na źródło, które również jest skasowane w PBN!",
                    )
                    return redirect(
                        "przemapuj_zrodla_pbn:przemapuj_zrodlo", zrodlo_id=zrodlo.pk
                    )

                try:
                    with transaction.atomic():
                        # Zbierz informacje o rekordach przed przemapowaniem
                        rekordy = Rekord.objects.filter(zrodlo=zrodlo)
                        rekordy_historia = []
                        rekordy_do_wyslania = []

                        for rekord in rekordy:
                            rekordy_historia.append(
                                {
                                    "id": list(rekord.pk),
                                    "tytul": rekord.tytul_oryginalny,
                                    "rok": rekord.rok,
                                    "opis_bibliograficzny": rekord.opis_bibliograficzny_cache
                                    or "",
                                }
                            )
                            # Zbierz oryginalne rekordy do wysłania do PBN
                            rekordy_do_wyslania.append(rekord.original)

                        liczba_rekordow_updated = Wydawnictwo_Ciagle.objects.filter(
                            zrodlo=zrodlo
                        ).update(zrodlo=zrodlo_nowe)

                        # Zapisz log operacji
                        PrzeMapowanieZrodla.objects.create(
                            zrodlo_skasowane_pbn_uid=zrodlo.pbn_uid,
                            zrodlo_stare=zrodlo,
                            zrodlo_nowe=zrodlo_nowe,
                            liczba_rekordow=liczba_rekordow_updated,
                            utworzono_przez=request.user,
                            rekordy_historia=rekordy_historia,
                        )

                        # Dodaj do kolejki PBN
                        sukces_pbn = 0
                        bledy_pbn = []
                        for original_rekord in rekordy_do_wyslania:
                            try:
                                PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
                                    user=request.user, rekord=original_rekord
                                )
                                sukces_pbn += 1
                            except Exception as e:
                                bledy_pbn.append(
                                    f"Rekord {original_rekord.pk}: {str(e)}"
                                )

                        messages.success(
                            request,
                            f"Pomyślnie przemapowano {liczba_rekordow_updated} rekordów "
                            f'ze źródła "{zrodlo}" do źródła "{zrodlo_nowe}". '
                            f"Dodano {sukces_pbn} rekordów do kolejki eksportu PBN.",
                        )

                        if bledy_pbn:
                            messages.warning(
                                request,
                                f"Wystąpiły błędy przy dodawaniu {len(bledy_pbn)} rekordów do kolejki PBN. "
                                f"Szczegóły: {'; '.join(bledy_pbn[:5])}",
                            )

                        return redirect("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")

                except Exception as e:
                    rollbar.report_exc_info(sys.exc_info())
                    messages.error(
                        request, f"Wystąpił błąd podczas przemapowania: {str(e)}"
                    )

        elif "preview" in request.POST:
            # Użytkownik chce zobaczyć podgląd
            if form.is_valid():
                typ_wyboru = form.cleaned_data.get("typ_wyboru")

                # Określ źródło docelowe dla podglądu
                journal_docelowy = None
                if typ_wyboru == PrzeMapowanieZrodlaForm.TYP_JOURNAL:
                    journal_id = form.cleaned_data["journal_docelowy"]
                    journal_docelowy = Journal.objects.get(pk=journal_id)
                    zrodlo_nowe_nazwa = f"{journal_docelowy.title} (NOWE ze źródła PBN)"
                    zrodlo_nowe = None  # Będzie utworzone dopiero po zatwierdzeniu
                else:
                    zrodlo_nowe = form.cleaned_data["zrodlo_docelowe"]
                    zrodlo_nowe_nazwa = str(zrodlo_nowe)

                # Pobierz przykładowe rekordy
                rekordy_przyklad = Rekord.objects.filter(zrodlo=zrodlo)[:10]

                context = {
                    "zrodlo": zrodlo,
                    "zrodlo_nowe": zrodlo_nowe,
                    "zrodlo_nowe_nazwa": zrodlo_nowe_nazwa,
                    "journal_docelowy": journal_docelowy,
                    "liczba_rekordow": liczba_rekordow,
                    "rekordy_przyklad": rekordy_przyklad,
                    "form": form,
                    "preview": True,
                    "sugerowane": sugerowane,
                }
                return render(
                    request, "przemapuj_zrodla_pbn/przemapuj_zrodlo.html", context
                )

    else:
        form = PrzeMapowanieZrodlaForm(
            zrodlo_skasowane=zrodlo,
            sugerowane_zrodla=sugerowane_queryset,
            sugerowane_journale=wszystkie_journale,
        )

    # Pobierz historię przemapowań dla tego źródła
    historia = PrzeMapowanieZrodla.objects.filter(zrodlo_stare=zrodlo).select_related(
        "zrodlo_nowe", "utworzono_przez"
    )[:10]

    context = {
        "zrodlo": zrodlo,
        "liczba_rekordow": liczba_rekordow,
        "form": form,
        "preview": False,
        "sugerowane": sugerowane,
        "historia": historia,
    }
    return render(request, "przemapuj_zrodla_pbn/przemapuj_zrodlo.html", context)


@login_required
def usun_zrodlo(request, zrodlo_id):
    """Usuwa źródło skasowane w PBN, które nie ma żadnych rekordów."""
    zrodlo = get_object_or_404(Zrodlo, pk=zrodlo_id)

    # Sprawdź czy źródło jest faktycznie skasowane w PBN
    if not zrodlo.pbn_uid or zrodlo.pbn_uid.status != DELETED:
        messages.error(
            request, "To źródło nie jest skasowane w PBN. Nie można go usunąć."
        )
        return redirect("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")

    # Policz liczbę rekordów
    liczba_rekordow = Rekord.objects.filter(zrodlo=zrodlo).count()

    if liczba_rekordow > 0:
        messages.error(
            request,
            f"To źródło ma {liczba_rekordow} rekordów. "
            f"Nie można usunąć źródła z rekordami. Użyj funkcji przemapowania.",
        )
        return redirect("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")

    if request.method == "POST":
        try:
            with transaction.atomic():
                # Zapisz log operacji przed usunięciem
                PrzeMapowanieZrodla.objects.create(
                    typ_operacji=PrzeMapowanieZrodla.TYP_USUNIECIE,
                    zrodlo_skasowane_pbn_uid=zrodlo.pbn_uid,
                    zrodlo_stare=zrodlo,
                    zrodlo_nowe=None,
                    liczba_rekordow=0,
                    utworzono_przez=request.user,
                    rekordy_historia=[],
                )

                # Zapisz informacje o źródle przed usunięciem
                nazwa_zrodla = str(zrodlo)

                # Usuń źródło
                zrodlo.delete()

                messages.success(
                    request,
                    f'Pomyślnie usunięto źródło "{nazwa_zrodla}" z systemu BPP.',
                )
                return redirect("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")

        except Exception as e:
            rollbar.report_exc_info(sys.exc_info())
            messages.error(request, f"Wystąpił błąd podczas usuwania: {str(e)}")
            return redirect("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")

    # GET - pokaż stronę potwierdzenia
    context = {
        "zrodlo": zrodlo,
        "liczba_rekordow": liczba_rekordow,
    }
    return render(request, "przemapuj_zrodla_pbn/usun_zrodlo.html", context)
