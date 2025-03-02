from django.urls import reverse
from sentry_sdk import capture_exception

from import_common.normalization import normalize_isbn
from pbn_api.exceptions import (
    AccessDeniedException,
    BrakZdefiniowanegoObiektuUczelniaWSystemieError,
    CharakterFormalnyNieobslugiwanyError,
    NeedsPBNAuthorisationException,
    PKZeroExportDisabled,
    PraceSerwisoweException,
    ResourceLockedException,
    SameDataUploadedRecently,
)
from pbn_api.models import SentData

from django.contrib.contenttypes.models import ContentType

from bpp.admin.helpers import link_do_obiektu


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


def sprobuj_wyslac_do_pbn(
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
                    from pbn_api.integrator import _pobierz_prace_po_elemencie

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
                    from pbn_api.integrator import _pobierz_prace_po_elemencie

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

    #
    # Sprawdź, czy każdy autor z dyscypliną ma odpowiednik w PBN, jeżeli nie -- wyświetl ostrzeżenie
    #

    for autor in (
        obj.autorzy_set.exclude(dyscyplina_naukowa=None)
        .exclude(jednostka__skupia_pracownikow=False)
        .exclude(afiliuje=False)
        .exclude(przypieta=False)
        .filter(autor__pbn_uid_id=None)
    ):
        url = reverse("admin:bpp_autor_change", args=(autor.autor_id,))
        notificator.warning(
            f"Autor {autor} ma w tej pracy przypiętą dyscyplinę i afiluje, ale nie "
            f"zostanie oświadczona w PBN, gdyż autor nie posiada odpowiednika w PBN. <a href={url} target=_blank>"
            f"Kliknij tutaj</a> aby wyedytować tego autora. "
        )

    try:
        pbn_client.sync_publication(
            obj,
            notificator=notificator,
            force_upload=force_upload,
            delete_statements_before_upload=uczelnia.pbn_api_kasuj_przed_wysylka,
            export_pk_zero=not uczelnia.pbn_api_nie_wysylaj_prac_bez_pk,
            always_affiliate_to_uid=(
                uczelnia.pbn_uid_id
                if uczelnia.pbn_api_afiliacja_zawsze_na_uczelnie
                else None
            ),
        )

    except SameDataUploadedRecently as e:
        link_do_wyslanych = reverse(
            "admin:pbn_api_sentdata_change",
            args=(SentData.objects.get_for_rec(obj).pk,),
        )

        notificator.info(
            f'Identyczne dane rekordu "{link_do_obiektu(obj)}" zostały wgrane do PBN w dniu {e}. '
            f"Nie aktualizuję w PBN API. Jeżeli chcesz wysłać ten rekord do PBN, musisz dokonać jakiejś zmiany "
            f"danych rekodu lub "
            f'usunąć informacje o <a target=_blank href="{link_do_wyslanych}">wcześniej wysłanych danych do PBN</a> '
            f"(Redagowanie -> PBN API -> Wysłane informacje). "
            f'<a target=_blank href="{obj.link_do_pbn()}">Kliknij tutaj, aby otworzyć w PBN</a>. ',
        )
        if raise_exceptions:
            raise e

        return

    except AccessDeniedException as e:
        notificator.warning(
            f'Nie można zsynchronizować obiektu "{link_do_obiektu(obj)}" z PBN pod adresem '
            f"API {e.url}. Brak dostępu -- najprawdopodobniej użytkownik nie posiada odpowiednich uprawnień "
            f"po stronie PBN/POLON. ",
        )
        if raise_exceptions:
            raise e

        return

    except PKZeroExportDisabled as e:
        notificator.warning(
            f"Eksport prac z PK=0 jest wyłączony w konfiguracji. Próba wysyłki do PBN rekordu "
            f'"{link_do_obiektu(obj)}" nie została podjęta z uwagi na konfigurację systemu. ',
        )
        if raise_exceptions:
            raise e

        return

    except NeedsPBNAuthorisationException as e:
        notificator.warning(
            f'Nie można zsynchronizować obiektu "{link_do_obiektu(obj)}" z PBN pod adresem '
            f"API {e.url}. Brak dostępu z powodu nieprawidłowego tokena -- wymagana autoryzacja w PBN. "
            f'<a target=_blank href="{reverse("pbn_api:authorize")}">Kliknij tutaj, aby autoryzować sesję</a>.',
        )
        if raise_exceptions:
            raise e

        return

    except ResourceLockedException as e:
        notificator.warning(
            f'Nie można zsynchronizować obiektu "{link_do_obiektu(obj)}" z PBN pod adresem '
            f"API {e.url}, ponieważ obiekt po stronie serwera PBN jest zablokowany. Spróbuj ponownie za jakiś czas."
        )

        if raise_exceptions:
            raise e

        return

    except Exception as e:
        try:
            link_do_wyslanych = reverse(
                "admin:pbn_api_sentdata_change",
                args=(SentData.objects.get_for_rec(obj).pk,),
            )
        except SentData.DoesNotExist:
            link_do_wyslanych = None

        extra = ""
        if link_do_wyslanych:
            extra = (
                '<a target=_blank href="%s">Kliknij, aby otworzyć widok wysłanych danych</a>.'
                % link_do_wyslanych
            )

        notificator.warning(
            'Nie można zsynchronizować obiektu "%s" z PBN. Kod błędu: %r. %s'
            % (link_do_obiektu(obj), e, extra),
        )

        # Zaloguj problem do Sentry, bo w sumie nie wiadomo, co to za problem na tym etapie...
        capture_exception(e)

        if raise_exceptions:
            raise e

        return

    sent_data = SentData.objects.get(
        content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk
    )
    sent_data_link = link_do_obiektu(
        sent_data, "Kliknij tutaj, aby otworzyć widok wysłanych danych. "
    )

    publication_link = link_do_obiektu(
        sent_data.pbn_uid,
        "Kliknij tutaj, aby otworzyć zwrotnie otrzymane z PBN dane o rekordzie. ",
    )
    notificator.success(
        f"Dane w PBN dla rekordu {link_do_obiektu(obj)} zostały zaktualizowane. "
        f'<a target=_blank href="{obj.link_do_pbn()}">Kliknij tutaj, aby otworzyć w PBN</a>. '
        f"{sent_data_link}{publication_link}",
    )

    return sent_data
