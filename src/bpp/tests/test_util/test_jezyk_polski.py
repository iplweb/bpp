from bpp.jezyk_polski import warianty_zapisanego_nazwiska


def _compare_stuff(input_list, output_list):
    """Helper function - sprawdza czy wszystkie elementy output są w input."""
    for elem in output_list:
        assert elem in input_list


def test_warianty_zapisanego_nazwiska():
    wzn = warianty_zapisanego_nazwiska

    _compare_stuff(
        list(wzn("Jan Maria", "Rokita", None)),
        [
            "Jan Maria Rokita",
            "J[an] M[aria] Rokita",
            "J. M. Rokita",
            "Jan Rokita",
            "J[an] Rokita",
            "J. Rokita",
            "Maria Rokita",
            "M[aria] Rokita",
            "M. Rokita",
        ],
    )

    _compare_stuff(
        list(wzn("Jan Maria", "Rokita-Potocki", None)),
        [
            "Jan Maria Rokita-Potocki",
            "Jan Maria Rokita",
            "Jan Maria Potocki",
            "J[an] M[aria] Rokita-Potocki",
            "J[an] M[aria] Rokita",
            "J[an] M[aria] Potocki",
            "J. M. Rokita-Potocki",
            "J. M. Rokita",
            "J. M. Potocki",
            "Jan Rokita-Potocki",
            "Jan Rokita",
            "Jan Potocki",
            "J[an] Rokita-Potocki",
            "J[an] Rokita",
            "J[an] Potocki",
            "J. Rokita-Potocki",
            "J. Rokita",
            "J. Potocki",
            "Maria Rokita-Potocki",
            "Maria Rokita",
            "Maria Potocki",
            "M[aria] Rokita-Potocki",
            "M[aria] Rokita",
            "M[aria] Potocki",
            "M. Rokita-Potocki",
            "M. Rokita",
            "M. Potocki",
        ],
    )

    _compare_stuff(
        list(wzn("Stanisław J.", "Czuczwar", None)),
        [
            "Stanisław J. Czuczwar",
            "S[tanisław] J. Czuczwar",
            "S. J. Czuczwar",
            "Stanisław Czuczwar",
            "S[tanisław] Czuczwar",
            "S. Czuczwar",
            "J. Czuczwar",
            "J. Czuczwar",
            "J. Czuczwar",
        ],
    )

    _compare_stuff(
        list(wzn("Zbigniew F.", "Zagórski", None)),
        [
            "Zbigniew F. Zagórski",
            "Z[bigniew] F. Zagórski",
            "Z. F. Zagórski",
            "Zbigniew Zagórski",
            "Z[bigniew] Zagórski",
            "Z. Zagórski",
            "F. Zagórski",
            "F. Zagórski",
            "F. Zagórski",
        ],
    )

    _compare_stuff(
        list(wzn("Jan", "Kowalski", "Nowak")),
        [
            "Jan Kowalski",
            "J[an] Kowalski",
            "J. Kowalski",
            "Jan Nowak",
            "J[an] Nowak",
            "J. Nowak",
        ],
    )
