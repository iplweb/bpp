# Design — per-uczelnia liczenie slotów/punktacji (warstwa write-side)

Data: 2026-06-02
Gałąź: `feature/multi-hosted-config`
Kontekst: następny wątek po cleanupie `get_default` (patrz
`docs/superpowers/HANDOFF-multi-hosted.md`, sekcja A).

## Cel i zakres

W instalacji wielouczelnianej jeden rekord może mieć autorów z wielu uczelni
(autor → afiliacja na jednostkę → jednostka ma uczelnię). Punktacja i sloty
muszą być liczone i **zapisywane osobno per uczelnia**, za każdym razem dla
**subsetu autorów z danej uczelni**.

**W zakresie tego spec (write-side foundation):**
- zmiana schematu cache (`Cache_Punktacja_Dyscypliny` zyskuje klucz uczelni),
- parametryzacja kalkulatora slotów uczelnią (filtr zbioru autorów),
- orkiestracja cachera: pętla po uczelniach rekordu,
- naprawa bazowego widoku SQL (join musi uwzględniać uczelnię),
- migracja + backfill przez przeliczenie (denorm rebuild).

**Poza zakresem (osobny, następny spec — read-side):**
- filtrowanie odczytów po uczelni oglądającego (`get_for_request`): raporty,
  `ewaluacja_optymalizacja`, `ewaluacja_metryki`, `ewaluacja2021`, oświadczenia
  (pełna inwentaryzacja niżej, sekcja „Następny krok: read-side"). „Liczba N",
  rankingi i API konsumują cache pośrednio (przez `Rekord`/serializery) — do
  zweryfikowania w read-side spec, nie inwentaryzowane tu jako bezpośredni
  importerzy,
- pipeline tabel tymczasowych `Cache_Punktacja_Autora_Sum` /
  `_Sum_Group` (raport_slotow),
- integrator per-uczelnia (handoff §B), drobne (handoff §C).

## Reguła wiodąca (decyzja domenowa usera)

**True per-university partition.** Dla pracy współautorskiej między uczelniami
slot każdego autora liczony jest z **dzielnikiem zawężonym do autorów danej
uczelni** — zarówno `k` (liczba autorów z dyscypliny), jak i `m` (wszyscy
autorzy rekordu) liczone są na subsetcie autorów z tej uczelni. W rezultacie
`pkdaut`/`slot` różnią się per uczelnia, a `Cache_Punktacja_Dyscypliny` to
agregat per (rekord, uczelnia, dyscyplina).

> Zastrzeżenie (zanotowane, decyzja usera): to świadome odejście od reguły
> „matematyka slotów zależy od roku, nie uczelni" z wcześniejszego handoffu.
> Per-instytucjonalne przeliczanie dzielnika zmienia liczby względem stanu
> obecnego dla prac współautorskich między uczelniami. User potwierdził to
> dwukrotnie, świadomie, jako regułę docelową. Caveat regulacyjny (udział
> jednostkowy wg MEiN bywa liczony z pełnej współautorskości) odnotowany na
> wypadek audytu liczb.

## Invariant zgodności

Przy **dokładnie jednej** uczelni (stan każdej żywej instalacji dziś) nowy kod
musi dawać liczby **identyczne** jak obecnie. Zachowanie wielouczelniane to
nowa zdolność, uśpiona dopóki nie istnieje druga `Uczelnia`. Mechanizm:
`uczelnia=None` w kalkulatorze ⇒ brak filtra autorów ⇒ ścieżka jak dziś.

## Stan obecny (zmapowany)

Pliki:
- `src/bpp/models/sloty/core.py` — `ISlot(original, uczelnia=None)`
  (dopasowanie kalkulatora), `IPunktacjaCacher` (materializacja cache).
- `src/bpp/models/sloty/common.py` — `SlotMixin`: `wszyscy()`,
  `autorzy_z_dyscypliny()`, `dyscypliny`, `liczba_k`, `k_przez_m`,
  `pkd_dla_autora` — wszystkie czytają autorów przez `original.autorzy_set`.
- `src/bpp/models/abstract/disciplines.py` —
  `ModelZPrzeliczaniemDyscyplin.przelicz_punkty_dyscyplin(uczelnia=None)`
  (wejście denorm; dziś `get_default()` fallback — TODO do usunięcia).
- `src/bpp/models/cache/punktacja.py` — modele cache.
- `src/bpp/migrations/0204_cache_punktacja_autora_query_view.sql` — definicja
  widoku `bpp_cache_punktacja_autora_view`.

Wyzwalanie przeliczenia: pole `@denormalized cached_punkty_dyscyplin` na
`Wydawnictwo_Ciagle` / `Wydawnictwo_Zwarte` / `Patent` woła
`self.przelicz_punkty_dyscyplin()` przy zmianie pól autorów (django-denorm).
Backfill ≈ pełny denorm rebuild (`denorms.flush()` / rebuildall).

Dzielnik (mechanika, `common.py`):
- `liczba_k(d)` = `len(autorzy_z_dyscypliny(d))` — autorzy afiliujący/przypięci
  z dyscypliny,
- `wszyscy()` = `autorzy_set.count()` — wszyscy autorzy rekordu (`m`),
- `pkd_dla_autora` = `pkd / liczba_k`, udziały oparte też o `k/m`.

## Zmiany schematu

- `Cache_Punktacja_Dyscypliny`: **dodać `uczelnia` FK**
  (`ForeignKey(Uczelnia, on_delete=CASCADE, null=True)`) — klucz partycji
  (tabela nie ma `jednostka`, więc uczelni nie da się wyprowadzić). `serialize()`
  uwzględnia `uczelnia_id`.
- `Cache_Punktacja_Autora`: **bez nowej kolumny** — uczelnia wynika z
  `jednostka.uczelnia`. Zmieniają się tylko liczone `slot`/`pkdaut`. Wiersz
  pozostaje keyowany `(rekord, autor, jednostka, dyscyplina)`; jeden wiersz
  autorstwa mapuje na dokładnie jedną jednostkę → jedną uczelnię.
- Indeks: `Cache_Punktacja_Dyscypliny(rekord_id, uczelnia, dyscyplina)` pod
  naprawiony join widoku i przyszłe odczyty per uczelnia.

Wpływ na `serialize()` / denorm: `Cache_Punktacja_Dyscypliny.serialize()` zyskuje
`uczelnia_id`, a `przelicz_punkty_dyscyplin()` zwraca payload wielouczelniany.
To zmienia łańcuch zapisywany w polu `@denormalized cached_punkty_dyscyplin`
(`TextField`) oraz wszelkie testy asertujące dokładny kształt `serialize()` —
trzeba je zaktualizować. Brak zmiany kontraktu odczytu (dalej lista list).

Uzasadnienie asymetrii (normalize vs denormalize): Autora ma `jednostka`, więc
uczelnia jest w pełni wyprowadzalna — brak kolumny = zero ryzyka
niespójności; koszt to jeden dodatkowy join (przez `bpp_jednostka`) w widoku
i zapytaniach grupujących per uczelnia. Decyzja usera: trzymać wyprowadzaną.

## Kalkulator slotów (Approach A — parametryzacja + filtr querysetów)

- `SlotMixin.__init__(self, original, uczelnia=None)`. Gdy `uczelnia` ustawione,
  trzy szwy czytające autorów filtrują po `jednostka__uczelnia`:
  - `wszyscy()` → `autorzy_set.filter(jednostka__uczelnia=U).count()` (`m`),
  - `autorzy_z_dyscypliny(d)` → dokłada `jednostka__uczelnia=U` (`k` + lista),
  - `dyscypliny` (cached_property) → tylko dyscypliny mające autora z `U`.
- `ISlot(original, uczelnia)` przekazuje `uczelnia` do konstruowanego
  `SlotKalkulator_*`. Istniejąca bramka `ukryte_statusy("sloty")` zostaje —
  teraz naturalnie per uczelnia (rekord może `CannotAdapt` dla jednej uczelni
  i policzyć się dla innej).
- `uczelnia=None` ⇒ brak filtra autorów ⇒ zachowanie jak dziś (invariant).

Ryzyko: pominięty odczyt `autorzy_set` przeciekłby autorów spoza uczelni.
Mitygacja: test, w którym pominięcie zmieniłoby liczbę (asercja na dzielnik).

Subtelność `m` (mianownik) a autorzy bez jednostki: `wszyscy()` dziś liczy
WSZYSTKICH autorów rekordu. Filtr `jednostka__uczelnia=U` wyklucza autorów z
`jednostka IS NULL` z mianownika KAŻDEJ uczelni — to świadoma konsekwencja
„subsetu autorów z danej uczelni" (autor bez jednostki nie należy do żadnej
uczelni), ale jest to zmiana zachowania także względem naiwnego „tagowania".
Decyzja: akceptowalne i spójne z regułą wiodącą; do pokrycia testem
(rekord z autorem bez jednostki → nie wpływa na `m` żadnej uczelni).

## Orkiestracja cachera

- `IPunktacjaCacher(original, uczelnia)` — w pełni per uczelnia:
  - `removeEntries()` zawężone: `Cache_Punktacja_Dyscypliny.filter(uczelnia=U)`
    i `Cache_Punktacja_Autora.filter(jednostka__uczelnia=U)`,
  - `rebuildEntries()` odpala zawężony kalkulator; nowe wiersze
    `Cache_Punktacja_Dyscypliny` tagowane `uczelnia=U`; `Cache_Punktacja_Autora`
    bez zmiany kształtu.
- `przelicz_punkty_dyscyplin(self, uczelnia=None)` (wejście denorm) zyskuje
  pętlę i **traci `get_default()`** (zamyka parked TODO):
  - **skasuj wszystkie** wiersze cache dla rekordu raz (czyści uczelnie, które
    wypadły — np. po zmianie afiliacji ostatniego autora z danej uczelni),
  - wylicz uczelnie rekordu — `uczelnie_rekordu()` = distinct `uczelnia` wśród
    afiliujących/przypiętych autorów (spójnie z filtrami `rebuildEntries`),
  - dla każdej zbuduj `IPunktacjaCacher(self, U)` i przebuduj (tylko create —
    globalny delete już zrobiony),
  - `uczelnia=` jawne ⇒ policz tylko tę jedną (targetowane przebudowy, testy).
- `cached_punkty_dyscyplin` (`@denormalized`) woła bez argumentów ⇒ auto-rebuild
  produkuje wszystkie uczelnie.

Zwracana wartość `przelicz_punkty_dyscyplin()`: dziś zwraca `ipc.serialize()`
jednej uczelni (krotka dwóch list), a wynik trafia do pola `@denormalized
cached_punkty_dyscyplin` (TextField, używane jako artefakt denorm/change-
detection, nie parsowane merytorycznie). Po wprowadzeniu pętli musi zwracać
**zagregowany, deterministyczny** payload ze wszystkich uczelni (np. konkatenacja
`serialize()` per uczelnia w stabilnej kolejności po `uczelnia_id`). Źródłem
prawdy są wiersze w tabelach cache; format zwrotki jest elastyczny, byle
deterministyczny (inaczej denorm „migałby" jako wiecznie brudny). Weryfikacja:
brak kodu czytającego `cached_punkty_dyscyplin` jako dane — potwierdzić w planie.

`uczelnie_rekordu()`: helper na `ModelZPrzeliczaniemDyscyplin` (lub modelu),
zwraca distinct `Uczelnia` z `autorzy_set` afiliujących/przypiętych. Może być
**luźnym nadzbiorem** — uczelnia bez policzalnych autorów po prostu nie wytworzy
żadnych wierszy (zawężony kalkulator zwróci pusto / `CannotAdapt`), więc
enumeracja nie musi co do joty replikować filtrów `rebuildEntries`
(`skupia_pracownikow`, `rodzaj_autora_uwzgledniany_w_kalkulacjach_slotow`).
Ważne tylko, by nie **pomijała** uczelni, która ma policzalnych autorów.

## Naprawa widoku SQL (poprawność, nie do odłożenia)

Nowa migracja DROP+CREATE `bpp_cache_punktacja_autora_view`, by join trafiał
też w uczelnię — inaczej rekord 2-uczelniany daje kartezjański iloczyn wierszy
między uczelniami:

```sql
CREATE VIEW bpp_cache_punktacja_autora_view AS
SELECT a.id, a.rekord_id, a.pkdaut, a.slot, a.autor_id, a.dyscyplina_id,
       a.jednostka_id,
       d.autorzy_z_dyscypliny, d.zapisani_autorzy_z_dyscypliny
FROM bpp_cache_punktacja_autora a
JOIN bpp_jednostka j ON j.id = a.jednostka_id
JOIN bpp_cache_punktacja_dyscypliny d
  ON a.rekord_id = d.rekord_id
 AND a.dyscyplina_id = d.dyscyplina_id
 AND d.uczelnia_id = j.uczelnia_id;
```

Model `managed=False` widoku (`Cache_Punktacja_Autora_Query_View`) **nie**
dostaje na razie nowego pola — ekspozycja `uczelnia` w odczytach to read-side.

## Migracja i backfill

- Migracja 1: dodanie nullable `uczelnia` FK + indeks (szybka, bez ciężkiego
  kroku danych blokującego tabelę).
- Migracja 2 (osobny plik): DROP+CREATE widoku z joinem uwzględniającym
  uczelnię.
- Backfill = **pełny denorm rebuild po deployu** (udokumentowany krok
  deploymentu), który repopuluje per uczelnia nowym kodem. Single-install ⇒
  liczby identyczne. Opcjonalna późniejsza migracja zacieśnia `uczelnia` do
  non-null po przeliczeniu.
- Zgodnie z regułą projektu: **żadnych edycji istniejących migracji** — same
  nowe pliki.

## Testy

- Unit: jeden rekord współautorski, 2 uczelnie → asercja, że `k`, `m`, `slot`,
  `pkdaut` każdej uczelni używają tylko jej autorów (różne dzielniki), oraz że
  `Cache_Punktacja_Dyscypliny` daje 2 wiersze z poprawną `uczelnia` i
  zawężonym `autorzy_z_dyscypliny`.
- Invariant: fixture jednouczelniany → liczby identyczne z obecnymi
  oczekiwaniami (ochrona przed regresją).
- `ukryte_statusy` per uczelnia: rekord liczony dla U1, `CannotAdapt` dla U2 →
  wiersze tylko dla U1.
- Widok: rekord 2-uczelniany → brak kartezjańskiej duplikacji; wiersz autora
  joinuje tylko agregat dyscypliny swojej uczelni.
- `uczelnie_rekordu()`: nie **pomija** żadnej uczelni mającej policzalnego
  autora (nadzbiór jest OK — uczelnia bez autorów daje zero wierszy, bez błędu).
- Wypadnięcie uczelni: po przeniesieniu ostatniego autora U2 do U1 i przeliczeniu
  — brak osieroconych wierszy U2.
- Autor bez jednostki: nie wpływa na mianownik `m` żadnej uczelni.
- Determinizm zwrotki `przelicz_punkty_dyscyplin()`: dwa przeliczenia tego samego
  rekordu dają identyczny string (denorm nie jest wiecznie brudny).

## Komendy weryfikacji

- Testy: `uv run pytest src/bpp/tests/test_models/test_sloty/ -q -p no:cacheprovider`
- Lint: `uv run ruff check <pliki>` (NIE `--fix`).
- `uv run python src/manage.py makemigrations --check --dry-run`
  (z `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1` gdy brak bazy).

## Następny krok: read-side (osobny spec)

Po wdrożeniu write-side cache zawiera wiersze per (rekord, uczelnia). Dopóki
odczyty NIE filtrują po uczelni, w instalacji wielouczelnianej liczyłyby
podwójnie/międzyuczelniano. **Single-install jest bezpieczny** (jedna uczelnia
= jeden komplet wierszy), więc read-side może iść jako kolejny, oddzielny spec.

Kontrakt read-side: filtrować po uczelni **oglądającego** (`get_for_request`),
analogicznie jak `Cache_Punktacja_Autora` po `jednostka__uczelnia`, a
`Cache_Punktacja_Dyscypliny` po `uczelnia`. Widok `managed=False`
(`Cache_Punktacja_Autora_Query_View`) trzeba wtedy rozszerzyć o `uczelnia`
(z `bpp_jednostka.uczelnia_id`) i pipeline tabel tymczasowych musi nieść
uczelnię.

Zinwentaryzowani konsumenci (write-side ich NIE rusza; do read-side spec):

- **raport_slotow** — `core.py`, `tables.py`, `filters.py`, `views/autor.py`,
  `models/uczelnia.py` (główny konsument widoku + tabel `_Sum`/`_Sum_Group`).
- **ewaluacja_optymalizacja** — `core/data_loader.py`,
  `core/optimization_phases.py`, `tasks/unpinning/{analysis,capacity_analysis}.py`,
  `utils.py`, `views/{author_works,author_works_exports,exports,helpers,
  verification}.py`, `views/evaluation_browser/prefetch.py`.
- **ewaluacja_metryki** — `models.py`, `utils.py`, `views/{detail,list}.py`.
- **ewaluacja2021** — `core/{plecakowy,sumator_base,util}.py`, `models.py`,
  `reports.py`.
- **ewaluacja_optymalizuj_publikacje** — `views.py` (też wywołuje rebuild —
  upewnić się, że po zmianie przypięcia/dyscypliny przelicza per uczelnia).
- **oswiadczenia** — `views.py`.
- **ewaluacja_common** — `utils.py`.
- **bpp** — `core.py`, `management/commands/zbieraj_sloty.py` (raport per autor).

Tabele tymczasowe pipeline'u raportów (`Cache_Punktacja_Autora_Sum`,
`_Sum_Group`, `bpp_temporary_cpaq*`, `bpp_temporary_cpasg*`) — przebudowa pod
uczelnię należy do read-side.

## Pozostaje parked (poza ścieżką read-side)

- Integrator per-uczelnia (handoff §B).
- Drobne (handoff §C).
