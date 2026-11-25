import json

from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.filter(name="pretty_json")
def pretty_json(value):
    """Formatuj wartość jako czytelny JSON string."""
    try:
        return json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    except (TypeError, ValueError):
        return str(value)


@register.filter(name="admin_change_url")
def admin_change_url(obj):
    """Zwróć URL strony edycji obiektu w module redagowania (admin).

    Działa dla dowolnego modelu — nazwa route'u budowana jest z
    ``app_label``/``model_name`` samego obiektu, więc jedno wywołanie
    obsługuje np. i ``Wydawnictwo_Ciagle``, i ``Wydawnictwo_Zwarte``.
    Gdy obiekt nie ma pk albo nie jest zarejestrowany w adminie —
    zwraca pusty string (link się nie pojawi).
    """
    if obj is None or getattr(obj, "pk", None) is None:
        return ""
    meta = obj._meta
    try:
        return reverse(
            f"admin:{meta.app_label}_{meta.model_name}_change",
            args=(obj.pk,),
        )
    except NoReverseMatch:
        return ""


@register.filter(name="dyscyplina_do_przypisania")
def dyscyplina_do_przypisania(author, session):
    """FD#620: czy wybrana dyscyplina zostanie przypisana autorowi na rok
    pracy przy tworzeniu rekordu (autor nie ma przypisania na ten rok) —
    te same warunki, co ``przypisz_brakujace_dyscypliny``.

    Autorów z przypisaniem na rok liczymy raz na sesję (atrybut obiektu
    sesji żyje przez jedno renderowanie) — bez zapytania na każdy wiersz."""
    from bpp.models import Autor_Dyscyplina
    from importer_publikacji.models import ImportedAuthor

    if (
        not author.matched_autor_id
        or not author.matched_jednostka_id
        or not author.matched_dyscyplina_id
        or author.match_status == ImportedAuthor.MatchStatus.UNMATCHED
    ):
        return False
    rok = (session.normalized_data or {}).get("year")
    if not rok:
        return False
    z_przypisaniem = getattr(session, "_fd620_autorzy_z_przypisaniem", None)
    if z_przypisaniem is None:
        z_przypisaniem = set(
            Autor_Dyscyplina.all_objects.filter(
                rok=rok,
                autor_id__in=session.authors.exclude(matched_autor=None).values(
                    "matched_autor_id"
                ),
            ).values_list("autor_id", flat=True)
        )
        session._fd620_autorzy_z_przypisaniem = z_przypisaniem
    return author.matched_autor_id not in z_przypisaniem


@register.filter(name="podstawa_dopasowania")
def podstawa_dopasowania(author):
    """FD#512: po czym importer rozpoznał autora — identyfikator osoby
    w PBN, ORCID czy imię i nazwisko.

    Liczone z bieżącego stanu wiersza: dostawca podał identyfikator i ten
    sam ma dopasowany autor BPP. Dla wyboru ręcznego i braku dopasowania
    — pusty tekst (podstawą jest decyzja redaktora)."""
    from importer_publikacji.models import ImportedAuthor

    autor = author.matched_autor
    if autor is None or author.match_status not in (
        ImportedAuthor.MatchStatus.AUTO_EXACT,
        ImportedAuthor.MatchStatus.AUTO_LOOSE,
    ):
        return ""
    if author.pbn_uid and autor.pbn_uid_id == author.pbn_uid:
        return "po identyfikatorze PBN"
    if author.orcid and (autor.orcid or "").strip().upper() == author.orcid.upper():
        return "po ORCID"
    return "po imieniu i nazwisku"


@register.filter(name="uwaga_o_dyscyplinie")
def uwaga_o_dyscyplinie(author, session):
    """FD#512: rozbieżność między dyscypliną z oświadczenia w PBN a dyscypliną
    ze zgłoszenia publikacji albo przypisaniem autora na rok pracy
    (``zrodla.uwagi_o_dyscyplinach``); ``None``, gdy wszystko się zgadza.

    Uwagi całej sesji liczymy raz na renderowanie (atrybut obiektu sesji)."""
    from importer_publikacji.zrodla import uwagi_o_dyscyplinach

    uwagi = getattr(session, "_fd512_uwagi_o_dyscyplinach", None)
    if uwagi is None:
        uwagi = uwagi_o_dyscyplinach(session)
        session._fd512_uwagi_o_dyscyplinach = uwagi
    return uwagi.get(author.pk)


@register.filter(name="rekord_z_odpowiednikiem_pbn")
def rekord_z_odpowiednikiem_pbn(session):
    """FD#512: rekord BPP, który ma już odpowiednik w PBN wybrany w tej
    sesji — albo ``None``. Pole jest unikalne, więc utworzony rekord nie
    zostałby powiązany (``_link_pbn_uid`` pomija powiązanie); redaktor ma
    to zobaczyć przed utworzeniem. Rekord utworzony przez tę sesję nie jest
    „cudzy”. Wynik liczymy raz na renderowanie."""
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    if hasattr(session, "_fd512_zajety_odpowiednik"):
        return session._fd512_zajety_odpowiednik

    zajety = None
    mongo_id = (session.matched_data or {}).get("pbn_mongo_id")
    if mongo_id:
        for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte):
            rekord = model.objects.filter(pbn_uid_id=mongo_id).first()
            if rekord is not None and not (
                session.created_record_id == rekord.pk
                and session.created_record_content_type is not None
                and session.created_record_content_type.model_class() is model
            ):
                zajety = rekord
                break
    session._fd512_zajety_odpowiednik = zajety
    return zajety
