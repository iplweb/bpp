from django.contrib import messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse

from bpp.models import Uczelnia

from .admin.helpers import merge_crossref_and_pbn_data
from .core import Komparator, StatusPorownania
from .forms import PobierzZCrossrefAPIForm


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

        if typ_pracy in ["book", "book-chapter", "edited-book"]:
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

    if form.is_valid():
        json_data = form.cleaned_data["json_data"]
        doi = form.cleaned_data["identyfikator_doi"]

        # Pobierz dane z PBN jeśli możliwe
        pbn_data = None
        pbn_error = None
        pbn_client = None

        try:
            uczelnia = Uczelnia.objects.get_default()
            if uczelnia and uczelnia.pbn_integracja:
                # Spróbuj uzyskać token użytkownika
                user_token = None
                if hasattr(request.user, "pbn_token"):
                    user_token = request.user.pbn_token

                if user_token:
                    pbn_client = uczelnia.pbn_client(user_token)
                    try:
                        # Pobierz dane z PBN po DOI
                        pbn_data = pbn_client.get_publication_by_doi(doi)
                        if pbn_data:
                            messages.success(
                                request, f"Znaleziono rekord w PBN dla DOI: {doi}"
                            )
                    except Exception as e:
                        pbn_error = f"Nie udało się pobrać danych z PBN: {str(e)}"
                        messages.warning(request, pbn_error)
                else:
                    pbn_error = "Brak tokenu PBN - zaloguj się do PBN w menu głównym"
                    messages.info(request, pbn_error)
            else:
                pbn_error = "Integracja z PBN nieaktywna"
        except Exception as e:
            pbn_error = f"Błąd konfiguracji PBN: {str(e)}"
            messages.warning(request, pbn_error)

        # Połącz dane z CrossRef i PBN
        merged_data = merge_crossref_and_pbn_data(json_data, pbn_data)

        # Przygotuj dane porównania (jak w oryginalnej funkcji)
        dane_porownania = Komparator.utworz_dane_porownania(json_data)
        dane_porownania_dict = {x["orig_atrybut"]: x for x in dane_porownania}

        # Dodaj informacje o danych PBN do porównania
        if pbn_data:
            # Dodaj specjalne oznaczenie dla pól pochodzących z PBN
            for pole, zrodlo in merged_data.get("_data_sources", {}).items():
                if "PBN" in zrodlo and pole in dane_porownania_dict:
                    dane_porownania_dict[pole]["zrodlo_danych"] = zrodlo

        typ_pracy = dane_porownania_dict.get("type", {}).get("wartosc_z_crossref", "")
        doi_val = dane_porownania_dict.get("DOI", {}).get("wartosc_z_crossref", "")

        # Przekierowanie jeśli niewłaściwy typ pracy
        if typ_pracy in ["book", "book-chapter", "edited-book"]:
            if "/wydawnictwo_ciagle/" in request.get_full_path():
                return HttpResponseRedirect(
                    "../../wydawnictwo_zwarte/pobierz-z-crossref-pbn/?identyfikator_doi="
                    + doi_val
                )
        else:
            if "/wydawnictwo_zwarte/" in request.get_full_path():
                return HttpResponseRedirect(
                    "../../wydawnictwo_ciagle/pobierz-z-crossref-pbn/?identyfikator_doi="
                    + doi_val
                )

        rekord_po_stronie_bpp = Komparator.czy_rekord_ma_odpowiednik_w_bpp(
            dane_porownania_dict
        )

        context["dane_porownania"] = dane_porownania
        context["do_skopiowania"] = Komparator.dane_do_skopiowania(json_data)
        context["ignorowane"] = Komparator.dane_ignorowane(json_data)
        context["obce"] = Komparator.dane_obce(json_data)

        # Dodaj informacje o połączonych danych
        context["merged_data"] = merged_data
        context["has_pbn_data"] = merged_data.get("has_pbn_data", False)
        context["data_sources"] = merged_data.get("data_sources", {})
        context["pbn_error"] = pbn_error
        context["combined_mode"] = True

        # Ustalamy źródło
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

        return TemplateResponse(
            request, crossref_pbn_templates.get("show", ""), context
        )

    context["crossref_form"] = form
    context["combined_mode"] = True
    return TemplateResponse(request, crossref_pbn_templates.get("form", ""), context)
