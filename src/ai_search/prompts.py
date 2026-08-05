"""System prompt (reguły + few-shot) dla tłumacza pytań PL -> DjangoQL.

Gramatyka i legenda operatorów NIE są tu duplikowane — to robi nagłówek
compact-schematu zwracany przez ``schema_export.schema_for_llm`` (patrz
``djangoql.llm._COMPACT_HEADER``). ``HARD_RULES`` niesie tylko framing
zadania: co model ma zrobić, jak zwrócić wynik, i krótkie przypomnienie
o braku samodzielnego `not`.
"""

HARD_RULES = """\
Tłumaczysz pytania w języku polskim na zapytania DSL DjangoQL dla systemu
bibliografii publikacji (BPP). Zwracasz WYŁĄCZNIE poprawne zapytanie w polu
`query`, albo `query=null` i wyjaśnienie po polsku w `error`, gdy pytania nie
da się wyrazić w tym DSL (np. jest ono ocenne/nieostre: "najlepsze",
"ciekawe").

Pamiętaj: nie ma samodzielnego operatora `not` — negujesz operatorem: !=,
!~, not in, not startswith, not endswith.
"""

FEW_SHOT = {
    "rekord": [
        ("publikacje z 2024 roku", "rok = 2024"),
        (
            "prace po 2020 zawierające w tytule nowotwór",
            'rok > 2020 and tytul_oryginalny ~ "nowotwor"',
        ),
        ("artykuły o charakterze AC", 'charakter_formalny.skrot = "AC"'),
        (
            "prace autora o nazwisku Kowalski",
            'autorzy.autor.nazwisko ~ "Kowalski"',
        ),
        ("publikacje z lat 2022-2024", "rok >= 2022 and rok <= 2024"),
        ("prace bez przypisanego źródła", "zrodlo = None"),
        (
            "tytuły niezawierające słowa raport",
            'tytul_oryginalny !~ "raport"',
        ),
        (
            "prace typu KBN PW lub PX",
            'typ_kbn.skrot in ("PW", "PX")',
        ),
    ],
    "autor": [
        (
            "autorzy o nazwisku zaczynającym się na Kow",
            'nazwisko startswith "Kow"',
        ),
        (
            "autorzy z imieniem Jan lub Anna",
            'imiona ~ "Jan" or imiona ~ "Anna"',
        ),
        ("autorzy z podanym ORCID", "orcid != None"),
        ("autorki i autorzy bez pseudonimu", "pseudonim = None"),
    ],
}


def _few_shot_text(model_key: str) -> str:
    lines = ["PRZYKŁADY:"]
    for pl, dsl in FEW_SHOT[model_key]:
        lines.append(f'"{pl}" -> {dsl}')
    return "\n".join(lines)


def build_system(schema_text: str, model_key: str) -> list:
    """Bloki `system` dla SDK anthropic.

    ``schema_text`` to gotowy, compact string ze ``schema_export.schema_for_llm``
    — wklejany dosłownie (bez json.dumps). Jedyny (a więc i ostatni) blok
    jest stabilny między kolejnymi wywołaniami dla tego samego modelu, więc
    dostaje ``cache_control`` (ephemeral), żeby Anthropic mógł go odczytać
    z cache przy kolejnych/ponawianych zapytaniach. Pytanie użytkownika NIE
    jest tu zawarte — dokłada je wołający (translator.py) jako osobną
    wiadomość ``user``.
    """
    text = (
        f"{HARD_RULES}\n"
        f"SCHEMAT (model {model_key}):\n{schema_text}\n"
        f"{_few_shot_text(model_key)}"
    )
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
