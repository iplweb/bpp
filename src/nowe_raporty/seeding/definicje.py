"""Definicje domyślnych raportów (slice A).

Treść zapytań DSL, kolumn i szablonu pochodzi z dumpu produkcyjnego
(``flexible_reports``), przepisana do kodu z poprawkami:

- zbite tagi HTML w szablonie (``<h2>...</h3>``) → spójne ``h2``/``h3``,
- błędne labele ``2.1`` „rozdziału" → „monografii",
- dorobiony wariant ``- uczelnia`` dla sekcji ``2.x`` (agregacja po całej
  uczelni; ``obiekt.pk`` znika) oraz cały ``raport-uczelni``.

Sekcje ``2.x`` muszą wstrzykiwać warunek po obiekcie (``autor=/jednostka=/
wydzial=``) RAZEM z ``typ_odpowiedzialnosci`` w jednym warunku — pinują rolę
do konkretnego autora na pojedynczym wierszu autorstwa; płaska, wstępnie
przefiltrowana lista prac tego nie wyraża.
"""

# --- Wspólna tabela + kolumny ------------------------------------------------

TABELA_LABEL = "Publikacje autorów"

TABELA = dict(
    label=TABELA_LABEL,
    sort_option=0,
    attrs={"class": "bpp-table"},
    group_prefix=None,
    empty_template="<center>Nie znaleziono takich rekordów.</center>",
)

KOLUMNY = [
    dict(
        label="Lp",
        position=0,
        sortable=False,
        attr_name="pk",
        template="{{ column.column.counter }}.",
        attrs={"td": {"class": "bpp-lp-column"}},
        display_totals=False,
        strip_html_on_export=False,
        exclude_from_export=True,
        footer_template="",
    ),
    dict(
        label="Opis bibliograficzny",
        position=1,
        sortable=True,
        attr_name="tytul_oryginalny",
        template="{{ record.opis_bibliograficzny_cache|safe }}",
        attrs=None,
        display_totals=True,
        strip_html_on_export=True,
        exclude_from_export=False,
        footer_template="<div align=right>Suma:</div>",
    ),
    dict(
        label="IF",
        position=3,
        sortable=True,
        attr_name="impact_factor",
        template="",
        attrs={"td": {"style": "text-align: right;"}},
        display_totals=True,
        strip_html_on_export=False,
        exclude_from_export=False,
        footer_template="{{ value }}",
    ),
    dict(
        label="Pkt. MNiSW",
        position=4,
        sortable=True,
        attr_name="punkty_kbn",
        template="",
        attrs={"td": {"style": "text-align: right;"}},
        display_totals=True,
        strip_html_on_export=False,
        exclude_from_export=False,
        footer_template="{{ value }}",
    ),
    dict(
        label="Typ KBN",
        position=5,
        sortable=True,
        attr_name="typ_kbn",
        template="",
        attrs=None,
        display_totals=False,
        strip_html_on_export=False,
        exclude_from_export=False,
        footer_template="{{ value }}",
    ),
    dict(
        label="Rok",
        position=2,
        sortable=True,
        attr_name="rok",
        template="",
        attrs={"td": {"style": "text-align: right;"}},
        display_totals=True,
        strip_html_on_export=False,
        exclude_from_export=False,
        footer_template="{{ count }}",
    ),
    dict(
        label="ID rekordu",
        position=6,
        sortable=False,
        attr_name="id",
        template="{{ value }}",
        attrs=None,
        display_totals=False,
        strip_html_on_export=False,
        exclude_from_export=False,
        footer_template="{{ value }}",
    ),
]

# (label kolumny, position, desc)
KOLEJNOSC = [
    ("Rok", 0, True),
    ("Opis bibliograficzny", 1, False),
]

# --- Datasource'y wspólne (bez filtra po obiekcie) ---------------------------
# scoping per-obiekt dla tych sekcji bierze sie z set_base_queryset() w kodzie.

DS_1_1 = """(
  impact_factor > 0
  AND punktacja_wewnetrzna = 0
  AND NOT (
      adnotacje ~ "wos"
      OR
      konferencja__baza_wos = 1
      OR
      adnotacje ~ "erih"
  )
  AND NOT typ_kbn = "PW"
)

OR adnotacje ~ "lista_a\""""

DS_1_2 = """adnotacje ~ "lista_b"

OR

(
impact_factor = 0
AND punkty_kbn > 0
AND charakter IN ["AC", "L", "Supl"]
AND NOT (
    adnotacje ~ "wos"
    OR
    konferencja__baza_wos = 1
    OR
    adnotacje ~ "erih"
    OR
    adnotacje ~ "lista_a"
)
AND NOT (typ_kbn = "PW")

AND NOT (
{%comment%}
punkt 1.4
{%endcomment%}
liczba_znakow_wydawniczych >= 20000
AND charakter IN ["AC", "L", "Supl"]
AND impact_factor=0
AND punkty_kbn > 0
AND NOT jezyk__skrot = "pol."

)
)"""

DS_1_3 = """adnotacje ~ "erih"
AND punkty_kbn > 0"""

DS_1_4 = """liczba_znakow_wydawniczych >= 20000
AND charakter IN ["AC", "L", "Supl"]
AND impact_factor=0
AND punkty_kbn > 0
AND NOT jezyk__skrot = "pol.\""""

DS_1_5 = '(adnotacje ~ "wos" OR konferencja__baza_wos = 1)'

DS_3 = 'charakter = "PAT"'

DS_4_1 = """charakter IN ["PSZ", "PRZ", "PST", "PSTS", "RZK", "ZRZ", "PSZ", "SZK", "ZSZ"]

AND NOT (


{% comment %}
Wyklucz prace z punktu 1.5 konferencje indeksowane w bazach WOS
{% endcomment %}


   (adnotacje ~ "wos" OR konferencja__baza_wos = 1)
   AND punkty_kbn > 0
)"""

DS_4_2 = 'typ_kbn = "PNP"'

# datasource'y wspólne, kluczowane po slug-u sekcji
WSPOLNE_DATASOURCE = {
    "1_1": (
        "1.1. Publikacje w czasopiśmie naukowym posiadającym Impact Factor IF "
        "(część A wykazu MNiSW)",
        DS_1_1,
    ),
    "1_2": (
        "1.2 Publikacja w czasopiśmie naukowym nieposiadającym IF "
        "(część B wykazu MNiSW)",
        DS_1_2,
    ),
    "1_3": (
        "1.3 Publikacja w czasopiśmie naukowym znajdującym się w bazie European "
        "Reference Index for the Humanities (ERIH (część C wykazu MNiSW)",
        DS_1_3,
    ),
    "1_4": (
        "1.4 Recenzowana publikacja naukowa w języku innym niż polski w "
        "zagranicznym czasopiśmie naukowym spoza list A,B,C, o objętości co "
        "najmniej 0,5 arkusza",
        DS_1_4,
    ),
    "1_5": (
        "1.5 Publikacja w recenzowanych materiałach z konferencji "
        "międzynarodowej uwzględnionej w Web of Science.",
        DS_1_5,
    ),
    "3": ("3. Patenty", DS_3),
    "4_1": ("4.1 Materiały konferencyjne", DS_4_1),
    "4_2": ("4.2 Publikacje popularnonaukowe", DS_4_2),
}

# --- Datasource'y 2.x (per typ obiektu) --------------------------------------
# generowane z jednego wzorca + klauzuli obiektu; field=None => uczelnia
# (agregacja po calej uczelni, bez "= {{ obiekt.pk }}").

DS_2_1_BAZA = """typ_odpowiedzialnosci IN ["aut.", "Aut. koresp."]
AND charakter IN ["KSZ", "KSP", "KS", "H"]
AND NOT (charakter IN ["KS", "KSP", "KSZ"] AND (typ_kbn = "000" OR typ_kbn="PNP"))
{% if punktuj_monografie %}
AND punkty_kbn > 0
{% endif %}"""

DS_2_2_BAZA = """charakter = "ROZ"
AND typ_odpowiedzialnosci IN ["aut.", "Aut. koresp."]
AND NOT (charakter="ROZ" AND (typ_kbn = "000" OR typ_kbn="PNP"))"""

DS_2_3_BAZA = """typ_odpowiedzialnosci IN ["red.", "red. nauk. wyd. pol."]
AND charakter IN ["KSZ", "KSP", "KS"]
AND NOT typ_kbn IN ["000", "PNP"]
{% if punktuj_monografie %}
AND punkty_kbn > 0
{% endif %}"""

DATASOURCE_2X_BAZA = {
    "2_1": ("2.1. Autorstwo monografii naukowej", DS_2_1_BAZA),
    "2_2": ("2.2 Autorstwo rozdziału w monografii naukowej", DS_2_2_BAZA),
    "2_3": ("2.3 Redakcja naukowa monografii naukowej wieloautorskiej", DS_2_3_BAZA),
}

# nazwa pola w DSL -> etykieta do labela datasource'a
OBJ_LABEL = {
    "autor": "autor",
    "jednostka": "jednostka",
    "wydzial": "wydział",
    None: "uczelnia",
}


def klauzula_obiektu(field):
    """Zwraca dopisek DSL pinujący warunek do obiektu, lub pusty dla uczelni."""
    if field is None:
        return ""
    return "\nAND " + field + " = {{ obiekt.pk|default:0 }}"


# --- Sekcje raportu ----------------------------------------------------------
# (slug elementu, tytuł sekcji, rodzaj). Rodzaj wskazuje datasource:
# wspólny (klucz w WSPOLNE_DATASOURCE), per-obiekt ("2_1/2_2/2_3"), albo
# "catchall" (4.3 Inne - data_from = EXCEPT_CATCHALL).

SEKCJE = [
    (
        "tabela_1_1",
        "1.1. Publikacje w czasopiśmie naukowym posiadającym Impact Factor IF",
        "1_1",
    ),
    (
        "tabela_1_2",
        "1.2 Publikacja w czasopiśmie naukowym nieposiadającym IF",
        "1_2",
    ),
    (
        "tabela_1_3",
        "1.3 Publikacja w czasopiśmie naukowym znajdującym się w bazie European "
        "Reference Index for the Humanities",
        "1_3",
    ),
    (
        "tabela_1_4",
        "1.4 Recenzowana publikacja naukowa w języku innym niż polski w "
        "zagranicznym czasopiśmie naukowym spoza list MNiSW o objętości co "
        "najmniej 0,5 arkusza",
        "1_4",
    ),
    (
        "tabela_1_5",
        "1.5 Publikacja w recenzowanych materiałach z konferencji "
        "międzynarodowej uwzględnionej w Web of Science.",
        "1_5",
    ),
    ("tabela_2_1", "2.1 Autorstwo monografii naukowej", "2_1"),
    ("tabela_2_2", "2.2 Autorstwo rozdziału w monografii naukowej", "2_2"),
    ("tabela_2_3", "2.3 Redakcja naukowa monografii naukowej wieloautorskiej", "2_3"),
    ("tabela_3", "3. Patenty", "3"),
    ("tabela_4_1", "4.1. Materiały konferencyjne", "4_1"),
    ("tabela_4_2", "4.2. Publikacje popularnonaukowe", "4_2"),
    ("tabela_4_3", "4.3. Inne", "catchall"),
]

# --- Raporty -----------------------------------------------------------------

RAPORTY = [
    {
        "slug": "raport-autorow",
        "title": "Raport autorów",
        "field": "autor",
        "naglowek": "Raport autora",
    },
    {
        "slug": "raport-jednostek",
        "title": "Raport jednostek",
        "field": "jednostka",
        "naglowek": "Raport jednostki",
    },
    {
        "slug": "raport-wydzialow",
        "title": "Raport wydziałów",
        "field": "wydzial",
        "naglowek": "Raport wydziału",
    },
    {
        "slug": "raport-uczelni",
        "title": "Raport uczelni",
        "field": None,
        "naglowek": "Raport uczelni",
    },
]


# --- Szablon raportu ---------------------------------------------------------


def _blok(slug):
    """Blok HTML jednej sekcji (nagłówek + tabela albo info o braku danych)."""
    return (
        "<h3>{{ elements." + slug + ".title }}</h3>\n"
        "{% if elements." + slug + ".object_list.exists %}\n"
        "{% render_table elements." + slug + ".table %}\n"
        "{% else %}\n"
        "<p>Nie znaleziono takich rekordów.</p>\n"
        "{% endif %}\n\n"
    )


def szablon(naglowek):
    """Zwraca szablon Django dla raportu o danym nagłówku H1.

    Zastępuje 4× prawie-identyczny szablon z dumpu; tagi HTML poprawione.
    """
    czesci = [
        "<h1>" + naglowek + " - {{ object }} za\n"
        "{% if od_roku == do_roku %}\n"
        "    rok {{ od_roku }}\n"
        "{% else %}\n"
        "    lata {{ od_roku }} - {{ do_roku }}\n"
        "{% endif %}\n"
        "</h1>\n\n"
        "{% load django_tables2 %}\n\n",
        "<h2>1. Publikacje w czasopismach naukowych</h2>\n",
    ]
    for slug in ["tabela_1_1", "tabela_1_2", "tabela_1_3", "tabela_1_4", "tabela_1_5"]:
        czesci.append(_blok(slug))

    czesci.append("<h2>2. Monografie naukowe</h2>\n")
    for slug in ["tabela_2_1", "tabela_2_2", "tabela_2_3"]:
        czesci.append(_blok(slug))

    czesci.append("<h2>3. Patenty</h2>\n")
    czesci.append(_blok("tabela_3"))

    czesci.append("<h2>4. Inne</h2>\n")
    for slug in ["tabela_4_1", "tabela_4_2", "tabela_4_3"]:
        czesci.append(_blok(slug))

    return "".join(czesci)
