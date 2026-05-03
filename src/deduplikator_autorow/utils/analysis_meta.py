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


def analiza_pary_meta(a: dict, b: dict) -> tuple[int, list[str]]:  # noqa: C901
    """Zwraca (score, reasons) dla pary (a, b) na bazie meta-cache.

    HARD REJECTION: jeżeli obie strony mają imiona, ale nie ma między nimi
    żadnego punktu wspólnego (ani pełne imię, ani 3-prefix, ani inicjał),
    a jednocześnie NIE wykryto pełnej zamiany imię↔nazwisko, kandydat jest
    natychmiast odrzucany. Zwracamy mocno ujemny score gwarantujący filtr
    `score >= min_confidence` w `search_general.generate_pairs`. To nie jest
    duplikat — żaden bonus z innych kryteriów (ORCID, nazwisko, lata) nie
    może tego nadpisać. 'Jan' i 'Agnieszka' to różne osoby.
    """
    # Wczesne policzenie sygnałów dopasowania imion + ewentualnego swap-a.
    common_imie = set(a["imiona_norm"]) & set(b["imiona_norm"])
    similar_imie = 0
    for ia in a["imiona_norm"]:
        for ib in b["imiona_norm"]:
            if len(ia) >= 3 and len(ib) >= 3 and ia != ib:
                if ia.startswith(ib[:3]) or ib.startswith(ia[:3]):
                    similar_imie += 1
    init_count_imie = _common_initials(a["imiona_norm"], b["imiona_norm"])
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

    if (
        a["imiona_norm"]
        and b["imiona_norm"]
        and not common_imie
        and similar_imie == 0
        and init_count_imie == 0
        and not wykryto_swap
    ):
        return -1000, [
            f"odrzucono: zupełnie różne imiona "
            f"('{' '.join(a['imiona_norm'])}' vs "
            f"'{' '.join(b['imiona_norm'])}') — to różni autorzy"
        ]

    score = 0
    reasons: list[str] = []

    pubs_b = b["publikacje_count"]
    if pubs_b <= 5:
        score += 10
        reasons.append(f"mało publikacji ({pubs_b}) - prawdopodobny duplikat")
    elif pubs_b <= 10:
        score -= 10
        reasons.append(f"średnio publikacji ({pubs_b}) - możliwy duplikat")
    else:
        score -= 20
        reasons.append(f"wiele publikacji ({pubs_b}) - mało prawdopodobny duplikat")

    if not b["ma_tytul"] and a["ma_tytul"]:
        score += 15
        reasons.append("brak tytułu naukowego u kandydata - prawdopodobny duplikat")
    elif b["ma_tytul"] and a["ma_tytul"]:
        if a.get("tytul_id") == b.get("tytul_id"):
            score += 10
            reasons.append("identyczny tytuł naukowy")
        else:
            score -= 15
            reasons.append("różny tytuł naukowy")

    if not b["ma_orcid"] and a["ma_orcid"]:
        score += 15
        reasons.append("brak ORCID u kandydata - prawdopodobny duplikat")
    elif b["ma_orcid"] and a["ma_orcid"]:
        if a.get("orcid_value") == b.get("orcid_value"):
            score += 50
            reasons.append("identyczny ORCID - to ten sam autor")
        else:
            score -= 50
            reasons.append("różny ORCID - to różni autorzy")

    if a["nazwisko_norm"] and b["nazwisko_norm"]:
        if a["nazwisko_norm"] == b["nazwisko_norm"]:
            score += 40
            reasons.append("identyczne nazwisko")
        elif (
            a["nazwisko_norm"] in b["nazwisko_norm"]
            or b["nazwisko_norm"] in a["nazwisko_norm"]
        ):
            score += 30
            reasons.append("podobne nazwisko (zawieranie)")
        else:
            parts_a = set(a.get("nazwisko_parts") or [])
            parts_b = set(b.get("nazwisko_parts") or [])
            common_parts = parts_a & parts_b
            if common_parts and (len(parts_a) > 1 or len(parts_b) > 1):
                if parts_a == parts_b:
                    # Pełny zestaw członów się zgadza (np. permutacja
                    # 'gal-cisoń' ↔ 'cisoń-gal').
                    score += 35
                    reasons.append("identyczne człony nazwiska złożonego (permutacja)")
                else:
                    score += 20
                    reasons.append(
                        f"wspólny człon nazwiska złożonego "
                        f"({', '.join(sorted(common_parts))})"
                    )

    if wykryto_swap:
        score += 50
        reasons.append("wykryto pełną zamianę imienia z nazwiskiem")

    if common_imie:
        score += 30 * len(common_imie)
        reasons.append(f"wspólne imię ({len(common_imie)})")

    if similar_imie:
        score += 15 * similar_imie
        reasons.append(f"podobne imię ({similar_imie})")

    if init_count_imie:
        score += 5 * init_count_imie
        reasons.append(f"pasujące inicjały ({init_count_imie})")

    if not b["imiona_norm"] and a["imiona_norm"]:
        score += 10
        reasons.append("brak imion u kandydata")

    common_lata = a["lata_publikacji"] & b["lata_publikacji"]
    if common_lata:
        score += 20
        reasons.append(f"wspólne lata publikacji: {sorted(common_lata)}")
    elif a["lata_publikacji"] and b["lata_publikacji"]:
        min_dist = min(
            abs(ra - rb) for ra in a["lata_publikacji"] for rb in b["lata_publikacji"]
        )
        if min_dist <= 2:
            score += 15
            reasons.append(f"bliskie lata publikacji (różnica {min_dist})")
        elif min_dist <= 7:
            score -= 5
            reasons.append(f"średnia odległość lat publikacji ({min_dist})")
        else:
            score -= 20
            reasons.append(f"duża odległość lat publikacji ({min_dist})")

    return score, reasons
