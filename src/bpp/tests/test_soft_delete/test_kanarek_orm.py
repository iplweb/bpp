"""Kanarek ORM-owy: nowy JOIN po soft-delete'owanym ``*_Autor`` bez predykatu.

Odpowiednik ``test_kanarek_katalogowy`` (tamten pilnuje ``pg_views``) o warstwę
wyżej. Przeszukuje KOD PRODUKCYJNY w poszukiwaniu wywołań ORM, które sięgają
przez relację do ``Wydawnictwo_Ciagle_Autor`` / ``Wydawnictwo_Zwarte_Autor`` /
``Patent_Autor``, i wymaga, żeby w tej samej instrukcji padło ``deleted_at``.

Dlaczego to jest potrzebne mimo managerów soft-delete: JOIN przez relację
(``filter(autorzy_set__…)``, ``Count("autorzy_set")``,
``Count("wydawnictwo_ciagle_autor")``) NIE pyta managera — Django złącza
surową tabelę. Ta klasa błędu wróciła w fazie 01 już trzy razy (widoki
``bpp_*_autorzy``, widoki pochodne, ``rozbieznosci_dyscyplin_zrodel``), za
każdym razem odkryta przez awarię, nie przez test.

Jak to działa
=============

Parsujemy każdy produkcyjny ``.py`` do AST i szukamy wywołań, które faktycznie
budują zapytanie (``WYWOLANIA_ORM``: ``filter``/``exclude``/``annotate``/
``Q``/``Count``/…). Dopiero w NICH sprawdzamy nazwy argumentów kluczowych i
literały napisowe pod kątem ścieżek relacji (``PODEJRZANE_SCIEZKI``). Werdykt
zapada na poziomie **instrukcji** (``ast.stmt``), nie linii — bo
``.filter(\\n  a=…,\\n  autorzy_set__deleted_at__isnull=True,\\n)`` rozkłada
predykat na inną linię niż lookup.

Świadomie WĄSKO, żeby kanarek nie krzyczał na:

* ``prefetch_related("autorzy_set__autor")`` i ``select_related`` — idą przez
  ``_default_manager``, są bezpieczne (przypina to
  ``test_prefetch_related_autorzy_set_odcina_skasowane``);
* ``router.register(r"patent_autor", …)`` i mapy nazw endpointów — to nazwy
  URL-i, nie relacje;
* docstringi cytujące ścieżki (``kompletnosc_polon/reguly.py``).

Znane ślepe plamy (świadome, dlatego OBOK stoją testy semantyczne w
``test_orm_wyciek_join.py``):

* **M2M ``autorzy__…``** — ``Q(autorzy__nazwisko=…)`` też złącza surową
  tabelę ``*_autor``, ale ta sama nazwa relacji na ``Rekord`` idzie po
  bezpiecznym ``bpp_autorzy_mat``. Rozróżnienie wymaga znajomości modelu po
  LEWEJ stronie zapytania, a ten bywa w innej instrukcji (tak jest w
  ``export_bibtex``). Statyczny kanarek tego nie rozstrzygnie;
* **odwrotne M2M od ``Autor``** — ``Count("wydawnictwo_ciagle")`` na
  ``Autor`` przechodzi przez through-model, ale ta sama nazwa na ``Zrodlo``
  czy ``Charakter_Formalny`` to zwykły FK. Znowu: zależy od lewego modelu;
* ścieżka sklejona w innej instrukcji niż wywołanie, ``**kwargs`` przekazane
  przez kilka warstw;
* DjangoQL i surowe parametry GET changelistu admina — to język zapytań
  użytkownika, świadomie surowy (patrz raport ``orm-leak-report.md``).

Gdy test padnie
===============

Nie dopisuj wpisu do ``DOZWOLONE`` odruchowo. Najpierw rozstrzygnij:

* czy zapytanie MA widzieć skasowane (audyt, rebuild denorm)? → dopisz
  do ``DOZWOLONE`` z powodem merytorycznym;
* w każdym innym przypadku dołóż ``…__deleted_at__isnull=True`` na TYM SAMYM
  joinie (nie osobnym ``filter()`` — Django zrobi drugi, nieskorelowany JOIN)
  i dopisz test regresji do ``test_orm_wyciek_join.py``.
"""

import ast
import pathlib

import pytest

#: Katalog ``src/`` — korzeń skanowania.
KORZEN = pathlib.Path(__file__).resolve().parents[3]

#: Nazwy relacji do trzech soft-delete'owanych through-modeli. ``autorzy_set``
#: to strona publikacji; pozostałe to nazwy odwrotne od strony ``Autor``,
#: ``Jednostka`` i słowników (brak ``related_name`` → nazwa modelu małymi).
RELACJE = (
    "autorzy_set",
    "wydawnictwo_ciagle_autor",
    "wydawnictwo_zwarte_autor",
    "patent_autor",
)

#: Wywołania, w których nazwa argumentu / literał napisowy jest ścieżką ORM.
#: ``prefetch_related``/``select_related``/``Prefetch`` CELOWO poza listą.
WYWOLANIA_ORM = frozenset(
    {
        "filter",
        "exclude",
        "annotate",
        "aggregate",
        "alias",
        "order_by",
        "values",
        "values_list",
        "only",
        "defer",
        "distinct",
        "get",
        "get_or_create",
        "update",
        "Q",
        "F",
        "Count",
        "Sum",
        "Avg",
        "Min",
        "Max",
        "Exists",
        "OuterRef",
        "Subquery",
        # ``dict(...)`` — bo zestawy lookupów bywają budowane jako
        # ``filter_kw = dict(rok=…, autorzy_set__…)`` i wstrzykiwane ``**``.
        "dict",
        # denorm: kwargs lecą prosto do ``qs.filter()``.
        "rebuild_instances_of",
    }
)

#: Katalogi/pliki spoza kodu produkcyjnego.
POMIJANE_FRAGMENTY_SCIEZKI = (
    "/tests/",
    "/migrations/",
    "/test_",
    "/conftest",
    "/fixtures/",
    "/demo_data/",
)

#: Znane, ŚWIADOME wystąpienia bez ``deleted_at``. Klucz: ścieżka względem
#: ``src/`` + fragment kodu, który ma zostać rozpoznany. Wartość: powód.
#: Dopisanie tu czegokolwiek jest decyzją projektową — patrz docstring modułu.
DOZWOLONE = {
    ("bpp/models/dyscyplina_naukowa.py", "rebuild_instances_of"): (
        "ŚWIADOMIE: rebuild_instances_of wybiera publikacje DO PRZELICZENIA. "
        "Publikacja ze skasowanym autorstwem potrzebuje przeliczenia tak "
        "samo (a nawet bardziej) niż ta z żywym — predykat wyciąłby ją ze "
        "zbioru i zostawił nieaktualne punkty. Przypięte testem "
        "test_denorm_rebuild_CELOWO_widzi_skasowane."
    ),
}


def _pliki_produkcyjne():
    for sciezka in sorted(KORZEN.rglob("*.py")):
        wzgledna = sciezka.relative_to(KORZEN).as_posix()
        if any(frag in "/" + wzgledna for frag in POMIJANE_FRAGMENTY_SCIEZKI):
            continue
        if wzgledna.endswith("tests.py"):
            continue
        yield sciezka, wzgledna


def _jest_sciezka_relacji(tekst: str) -> bool:
    """Czy ``tekst`` (nazwa kwargu albo literał) jest ścieżką ORM do
    through-modelu? ``autorzy_set__autor`` tak, ``patent_autor`` (nazwa
    endpointu w routerze) — tylko gdy stoi samo albo z ``__``."""
    if not isinstance(tekst, str):
        return False
    for relacja in RELACJE:
        if tekst == relacja or tekst.startswith(relacja + "__"):
            return True
        if "__" + relacja + "__" in tekst or tekst.endswith("__" + relacja):
            return True
    return False


def _nazwa_wywolania(wezel: ast.Call) -> str | None:
    if isinstance(wezel.func, ast.Attribute):
        return wezel.func.attr
    if isinstance(wezel.func, ast.Name):
        return wezel.func.id
    return None


def _wywolanie_dotyka_relacji(wezel: ast.Call) -> bool:
    if _nazwa_wywolania(wezel) not in WYWOLANIA_ORM:
        return False
    for kw in wezel.keywords:
        if kw.arg and _jest_sciezka_relacji(kw.arg):
            return True
    for arg in wezel.args:
        if isinstance(arg, ast.Constant) and _jest_sciezka_relacji(arg.value):
            return True
    return False


def _podejrzane_instrukcje(zrodlo: str, wzgledna: str):
    """Zwraca [(linia, pierwsza linia instrukcji)] — instrukcje z wywołaniem
    ORM po relacji do ``*_Autor``, bez ``deleted_at``, spoza ``DOZWOLONE``."""
    try:
        drzewo = ast.parse(zrodlo)
    except SyntaxError:
        # Plik niekompilowalny — nie zadanie tego kanarka.
        return []

    zlozone = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.If,
        ast.While,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.Module,
    )
    wynik = []
    for wezel in ast.walk(drzewo):
        if not isinstance(wezel, ast.stmt) or isinstance(wezel, zlozone):
            continue

        if isinstance(wezel, (ast.For, ast.AsyncFor)):
            # Pętla po LIŚCIE nazw relacji (``for relation in ("wydawnictwo_
            # ciagle_autor", …)``) — ścieżka jest tu, a agregat w ciele.
            # Patrzymy na iterator, werdykt na całej pętli.
            literaly = [
                w.value for w in ast.walk(wezel.iter) if isinstance(w, ast.Constant)
            ]
            if not any(_jest_sciezka_relacji(x) for x in literaly):
                continue
        elif not any(
            isinstance(w, ast.Call) and _wywolanie_dotyka_relacji(w)
            for w in ast.walk(wezel)
        ):
            continue

        segment = ast.get_source_segment(zrodlo, wezel)
        if not segment or "deleted_at" in segment:
            continue
        if any(
            plik == wzgledna and fragment in segment for (plik, fragment) in DOZWOLONE
        ):
            continue
        wynik.append((wezel.lineno, segment.strip().splitlines()[0][:110]))
    return wynik


def test_kanarek_orm_join_po_autorstwie_ma_predykat_deleted_at():
    """Żadne produkcyjne wywołanie ORM nie JOIN-uje ``*_Autor`` bez
    ``deleted_at``.

    Wyrocznia jest strukturalna (AST) + tekstowa (obecność ``deleted_at``
    w tej samej instrukcji), więc kanarek NIE dowodzi poprawności
    semantycznej — dowodzi tylko, że autor kodu w ogóle pomyślał o
    soft-delete. Semantyki pilnują testy w ``test_orm_wyciek_join.py``.
    """
    znaleziska = []
    for sciezka, wzgledna in _pliki_produkcyjne():
        zrodlo = sciezka.read_text(encoding="utf-8")
        if not any(relacja in zrodlo for relacja in RELACJE):
            continue
        for lineno, fragment in _podejrzane_instrukcje(zrodlo, wzgledna):
            znaleziska.append(f"{wzgledna}:{lineno}: {fragment}")

    assert not znaleziska, (
        "JOIN po soft-delete'owanym through-modelu bez predykatu "
        "``deleted_at`` (Django nie pyta tu managera!):\n  "
        + "\n  ".join(znaleziska)
        + "\n\nCo zrobić — patrz docstring modułu "
        "src/bpp/tests/test_soft_delete/test_kanarek_orm.py"
    )


def test_kanarek_orm_wykrywa_swiezy_wyciek():
    """Meta-test: kanarek naprawdę łapie wzorce, a nie zawsze przechodzi.

    Bez tego „zielony kanarek" nie niósłby informacji — ten sam powód, dla
    którego ``test_kanarek_katalogowy`` ma test semantyczny obok
    substringowych.
    """
    assert _podejrzane_instrukcje(
        "Wydawnictwo_Ciagle.objects.filter(autorzy_set__autor=x)\n", "p.py"
    )
    assert _podejrzane_instrukcje(
        'Autor.objects.annotate(n=Count("wydawnictwo_ciagle_autor"))\n', "p.py"
    )
    assert _podejrzane_instrukcje(
        "Wydawnictwo_Ciagle_Streszczenie.objects.filter(\n"
        "    rekord__autorzy_set__jednostka__uczelnia=u\n"
        ")\n",
        "p.py",
    )
    assert _podejrzane_instrukcje(
        'for relation in ("wydawnictwo_ciagle_autor", "patent_autor"):\n'
        "    Autor.objects.annotate(n=Count(relation))\n",
        "p.py",
    )

    # ...a na poprawnych i bezpiecznych formach MILCZY:
    assert not _podejrzane_instrukcje(
        "Wydawnictwo_Ciagle.objects.filter(\n"
        "    autorzy_set__autor=x,\n"
        "    autorzy_set__deleted_at__isnull=True,\n"
        ")\n",
        "p.py",
    )
    assert not _podejrzane_instrukcje(
        'Wydawnictwo_Ciagle.objects.prefetch_related("autorzy_set__autor")\n',
        "p.py",
    )
    assert not _podejrzane_instrukcje(
        'router.register(r"patent_autor", Patent_AutorViewSet)\n', "p.py"
    )
    assert not _podejrzane_instrukcje(
        '"""Docstring cytujący autorzy_set__upowaznienie_pbn."""\n', "p.py"
    )


@pytest.mark.parametrize("klucz", sorted(DOZWOLONE))
def test_wpisy_dozwolone_nadal_istnieja(klucz):
    """Każdy wpis w ``DOZWOLONE`` musi wciąż pasować do realnego kodu.

    Bez tego lista zamienia się w cmentarz nieaktualnych wyjątków, który po
    cichu przepuści przyszły wyciek w tym samym pliku.
    """
    plik, fragment = klucz
    sciezka = KORZEN / plik
    assert sciezka.exists(), f"DOZWOLONE wskazuje na nieistniejący plik {plik}"
    assert fragment in sciezka.read_text(encoding="utf-8"), (
        f"DOZWOLONE[{klucz}] nie pasuje już do kodu — usuń wpis albo "
        f"zaktualizuj fragment."
    )
