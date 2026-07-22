"""Analiza pary autorów na bazie wyłącznie meta-cache (bez SQL).

Mirror'uje wagi punktowe z ``utils/analysis.py:analiza_duplikatow`` żeby
zachować spójność scoringu między fazą PBN i general.
Pomija tylko analizę płci (która w wersji DB-owej używa
``Autor.plec`` + heurystyki na imieniu — nie potrzebne w v1 trybu general).
"""


def _common_initials(imiona_a: list[str], imiona_b: list[str]) -> int:
    initials_a = {x[0] for x in imiona_a if x}
    initials_b = {x[0] for x in imiona_b if x}
    return len(initials_a & initials_b)


def _name_or_initial_match(a: str, b: str) -> bool:
    """True jeśli ``a == b`` albo jedna strona jest inicjałem drugiej.

    Inicjał = pojedyncza litera (ewentualnie z kropką, jak 'J.'). Tym samym
    'jan' i 'j.' są dopasowaniem, ale 'jan' i 'ja' już nie.
    """
    if not a or not b:
        return False
    a_clean = a.lower().rstrip(".")
    b_clean = b.lower().rstrip(".")
    if a_clean == b_clean:
        return True
    if len(a_clean) == 1 and b_clean.startswith(a_clean):
        return True
    if len(b_clean) == 1 and a_clean.startswith(b_clean):
        return True
    return False


def _signals(a: dict, b: dict) -> dict:
    """Policz sygnały dopasowania imion + swap-a (raz, używane wielokrotnie)."""
    similar_imie = 0
    for ia in a["imiona_norm"]:
        for ib in b["imiona_norm"]:
            if len(ia) >= 3 and len(ib) >= 3 and ia != ib:
                if ia.startswith(ib[:3]) or ib.startswith(ia[:3]):
                    similar_imie += 1
    # Swap obejmuje też przypadek z inicjałem: 'Jan Kowalski' ↔ 'Kowalski J.'
    # gdzie database swap (imiona='Kowalski', nazwisko='J.') ma inicjał 'J'
    # pasujący do imienia 'Jan' z drugiej strony.
    wykryto_swap = (
        bool(a["nazwisko_norm"])
        and bool(b["nazwisko_norm"])
        and bool(a["imiona_norm"])
        and bool(b["imiona_norm"])
        and any(
            _name_or_initial_match(a["nazwisko_norm"], imie)
            for imie in b["imiona_norm"]
        )
        and any(
            _name_or_initial_match(b["nazwisko_norm"], imie)
            for imie in a["imiona_norm"]
        )
    )
    return {
        "common_imie": set(a["imiona_norm"]) & set(b["imiona_norm"]),
        "similar_imie": similar_imie,
        "init_count_imie": _common_initials(a["imiona_norm"], b["imiona_norm"]),
        "wykryto_swap": wykryto_swap,
    }


def _rule_publikacje(a: dict, b: dict, sig: dict) -> tuple[int, str]:
    pubs_b = b["publikacje_count"]
    if pubs_b <= 5:
        return 10, f"mało publikacji ({pubs_b}) - prawdopodobny duplikat"
    if pubs_b <= 10:
        return -10, f"średnio publikacji ({pubs_b}) - możliwy duplikat"
    return -20, f"wiele publikacji ({pubs_b}) - mało prawdopodobny duplikat"


def _rule_tytul(a: dict, b: dict, sig: dict) -> tuple[int, str] | None:
    if not b["ma_tytul"] and a["ma_tytul"]:
        return 15, "brak tytułu naukowego u kandydata - prawdopodobny duplikat"
    if b["ma_tytul"] and a["ma_tytul"]:
        if a.get("tytul_id") == b.get("tytul_id"):
            return 10, "identyczny tytuł naukowy"
        return -15, "różny tytuł naukowy"
    return None


def _rule_orcid(a: dict, b: dict, sig: dict) -> tuple[int, str] | None:
    if not b["ma_orcid"] and a["ma_orcid"]:
        return 15, "brak ORCID u kandydata - prawdopodobny duplikat"
    if b["ma_orcid"] and a["ma_orcid"]:
        if a.get("orcid_value") == b.get("orcid_value"):
            return 50, "identyczny ORCID - to ten sam autor"
        return -50, "różny ORCID - to różni autorzy"
    return None


def _rule_nazwisko(a: dict, b: dict, sig: dict) -> tuple[int, str] | None:
    if not (a["nazwisko_norm"] and b["nazwisko_norm"]):
        return None
    if a["nazwisko_norm"] == b["nazwisko_norm"]:
        return 40, "identyczne nazwisko"
    if (
        a["nazwisko_norm"] in b["nazwisko_norm"]
        or b["nazwisko_norm"] in a["nazwisko_norm"]
    ):
        return 30, "podobne nazwisko (zawieranie)"
    parts_a = set(a.get("nazwisko_parts") or [])
    parts_b = set(b.get("nazwisko_parts") or [])
    common_parts = parts_a & parts_b
    if common_parts and (len(parts_a) > 1 or len(parts_b) > 1):
        if parts_a == parts_b:
            # Pełny zestaw członów się zgadza (np. permutacja
            # 'gal-cisoń' ↔ 'cisoń-gal').
            return 35, "identyczne człony nazwiska złożonego (permutacja)"
        return 20, (
            f"wspólny człon nazwiska złożonego ({', '.join(sorted(common_parts))})"
        )
    return None


def _rule_poprzednie_nazwisko(a: dict, b: dict, sig: dict) -> tuple[int, str] | None:
    """Nazwisko jednego autora figuruje w poprzednich nazwiskach drugiego.

    Łapie zmianę nazwiska (panieńskie → po mężu, dwuczłonowe → jednoczłonowe):
    to samo nazwisko jako obecne u jednego rekordu i jako poprzednie u drugiego,
    albo wspólne poprzednie nazwisko po obu stronach (FD#407).
    """
    a_naz = a["nazwisko_norm"]
    b_naz = b["nazwisko_norm"]
    a_prev = set(a.get("poprzednie_nazwiska_norm") or [])
    b_prev = set(b.get("poprzednie_nazwiska_norm") or [])
    if (a_naz and a_naz in b_prev) or (b_naz and b_naz in a_prev):
        return 40, "nazwisko figuruje w poprzednich nazwiskach drugiego autora"
    wspolne = a_prev & b_prev
    if wspolne:
        return 35, f"wspólne poprzednie nazwisko ({', '.join(sorted(wspolne))})"
    return None


def _rule_swap(a: dict, b: dict, sig: dict) -> tuple[int, str] | None:
    if sig["wykryto_swap"]:
        return 50, "wykryto pełną zamianę imienia z nazwiskiem"
    return None


def _rule_wspolne_imie(a: dict, b: dict, sig: dict) -> tuple[int, str] | None:
    n = len(sig["common_imie"])
    if n:
        return 30 * n, f"wspólne imię ({n})"
    return None


def _rule_podobne_imie(a: dict, b: dict, sig: dict) -> tuple[int, str] | None:
    n = sig["similar_imie"]
    if n:
        return 15 * n, f"podobne imię ({n})"
    return None


def _rule_inicjaly(a: dict, b: dict, sig: dict) -> tuple[int, str] | None:
    n = sig["init_count_imie"]
    if n:
        return 5 * n, f"pasujące inicjały ({n})"
    return None


def _rule_brak_imion(a: dict, b: dict, sig: dict) -> tuple[int, str] | None:
    if not b["imiona_norm"] and a["imiona_norm"]:
        return 10, "brak imion u kandydata"
    return None


def _rule_lata(a: dict, b: dict, sig: dict) -> tuple[int, str] | None:
    common_lata = a["lata_publikacji"] & b["lata_publikacji"]
    if common_lata:
        return 20, f"wspólne lata publikacji: {sorted(common_lata)}"
    if not (a["lata_publikacji"] and b["lata_publikacji"]):
        return None
    min_dist = min(
        abs(ra - rb) for ra in a["lata_publikacji"] for rb in b["lata_publikacji"]
    )
    if min_dist <= 2:
        return 15, f"bliskie lata publikacji (różnica {min_dist})"
    if min_dist <= 7:
        return -5, f"średnia odległość lat publikacji ({min_dist})"
    return -20, f"duża odległość lat publikacji ({min_dist})"


# Kolejność reguł = kolejność powodów w wyniku (musi pozostać identyczna).
_RULES = (
    _rule_publikacje,
    _rule_tytul,
    _rule_orcid,
    _rule_nazwisko,
    _rule_poprzednie_nazwisko,
    _rule_swap,
    _rule_wspolne_imie,
    _rule_podobne_imie,
    _rule_inicjaly,
    _rule_brak_imion,
    _rule_lata,
)


def analiza_pary_meta(a: dict, b: dict) -> tuple[int, list[str]]:
    """Zwraca (score, reasons) dla pary (a, b) na bazie meta-cache.

    HARD REJECTION: jeżeli obie strony mają imiona, ale nie ma między nimi
    żadnego punktu wspólnego (ani pełne imię, ani 3-prefix, ani inicjał),
    a jednocześnie NIE wykryto pełnej zamiany imię↔nazwisko, kandydat jest
    natychmiast odrzucany. Zwracamy mocno ujemny score gwarantujący filtr
    `score >= min_confidence` w `search_general.generate_pairs`. To nie jest
    duplikat — żaden bonus z innych kryteriów (ORCID, nazwisko, lata) nie
    może tego nadpisać. 'Jan' i 'Agnieszka' to różne osoby.

    Scoring jest tabelą reguł ``_RULES`` — każda reguła zwraca
    ``(waga, powód)`` albo ``None`` (brak wkładu). Pętla akumuluje punkty i
    powody w kolejności reguł; ta kolejność jest częścią kontraktu.
    """
    sig = _signals(a, b)

    if (
        a["imiona_norm"]
        and b["imiona_norm"]
        and not sig["common_imie"]
        and sig["similar_imie"] == 0
        and sig["init_count_imie"] == 0
        and not sig["wykryto_swap"]
    ):
        return -1000, [
            f"odrzucono: zupełnie różne imiona "
            f"('{' '.join(a['imiona_norm'])}' vs "
            f"'{' '.join(b['imiona_norm'])}') — to różni autorzy"
        ]

    score = 0
    reasons: list[str] = []
    for rule in _RULES:
        result = rule(a, b, sig)
        if result is not None:
            weight, reason = result
            score += weight
            reasons.append(reason)

    return score, reasons
