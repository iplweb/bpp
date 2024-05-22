from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse

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

        if typ_pracy in ["book", "book-chapter"]:
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
