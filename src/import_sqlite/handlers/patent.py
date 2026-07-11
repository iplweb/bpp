"""Handler typu ``patent``: parsowanie ``parsed_json`` → ``PatentData``
(czyste) oraz materializacja ``PatentData`` → modele BPP (DB).
"""

from dataclasses import dataclass, field
from datetime import date, datetime

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
