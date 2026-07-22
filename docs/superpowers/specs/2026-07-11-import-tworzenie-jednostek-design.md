# Tworzenie brakujących jednostek podczas importu pracowników

Data: 2026-07-11
Status: zaakceptowany (design po self-review Fable), do implementacji
Gałąź: `feat/import-pracownikow-tworzenie-jednostek`

> Rewizja po adwersaryjnym self-review (subagent Fable). Naprawione blockery:
> 3 ścieżki `IntegrityError`, puste bramkowanie (gating), cykl życia decyzji vs
> `on_restart`. Szczegóły w §12.

## 1. Problem i kontekst

Faza analizy (`import_pracownikow.pipeline.analyze`) matchuje jednostkę wiersza
przez `matchuj_jednostke`. Gdy jednostki nie ma, `_matchuj_jednostke_lub_wyjatek`
**rzuca** `XLSMatchError` → propaguje przez `_przetworz_wiersz` → `analizuj` →
`LiveOperation.run` → runner liveops. Efekt: cała operacja pada na pierwszym
niedopasowanym wierszu (`stage -1`, ~1 s), traceback tylko w kolumnie `traceback`.

Zaobserwowane na zrzucie IHIT (`63d66aae-…`, `pracownicy IHIT 31_12_2025
afiliacje.csv`): baza po `--from-dump` ma tylko 3 jednostki (`Wydział Domyślny`
[root, `jest_lustrem=True`, `legacy_wydzial_id=1`], `Jednostka Domyślna`, `Obca
jednostka`), więc prawie każdy wiersz to brak dopasowania; pierwszy (`Zakład
Transfuzjologii`) wywala import.

Cel: import **nie wywala się** na braku jednostki — klasyfikuje, odracza i
pozwala użytkownikowi utworzyć brakujące jednostki (albo zmapować/pominąć)
podczas importu.

## 2. Zasada architektoniczna (bez zmian)

Dwie fazy: **analiza = dry-run** (nic do domeny, odkłada braki), **integracja =
commit** (materializuje create'y). Reużywamy słownictwo statusów autora
(`import_pracownikow.pewnosc`): `twardy`, `zgadywanie` (auto-wybór, widoczny),
`wielu`, `brak`.

## 3. Klasyfikacja jednostki (funkcja nie-rzucająca)

Nowa funkcja `sklasyfikuj_jednostke(nazwa, wydzial) -> (jednostka|None, status,
auto_similarity|None)` w `import_common/core/jednostka.py` (obok `matchuj_jednostke`):

1. Znormalizuj `nazwa` przez `normalize_nazwa_jednostki` (whitespace-only).
   Jeśli po normalizacji **pusta** → zwróć `(None, "brak", None)` z markerem
   „brak nazwy" (patrz §5.4) — **nie** rzucaj.
2. Spróbuj `matchuj_jednostke(nazwa, wydzial)` w `try`; łap **oba**
   `Jednostka.DoesNotExist` **i** `Jednostka.MultipleObjectsReturned`
   (jednostka.py:68/77 potrafi rzucić Multiple na remisie prefiksowym/skrócie).
   Sukces → `(jednostka, "twardy", None)`.
3. Brak/remis → policz najlepsze **podobieństwo trigramowe** (`TrigramSimilarity`
   nad `nazwa` i `skrot`; `pg_trgm` jest w baseline). Pula kandydatów
   **ograniczona** do jednostek przyjmujących afiliacje i widocznych:
   `skupia_pracownikow=True`, `widoczna=True`, `jest_lustrem=False`, oraz
   (`rodzaj IS NULL` lub `rodzaj.autor_moze_afiliowac=True`) — warunki
   `Jednostka.przyjmuje_afiliacje()` (jednostka.py:270). To wyklucza „Obca
   jednostka", węzły-lustra „Wydział", jednostki ukryte/historyczne.
   - `best_sim >= PRÓG_ZGADYWANIA` (stała, domyślnie **0.7**) →
     `(best, "zgadywanie", best_sim)` — auto-wybór, **oflagowany** (§5).
   - w przeciwnym razie → `(None, "brak", None)`.

Uwaga: `TrigramSimilarity` liczy na surowych kolumnach DB — normalizujemy tylko
argument wejściowy (whitespace), nie kolumnę.

**Twardy crash znika** — braki/remisy/pusta nazwa nigdy nie rzucają.

## 4. Model danych

### 4.1. `ImportPracownikow` — nowe pole
- `tworz_brakujace_jednostki` — `BooleanField(default=True)`. Przełącznik §7.

### 4.2. `ImportPracownikowRow` — nowe pola
- `jednostka_status` — `CharField(max_length=20, choices=STATUS_CHOICES,
  null=True, blank=True)` — status dopasowania jednostki (odrębny od `confidence`
  autora). `twardy` na dopasowaniu dokładnym.
- `zrodlo_jednostki` — `ForeignKey("ImportPracownikowJednostka", null=True,
  blank=True, on_delete=models.SET_NULL)` — decyzja o źródłowej nazwie jednostki
  (wiersze o tej samej nazwie współdzielą jedną decyzję). **SET_NULL** — kasowanie
  decyzji nie może kasować wierszy podglądu. `row.jednostka` pozostaje `None` do
  rozstrzygnięcia w integracji (dla `twardy` ustawione wprost, bez decyzji).

### 4.3. Nowy model `ImportPracownikowJednostka` (decyzja per unikalna nazwa)
Deduplikacja po znormalizowanej nazwie (wzorzec `ImportPracownikowOdpiecie`):

- `parent` → `ImportPracownikow`, `on_delete=CASCADE`,
  `related_name="jednostki_do_decyzji"`
- `nazwa_zrodlowa` — `CharField(max_length=512)` (limit = `Jednostka.nazwa`),
  znormalizowana; wartość źródłowa > 512 znaków → wiersz pominięty (§5.4)
- `skrot_sugerowany` — `CharField(max_length=128)`, baza skrótu (§6.4)
- `tryb` — `CharField` `"zgadywanie"` | `"brak"` (ustawia analiza)
- `auto_jednostka` — `FK Jednostka, null, on_delete=SET_NULL, related_name="+"`
- `auto_similarity` — `FloatField(null=True)` — do pokazania userowi
- `wybrany_parent` — `FK Jednostka, null, on_delete=SET_NULL, related_name="+"` —
  miejsce w drzewie dla nowej jednostki. **Semantyka `None` zależy od
  `uczelnia.uzywaj_wydzialow`** (rozstrzyga integracja):
  `False` → root; `True` → domyślny węzeł-wydział (istniejący root
  `jest_lustrem=True`, a gdy brak — utworzony przez §6.1).
- `decyzja` — `CharField` `"akceptuj"` | `"mapuj"` | `"pomin"`, default `"akceptuj"`
- `wybrana_jednostka` — `FK Jednostka, null, on_delete=SET_NULL, related_name="+"`
  (cel przy `mapuj`)
- `utworzona` — `FK Jednostka, null, on_delete=SET_NULL, related_name="+"` —
  jednostka utworzona przez integrację (guard idempotencji)

`Meta.unique_together = (("parent", "nazwa_zrodlowa"),)`,
`ordering = ["nazwa_zrodlowa"]`.

**Uwaga o gating:** default `decyzja="akceptuj"` z bezpiecznym auto-umiejscowieniem
oznacza, że import może iść **bez** interakcji usera (kluczowe dla IHIT: setki
jednostek — nie wymuszamy ręcznej akceptacji każdej). Ekran §5 to **opcjonalna
korekta**, nie twarda bramka. Panel wyników pokazuje wyraźne podsumowanie + link
(§5.5). (Twardej bramki nie ma — istniejący flow autora też jej nie ma;
`ZatwierdzImportView.post` przechodzi bezwarunkowo.)

### 4.4. Migracje / baseline
Jedna migracja `import_pracownikow` (pole na `ImportPracownikow`, 2 pola na Row,
nowy model). Wszystkie nowe FK do `Jednostka` = `SET_NULL`. Baseline odświeżyć
**raz przy scaleniu** (`make baseline-update`), nie w tej gałęzi.

## 5. Ekran „Jednostki: weryfikacja" (`<uuid:pk>/jednostki/`)

Widok `WeryfikacjaJednostekView` (grupa uprawnień jak reszta importu). Dostępny
**po analizie**; **opcjonalny** (nie blokuje `zatwierdz`). Dwie sekcje:

```
DOPASOWANE AUTOMATYCZNIE (zweryfikuj)                       [tryb=zgadywanie]
 «Zakład Hematologii Eksperymentalnej»  →  auto: «Zakład Hematologii» (0.82)
    (•) Zaakceptuj    ( ) Zmień na… [picker]    ( ) Utwórz nową zamiast

DO UTWORZENIA                                                    [tryb=brak]
 «Zakład Transfuzjologii»            (12 osób)
    (•) Utwórz nową   parent: [Wydział Domyślny ▾]   ( ) Mapuj na… [picker]   ( ) Pomiń
```

### 5.1. Reguły miejsca w drzewie
- `uczelnia.uzywaj_wydzialow == False` → brak pickera parenta; nowe w **root**.
- `== True`, są węzły-wydziały → picker parenta (root `Jednostka`, post-#438 — nie
  legacy `Wydzial`), default = istniejący `Wydział Domyślny` (root `jest_lustrem`).
- `== True`, brak węzła-wydziału → baner + „Utwórz «Wydział Domyślny»" (§6.1).

### 5.2. Rozstrzyganie (htmx, wzorzec `PrzelaczOdpiecieView`)
Lekkie widoki POST ustawiające `decyzja`, `wybrany_parent`, `wybrana_jednostka` na
obiekcie decyzji.

### 5.3. Bezpieczeństwo/higiena nazw
Render przez `{{ }}` (auto-escape; żadnego `|safe`/`mark_safe` na danych z pliku).
Długie nazwy skracane do wyświetlenia z pełnym tekstem w `title=`.

### 5.4. Pusta / za długa nazwa jednostki
`JednostkaForm.nazwa_jednostki` jest dziś `required` → pusta komórka rzuca
`XLSParseError`. Zmieniamy: pusta/whitespace nazwa → wiersz **pominięty**
(`jednostka=None`, `jednostka_status="brak"`, bez decyzji, `zmiany_potrzebne=False`),
zliczony jako „brak nazwy jednostki" — bez crasha. Nazwa > 512 znaków → analogicznie
pominięty (log per-wiersz).

### 5.5. Panel wyników
Po analizie panel/`result_context` pokazuje: `N do utworzenia`, `M dopasowanych
automatycznie`, `K pominiętych (brak jednostki)` + link do ekranu §5.

## 6. Integracja — nowa PIERWSZA faza w `integruj`

Faza jednostek jest **literalnie pierwszym krokiem** `integruj`, **przed**
snapshotem `stare_jednostki` (integrate.py:379–383) i **przed** fazą nowych autorów
(integrate.py:389–395). Inaczej: (a) snapshot pominąłby świeżo podłączone wiersze
(przepięcia by nie działały), (b) `_przygotuj_nowego_autora` → `odtworz_autor_jednostka`
z `jednostka=None` → `get_or_create(jednostka_id=None)` → `IntegrityError`.

### 6.1. Uczelnia + Wydział Domyślny
`uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()`. Gdy `None` (0 lub >1
uczelni) → **degradacja bez crasha**: jednostek nie da się utworzyć, wiersze
`brak`/`zgadywanie`-do-utworzenia zostają niedopasowane i raportowane; log.
Gdy `uczelnia.uzywaj_wydzialow` i istnieje akceptowana decyzja `brak` z
`wybrany_parent IS NULL`, a nie ma węzła-wydziału — utwórz go **reużywając**
`znajdz_lub_utworz_wydzial_domyslny(uczelnia)` +
`znajdz_lub_utworz_wezel_wydzialu(...)` z `pbn_import.utils.institution_import`
(tworzą legacy `Wydzial` + mirror root `Jednostka` z `jest_lustrem`,
`legacy_wydzial_id`, `rodzaj`). Wynik = `parent_domyslny`.

### 6.2. Rozstrzygnięcie każdej decyzji `ImportPracownikowJednostka`
Guard idempotencji: jeśli `utworzona_id is not None` → użyj `utworzona`, pomiń
tworzenie (przeżywa restart / podwójny commit).
- `decyzja="akceptuj"` + `tryb="brak"`:
  - **finalny match po iexact** tuż przed create (`Jednostka.objects.filter(
    nazwa__iexact=nazwa_zrodlowa).first()`), żeby złapać wariant wielkości liter /
    drift bazy → jeśli jest, użyj go (jak `mapuj`);
  - efektywny parent (`resolve_parent`): jawny `wybrany_parent`; dla `None` — root
    gdy `uzywaj_wydzialow=False`, inaczej `parent_domyslny`;
  - `skrot = unikalny_skrot(skrot_sugerowany)` (§6.4);
  - `Jednostka.objects.create(nazwa=nazwa_zrodlowa[:512], skrot=skrot, uczelnia,
    parent=efektywny_parent)`; zapisz do `utworzona`.
- `decyzja="akceptuj"` + `tryb="zgadywanie"` → `utworzona = auto_jednostka`.
- `decyzja="mapuj"` → `utworzona = wybrana_jednostka` (użycie istniejącej).
- `decyzja="pomin"` → nie tworzymy; wiersze zostają niedopasowane.

### 6.3. Podłączenie wierszy
Dla każdego wiersza z `zrodlo_jednostki` i rozstrzygniętą jednostką: ustaw
`row.jednostka = rozstrzygnieta`, potem **przelicz AJ** identycznie jak analiza dla
dopasowanych wierszy (reużyj `odtworz_autor_jednostka(row, row.autor)` gdy
`row.autor` jest, inaczej `zmiany_potrzebne` wg reguł `_przetworz_wiersz`).
Wiersze decyzji `pomin` (lub bez rozstrzygnięcia) → `jednostka=None`,
`zmiany_potrzebne=False`.

### 6.4. Generowanie `skrot`
- Czysta funkcja `zaproponuj_skrot(nazwa) -> str` (bez DB): akronim z wielkich
  liter słów (`Zakład Transfuzjologii` → `ZT`); pusty/1-znak → przycięta nazwa
  (≤128). Używana w analizie do `skrot_sugerowany`.
- Unikalność rozstrzygana **w integracji** funkcją `unikalny_skrot(base,
  zajete_w_runie)`: sprawdza DB (`Jednostka.skrot`) **oraz** zbiór skrótów
  utworzonych wcześniej w tym samym runie (kolizja in-batch: dwa pliki → „ZT") →
  sufiks numeryczny (`ZT`, `ZT2`, …), przycięcie do 128.

### 6.5. Zmiany w analizie (`_przetworz_wiersz`) — kluczowe dla braku crasha
Gdy status jednostki ≠ `twardy` (czyli `zgadywanie`/`brak` → decyzja, `row.jednostka
= None` na tym etapie):
- **NIE** licz `autor_jednostka` ani nie zapisuj `diff["autor_jednostka"]`
  (inaczej integracja robi `get_or_create(jednostka_id=None)` → crash);
- ustaw `autor_jednostka=None`, `zmiany_potrzebne=False`, podłącz `zrodlo_jednostki`.
Dla `zgadywanie` `row.jednostka` MOŻE być ustawiona na `auto_jednostka` już w
analizie (jest realna), ale AJ i tak liczymy dopiero w integracji po potwierdzeniu
decyzji — dla spójności `zgadywanie` traktujemy jak odroczone (`row.jednostka=None`
w wierszu, realna jednostka w `decyzja.auto_jednostka`).

### 6.6. Guard nowych autorów
Filtr `_przygotuj_nowego_autora` (integrate.py:390) dostaje dodatkowo
`jednostka__isnull=False` — wiersz `brak` autora + `pomin` jednostki nie może
tworzyć AJ z `jednostka=None`.

## 7. Przełącznik „Twórz brakujące jednostki"

Pole `ImportPracownikow.tworz_brakujace_jednostki` (default **True**). Checkbox w
`MapowanieForm` (plain `forms.Form` — ręczne dodanie pola + odczyt w
`MapowanieView.form_valid` → `obj.tworz_brakujace_jednostki = ...` +
`update_fields`). OFF → analiza nie tworzy decyzji `brak`; wiersze niedopasowane są
pomijane/raportowane (bez AJ, bez crasha). `zgadywanie` (auto-match do istniejącej)
działa niezależnie od przełącznika (nie tworzy nowej jednostki).

## 8. Cykl życia decyzji vs restart / re-analiza

`on_restart` (models.py:85) kasuje wiersze i odpięcia przy cofnięciu stanu (np.
`MapowanieView` → re-map). Reguły dla decyzji:
- `on_restart` **NIE kasuje** `ImportPracownikowJednostka` (utrata wyborów usera).
- `analizuj` **reconciliuje** decyzje: dla każdej nazwy wymagającej decyzji
  `get_or_create(parent, nazwa_zrodlowa)`; przy każdym runie **odświeża** pola
  liczone (`tryb`, `auto_jednostka`, `auto_similarity`, `skrot_sugerowany`), a
  **zachowuje** pola wyboru usera (`decyzja`, `wybrany_parent`, `wybrana_jednostka`)
  jeśli już ustawione. Po przetworzeniu wszystkich wierszy: **kasuje** decyzje tego
  `parent`, których `nazwa_zrodlowa` nie wystąpiła w tym runie (stale/ghost — inaczej
  wisiałyby w podsumowaniu na zawsze).
- Dedup **case-insensitive**: klucz reconcile po `nazwa_zrodlowa.casefold()`
  (dwie warianty wielkości liter → jedna decyzja).
- Po udanej integracji + RestartAnaliza: utworzone jednostki exact-matchują
  (`twardy`) → ich nazwy nie generują decyzji → stale-cleanup je usuwa (jednostki
  zostają; `utworzona` FK = SET_NULL, więc kasowanie decyzji nic nie psuje).

## 9. Interakcje brzegowe (§9 odpięcia / §10 przepięcia)

- **Odpięcia:** jednostki powstają w integracji przed `_wykonaj_odpiecia`, więc
  `pary_z_pliku` jest wtedy poprawne; guard **G1** (integrate.py:195–197) pomija
  odpięcie, gdy para `(autor, jednostka)` trafiła do wierszy po `mapuj`/utworzeniu.
  Analizowy `_materializuj_odpiecia` widzi odroczone wiersze jako `jednostka=None`
  (nie w parach), ale te jednostki jeszcze nie istnieją → brak AJ → brak fałszywych
  odpięć. **Uwaga UX:** lista odpięć w podglądzie może pokazać mylące „spoza pliku"
  dla autorów, których wiersze są odroczone — akceptowalne w tej iteracji.
- **Przepięcia:** `PrzepnijPraceView`/`ZaznaczWszystkiePrzepieciaView` wymagają
  `jednostka` ustawionej (views.py:475), więc dla wierszy odroczonych user **nie
  może** włączyć przepięcia w podglądzie. **Znane ograniczenie tej iteracji** —
  przepięcie dla nowo utworzonych/zmapowanych jednostek to osobny follow-up.

## 10. Testy (pytest + model_bakery, bez unittest.TestCase)

Klasyfikator/skrót (czyste):
- `sklasyfikuj_jednostke`: dokładne→twardy; brak→brak; podobne≥0.7→zgadywanie
  (+similarity); remis (`MultipleObjectsReturned`) nie rzuca; pusta nazwa→brak;
  pula fuzzy wyklucza obcą/lustro/ukrytą.
- `zaproponuj_skrot`: akronim, fallback; `unikalny_skrot`: kolizja DB **i in-batch**
  (dwie nazwy → „ZT"/„ZT2").

Analiza:
- brak → decyzja `tryb="brak"`, wiersz odroczony (`jednostka=None`,
  `jednostka_status="brak"`, **brak** `diff["autor_jednostka"]`,
  `zmiany_potrzebne=False`), analiza **nie rzuca**;
- pusta nazwa jednostki → wiersz pominięty, brak crasha;
- reconcile: re-analiza zachowuje `decyzja`/`wybrany_parent`; kasuje decyzje stale;
  dedup case-insensitive.

Integracja:
- `akceptuj`+`brak` → tworzy `Jednostka` + podłącza wszystkie wiersze tej nazwy;
- `zgadywanie`→auto, `mapuj`→wybrana, `pomin`→wiersze niedopasowane;
- `uzywaj_wydzialow=True` bez węzła-wydziału → tworzy „Wydział Domyślny" (mirror
  node) i pod nim jednostki; `=False` → root;
- **ordering:** faza jednostek przed snapshotem i przed nowymi autorami — brak
  `jednostka_id=None` w AJ; `pomin`+`utworz_nowego=True` nie crashuje (guard §6.6);
- idempotencja: drugi commit nie duplikuje (guard `utworzona`);
- 0/>1 uczelnia → degradacja bez crasha;
- `iexact` re-match tuż przed create (wariant wielkości liter nie tworzy duplikatu).

Regresja bugu:
- fixture z niedopasowaną jednostką (plik typu IHIT) przechodzi analizę bez
  `XLSMatchError`.

Widok/escaping:
- ekran weryfikacji: nazwa z `<script>` renderowana bezpiecznie; toggle OFF →
  wiersze pominięte, brak decyzji `brak`.

## 11. Poza zakresem (osobne follow-upy)

1. Read-only admin dla `ImportPracownikow` + wierszy + traceback.
2. Ręczny picker profili mapowania (dziś tylko auto-match po nagłówkach).
3. Skracanie/higiena nagłówków w ekranie mapowania.
4. Przepięcie prac dla nowo utworzonych/zmapowanych jednostek (§9).

## 12. Dziennik rewizji (self-review Fable)

Naprawione względem pierwszej wersji:
- **Gating** był pusty (`decyzja` default `akceptuj` + brak precedensu bramki) →
  zamieniony na bezpieczne defaulty + opcjonalny ekran + podsumowanie (§4.3/§5.5).
- **3 ścieżki `IntegrityError`**: `diff["autor_jednostka"]` z `jednostka=None`
  (§6.5), kolejność fazy vs snapshot/nowi autorzy (§6), `pomin`+`utworz_nowego`
  (§6.6).
- **Cykl życia decyzji** vs `on_restart`/re-analiza: reconcile get_or_create +
  refresh + stale-cleanup, `on_restart` nie kasuje decyzji (§8).
- **`on_delete`**: `zrodlo_jednostki` + FK do `Jednostka` = SET_NULL (§4).
- **skrot in-batch collision**: unikalność w integracji, nie w czystej funkcji (§6.4).
- **uczelnia**: `get_single_uczelnia_or_none`, degradacja przy 0/>1 (§6.1).
- **Wydział Domyślny**: reużycie helperów pbn_import (mirror node #438) (§6.1).
- **Pula fuzzy**: ograniczona do `przyjmuje_afiliacje()` (§3).
- **Pusta/za długa nazwa**: pominięcie, nie crash (§5.4).
- **`wielu`/remis**: `MultipleObjectsReturned` łapane → trigram (§3).
- **Przepięcia** dla odroczonych: udokumentowane ograniczenie (§9).
