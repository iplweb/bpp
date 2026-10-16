"""Soft-delete PUBLIKACJI: filtr w widokach + gałąź kasująca + bramka WHEN.

Odpowiednik migracji ``0489`` (faza 01) dla drugiej ścieżki: tamta objęła
3 tabele ``*_autor``, ta obejmuje 5 tabel publikacji. Kolejność operacji jest
WYMUSZONA z dokładnie tego samego powodu:

  1) widoki (wprowadzają ``deleted_at`` do drzewa zapytania)  ->
  2) funkcje ``bpp_refresh_rekord_*`` (gałąź kasująca)        ->
  3) regeneracja bramki WHEN (czyta ``pg_depend`` PO kroku 1)

Odwrócenie 1<->3 daje bramkę bez ``deleted_at``, czyli cichy staleness:
soft-deletowana publikacja zostaje w ``bpp_rekord_mat``.

Żadna z trzech zmian nie wystarcza sama — uzasadnienie jak w ``0489``:
funkcja refresh po ``0432`` robi wyłącznie ``INSERT ... ON CONFLICT DO
UPDATE``, więc wypadnięcie wiersza ze źródła jest dla niej no-opem; a bez
``deleted_at`` w bramce ``WHEN`` UPDATE soft-delete w ogóle nie dochodzi do
funkcji triggera.

DLACZEGO NIE DA SIĘ UŻYĆ ``_filtruj_widok`` Z ``0489``
------------------------------------------------------
Tamta funkcja dopisuje ``WHERE`` na KOŃCU definicji i asertuje, że definicja
kończy się gołym ``FROM <tabela>``. Dla widoków publikacji to założenie jest
FAŁSZYWE — występują tu trzy różne kształty (zweryfikowane introspekcją
żywego katalogu, nie lekturą plików ``.sql``):

- **A**: ``bpp_wydawnictwo_ciagle_view``, ``bpp_wydawnictwo_zwarte_view``,
  ``bpp_patent_view`` — kończą się ``LEFT JOIN <tabela>_autor ... GROUP BY
  <tabela>.id`` i NIE mają ``WHERE`` najwyższego poziomu. Dopisanie ``WHERE``
  na końcu byłoby błędem składni (``WHERE`` po ``GROUP BY``), więc predykat
  wstawiamy PRZED ``GROUP BY``.
- **B**: ``bpp_praca_doktorska_view``, ``bpp_praca_habilitacyjna_view`` —
  kończą się gołym ``FROM <tabela>``; tu wzorzec z ``0489`` działa wprost.
- **C**: ``bpp_praca_doktorska_autorzy``,
  ``bpp_praca_habilitacyjna_autorzy`` — mają WŁASNY ``WHERE`` najwyższego
  poziomu (join po przecinku z ``bpp_autor``), więc predykat wstawiamy do
  niego, zaraz za słowem ``WHERE``.

⚠️ Rozpoznawanie kształtu NIE może iść po samym wystąpieniu słowa ``WHERE``:
widoki rodziny A zawierają ``count(...) FILTER (WHERE ... deleted_at IS
NULL)`` (migracja ``0494``), a wszystkie zawierają ``WHERE`` w skalarnych
podzapytaniach o ``django_content_type``. Dyskryminatorem jest ``WHERE``/
``GROUP BY`` na WCIĘCIU DWÓCH SPACJI, czyli na poziomie klauzuli głównej
w formacie ``pg_get_viewdef(..., pretty=true)``.

⚠️ AGREGATY: w rodzinie A filtrujemy tabelę PUBLIKACJI, która jest lewą
(napędzającą) stroną ``LEFT JOIN``-a — to jest bezpieczne. Pułapka opisana w
handoffie (§3.2) dotyczy filtrowania strony PRAWEJ (``*_autor``): warunek na
niej zdegenerowałby ``LEFT JOIN`` do ``INNER JOIN`` i publikacja, której
wszystkich autorów skasowano, wypadłaby z widoku. Dlatego ``liczba_autorow``
jest liczona przez ``count(...) FILTER (...)`` (``0494``) i tej konstrukcji
tutaj NIE ruszamy.

⚠️ KLUCZ w rodzinie C: ``object_id_raw`` to id PUBLIKACJI (autor leży na jej
wierszu), więc filtr po własnej kolumnie ``deleted_at`` tabeli publikacji
jest poprawny. To INNA sytuacja niż w widokach ``*_autorzy`` trzech typów
z through-modelem (faza 01), gdzie filtrowano po kolumnie wiersza through.
Nie kopiować klucza między fazami bez sprawdzenia, co dana kolumna znaczy.

Definicje są GENEROWANE z introspekcji (jak w ``0432``/``0433``/``0489``),
a nie przepisane do ``.sql`` — kopia rozjechałaby się przy najbliższej
zmianie kolumn.
"""

import importlib

from django.db import connection, migrations

_p0432 = importlib.import_module("bpp.migrations.0432_cache_trigger_plpgsql")
_p0433 = importlib.import_module("bpp.migrations.0433_cache_trigger_when_gate")

REKORD_SITES = _p0432.REKORD_SITES  # [(tabela, model, autor_na_wierszu), ...]

# Klauzule główne w formacie pg_get_viewdef(pretty=true) stoją na wcięciu
# dwóch spacji. To odróżnia je od WHERE-ów w podzapytaniach skalarnych
# (wcięcie 10) i od FILTER (WHERE ...) w liście SELECT.
MARKER_GROUP_BY = "\n  GROUP BY "
MARKER_WHERE = "\n  WHERE "


def _widoki(tabela, autor_na_wierszu):
    """Widoki danej publikacji objęte filtrem: rekordowy + ewentualny
    autorski (tylko gdy autor leży na wierszu publikacji)."""
    yield tabela + "_view"
    if autor_na_wierszu:
        yield tabela + "_autorzy"


def _viewdef(cur, widok):
    cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", [widok])
    return cur.fetchone()[0].rstrip().rstrip(";")


def _z_filtrem(orig, tabela, widok):
    """Definicja widoku wzbogacona o ``<tabela>.deleted_at IS NULL``.

    Kształt rozpoznajemy JAWNIE i każdy nieoczekiwany wariant kończy się
    ``RuntimeError`` — cicha akceptacja dałaby widok bez filtra, czyli
    dokładnie ten rodzaj przecieku, który ta migracja ma zamknąć.
    """
    predykat = f"{tabela}.deleted_at IS NULL"
    n_group_by = orig.count(MARKER_GROUP_BY)
    n_where = orig.count(MARKER_WHERE)

    if n_group_by == 1 and n_where == 0:  # rodzina A
        glowa, ogon = orig.split(MARKER_GROUP_BY)
        return f"{glowa}\n  WHERE {predykat}{MARKER_GROUP_BY}{ogon}"

    if n_group_by == 0 and n_where == 1:  # rodzina C
        glowa, ogon = orig.split(MARKER_WHERE)
        # Wstawiamy ZARAZ ZA "WHERE", a nie na końcu definicji — dzięki temu
        # jesteśmy odporni na to, co po WHERE jeszcze następuje.
        return f"{glowa}{MARKER_WHERE}{predykat} AND {ogon}"

    if n_group_by == 0 and n_where == 0:  # rodzina B
        if not orig.endswith(f"FROM {tabela}"):
            raise RuntimeError(
                f"{widok}: brak GROUP BY i WHERE, ale definicja nie konczy "
                f"sie na 'FROM {tabela}' -- dopisanie WHERE bylo by "
                f"niepoprawne. Definicja: ...{orig[-160:]!r}"
            )
        return f"{orig}\n  WHERE {predykat}"

    raise RuntimeError(
        f"{widok}: nierozpoznany ksztalt definicji (GROUP BY x{n_group_by}, "
        f"WHERE x{n_where}) -- nie zgaduje, gdzie wstawic filtr"
    )


def _bez_filtra(orig, tabela, widok):
    """Odwrotność ``_z_filtrem`` — usuwa DOKŁADNIE ten tekst, który tamta
    wstawiła. Symetria jest tu ważniejsza od elegancji: odtwarzanie
    oryginału z plików ``.sql`` (jak w ``0489.backward``) nie zadziała, bo
    widoki publikacji były redefiniowane w kilku migracjach (m.in. ``0494``
    dokładająca ``count(...) FILTER``) i nie ma jednego pliku źródłowego.

    ⚠️ Szukamy DWÓCH form predykatu, bo katalog nie przechowuje tekstu, który
    wstawiliśmy, tylko jego postać ZNORMALIZOWANĄ. Gdy w zasięgu zapytania
    jest jedna tabela (rodzina B), Postgres usuwa zbędną kwalifikację i
    ``bpp_praca_doktorska.deleted_at IS NULL`` wraca jako gołe
    ``deleted_at IS NULL``.

    ⚠️ KOLEJNOŚĆ KANDYDATÓW JEST NOŚNA, nie kosmetyczna. Wariant z ``AND``
    (rodzina C) MUSI być sprawdzany pierwszy: w definicji
    ``WHERE <predykat> AND bpp_autor.id = ...`` wzorzec
    ``\\n  WHERE <predykat>`` pasuje jako PREFIKS, a usunięcie samego prefiksu
    zostawiłoby ``WHERE`` zaczynające się od ``AND`` — składniowy gruz.
    """
    kandydaci = []
    for predykat in (f"{tabela}.deleted_at IS NULL", "deleted_at IS NULL"):
        kandydaci.append(f"{predykat} AND ")  # rodzina C — NAJPIERW
    for predykat in (f"{tabela}.deleted_at IS NULL", "deleted_at IS NULL"):
        kandydaci.append(f"\n  WHERE {predykat}")  # rodziny A i B

    for wstawka in kandydaci:
        if orig.count(wstawka) == 1:
            return orig.replace(wstawka, "", 1)
    raise RuntimeError(
        f"{widok}: nie znalazlem (dokladnie jednej) wstawki z filtrem "
        f"soft-delete -- definicja zmieniona poza ta migracja?"
    )


def _funkcja_z_galezia_kasujaca(cur, table, model, autor_na_wierszu):
    """``bpp_refresh_rekord_<model>()`` z ``0432`` + gałąź kasująca.

    Ciało generowane identycznie jak ``_p0432._create_rekord_function``
    (ten sam upsert z pozycyjnym mapowaniem kolumn), z jedną różnicą: gdy
    wiersz jest soft-deletowany, kasujemy go z tabel ``_mat`` i wychodzimy.

    ``pg_advisory_xact_lock`` stoi PRZED rozgałęzieniem — kasowanie musi brać
    ten sam lock co upsert (uzasadnienie w ``0489``).

    ⚠️ Doktorat i habilitacja (``autor_na_wierszu=True``) dotykają OBU tabel
    ``_mat``, bo autor leży na wierszu publikacji. Nazwy kluczy są RÓŻNE:
    w ``bpp_rekord_mat`` kolumna nazywa się ``id``, w ``bpp_autorzy_mat`` —
    ``rekord_id`` (patrz ``_create_rekord_function`` i
    ``_create_delete_rekord_function`` w ``0432``).

    Restore (``deleted_at`` -> NULL) leci normalną ścieżką upsertu — wiersz
    wraca do widoku źródłowego, więc nic dodatkowego nie trzeba.
    """
    body_autorzy = ""
    kasuj_autorzy = ""
    if autor_na_wierszu:
        upsert_autorzy = _p0432._upsert_sql(
            cur, "bpp_autorzy_mat", table + "_autorzy", "object_id_raw = NEW.id"
        )
        body_autorzy = (
            "\n      DELETE FROM bpp_autorzy_mat "
            "WHERE rekord_id = ARRAY[ct, NEW.id]::integer[];\n"
            f"      {upsert_autorzy};"
        )
        kasuj_autorzy = (
            "\n          DELETE FROM bpp_autorzy_mat "
            "WHERE rekord_id = ARRAY[ct, NEW.id]::integer[];"
        )
    upsert_rekord = _p0432._upsert_sql(
        cur, "bpp_rekord_mat", table + "_view", "object_id_raw = NEW.id"
    )
    return f"""
CREATE OR REPLACE FUNCTION bpp_refresh_rekord_{model}() RETURNS trigger
LANGUAGE plpgsql AS $bpp_body$
DECLARE ct integer;
BEGIN
      {_p0432._ct_lookup(model)}
      PERFORM pg_advisory_xact_lock(ct, NEW.id);
      IF NEW.deleted_at IS NOT NULL THEN
          DELETE FROM bpp_rekord_mat WHERE id = ARRAY[ct, NEW.id]::integer[];\
{kasuj_autorzy}
          RETURN NULL;
      END IF;
      {upsert_rekord};{body_autorzy}
      RETURN NULL;
END $bpp_body$;
"""


def _regeneruj_bramke():
    """Ta sama logika co ``0433.forward``, ale tylko dla tabel PUBLIKACJI.

    Bramka jest wyliczana z ``pg_depend``, więc po zmianie definicji widoku
    (krok 1) sama wciągnie ``deleted_at``; po cofnięciu widoku (backward)
    sama ją zgubi. Tabele ``*_autor`` obsłużyła faza 01 — tu ich nie ruszamy.
    """
    with connection.cursor() as cur:
        for tabela, refresh_fn, widoki in _p0433.GATED:
            if tabela.endswith("_autor"):
                continue
            kolumny = _p0433._gate_columns(cur, tabela, widoki)
            if not kolumny:
                # Bezpiecznik z 0433: bez kolumn powstałby niebramkowany
                # UPDATE. Jeśli tu jesteśmy, krok 1 nie zadziałał.
                raise RuntimeError(
                    f"bramka dla {tabela}: pg_depend nie zwrocil zadnej "
                    f"kolumny (widoki={widoki}) -- nie tworze "
                    f"niezbramkowanego UPDATE"
                )
            when = _p0433._when_clause(kolumny)
            cur.execute(f"DROP TRIGGER IF EXISTS {tabela}_cache_upd ON {tabela};")
            cur.execute(
                f"CREATE TRIGGER {tabela}_cache_upd AFTER UPDATE ON {tabela} "
                f"FOR EACH ROW WHEN ({when}) "
                f"EXECUTE PROCEDURE {refresh_fn}();"
            )


def _przebuduj_widoki(cur, transformacja):
    for tabela, _model, autor_na_wierszu in REKORD_SITES:
        for widok in _widoki(tabela, autor_na_wierszu):
            orig = _viewdef(cur, widok)
            nowa = transformacja(orig, tabela, widok)
            cur.execute(f"CREATE OR REPLACE VIEW {widok} AS {nowa}")


def forward(apps, schema_editor):
    with connection.cursor() as cur:
        _przebuduj_widoki(cur, _z_filtrem)  # 1) widoki
        for tabela, model, autor_na_wierszu in REKORD_SITES:  # 2) funkcje
            cur.execute(
                _funkcja_z_galezia_kasujaca(cur, tabela, model, autor_na_wierszu)
            )
    _regeneruj_bramke()  # 3) bramka


def backward(apps, schema_editor):
    with connection.cursor() as cur:
        _przebuduj_widoki(cur, _bez_filtra)  # 1) widoki bez filtra
        for tabela, model, autor_na_wierszu in REKORD_SITES:  # 2) funkcje
            cur.execute(
                _p0432._create_rekord_function(cur, tabela, model, autor_na_wierszu)
            )
    _regeneruj_bramke()  # 3) bramka (deleted_at zniknie z pg_depend samo)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0496_publikacje_soft_delete_fields"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
