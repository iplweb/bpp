from django.contrib import messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse

from bpp.models import Crossref_Mapper, Uczelnia

from .admin.helpers import merge_crossref_and_pbn_data
from .core import Komparator, StatusPorownania
from .forms import PobierzZCrossrefAPIForm


def _czy_typ_jest_wydawnictwem_zwartym(typ_pracy: str) -> bool:
    """
    Sprawdza w Crossref_Mapper czy dany typ pracy powinien być
    traktowany jako wydawnictwo zwarte.
    """
    if not typ_pracy:
        return False

    try:
        # Konwertuj nazwę typu na klucz enum (np. "book-chapter" -> "BOOK_CHAPTER")
        enum_key = typ_pracy.upper().replace("-", "_")
        charakter_crossref_value = Crossref_Mapper.CHARAKTER_CROSSREF[enum_key]
        mapper = Crossref_Mapper.objects.get(
            charakter_crossref=charakter_crossref_value
        )
        return mapper.jest_wydawnictwem_zwartym
    except (Crossref_Mapper.DoesNotExist, KeyError):
        return False


def pobierz_z_crossref(request, context=None, crossref_templates=None):
    if context is None:
        context = {}

    form = PobierzZCrossrefAPIForm()
    if request.method == "POST":
        form = PobierzZCrossrefAPIForm(request.POST)
    elif request.method == "GET" and request.GET.get("identyfikator_doi"):
        form = PobierzZCrossrefAPIForm(request.GET)
    else:
        context["crossref_form"] = form
        return TemplateResponse(request, crossref_templates.get("form", ""), context)

    if form.is_valid():
        json_data = form.cleaned_data["json_data"]

        dane_porownania = Komparator.utworz_dane_porownania(json_data)

        dane_porownania_dict = {x["orig_atrybut"]: x for x in dane_porownania}

        typ_pracy = dane_porownania_dict.get("type", {}).get("wartosc_z_crossref", "")
        doi = dane_porownania_dict.get("DOI", {}).get("wartosc_z_crossref", "")

        jest_zwarte = _czy_typ_jest_wydawnictwem_zwartym(typ_pracy)

        if jest_zwarte:
            if "/wydawnictwo_ciagle/" in request.get_full_path():
                return HttpResponseRedirect(
                    "../../wydawnictwo_zwarte/pobierz-z-crossref/?identyfikator_doi="
                    + doi
                )
        else:
            if "/wydawnictwo_zwarte/" in request.get_full_path():
                return HttpResponseRedirect(
                    "../../wydawnictwo_ciagle/pobierz-z-crossref/?identyfikator_doi="
                    + doi
                )

        rekord_po_stronie_bpp = Komparator.czy_rekord_ma_odpowiednik_w_bpp(
            dane_porownania_dict
        )

        context["dane_porownania"] = dane_porownania
        context["do_skopiowania"] = Komparator.dane_do_skopiowania(json_data)
        context["ignorowane"] = Komparator.dane_ignorowane(json_data)
        context["obce"] = Komparator.dane_obce(json_data)

        # Ustalamy zrodlo
        container_title = dane_porownania_dict.get("container-title", {})
        short_container_title = dane_porownania_dict.get("short-container-title", {})
        issn = dane_porownania_dict.get("ISSN", {})

        if container_title and short_container_title:
            if (
                container_title["rezultat"].status == StatusPorownania.BLAD
                and short_container_title["rezultat"].status == StatusPorownania.BLAD
            ):
                context["dane_nowego_zrodla"] = {
                    "nazwa": container_title.get("wartosc_z_crossref", ""),
                    "skrot": short_container_title.get("wartosc_z_crossref", ""),
                    "issn": issn.get("wartosc_z_crossref", ""),
                }

        context["rekord_po_stronie_bpp"] = rekord_po_stronie_bpp

        context["identyfikator_doi"] = form.cleaned_data["identyfikator_doi"]

        return TemplateResponse(request, crossref_templates.get("show", ""), context)

    context["crossref_form"] = form
    return TemplateResponse(request, crossref_templates.get("form", ""), context)


def _pobierz_dane_z_pbn(request, doi):
    """
    Pobiera dane z PBN API dla podanego DOI.
    Zwraca krotkę (pbn_data, pbn_error).
    """
    pbn_data = None
    pbn_error = None

    try:
        uczelnia = Uczelnia.objects.get_default()
        if not uczelnia or not uczelnia.pbn_integracja:
            return None, "Integracja z PBN nieaktywna"

        user_token = getattr(request.user, "pbn_token", None)
        if not user_token:
            pbn_error = "Brak tokenu PBN - zaloguj się do PBN w menu głównym"
            messages.info(request, pbn_error)
            return None, pbn_error

        pbn_client = uczelnia.pbn_client(user_token)
        try:
            pbn_data = pbn_client.get_publication_by_doi(doi)
            if pbn_data:
                messages.success(request, f"Znaleziono rekord w PBN dla DOI: {doi}")
        except Exception as e:
            pbn_error = f"Nie udało się pobrać danych z PBN: {str(e)}"
            messages.warning(request, pbn_error)
    except Exception as e:
        pbn_error = f"Błąd konfiguracji PBN: {str(e)}"
        messages.warning(request, pbn_error)

    return pbn_data, pbn_error


def _sprawdz_przekierowanie_typu_pracy(request, typ_pracy, doi_val, url_suffix):
    """
    Sprawdza czy należy przekierować na inny typ wydawnictwa.
    Zwraca HttpResponseRedirect lub None.
    """
    jest_zwarte = _czy_typ_jest_wydawnictwem_zwartym(typ_pracy)
    full_path = request.get_full_path()

    if jest_zwarte and "/wydawnictwo_ciagle/" in full_path:
        return HttpResponseRedirect(
            f"../../wydawnictwo_zwarte/{url_suffix}?identyfikator_doi=" + doi_val
        )
    if not jest_zwarte and "/wydawnictwo_zwarte/" in full_path:
        return HttpResponseRedirect(
            f"../../wydawnictwo_ciagle/{url_suffix}?identyfikator_doi=" + doi_val
        )
    return None


def _ustaw_dane_nowego_zrodla(context, dane_porownania_dict):
    """
    Ustawia dane nowego źródła w kontekście jeśli wymagane.
    """
    container_title = dane_porownania_dict.get("container-title", {})
    short_container_title = dane_porownania_dict.get("short-container-title", {})
    issn = dane_porownania_dict.get("ISSN", {})

    if not (container_title and short_container_title):
        return

    if (
        container_title.get("rezultat")
        and container_title["rezultat"].status == StatusPorownania.BLAD
        and short_container_title.get("rezultat")
        and short_container_title["rezultat"].status == StatusPorownania.BLAD
    ):
        context["dane_nowego_zrodla"] = {
            "nazwa": container_title.get("wartosc_z_crossref", ""),
            "skrot": short_container_title.get("wartosc_z_crossref", ""),
            "issn": issn.get("wartosc_z_crossref", ""),
        }


def pobierz_z_crossref_oraz_pbn(request, context=None, crossref_pbn_templates=None):
    """
    Pobiera dane z CrossRef API oraz PBN API i łączy je w jeden zestaw danych.
    """
    if context is None:
        context = {}

    form = PobierzZCrossrefAPIForm()
    if request.method == "POST":
        form = PobierzZCrossrefAPIForm(request.POST)
    elif request.method == "GET" and request.GET.get("identyfikator_doi"):
        form = PobierzZCrossrefAPIForm(request.GET)
    else:
        context["crossref_form"] = form
        context["combined_mode"] = True
        return TemplateResponse(
            request, crossref_pbn_templates.get("form", ""), context
        )

    if not form.is_valid():
        context["crossref_form"] = form
        context["combined_mode"] = True
        return TemplateResponse(
            request, crossref_pbn_templates.get("form", ""), context
        )

    json_data = form.cleaned_data["json_data"]
    doi = form.cleaned_data["identyfikator_doi"]

    # Pobierz dane z PBN
    pbn_data, pbn_error = _pobierz_dane_z_pbn(request, doi)

    # Połącz dane z CrossRef i PBN
    merged_data = merge_crossref_and_pbn_data(json_data, pbn_data)

    # Przygotuj dane porównania
    dane_porownania = Komparator.utworz_dane_porownania(json_data)
    dane_porownania_dict = {x["orig_atrybut"]: x for x in dane_porownania}

    # Dodaj informacje o danych PBN do porównania
    if pbn_data:
        for pole, zrodlo in merged_data.get("_data_sources", {}).items():
            if "PBN" in zrodlo and pole in dane_porownania_dict:
                dane_porownania_dict[pole]["zrodlo_danych"] = zrodlo

    typ_pracy = dane_porownania_dict.get("type", {}).get("wartosc_z_crossref", "")
    doi_val = dane_porownania_dict.get("DOI", {}).get("wartosc_z_crossref", "")

    # Sprawdź przekierowanie
    redirect = _sprawdz_przekierowanie_typu_pracy(
        request, typ_pracy, doi_val, "pobierz-z-crossref-pbn/"
    )
    if redirect:
        return redirect

    # Wypełnij kontekst
    context["dane_porownania"] = dane_porownania
    context["do_skopiowania"] = Komparator.dane_do_skopiowania(json_data)
    context["ignorowane"] = Komparator.dane_ignorowane(json_data)
    context["obce"] = Komparator.dane_obce(json_data)
    context["merged_data"] = merged_data
    context["has_pbn_data"] = merged_data.get("has_pbn_data", False)
    context["data_sources"] = merged_data.get("data_sources", {})
    context["pbn_error"] = pbn_error
    context["combined_mode"] = True
    context["rekord_po_stronie_bpp"] = Komparator.czy_rekord_ma_odpowiednik_w_bpp(
        dane_porownania_dict
    )
    context["identyfikator_doi"] = form.cleaned_data["identyfikator_doi"]

    _ustaw_dane_nowego_zrodla(context, dane_porownania_dict)

    return TemplateResponse(request, crossref_pbn_templates.get("show", ""), context)
