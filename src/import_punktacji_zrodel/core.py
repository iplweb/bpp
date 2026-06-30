"""Logika importu punktacji źródeł z pliku JCR do Punktacja_Zrodla."""

from django.contrib.messages import constants

from import_common.core import matchuj_zrodlo
from import_punktacji_zrodel.parser import wczytaj_plik_jcr

_KWARTYL_LABEL = {None: "brak", 1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}


def _q(v) -> str:
    return _KWARTYL_LABEL.get(v, str(v))


def _detect_duplicates(czasopisma):
    """Zwraca {index: (index_pierwszego, "ISSN"/"eISSN")} dla powtórzeń."""
    dups = {}
    issn_seen = {}
    eissn_seen = {}
    for i, cz in enumerate(czasopisma):
        powody = []
        first = None
        if cz.issn:
            if cz.issn in issn_seen:
                powody.append("ISSN")
                first = issn_seen[cz.issn]
            else:
                issn_seen[cz.issn] = i
        if cz.e_issn:
            if cz.e_issn in eissn_seen:
                powody.append("eISSN")
                if first is None:
                    first = eissn_seen[cz.e_issn]
            else:
                eissn_seen[cz.e_issn] = i
        if powody:
            dups[i] = (first, ", ".join(powody))
    return dups


def _compare_if(cz, pz, parent, operacje, to_save):
    """Porównuje impact_factor i aktualizuje operacje/to_save."""
    if not parent.importuj_impact_factor:
        return
    if cz.impact_factor is None:
        operacje.append("IF: brak danych (N/A) w pliku")
        return
    stare = pz.impact_factor if pz else None
    if stare != cz.impact_factor:
        operacje.append(
            f"IF: {stare if stare is not None else 'brak'} → {cz.impact_factor}"
        )
        to_save["impact_factor"] = cz.impact_factor
    else:
        operacje.append("IF bez zmian")


def _compare_kwartyl(cz, pz, parent, operacje, to_save):
    """Porównuje kwartyl_w_wos i aktualizuje operacje/to_save."""
    if not parent.importuj_kwartyl_wos:
        return
    if cz.kwartyl_wos is None:
        operacje.append("Kwartyl: brak danych (N/A) w pliku")
        return
    stare_q = pz.kwartyl_w_wos if pz else None
    if stare_q != cz.kwartyl_wos:
        operacje.append(f"Kwartyl: {_q(stare_q)} → {_q(cz.kwartyl_wos)}")
        to_save["kwartyl_w_wos"] = cz.kwartyl_wos
    else:
        operacje.append("Kwartyl bez zmian")


def _process_one_journal(i, cz, rok, parent, dry_run, is_dup, dup_of, dup_reason):
    """Przetwarza jedno czasopismo i tworzy WierszImportuPunktacjiZrodel."""
    dup_prefix = f"DUPLIKAT wiersza {dup_of + 1} ({dup_reason}). " if is_dup else ""
    zrodlo = matchuj_zrodlo(
        cz.nazwa,
        issn=cz.issn,
        e_issn=cz.e_issn,
        disable_fuzzy=True,
        disable_skrot=True,
        disable_title_matching=parent.nie_porownuj_po_tytulach,
    )
    dane = {
        "nazwa": cz.nazwa,
        "issn": cz.issn,
        "e_issn": cz.e_issn,
        "impact_factor": (
            str(cz.impact_factor) if cz.impact_factor is not None else None
        ),
        "kwartyl_wos": cz.kwartyl_wos,
    }
    dup_kwargs = dict(
        is_duplicate=is_dup,
        duplicate_of_row=(dup_of + 1) if dup_of is not None else None,
        duplicate_reason=dup_reason,
    )

    if zrodlo is None:
        parent.wierszimportupunktacjizrodel_set.create(
            nr_wiersza=i + 1,
            dane_z_xls=dane,
            zrodlo=None,
            rezultat=dup_prefix + "Brak źródła w BPP",
            wymaga_zmian=False,
            **dup_kwargs,
        )
        return

    pz = zrodlo.punktacja_zrodla_set.filter(rok=rok).first()
    operacje: list[str] = []
    to_save: dict = {}

    _compare_if(cz, pz, parent, operacje, to_save)
    _compare_kwartyl(cz, pz, parent, operacje, to_save)

    if to_save and not dry_run:
        if pz is None:
            pz = zrodlo.punktacja_zrodla_set.create(rok=rok)
        for k, v in to_save.items():
            setattr(pz, k, v)
        pz.save(update_fields=list(to_save))

    parent.wierszimportupunktacjizrodel_set.create(
        nr_wiersza=i + 1,
        dane_z_xls=dane,
        zrodlo=zrodlo,
        rezultat=dup_prefix + ". ".join(operacje),
        wymaga_zmian=bool(to_save),
        **dup_kwargs,
    )


def analyze_jcr_file(path, parent):
    parsed = wczytaj_plik_jcr(path)

    rok = parent.rok or parsed.rok
    if rok is None:
        msg = "Nie udało się ustalić roku (brak nagłówka i metadanych JCR)."
        parent.wierszimportupunktacjizrodel_set.create(
            nr_wiersza=0, dane_z_xls={}, rezultat=msg
        )
        parent.send_notification(msg, level=constants.ERROR)
        raise ValueError(msg)
    if parent.rok is None:
        parent.rok = rok
        parent.save(update_fields=["rok"])

    dry_run = not parent.zapisz_zmiany_do_bazy
    dups = _detect_duplicates(parsed.czasopisma)
    total = len(parsed.czasopisma) or 1

    for i, cz in enumerate(parsed.czasopisma):
        parent.send_progress((i + 1) * 100.0 / total)
        is_dup = i in dups
        dup_of, dup_reason = dups.get(i, (None, ""))
        _process_one_journal(i, cz, rok, parent, dry_run, is_dup, dup_of, dup_reason)
