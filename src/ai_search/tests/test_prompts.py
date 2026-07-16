from ai_search.prompts import FEW_SHOT, HARD_RULES, build_system

SCHEMA_TEXT = (
    "# DjangoQL schema\n"
    "# Negate with != / !~ / not in / not startswith / not endswith.\n"
    "start model: bpp.rekord\n\n"
    "bpp.rekord:\n  rok  int  e.g. rok = 2024\n"
)


def test_build_system_has_cache_control_on_last_block():
    blocks = build_system(SCHEMA_TEXT, "rekord")
    assert blocks[-1]["cache_control"] == {"type": "ephemeral"}
    assert blocks[-1]["type"] == "text"


def test_build_system_embeds_schema_verbatim_not_json_dumped():
    blocks = build_system(SCHEMA_TEXT, "rekord")
    text = blocks[-1]["text"]
    # schemat jest stringiem wklejonym wprost — nie ma otaczających cudzysłowów
    # jak przy json.dumps(schema_text).
    assert SCHEMA_TEXT in text
    assert f'"{SCHEMA_TEXT}"' not in text
    assert f"'{SCHEMA_TEXT}'" not in text


def test_build_system_has_negation_reminder():
    blocks = build_system(SCHEMA_TEXT, "rekord")
    text = blocks[-1]["text"]
    assert "not startswith" in text


def test_build_system_includes_few_shot_for_model_key():
    blocks = build_system(SCHEMA_TEXT, "autor")
    text = blocks[-1]["text"]
    pl, dsl = FEW_SHOT["autor"][0]
    assert pl in text
    assert dsl in text


def test_hard_rules_is_short_and_does_not_duplicate_grammar_legend():
    # HARD_RULES nie powinno duplikowac calej legendy operatorow (to robi
    # naglowek compact-schematu) - tylko framing zadania + krotkie
    # przypomnienie o negacji.
    assert len(HARD_RULES.splitlines()) <= 12
    assert "query" in HARD_RULES
    assert "error" in HARD_RULES


def test_few_shot_covers_both_models():
    assert FEW_SHOT["rekord"]
    assert FEW_SHOT["autor"]
    for examples in FEW_SHOT.values():
        for pl, dsl in examples:
            assert isinstance(pl, str) and pl
            assert isinstance(dsl, str) and dsl
