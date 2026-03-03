from crossref_bpp.core import Komparator


def categorize_crossref_fields(raw_data: dict) -> dict:
    """Kategoryzuj klucze raw_data z CrossRef API na trzy grupy.

    Zwraca {"wyodrebnione": [...], "ignorowane": [...], "obce": [...]}
    gdzie kazda lista to posortowane (key, value) tuples.

    - wyodrebnione: pola ktore BPP odczytuje (do_zmatchowania + do_skopiowania)
    - ignorowane: pola znane BPP, ale nieuzywane
    - obce: pola nierozpoznane przez BPP
    """
    if not raw_data or not isinstance(raw_data, dict):
        return {
            "wyodrebnione": [],
            "ignorowane": [],
            "obce": [],
        }

    znane = set(Komparator.atrybuty.do_zmatchowania) | set(
        Komparator.atrybuty.do_skopiowania
    )
    ignorowane_set = set(Komparator.atrybuty.ignorowane)
    wszystkie = set(Komparator.atrybuty.wszystkie)

    wyodrebnione = []
    ignorowane = []
    obce = []

    for key in sorted(raw_data.keys()):
        value = raw_data[key]
        if key in znane:
            wyodrebnione.append((key, value))
        elif key in ignorowane_set:
            ignorowane.append((key, value))
        elif key not in wszystkie:
            obce.append((key, value))

    return {
        "wyodrebnione": wyodrebnione,
        "ignorowane": ignorowane,
        "obce": obce,
    }
