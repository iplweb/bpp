"""Wiązanie sesji importu ze zgłoszeniem publikacji (FD#443).

Jedno miejsce z regułami „które zgłoszenie domyka ta sesja importu" —
używane przez zadanie Celery (auto-wiązanie + zapis zwrotny), przez widok
wyboru kandydata, przez walidację jawnego wyboru (ukryte pole ``zgloszenie``
w ``FetchForm``) oraz przez prefill dyscyplin. Reguły siedzą tutaj, żeby
``views/wizard.py``, ``tasks.py`` i pozostałe widoki ich nie powielały.

Zasady (spec ``docs/superpowers/specs/2026-07-22-zgloszenie-zaimportowane-\
przez-importer-design.md``):

* wiązanie **wyłącznie po DOI** — dopasowanie po tytule jest wykluczone
  (D5: dwa zgłoszenia o identycznym tytule oznaczyłyby przypadkowe),
* DOI zgłoszenia czytamy z DWÓCH pól: ``doi`` **oraz** ``strona_www``
  (patrz :func:`_pk_pasujacych_po_doi` — publiczny formularz nie ma pola
  ``doi``, więc produkcyjnie DOI ląduje w ``strona_www``),
* kandydaci nie przekraczają granicy uczelni (D8) — ``Zgloszenie_Publikacji``
  nie ma pola ``uczelnia``, więc atrybucja idzie przez jednostki autorów,
* ``WYMAGA_ZMIAN`` jest wykluczony (D9) — zgłoszenie jest wtedy w rękach
  autora (aktywny ``kod_do_edycji``); przestemplowanie zabrałoby mu pracę,
* zapis zwrotny jest idempotentny, odporny na soft-delete (dostęp przez FK
  idzie ``_base_manager``, który **nie** filtruje usuniętych) i rewaliduje
  status w chwili zapisu, a nie w chwili związania.

``SoftDeleteModel.delete()`` emuluje ``on_delete``, więc skasowanie zgłoszenia
zwykłą ścieżką samo wyzeruje ``ImportSession.zgloszenie``. Guard na
``deleted_at`` w :func:`oznacz_jako_zaimportowane` pilnuje ścieżek, które
``delete()`` omijają — bulk ``UPDATE deleted_at``, surowy SQL, migracje danych,
wyścig transakcji.
"""

import logging

from django.db.models import Q
from django.utils import timezone

from import_common.normalization import extract_doi_from_url, normalize_doi

logger = logging.getLogger(__name__)


def _wykluczone_statusy():
    """Statusy, w których zgłoszenia nie ma już czym domykać.

    ``ZAAKCEPTOWANY`` i ``ZAIMPORTOWANY`` — praca jest już w BPP.
    ``ODRZUCONO``/``SPAM`` — zgłoszenie zamknięte.
    ``WYMAGA_ZMIAN`` — zgłoszenie jest po stronie zgłaszającego (D9).
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji

    statusy = Zgloszenie_Publikacji.Statusy
    return (
        statusy.ODRZUCONO,
        statusy.SPAM,
        statusy.ZAIMPORTOWANY,
        statusy.ZAAKCEPTOWANY,
        statusy.WYMAGA_ZMIAN,
    )


def _doi_sesji(session):
    """Znormalizowane DOI sesji importu albo ``None``.

    Ta sama normalizacja, co w ``views.authors._find_matching_zgloszenie``
    — wspólny ``import_common.normalization.normalize_doi``.
    """
    return normalize_doi((session.normalized_data or {}).get("doi"))


def _uczelnia_pk(uczelnia):
    """Klucz główny uczelni — z instancji, z gołego pk albo ``None``.

    Wołający mają raz instancję (``Uczelnia.get_for_request``), raz samo
    ``session.uczelnia_id`` (tańsze — bez dociągania wiersza uczelni).
    """
    if uczelnia is None:
        return None
    return getattr(uczelnia, "pk", uczelnia)


def _zawez_do_uczelni(qs, uczelnia):
    """Zawęź zgłoszenia do uczelni sesji importu / redaktora (D8).

    ``uczelnia`` to instancja ``bpp.Uczelnia``, jej pk albo ``None``.

    ``Zgloszenie_Publikacji`` nie ma FK do uczelni — jedyna droga w ORM
    prowadzi przez jednostki autorów zgłoszenia. JOIN przez autorów mnoży
    wiersze, więc dokładamy tu ``.distinct()`` (wołający nie musi pamiętać).

    No-op (jak w :func:`bpp.util.uczelnia_scope.scope_rekord_do_uczelni`
    i ``permissions.scope_import_do_uczelni``), gdy:

    * nie znamy uczelni (brak mapowania Site→Uczelnia) — nie chcemy nagle
      ukryć wszystkiego,
    * w instalacji jest dokładnie jedna uczelnia — filtr byłby no-opem,
      a kosztowałby JOIN + DISTINCT.

    **Znane ograniczenia semantyki (świadome, udokumentowane):**

    * *przeciek D8 przy autorach z dwóch uczelni* — JOIN daje semantykę OR:
      zgłoszenie, którego autorzy siedzą w jednostkach DWÓCH uczelni, jest
      kandydatem dla OBU. Bez pola ``uczelnia`` na samym zgłoszeniu nie da
      się tego rozstrzygnąć czysto (praca współautorska naprawdę „należy"
      do obu), a wariant restrykcyjny (``wszyscy`` autorzy z jednej
      uczelni) ukrywałby zgłoszenia współautorskie przed obiema.
    * *zgłoszenia BEZ autorów wypadają* — INNER JOIN nie ma czego dopasować.
      To decyzja **fail-closed**: w instalacji wielouczelnianej zgłoszenie
      bez ani jednego autora nie daje się przypisać do uczelni, więc lepiej
      nie pokazać go nikomu, niż pokazać wszystkim. Operator i tak dojdzie
      do niego przez moduł redagowania i zwiąże jawnie (ścieżka A →
      :func:`zgloszenie_dozwolone`, która tę samą regułę egzekwuje —
      jawny wybór też nie przekracza granicy uczelni).

    UWAGA: ``tylko_jedna_uczelnia()`` odpala ``COUNT`` **natychmiast**, przy
    budowie querysetu — funkcja nie jest leniwa. Dlatego wołający wychodzą
    wcześniej (brak DOI, brak pk), zanim tu w ogóle wejdą.
    """
    from bpp.util.uczelnia_scope import tylko_jedna_uczelnia

    uczelnia_pk = _uczelnia_pk(uczelnia)
    if uczelnia_pk is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(
        zgloszenie_publikacji_autor__jednostka__uczelnia_id=uczelnia_pk
    ).distinct()


def _dozwolone_zgloszenia(uczelnia):
    """Baza kandydatów: statusy (D9) + granica uczelni (D8), bez DOI.

    Jedno źródło obu reguł dla :func:`kandydaci_dla_sesji` (dopasowanie
    po DOI) i :func:`zgloszenie_dozwolone` (wybór jawny).
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji

    return _zawez_do_uczelni(
        Zgloszenie_Publikacji.objects.exclude(status__in=_wykluczone_statusy()),
        uczelnia,
    )


def _pk_pasujacych_po_doi(qs, doi):
    """PK zgłoszeń, których DOI **równa się** ``doi`` (już znormalizowanemu).

    Dlaczego dwa pola i dokładne dofiltrowanie w Pythonie:

    * publiczny formularz zgłoszenia (``zglos_publikacje.forms``) nie ma
      pola ``doi``, a help-text każe wkleić DOI do ``strona_www``
      (``https://dx.doi.org/…``). Admin ma zgłoszenia read-only. Produkcyjnie
      ``Zgloszenie_Publikacji.doi`` jest więc PUSTE — samo ``doi__iexact``
      nie dopasowałoby niczego, a ścieżki B i C byłyby martwym kodem. Tę
      samą kolejność (``strona_www`` przed ``doi``) stosuje już
      ``admin.zgloszenie_publikacji.importer_url``.
    * SQL zawęża tylko zgrubnie (``icontains`` po obu polach), bo LIKE nie
      umie rozpoznać, gdzie w URL-u kończy się DOI. Dokładne porównanie
      robimy w Pythonie przez ``extract_doi_from_url``/``normalize_doi``:
      inaczej DOI będące PREFIKSEM innego (``10.1/abc`` vs ``10.1/abc.2``)
      wpuściłoby fałszywe trafienie i zamieniło ścieżkę B (auto-wiązanie)
      w ciche oznaczenie cudzego zgłoszenia.

    ``order_by()`` kasuje domyślne ``Meta.ordering`` — inaczej
    ``SELECT DISTINCT`` + ``ORDER BY`` po kolumnie spoza listy pól wywala
    się na PostgreSQL-u.
    """
    return {
        pk
        for pk, zgl_doi, strona_www in qs.order_by().values_list(
            "pk", "doi", "strona_www"
        )
        if normalize_doi(zgl_doi) == doi or extract_doi_from_url(strona_www) == doi
    }


def kandydaci_dla_sesji(session):
    """Zgłoszenia, które ta sesja importu mogłaby domknąć.

    Zwraca ``QuerySet`` (możliwie pusty — nigdy ``None``), żeby wołający
    mógł go bezpiecznie filtrować (walidacja wyboru operatora,
    ``views.zgloszenie.ZgloszenieWyborView``), liczyć i iterować.

    Dopasowanie po DOI wymaga materializacji pośredniego zapytania (patrz
    :func:`_pk_pasujacych_po_doi`), więc wynikowy queryset jest zawężony
    przez ``pk__in`` — dzięki temu jest znowu „płaski" (bez JOIN-a po
    autorach i bez ``DISTINCT``) i da się go dalej filtrować.

    ``prefetch_related`` na autorach: baner (``_baner_zgloszenia.html``)
    woła ``zgl.zgloszenie_publikacji_autor_set.first`` dla każdego
    kandydata — bez tego mamy N+1.

    Działa tak samo dla importu pojedynczego, jak i dla wpisu z paczki
    (``MultipleWorksImport`` idzie tą samą drogą: ``_start_import_session``
    → ``fetch_session_task`` → :func:`zwiaz_automatycznie`). Spec §11
    nazywa paczkę „poza zakresem", ale wyłączanie tego byłoby regresją —
    zgłoszenie domknięte importem z paczki jest domknięte tak samo.
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji

    doi = _doi_sesji(session)
    if not doi:
        return Zgloszenie_Publikacji.objects.none()

    zgrubne = _dozwolone_zgloszenia(session.uczelnia_id).filter(
        Q(doi__icontains=doi) | Q(strona_www__icontains=doi)
    )
    return Zgloszenie_Publikacji.objects.filter(
        pk__in=_pk_pasujacych_po_doi(zgrubne, doi)
    ).prefetch_related("zgloszenie_publikacji_autor_set")


def zgloszenie_dozwolone(pk, uczelnia):
    """Zgłoszenie, które wolno związać z sesją importu tej uczelni.

    Zwraca obiekt albo ``None``. Egzekwuje te same reguły co
    :func:`kandydaci_dla_sesji` (statusy D9 + granica uczelni D8), ale bez
    dopasowania po DOI — wybór jest tu jawny (ścieżka A: przycisk „Użyj
    importera" w module redagowania, ukryte pole ``zgloszenie``
    w ``FetchForm``).

    ``uczelnia`` to instancja ``bpp.Uczelnia``, jej pk albo ``None``
    (brak mapowania Site→Uczelnia — wtedy filtr per-uczelnia jest no-opem,
    dokładnie jak w :func:`kandydaci_dla_sesji`).

    Wartość niepoprawna (śmieć w ukrytym polu, ręcznie podrasowany URL)
    daje ``None``, nie wyjątek: wiązanie jest opcjonalne, więc nie może
    zablokować importu.
    """
    if not pk:
        return None

    try:
        return _dozwolone_zgloszenia(uczelnia).filter(pk=pk).first()
    except (TypeError, ValueError):
        logger.info(
            "Odrzucono niepoprawny identyfikator zgłoszenia publikacji: %r.", pk
        )
        return None


def zwiaz_automatycznie(session):
    """Ustaw ``session.zgloszenie``, gdy kandydat jest dokładnie jeden.

    Zwraca ``True`` tylko wtedy, gdy wiązanie faktycznie powstało. Zero
    kandydatów → nie ma czego wiązać; dwa lub więcej → decyduje operator
    (ścieżka C, ``views.zgloszenie.ZgloszenieWyborView``).

    Nie nadpisuje istniejącego wiązania — jawny wybór (ścieżka A) jest
    zawsze mocniejszy od heurystyki po DOI.
    """
    if session.zgloszenie_id:
        return False

    # LIMIT 2 wystarczy do rozstrzygnięcia „dokładnie jeden".
    kandydaci = list(kandydaci_dla_sesji(session)[:2])
    if len(kandydaci) != 1:
        return False

    session.zgloszenie = kandydaci[0]
    session.save(update_fields=["zgloszenie"])
    return True


def oznacz_jako_zaimportowane(session, record):
    """Zapis zwrotny na zgłoszeniu po udanym imporcie. Idempotentny.

    Zwraca ``True``, gdy zgłoszenie zostało oznaczone; ``False``, gdy
    pominięto (brak wiązania, zgłoszenie soft-usunięte, albo jego status
    zdążył wejść w :func:`_wykluczone_statusy` — w tym „już oznaczone",
    więc ponowienie zadania nie przesuwa daty ani nie zmienia autora).

    **Jeden warunkowy ``UPDATE``**, nie „przeczytaj → sprawdź → zapisz".
    Między związaniem sesji (etap fetch) a tym zapisem (etap create) mija
    cała praca operatora w kreatorze, a wczytany wcześniej ``session
    .zgloszenie`` niesie stan sprzed tego czasu. Warunek w ``WHERE``
    rewaliduje status w chwili zapisu i przy okazji domyka wyścig (bez
    ``SELECT ... FOR UPDATE``): zgłoszenie zwrócone w międzyczasie autorowi
    (``WYMAGA_ZMIAN``) nie zostanie przestemplowane.

    ``zaimportowal`` bierzemy z ``session.created_by``, nie
    ``modified_by`` — „kto to zrobił" znaczy kto uruchomił import, nie kto
    ostatnio dotknął wiersza.

    ``kod_do_edycji`` kasujemy razem z oznaczeniem. Widok edycji
    (``zglos_publikacje.views``) autoryzuje autora **samym kodem**, nie
    patrząc na status — żywy kod na zgłoszeniu ZAIMPORTOWANYM pozwoliłby
    autorowi cofnąć je do ``PO_ZMIANACH``, co zgasiłoby panel audytu
    i przywróciło przycisk „Użyj importera" mimo istniejącego już rekordu
    (prosta droga do duplikatu). Pole jest ``unique``, ale ``null=True``,
    więc wiele ``NULL``-i współistnieje bez konfliktu.

    Bez własnego ``transaction.atomic()``: pojedynczy ``UPDATE`` jest
    atomowy sam z siebie, a wołający (``tasks.create_publication_task``)
    i tak dokłada swój blok — zagnieżdżenie tworzyłoby tylko zbędny
    savepoint.
    """
    from django.contrib.contenttypes.models import ContentType

    from zglos_publikacje.models import Zgloszenie_Publikacji

    if not session.zgloszenie_id:
        return False

    # Dostęp przez FK idzie ``_base_manager``, który NIE filtruje
    # soft-usuniętych. Zwykłe ``zgl.delete()`` samo wyzeruje to FK (biblioteka
    # emuluje ``on_delete``), ale bulk UPDATE, surowy SQL czy migracja danych
    # już nie. ``objects`` (SoftDeleteManager) i tak by je odsiał w UPDATE
    # niżej — jawny guard jest po to, żeby przypadek dało się rozpoznać
    # w logach zamiast zgadywać, czemu UPDATE zwrócił zero.
    zgl = session.zgloszenie

    if zgl.deleted_at is not None:
        logger.warning(
            "Sesja importu %s wskazuje na soft-usunięte zgłoszenie %s — "
            "pomijam oznaczanie jako zaimportowane.",
            session.pk,
            zgl.pk,
        )
        return False

    zaktualizowane = (
        Zgloszenie_Publikacji.objects.filter(pk=session.zgloszenie_id)
        .exclude(status__in=_wykluczone_statusy())
        .update(
            status=Zgloszenie_Publikacji.Statusy.ZAIMPORTOWANY,
            zaimportowano=timezone.now(),
            zaimportowal_id=session.created_by_id,
            content_type=ContentType.objects.get_for_model(record),
            object_id=record.pk,
            kod_do_edycji=None,
        )
    )

    if not zaktualizowane:
        # Status czytamy ŚWIEŻO — ``zgl.status`` niesie stan sprzed pracy
        # operatora, a w logu chcemy zobaczyć powód odrzucenia UPDATE-u.
        aktualny_status = (
            Zgloszenie_Publikacji.global_objects.filter(pk=session.zgloszenie_id)
            .values_list("status", flat=True)
            .first()
        )
        logger.info(
            "Zgłoszenie %s nie kwalifikuje się już do oznaczenia jako "
            "zaimportowane (status w chwili zapisu: %s) — pomijam "
            "(sesja importu %s).",
            zgl.pk,
            aktualny_status,
            session.pk,
        )
        return False

    logger.info(
        "Zgłoszenie %s oznaczone jako zaimportowane przez sesję importu %s "
        "(rekord %s).",
        zgl.pk,
        session.pk,
        record.pk,
    )
    return True
