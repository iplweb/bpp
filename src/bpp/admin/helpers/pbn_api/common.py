import sys

from django.urls import reverse
from django.utils.html import format_html, format_html_join

from bpp.admin.helpers import link_do_obiektu
from bpp.zglaszanie_bledow import capture_exception
from import_common.normalization import normalize_isbn
from pbn_api.adapters.wydawnictwo_autor import (
    powiazania_bez_identyfikatora_osoby,
    powiazania_do_oswiadczenia,
)
from pbn_api.exceptions import (
    AccessDeniedException,
    AutorBezIdentyfikatoraPBN,
    BrakZdefiniowanegoObiektuUczelniaWSystemieError,
    CharakterFormalnyNieobslugiwanyError,
    NeedsPBNAuthorisationException,
    PBNValidationError,
    PKZeroExportDisabled,
    PraceSerwisoweException,
    ResourceLockedException,
    SameDataUploadedRecently,
    WillNotExportError,
)
from pbn_api.models import SentData


def sprawdz_czy_ustawiono_wysylke_tego_charakteru_formalnego(charakter_formalny):
    if charakter_formalny.rodzaj_pbn is None:
        raise CharakterFormalnyNieobslugiwanyError(
            "ten rekord nie może być wyeksportowany do PBN, gdyż ustawienia jego charakteru formalnego "
            "po stronie bazy BPP na to nie pozwalają"
        )


def sprawdz_wysylke_do_pbn_w_parametrach_uczelni(uczelnia):
    """
    :param uczelnia:
    :return: zwraca False jeżeli integracja wyłączona lub aktualizowanie na bieżąco wyłączone;
    zwraca obiekt uczelnia jeżeli jest OK,
    podnosi wyjątek jeżeli brak obiektu Uczelnia
    """
    if uczelnia is None:
        raise BrakZdefiniowanegoObiektuUczelniaWSystemieError()

    if not uczelnia.pbn_integracja or not uczelnia.pbn_aktualizuj_na_biezaco:
        return False

    return uczelnia


def komunikat_autorzy_bez_identyfikatora(obj, autorzy):
    """Komunikat HTML o zatrzymanej wysyłce pracy do PBN (FD#509).

    :param obj: praca (rekord BPP), której nie wysłano.
    :param autorzy: powiązania autor–rekord, których oświadczenia nie da się
        wysłać (``AutorBezIdentyfikatoraPBN.autorzy``).
    """
    lista = format_html_join(
        "",
        '<li><a href="{}" target="_blank">{}</a> (dyscyplina: {})</li>',
        (
            (
                reverse("admin:bpp_autor_change", args=(wa.autor_id,)),
                wa.autor,
                wa.dyscyplina_naukowa,
            )
            for wa in autorzy
        ),
    )
    return format_html(
        'Rekord "{}" NIE został wysłany do PBN. Ci autorzy mają w tej pracy '
        "przypiętą dyscyplinę i afiliują, ale nie mają ani odpowiednika "
        "w PBN, ani identyfikatora ORCID, więc ich oświadczenia nie da się "
        "wysłać: <ul>{}</ul>Co zrobić: kliknij autora, ustaw mu „Odpowiednik "
        "w PBN” albo wpisz „Identyfikator ORCID”, a potem wyślij pracę "
        "ponownie. Jeżeli ta osoba nie powinna być oświadczana w tej pracy — "
        "odepnij jej dyscyplinę albo popraw afiliację w tej pracy. ",
        link_do_obiektu(obj),
        lista,
    )


def komunikat_pominiete_oswiadczenia(obj, wszystkich, pominieci):
    """Ostrzeżenie HTML po wysyłce pracy z niepełnymi oświadczeniami (FD#509).

    Uczelnia ma włączone „Wysyłaj prace, gdy autor nie ma identyfikatora
    w PBN”, więc praca poszła — ale bez oświadczeń autorów bez odpowiednika
    w PBN i bez ORCID. Redaktor ma zobaczyć liczby i nazwiska, a nie sam
    komunikat o sukcesie.

    :param obj: wysłana praca (rekord BPP).
    :param wszystkich: ilu autorów pracy ma dostać oświadczenie.
    :param pominieci: powiązania autor–rekord, których oświadczeń nie wysłano.
    """
    lista = format_html_join(
        "",
        '<li><a href="{}" target="_blank">{}</a> (dyscyplina: {})</li>',
        (
            (
                reverse("admin:bpp_autor_change", args=(wa.autor_id,)),
                wa.autor,
                wa.dyscyplina_naukowa,
            )
            for wa in pominieci
        ),
    )
    return format_html(
        'UWAGA: oświadczenia rekordu "{}" w PBN są NIEPEŁNE. Z {} autorów '
        "z przypiętą dyscypliną do PBN trafiło {} oświadczeń, pominięto {}. "
        "Bez oświadczenia zostali autorzy, którzy nie mają ani odpowiednika "
        "w PBN, ani identyfikatora ORCID: <ul>{}</ul>Żeby dosłać brakujące "
        "oświadczenia, kliknij autora, ustaw mu „Odpowiednik w PBN” albo "
        "wpisz „Identyfikator ORCID”, a potem wyślij pracę ponownie. ",
        link_do_obiektu(obj),
        wszystkich,
        wszystkich - len(pominieci),
        len(pominieci),
        lista,
    )


def ostrzez_o_pominietych_oswiadczeniach(obj, uczelnia, notificator):
    """Po udanej wysyłce: ostrzeż, jeśli część oświadczeń nie poszła (FD#509).

    Tylko dla uczelni z włączonym ``pbn_wysylaj_bez_identyfikatora_autora`` —
    bez tego ustawienia taka praca w ogóle nie zostałaby wysłana.
    """
    if not uczelnia.pbn_wysylaj_bez_identyfikatora_autora:
        return
    pominieci = list(powiazania_bez_identyfikatora_osoby(obj.autorzy_set))
    if not pominieci:
        return
    notificator.warning(
        komunikat_pominiete_oswiadczenia(
            obj, powiazania_do_oswiadczenia(obj.autorzy_set).count(), pominieci
        )
    )


def sprobuj_wyslac_do_pbn(  # noqa: C901
    obj, pbn_client, uczelnia, notificator, force_upload=False, raise_exceptions=False
):
    # Sprawdź, czy wydawnictwo nadrzędne ma odpowoednik PBN:
    if (
        hasattr(obj, "wydawnictwo_nadrzedne_id")
        and obj.wydawnictwo_nadrzedne_id is not None
    ):
        wn = obj.wydawnictwo_nadrzedne
        if wn.pbn_uid_id is None:
            notificator.info(
                "Wygląda na to, że wydawnictwo nadrzędne tego rekordu nie posiada odpowiednika "
                "w PBN, spróbuję go pobrać.",
            )
            udalo = False
            if wn.isbn:
                ni = normalize_isbn(wn.isbn)
                if ni:
                    from pbn_integrator.utils import _pobierz_prace_po_elemencie

                    res = None
                    try:
                        res = _pobierz_prace_po_elemencie(pbn_client, "isbn", ni)
                    except PraceSerwisoweException:
                        notificator.warning(
                            "Pobieranie z PBN odpowiednika wydawnictwa nadrzędnego pracy po ISBN nie powiodło się "
                            "-- trwają prace serwisowe po stronie PBN. ",
                        )
                    except NeedsPBNAuthorisationException:
                        notificator.warning(
                            "Wyszukanie PBN UID wydawnictwa nadrzędnego po ISBN nieudane - "
                            "autoryzuj się najpierw w PBN. ",
                        )

                    if res:
                        notificator.info(
                            f"Udało się dopasować PBN UID wydawnictwa nadrzędnego po ISBN "
                            f"({', '.join([x.tytul_oryginalny for x in res])}). ",
                        )
                        udalo = True

            elif wn.doi:
                nd = normalize_isbn(wn.doi)
                if nd:
                    from pbn_integrator.utils import _pobierz_prace_po_elemencie

                    res = None
                    try:
                        res = _pobierz_prace_po_elemencie(pbn_client, "doi", nd)
                    except PraceSerwisoweException as e:
                        notificator.warning(
                            "Pobieranie z PBN odpowiednika wydawnictwa nadrzędnego pracy po DOI nie powiodło się "
                            "-- trwają prace serwisowe po stronie PBN. ",
                        )
                        if raise_exceptions:
                            raise e

                    except NeedsPBNAuthorisationException as e:
                        notificator.warning(
                            "Wyszukanie PBN UID wydawnictwa nadrzędnego po DOI nieudane - "
                            "autoryzuj się najpierw w PBN. ",
                        )
                        if raise_exceptions:
                            raise e

                    if res:
                        notificator.info(
                            f"Udało się dopasować PBN UID wydawnictwa nadrzędnego po DOI. "
                            f"({', '.join([x.tytul_oryginalny for x in res])}). ",
                        )
                        udalo = True

            if not udalo:
                notificator.warning(
                    "Wygląda na to, że nie udało się dopasować rekordu nadrzędnego po ISBN/DOI do rekordu "
                    "po stronie PBN. Jeżeli jednak dokonano autoryzacji w PBN, to pewne rekordy z PBN "
                    "zostały teraz pobrane i możesz spróbować ustawić odpowiednik "
                    "PBN dla wydawnictwa nadrzędnego ręcznie. ",
                )

    # Autor z przypiętą dyscypliną, bez odpowiednika w PBN, ale z ORCID:
    # oświadczenie idzie po ORCID (FD#509). To nie jest błąd — tylko
    # informacja, bo PBN przypisze je do osoby wyłącznie wtedy, gdy zna ten
    # ORCID. Autor bez odpowiednika I bez ORCID zatrzymuje wysyłkę niżej
    # (``AutorBezIdentyfikatoraPBN``).
    for autor in (
        obj.autorzy_set.exclude(dyscyplina_naukowa=None)
        .exclude(jednostka__skupia_pracownikow=False)
        .exclude(jednostka_id__lt=0)
        .exclude(afiliuje=False)
        .exclude(przypieta=False)
        .filter(autor__pbn_uid_id=None)
        .exclude(autor__orcid=None)
        .exclude(autor__orcid="")
        .select_related("autor")
    ):
        notificator.info(
            format_html(
                "Autor {} nie ma odpowiednika w PBN — jego oświadczenie "
                "zostanie wysłane z identyfikatorem ORCID ({}). Jeżeli PBN nie "
                'rozpozna tego ORCID, <a href="{}" target="_blank">ustaw '
                "autorowi „Odpowiednik w PBN”</a>. ",
                autor.autor,
                autor.autor.orcid,
                reverse("admin:bpp_autor_change", args=(autor.autor_id,)),
            )
        )

    open_in_pbn_link = ""
    if obj.pbn_uid_id:
        open_in_pbn_link = format_html(
            '<a target="_blank" href="{}">Otwórz w PBN</a>. ',
            obj.link_do_pbn(uczelnia=uczelnia),
        )

    open_in_pi_link = obj.link_do_pi(uczelnia=uczelnia) or ""
    if open_in_pi_link:
        open_in_pi_link = format_html(
            '<a target="_blank" href="{}">Otwórz w Profilu Instytucji</a>. ',
            open_in_pi_link,
        )

    try:
        pbn_client.sync_publication(
            obj,
            notificator=notificator,
            force_upload=force_upload,
            export_pk_zero=not uczelnia.pbn_api_nie_wysylaj_prac_bez_pk,
            always_affiliate_to_uid=(
                uczelnia.pbn_uid_id
                if uczelnia.pbn_api_afiliacja_zawsze_na_uczelnie
                else None
            ),
        )

        # Być moze obj.pbn_uid_id uległ zmianie. Jeżeli tak -- zregeneruj link:
        if obj.pbn_uid_id:
            open_in_pbn_link = format_html(
                '<a target="_blank" href="{}">Kliknij tutaj, aby otworzyć w PBN</a>. ',
                obj.link_do_pbn(uczelnia=uczelnia),
            )
        open_in_pi_link = obj.link_do_pi(uczelnia=uczelnia) or ""
        if open_in_pi_link:
            open_in_pi_link = format_html(
                '<a target="_blank" href="{}">Otwórz w Profilu Instytucji</a>. ',
                open_in_pi_link,
            )

    except SameDataUploadedRecently as e:
        link_do_wyslanych = reverse(
            "admin:pbn_api_sentdata_change",
            args=(SentData.objects.get_for_rec(obj, uczelnia).pk,),
        )

        notificator.info(
            format_html(
                'Identyczne dane rekordu "{}" zostały wgrane do PBN w dniu {}. '
                "Nie aktualizuję w PBN API. Jeżeli chcesz wysłać ten rekord do "
                "PBN, musisz dokonać jakiejś zmiany danych rekodu lub usunąć "
                'informacje o <a target="_blank" href="{}">wcześniej wysłanych '
                "danych do PBN</a> (Redagowanie -> PBN API -> Wysłane "
                "informacje). {}{}",
                link_do_obiektu(obj),
                e,
                link_do_wyslanych,
                open_in_pbn_link,
                open_in_pi_link,
            )
        )
        if raise_exceptions:
            raise e

        return

    except AccessDeniedException as e:
        notificator.warning(
            format_html(
                'Nie można zsynchronizować obiektu "{}" z PBN pod adresem API {}. '
                "Brak dostępu -- najprawdopodobniej użytkownik nie posiada "
                "odpowiednich uprawnień po stronie PBN/POLON. {}{}",
                link_do_obiektu(obj),
                e.url,
                open_in_pbn_link,
                open_in_pi_link,
            ),
        )
        if raise_exceptions:
            raise e

        return

    except PKZeroExportDisabled as e:
        notificator.warning(
            format_html(
                "Eksport prac z PK=0 jest wyłączony w konfiguracji. Próba "
                'wysyłki do PBN rekordu "{}" nie została podjęta z uwagi na '
                "konfigurację systemu. ",
                link_do_obiektu(obj),
            ),
        )
        if raise_exceptions:
            raise e

        return

    except NeedsPBNAuthorisationException as e:
        notificator.warning(
            format_html(
                'Nie można zsynchronizować obiektu "{}" z PBN pod adresem API {}. '
                "Brak dostępu z powodu nieprawidłowego tokena -- wymagana "
                'autoryzacja w PBN. <a target="_blank" href="{}">Kliknij tutaj, '
                "aby autoryzować sesję</a>. {}{}",
                link_do_obiektu(obj),
                e.url,
                reverse("pbn_api:authorize"),
                open_in_pbn_link,
                open_in_pi_link,
            ),
        )
        if raise_exceptions:
            raise e

        return

    except ResourceLockedException as e:
        notificator.warning(
            format_html(
                'Nie można zsynchronizować obiektu "{}" z PBN pod adresem API {}, '
                "ponieważ obiekt po stronie serwera PBN jest zablokowany. "
                "Spróbuj ponownie za jakiś czas. {}{}",
                link_do_obiektu(obj),
                e.url,
                open_in_pbn_link,
                open_in_pi_link,
            ),
        )

        if raise_exceptions:
            raise e

        return

    except PBNValidationError as e:
        komunikaty = format_html_join(
            "", "<li>{}</li>", ((m,) for m in e.user_messages())
        )
        notificator.warning(
            format_html(
                'Rekord "{}" został odrzucony przez PBN z powodu błędów '
                "walidacji danych: <ul>{}</ul>Popraw dane rekordu i spróbuj "
                "ponownie. {}{}",
                link_do_obiektu(obj),
                komunikaty,
                open_in_pbn_link,
                open_in_pi_link,
            )
        )
        if raise_exceptions:
            raise e

        return

    except AutorBezIdentyfikatoraPBN as e:
        # FD#509: oświadczenie któregoś autora przepadłoby po cichu (brak
        # odpowiednika w PBN i brak ORCID), więc NIC nie poszło do PBN.
        # Osobna gałąź (przed ogólną ``WillNotExportError``), bo redaktor
        # potrzebuje listy autorów z odnośnikami do ich edycji.
        notificator.error(komunikat_autorzy_bez_identyfikatora(obj, e.autorzy))
        if raise_exceptions:
            raise e

        return

    except WillNotExportError as e:
        # Rekordu nie da się wysłać, dopóki ktoś czegoś nie uzupełni — a NIE
        # awaria kodu. Komunikat wyjątku jest już napisany po polsku i wprost
        # mówi, czego brakuje, więc podajemy go redaktorowi zamiast
        # generycznego „Kod błędu: …" z gałęzi niżej.
        #
        # Bez tej gałęzi wpadało to do `except Exception`, opatrzonego
        # komentarzem „nie wiadomo, co to za problem" — i szło do Rollbara
        # (itemy Rollbar #1475, #1473), mimo że system działał poprawnie.
        #
        # „lub konfigurację" w komunikacie jest celowe: ta gałąź łapie też
        # przypadki, w których poprawka NIE leży w rekordzie —
        # `CharakterFormalnyMissingPBNUID` (słownik charakterów formalnych)
        # oraz gołe `WillNotExportError` podnoszone przez
        # `Uczelnia.pbn_client()` przy braku autoryzacji w PBN.
        #
        # UWAGA NA KOLEJNOŚĆ: `PKZeroExportDisabled` (też podklasa
        # WillNotExportError) ma własną gałąź WYŻEJ i musi tam zostać — ma
        # inny, konfiguracyjny komunikat. Pilnuje tego parametryzacja
        # testu `..._will_not_export_czytelny_komunikat_bez_rollbar`.
        notificator.warning(
            format_html(
                'Rekord "{}" nie zostanie wysłany do PBN: {}. '
                "Popraw dane rekordu lub konfigurację i spróbuj ponownie. {}{}",
                link_do_obiektu(obj),
                e,
                open_in_pbn_link,
                open_in_pi_link,
            )
        )
        if raise_exceptions:
            raise e

        return

    except Exception as e:
        try:
            link_do_wyslanych = reverse(
                "admin:pbn_api_sentdata_change",
                args=(SentData.objects.get_for_rec(obj, uczelnia).pk,),
            )
        except SentData.DoesNotExist:
            link_do_wyslanych = None

        extra = ""
        if link_do_wyslanych:
            extra = format_html(
                '<a target="_blank" href="{}">'
                "Kliknij, aby otworzyć widok wysłanych danych</a>.",
                link_do_wyslanych,
            )

        notificator.warning(
            format_html(
                'Nie można zsynchronizować obiektu "{}" z PBN. Kod błędu: {}. {} {}{}',
                link_do_obiektu(obj),
                e,
                extra,
                open_in_pbn_link,
                open_in_pi_link,
            )
        )

        # Zgłoś problem do monitoringu, bo w sumie nie wiadomo, co to za problem na tym etapie...
        capture_exception(sys.exc_info())

        if raise_exceptions:
            raise e

        return

    # Multi-hosted (Track 4): zawężamy do uczelni z kontekstu akcji — ta sama
    # uczelnia, której client wysyłał rekord (``self.uczelnia`` w sync). Bez
    # tego, gdy ≥2 uczelnie wysłały ten rekord, ``.get()`` rzuciłby
    # ``MultipleObjectsReturned``.
    sent_data = SentData.objects.get_for_rec(obj, uczelnia)
    sent_data_link = link_do_obiektu(sent_data, "Otwórz widok wysłanych danych. ")

    publication_link = link_do_obiektu(
        sent_data.pbn_uid,
        "Otwórz lokalną kopię danych z PBN. ",
    )

    notificator.success(
        format_html(
            "Dane w PBN dla rekordu {} zostały zaktualizowane. {}{}{}{}",
            link_do_obiektu(obj),
            open_in_pbn_link,
            open_in_pi_link,
            sent_data_link,
            publication_link,
        ),
    )

    # PO komunikacie o sukcesie: liczby dotyczą tego, co właśnie trafiło do PBN.
    ostrzez_o_pominietych_oswiadczeniach(obj, uczelnia, notificator)

    return sent_data
