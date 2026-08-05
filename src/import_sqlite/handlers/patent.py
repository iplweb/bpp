"""Handler typu ``patent``: parsowanie ``parsed_json`` → ``PatentData``
(czyste) oraz materializacja ``PatentData`` → modele BPP (DB).
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from bpp.util import safe_html
from import_sqlite.core.author_names import split_name
from import_sqlite.reader import RawRecord

SZCZEGOLY_MAX = 512


@dataclass
class PatentData:
    source_id: str
    source_url: str
    tytul: str
    rok: int | None
    numer_zgloszenia: str
    data_zgloszenia: date | None
    numer_prawa: str
    data_decyzji: date | None
    szczegoly: str
    adnotacje: str
    inventors: list[str] = field(default_factory=list)


def parse_ddmmyyyy(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%d-%m-%Y").date()
    except (ValueError, AttributeError):
        return None


def _year_from(s: str | None) -> int | None:
    d = parse_ddmmyyyy(s)
    return d.year if d else None


def parse_patent(rec: RawRecord) -> PatentData:
    p = rec.parsed
    af = p.get("all_fields") or {}

    data_zgloszenia = parse_ddmmyyyy(p.get("application_date"))
    data_decyzji = parse_ddmmyyyy(af.get("Data udzielenia prawa"))
    rok = _year_from(p.get("application_date")) or _year_from(
        af.get("Data udzielenia prawa")
    )

    tytul_ang = af.get("Nazwa wynalazku / wzoru / utworu w języku angielskim") or ""
    mkp = af.get("Klasyfikacja MKP") or ""
    score = p.get("patent_score") or ""
    szczegoly_parts = [
        x for x in (tytul_ang, mkp, f"Punktacja: {score}" if score else "") if x
    ]
    szczegoly_full = " | ".join(szczegoly_parts)
    szczegoly = szczegoly_full[:SZCZEGOLY_MAX]

    adnotacje_parts = []
    if len(szczegoly_full) > SZCZEGOLY_MAX:
        adnotacje_parts.append(szczegoly_full)
    for key in ("Opis w języku polskim", "Opis w języku angielskim"):
        if af.get(key):
            adnotacje_parts.append(f"{key}: {af[key]}")
    adnotacje = "\n\n".join(adnotacje_parts)

    return PatentData(
        source_id=rec.source_id,
        source_url=rec.source_url,
        tytul=(p.get("title") or "").strip(),
        rok=rok,
        numer_zgloszenia=(p.get("application_number") or "").strip(),
        data_zgloszenia=data_zgloszenia,
        numer_prawa=(af.get("Numer patentu/prawa") or "").strip(),
        data_decyzji=data_decyzji,
        szczegoly=szczegoly,
        adnotacje=adnotacje,
        inventors=list(p.get("inventors") or []),
    )


# --------------------------------------------------------------------------
# Materializacja PatentData → modele BPP (wymaga skonfigurowanego Django + DB)
# --------------------------------------------------------------------------


@dataclass
class ImportContext:
    uczelnia: object
    obca_jednostka: object
    status_korekty: object
    zrodlo_informacji: object


def build_context() -> "ImportContext":
    """Zbierz obiekty słownikowe potrzebne do importu; waliduj preconditiony.

    Głośno pada (``ValueError``), gdy uczelnia nie ma ``obca_jednostka`` —
    lepiej tu niż ``IntegrityError`` w środku pętli (jednostka twórcy jest
    NOT NULL).
    """
    from bpp.models import Status_Korekty, Uczelnia, Zrodlo_Informacji

    uczelnia = Uczelnia.objects.get_single_uczelnia_or_fail()
    if uczelnia.obca_jednostka is None:
        raise ValueError(
            "Uczelnia nie ma ustawionej 'obca_jednostka' — ustaw ją w adminie "
            "przed importem (potrzebna jako jednostka twórców spoza uczelni)."
        )
    status = (
        Status_Korekty.objects.filter(nazwa="przed korektą").first()
        or Status_Korekty.objects.first()
    )
    zrodlo, _ = Zrodlo_Informacji.objects.get_or_create(
        nazwa="Import z pliku SQLite (harvester ASB)"
    )
    return ImportContext(uczelnia, uczelnia.obca_jednostka, status, zrodlo)


def resolve_inventor(nazwisko_zrodlowe, decyzja, ctx):
    """Zwróć ``(autor, jednostka, afiliuje)`` dla rozstrzygniętego twórcy.

    ``decyzja == "NOWY"`` → utwórz ``Autor`` i przypisz do obcej jednostki.
    Inaczej ``decyzja`` to pk istniejącego ``Autor``-a. ``afiliuje`` zależy
    WYŁĄCZNIE od ``skupia_pracownikow`` jednostki (obca ma je False).
    """
    from bpp.models import Autor

    if decyzja == "NOWY":
        given, family = split_name(nazwisko_zrodlowe)
        autor = Autor.objects.create(imiona=given, nazwisko=family)
        autor.dodaj_jednostke(ctx.obca_jednostka)
        jednostka = ctx.obca_jednostka
    else:
        autor = Autor.objects.get(pk=int(decyzja))
        jednostka = autor.aktualna_jednostka or ctx.obca_jednostka
    return autor, jednostka, bool(jednostka.skupia_pracownikow)


def apply_patent(pd: PatentData, decisions: dict, ctx: "ImportContext") -> tuple:
    """Utwórz lub zaktualizuj ``Patent`` z ``PatentData`` wg ``decisions``.

    Zwraca ``(status, powod)``; status ∈ {UTWORZONY, ZAKTUALIZOWANY,
    WSTRZYMANY}. Cała materializacja w savepoincie (``transaction.atomic``),
    więc wstrzymanie/``ValidationError`` cofa TYLKO ten patent.
    """
    from bpp.models import Patent

    # 1) Pre-check: wszyscy twórcy muszą mieć decyzję — PRZED jakimkolwiek
    #    zapisem do bazy (żeby hold nie zostawił utworzonych Autor-ów NOWY).
    for nazwisko_zrodlowe in pd.inventors:
        if not decisions.get(nazwisko_zrodlowe, "").strip():
            return ("WSTRZYMANY", f"nierozstrzygnięty twórca: {nazwisko_zrodlowe}")

    try:
        with transaction.atomic():
            existing = list(
                Patent.objects.filter(numer_prawa_wylacznego=pd.numer_prawa)
            )
            if len(existing) > 1:
                return ("WSTRZYMANY", "niejednoznaczny klucz numer_prawa_wylacznego")

            # 2) Rozstrzygnij twórców, dedupe po pk (pierwsze wystąpienie wygrywa
            #    zapisany_jako i kolejność).
            resolved = []  # (autor, jednostka, afiliuje, zapisany_jako, kolejnosc)
            seen_pk = set()
            for kolejnosc, nazwisko_zrodlowe in enumerate(pd.inventors):
                autor, jednostka, afiliuje = resolve_inventor(
                    nazwisko_zrodlowe, decisions[nazwisko_zrodlowe].strip(), ctx
                )
                if autor.pk in seen_pk:
                    continue
                seen_pk.add(autor.pk)
                resolved.append(
                    (autor, jednostka, afiliuje, nazwisko_zrodlowe, kolejnosc)
                )

            wydzial = next(
                (j for (_a, j, _af, _z, _k) in resolved if j.skupia_pracownikow),
                None,
            )

            if existing:
                patent = existing[0]
                patent.autorzy_set.all().delete()
                created = False
            else:
                patent = Patent()
                created = True

            patent.tytul_oryginalny = safe_html(pd.tytul)
            patent.rok = pd.rok
            patent.numer_zgloszenia = pd.numer_zgloszenia or None
            patent.data_zgloszenia = pd.data_zgloszenia
            patent.numer_prawa_wylacznego = pd.numer_prawa
            patent.data_decyzji = pd.data_decyzji
            patent.wydzial = wydzial
            patent.www = pd.source_url
            patent.szczegoly = pd.szczegoly
            patent.adnotacje = pd.adnotacje
            patent.status_korekty = ctx.status_korekty
            patent.informacja_z = ctx.zrodlo_informacji
            patent.save()

            for autor, jednostka, afiliuje, zapisany_jako, kolejnosc in resolved:
                patent.dodaj_autora(
                    autor,
                    jednostka,
                    zapisany_jako=zapisany_jako,
                    kolejnosc=kolejnosc,
                    afiliuje=afiliuje,
                )
    except ValidationError as e:
        return ("WSTRZYMANY", f"ValidationError: {e}")

    return ("UTWORZONY" if created else "ZAKTUALIZOWANY", "")
