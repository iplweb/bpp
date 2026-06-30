import logging
import sys

import rollbar
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import TrigramSimilarity
from django.db import models, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from bpp.models import Rekord, Rodzaj_Zrodla, Wydawnictwo_Ciagle, Zrodlo
from bpp.util import zaloguj_polkniety_wyjatek
from pbn_api.const import ACTIVE, DELETED
from pbn_api.models import Journal
from pbn_export_queue.models import PBN_Export_Queue

from .forms import PrzeMapowanieZrodlaForm
from .models import PrzeMapowanieZrodla

logger = logging.getLogger(__name__)


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


def _dodaj_issn_dopasowania(
    matches, nazwa_do_wyszukania, name_attr, has_mnisw, bucket, max_results, seen_ids
):
    """Krok ISSN/e-ISSN: rozdziel na (ISSN+NAZWA) i (sam ISSN) i wrzuć do koszyka.

    - ISSN+NAZWA (score 1.0): "najlepsze" gdy ma mniswId, inaczej "dobre".
    - sam ISSN (score 0.9): zawsze "dobre".
    """
    issn_nazwa = []
    issn_only = []
    for obj in matches:
        if obj.pk in seen_ids:
            continue
        nazwa_obj = getattr(obj, name_attr)
        if nazwa_do_wyszukania and nazwa_obj.lower().startswith(
            nazwa_do_wyszukania.lower()
        ):
            issn_nazwa.append(obj)
        else:
            issn_only.append(obj)

    for obj in issn_nazwa[:max_results]:
        seen_ids.add(obj.pk)
        item = (obj, "ISSN+NAZWA", 1.0)
        if has_mnisw(obj):
            bucket["najlepsze"].append(item)
        else:
            bucket["dobre"].append(item)

    for obj in issn_only[:max_results]:
        seen_ids.add(obj.pk)
        bucket["dobre"].append((obj, "ISSN", 0.9))


def _dodaj_prefix_dopasowania(matches, has_mnisw, issn_match, bucket, seen_ids):
    """Krok PREFIX (score 0.8): "najlepsze" tylko gdy ISSN się zgadza i jest
    mniswId, w przeciwnym razie "dobre"."""
    for obj in matches:
        if obj.pk in seen_ids:
            continue
        seen_ids.add(obj.pk)
        item = (obj, "PREFIX", 0.8)
        if issn_match(obj) and has_mnisw(obj):
            bucket["najlepsze"].append(item)
        else:
            bucket["dobre"].append(item)


def _dodaj_similarity_dopasowania(matches, has_mnisw, bucket, seen_ids):
    """Krok SIMILARITY: "dobre" gdy ma mniswId i podobieństwo > 0.7, inaczej
    "akceptowalne"."""
    for obj in matches:
        if obj.pk in seen_ids:
            continue
        seen_ids.add(obj.pk)
        podobienstwo = getattr(obj, "similarity", 0.5)
        item = (obj, "SIMILARITY", podobienstwo)
        if has_mnisw(obj) and podobienstwo > 0.7:
            bucket["dobre"].append(item)
        else:
            bucket["akceptowalne"].append(item)


def _przetworz_strone(
    *,
    bucket,
    nazwa_do_wyszukania,
    name_attr,
    has_mnisw,
    issn_match,
    issn_matches,
    finder_prefix,
    finder_trigram,
    max_results,
):
    """Wykonaj trzy kroki scoringu (ISSN, PREFIX, SIMILARITY) dla jednej tabeli."""
    seen_ids = set()
    _dodaj_issn_dopasowania(
        issn_matches,
        nazwa_do_wyszukania,
        name_attr,
        has_mnisw,
        bucket,
        max_results,
        seen_ids,
    )
    if nazwa_do_wyszukania:
        _dodaj_prefix_dopasowania(
            finder_prefix(nazwa_do_wyszukania)[:max_results],
            has_mnisw,
            issn_match,
            bucket,
            seen_ids,
        )
        _dodaj_similarity_dopasowania(
            finder_trigram(nazwa_do_wyszukania)[:max_results],
            has_mnisw,
            bucket,
            seen_ids,
        )


def znajdz_podobne_zrodla(journal_skasowane, max_results=10):
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
    def zrodlo_has_mnisw(zrodlo):
        return bool(zrodlo.pbn_uid and zrodlo.pbn_uid.mniswId)

    def zrodlo_issn_match(zrodlo):
        # PREFIX może być "najlepsze" TYLKO gdy ISSN się zgadza i mamy
        # skasowane źródło w BPP do porównania.
        if not (zrodlo_skasowane and journal_skasowane):
            return False
        return bool(
            (journal_skasowane.issn and zrodlo.issn == journal_skasowane.issn)
            or (journal_skasowane.eissn and zrodlo.e_issn == journal_skasowane.eissn)
        )

    _przetworz_strone(
        bucket=results["zrodla_bpp"],
        nazwa_do_wyszukania=nazwa_do_wyszukania,
        name_attr="nazwa",
        has_mnisw=zrodlo_has_mnisw,
        issn_match=zrodlo_issn_match,
        issn_matches=find_by_issn(journal_skasowane, exclude_id=zrodlo_skasowane_id),
        finder_prefix=lambda nazwa: find_by_name_prefix(
            nazwa, exclude_id=zrodlo_skasowane_id
        ),
        finder_trigram=lambda nazwa: find_by_trigram(
            nazwa, exclude_id=zrodlo_skasowane_id, min_similarity=0.5
        ),
        max_results=max_results,
    )

    # CZĘŚĆ 2: SZUKANIE W TABELI JOURNAL (źródła PBN które NIE są w BPP)
    def journal_has_mnisw(journal):
        return bool(journal.mniswId)

    def journal_issn_match(journal):
        if not journal_skasowane:
            return False
        return bool(
            (journal_skasowane.issn and journal.issn == journal_skasowane.issn)
            or (journal_skasowane.eissn and journal.eissn == journal_skasowane.eissn)
        )

    _przetworz_strone(
        bucket=results["journale_pbn"],
        nazwa_do_wyszukania=nazwa_do_wyszukania,
        name_attr="title",
        has_mnisw=journal_has_mnisw,
        issn_match=journal_issn_match,
        issn_matches=find_journals_by_issn(journal_skasowane),
        finder_prefix=find_journals_by_prefix,
        finder_trigram=find_journals_by_trigram,
        max_results=max_results,
    )

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


def _zbuduj_sugerowane_queryset(sugerowane, zrodlo):
    """Zbuduj queryset źródeł BPP do formularza na podstawie sugestii.

    Gdy są sugestie - ogranicz do nich; w przeciwnym razie pokaż do 20
    aktywnych źródeł (najpierw z mniswId, potem alfabetycznie)."""
    wszystkie_zrodla = []
    for kategoria in ["najlepsze", "dobre", "akceptowalne"]:
        wszystkie_zrodla.extend(sugerowane["zrodla_bpp"][kategoria])

    if wszystkie_zrodla:
        # Struktura krotki: (zrodlo, typ_dopasowania, podobienstwo)
        sugerowane_ids = [item[0].pk for item in wszystkie_zrodla]
        return Zrodlo.objects.filter(pk__in=sugerowane_ids)

    # Brak sugestii - pokaż wszystkie aktywne źródła
    return (
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


def _zbierz_wszystkie_journale(sugerowane):
    """Spłaszcz wszystkie sugerowane journale PBN do jednej listy."""
    wszystkie_journale = []
    for kategoria in ["najlepsze", "dobre", "akceptowalne"]:
        wszystkie_journale.extend(sugerowane["journale_pbn"][kategoria])
    return wszystkie_journale


def _utworz_zrodlo_z_journala(request, journal_docelowy):
    """Utwórz nowe Zrodlo na podstawie wybranego Journal z PBN."""
    rodzaj_czasopismo = Rodzaj_Zrodla.objects.get(nazwa="czasopismo")
    zrodlo_nowe = Zrodlo.objects.create(
        nazwa=journal_docelowy.title or "",
        issn=journal_docelowy.issn or "",
        e_issn=journal_docelowy.eissn or "",
        pbn_uid=journal_docelowy,
        rodzaj=rodzaj_czasopismo,
    )
    messages.info(
        request,
        f'Utworzono nowe źródło "{zrodlo_nowe.nazwa}" na podstawie danych z PBN.',
    )
    return zrodlo_nowe


def _zbierz_rekordy_do_przemapowania(zrodlo):
    """Zbierz historię i oryginalne rekordy przed przemapowaniem źródła."""
    rekordy_historia = []
    rekordy_do_wyslania = []
    for rekord in Rekord.objects.filter(zrodlo=zrodlo):
        rekordy_historia.append(
            {
                "id": list(rekord.pk),
                "tytul": rekord.tytul_oryginalny,
                "rok": rekord.rok,
                "opis_bibliograficzny": rekord.opis_bibliograficzny_cache or "",
            }
        )
        rekordy_do_wyslania.append(rekord.original)
    return rekordy_historia, rekordy_do_wyslania


def _dodaj_rekordy_do_kolejki_pbn(request, rekordy_do_wyslania):
    """Dodaj rekordy do kolejki eksportu PBN, zwracając (sukces, lista_bledow)."""
    sukces_pbn = 0
    bledy_pbn = []
    for original_rekord in rekordy_do_wyslania:
        try:
            PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
                user=request.user, rekord=original_rekord
            )
            sukces_pbn += 1
        except Exception as e:
            zaloguj_polkniety_wyjatek(
                f"Dodawanie rekordu do kolejki eksportu PBN "
                f"przy przemapowaniu źródła PBN "
                f"(rekord pk={original_rekord.pk})",
                logger=logger,
            )
            bledy_pbn.append(f"Rekord {original_rekord.pk}: {str(e)}")
    return sukces_pbn, bledy_pbn


def _obsluz_confirm(request, zrodlo, form):
    """Obsłuż potwierdzone przemapowanie. Zwróć HttpResponse (redirect) lub
    None gdy należy wyrenderować stronę (np. po błędzie)."""
    typ_wyboru = form.cleaned_data.get("typ_wyboru")

    # Określ źródło docelowe
    if typ_wyboru == PrzeMapowanieZrodlaForm.TYP_JOURNAL:
        journal_docelowy = Journal.objects.get(pk=form.cleaned_data["journal_docelowy"])
        zrodlo_nowe = _utworz_zrodlo_z_journala(request, journal_docelowy)
    else:
        zrodlo_nowe = form.cleaned_data["zrodlo_docelowe"]

    # Walidacja: nie można przemapować na źródło również skasowane
    if zrodlo_nowe.pbn_uid and zrodlo_nowe.pbn_uid.status == DELETED:
        messages.error(
            request,
            "Nie można przemapować na źródło, które również jest skasowane w PBN!",
        )
        return redirect("przemapuj_zrodla_pbn:przemapuj_zrodlo", zrodlo_id=zrodlo.pk)

    try:
        with transaction.atomic():
            rekordy_historia, rekordy_do_wyslania = _zbierz_rekordy_do_przemapowania(
                zrodlo
            )

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

            sukces_pbn, bledy_pbn = _dodaj_rekordy_do_kolejki_pbn(
                request, rekordy_do_wyslania
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
        messages.error(request, f"Wystąpił błąd podczas przemapowania: {str(e)}")

    return None


def _obsluz_preview(request, zrodlo, form, liczba_rekordow, sugerowane):
    """Wyrenderuj podgląd zmian przed przemapowaniem."""
    typ_wyboru = form.cleaned_data.get("typ_wyboru")

    journal_docelowy = None
    if typ_wyboru == PrzeMapowanieZrodlaForm.TYP_JOURNAL:
        journal_docelowy = Journal.objects.get(pk=form.cleaned_data["journal_docelowy"])
        zrodlo_nowe_nazwa = f"{journal_docelowy.title} (NOWE ze źródła PBN)"
        zrodlo_nowe = None  # Będzie utworzone dopiero po zatwierdzeniu
    else:
        zrodlo_nowe = form.cleaned_data["zrodlo_docelowe"]
        zrodlo_nowe_nazwa = str(zrodlo_nowe)

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
    return render(request, "przemapuj_zrodla_pbn/przemapuj_zrodlo.html", context)


@login_required
def przemapuj_zrodlo(request, zrodlo_id):
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
    sugerowane_queryset = _zbuduj_sugerowane_queryset(sugerowane, zrodlo)
    wszystkie_journale = _zbierz_wszystkie_journale(sugerowane)

    if request.method == "POST":
        form = PrzeMapowanieZrodlaForm(
            request.POST,
            zrodlo_skasowane=zrodlo,
            sugerowane_zrodla=sugerowane_queryset,
            sugerowane_journale=wszystkie_journale,
        )

        if "confirm" in request.POST and form.is_valid():
            odpowiedz = _obsluz_confirm(request, zrodlo, form)
            if odpowiedz is not None:
                return odpowiedz
        elif "preview" in request.POST and form.is_valid():
            return _obsluz_preview(request, zrodlo, form, liczba_rekordow, sugerowane)
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
