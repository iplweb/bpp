from import_sqlite.core.author_names import sort_key, split_name


def test_split_name_basic():
    assert split_name("Anna Wawruszak") == ("Anna", "Wawruszak")


def test_split_name_hyphenated_surname():
    assert split_name("Wirginia Kukuła-Koch") == ("Wirginia", "Kukuła-Koch")


def test_split_name_multi_token_surname():
    assert split_name("Jan von Neumann") == ("Jan", "von Neumann")


def test_split_name_single_token():
    assert split_name("Cher") == ("", "Cher")


def test_split_name_empty():
    assert split_name("   ") == ("", "")


def test_sort_key_groups_spelling_variants():
    # "Kowalski" i "Kovalski" NIE są równe, ale mają sąsiadujące klucze
    assert sort_key("Kowalski") != sort_key("Kovalski")
    assert abs(ord(sort_key("Kowalski")[2]) - ord(sort_key("Kovalski")[2])) <= 3


def test_sort_key_strips_diacritics_and_case():
    assert sort_key("Kukuła-Koch") == sort_key("kukula koch")
