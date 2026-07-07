# Sugerowanie punktacji ministerialnej w importerze publikacji

**Zgłoszenie:** Freshdesk #384 (pod-zgłoszenie #379, uwaga #5 z „importowanie bpp.docx")
**Data:** 2026-07-07
**Gałąź:** `fd-384-sugeruj-punktacje-importer` (baza: `dev`)
**Zastępuje:** zamknięty PR #404 (`fd-384-sugeruj-punktacje`)
**Rewizja:** po self-review (fable) — findingi F1–F10 wniesione.

## 1. Kontekst i problem

Operator wprowadzający dane w importerze publikacji nie ma skąd wiedzieć, ile
punktów MNiSW (20/40/80/140/200…) przypisać publikacji. Klient sformułował to
jako „przełącznik »sugeruj punktację« dla całej instytucji", i pierwotny PR #404
wziął to **dosłownie**: dodał `Uczelnia.sugeruj_punktacje` (BooleanField) i za tą
flagą zagatował cichy, automatyczny auto-fill punktacji ze źródła.

Realna potrzeba to **jawna podpowiedź w toku importu**: operator ma zobaczyć, na
jakiej podstawie i ile punktów system proponuje, i móc to zaakceptować, zmienić
albo pominąć. Cichy globalny auto-fill jest nieprzejrzysty i myli operatora.

Ustalenia weryfikacyjne:

- `Uczelnia.sugeruj_punktacje` **nie istnieje** na `dev` — było wyłącznie w
  zamkniętym PR #404. Nie ma czego chronić przy migracjach.
- Pre-istniejąca, podobnie brzmiąca flaga to `podpowiadaj_dyscypliny`
  (`bpp/models/uczelnia.py:435`) — dotyczy **dyscyplin, nie punktacji**, jest
  w aktywnym użyciu i **pozostaje nietknięta**.

## 2. Cel

Dodać w importerze publikacji **dedykowany krok „Punktacja"** (między
potwierdzeniem autorów a przeglądem końcowym), który pokazuje **czarno na
białym**:

1. **Wyd. ciągłe (artykuł):** źródło i jego punktacja `punkty_kbn` z
   `Punktacja_Zrodla` za dany rok — albo wyraźne **„brak danych"** dla
   źródła/roku.
2. **Wyd. zwarte (monografia/rozdział):** wydawca i jego **poziom** za rok.
   Rozróżnienie:
   - **brak wydawcy** → „brak danych, nie można zaproponować";
   - **wydawca bez poziomu za rok** (`get_tier == -1` lub `poziom == NULL`) →
     traktowany jako **„spoza wykazu" (poziom 0)** z jawną adnotacją; sugestia
     wg progów poziomu 0 (20/5/5).
3. **Sugestię punktów** `punkty_kbn` — albo informację, że **nie da się
   zaproponować, z wytłumaczeniem dlaczego**.

Sugestia jest **wyłącznie podpowiedzią** — pole „punkty MNiSW" jest zawsze
edytowalne; operator przyjmuje, zmienia albo zostawia.

## 3. Zakres

**W zakresie (v1):**

- Nowy krok wizarda „Punktacja" dla obu typów (`jest_wydawnictwem_zwartym`).
- Ścieżka ciągłych: `punkty_kbn` z `Punktacja_Zrodla` dla (źródło, rok).
- Ścieżka zwartych: derywacja z poziomu wydawcy + klasyfikacji rekordu
  (książka/rozdział wg `charakter_sloty`; w importerze zawsze autorstwo — patrz
  §7), na bazie progów z komendy `ustaw_zwrotnie_punkty_zwartych`.
- Jawne „brak danych" dla źródła/wydawcy/poziomu/roku.
- **Ostrzeżenie HST** (tanie, v1): gdy któryś dopasowany autor ma dyscyplinę
  z dziedziny HST, pokaż warning „autorzy z dyscyplin HST — właściwy próg może
  być wyższy (np. 300 dla monografii)". Bez zmiany samej sugestii (patrz §9-A).
- Zapis wybranej wartości i uwzględnienie jej przy tworzeniu rekordu.

**Poza zakresem (v1):**

- Nowa flaga per-instytucja (§8).
- **Augmentacja HST progów** w samej wartości sugestii (tylko warning, §9-A).
- Rozróżnianie autorstwo/redakcja w importerze — dziś importer i tak tworzy
  wszystkich jako autorów (§7, F1); pełna obsługa redakcji to osobny temat.
- Sugerowanie IF/kwartyli dla zwartych (nie dotyczy).

## 4. Architektura — nowy krok wizarda „Punktacja"

Importer to sekwencja widoków HTMX w `src/importer_publikacji/views/wizard.py`.
**Nie ma liniowego rejestru „następny krok"** — każdy POST-handler ustawia
`session.status` i **zwraca renderer następnego kroku**. Łańcuch:

`Verify.post → _render_source_step` · `Source.post → _render_authors_step` ·
`AuthorsConfirmView.post → _render_review_step` · `ReviewView`/`CreateView`.
Rekord powstaje dopiero w `create_publication_task` (Celery) **po** Review.

Wpięcie kroku **Punktacja** między potwierdzeniem autorów a Review wymaga:

| Zmiana | Plik / miejsce |
|--------|----------------|
| Nowa wartość `Status.PUNKTACJA` | `models.py:16` (TextChoices) + migracja |
| Wpisy w `get_continue_url` | `models.py:195` — `AUTHORS_MATCHED → "punktacja"`, `PUNKTACJA → "review"` |
| Przełączenie wyjścia z autorów | `wizard.py:546` `AuthorsConfirmView.post`: `_render_review_step` → `_render_punktacja_step` |
| Nowy widok `PunktacjaView` (get/post) | `wizard.py` (wzorzec `SourceView`) |
| Renderery `_render_punktacja_step/_full` + `_punktacja_context` | `views/steps.py` (wzorzec `_render_source_*`) |
| Stała `STEP_PUNKTACJA` | `views/helpers.py:25` |
| URL `name="punktacja"` | `urls.py` (między `authors-confirm` a `review`) |
| Re-export `PunktacjaView` + renderery | `views/__init__.py` |
| Szablon `partials/step_punktacja.html` | mirror `step_source.html`; „Wstecz" → `authors`, submit → `punktacja` |
| Nawigacja „Wstecz" w Review | `partials/step_review.html` → `punktacja` |

`PunktacjaView.post` zapisuje wybraną wartość do `session.matched_data["punkty_kbn"]`
(JSONField — bez migracji; ten sam wzorzec co `matched_data["wydawca_opis"]`
w `SourceView`), ustawia `status = PUNKTACJA`, zwraca `_render_review_step`.

Krok zna z sesji: typ (`session.jest_wydawnictwem_zwartym`), źródło/wydawcę
(`session.zrodlo` / `session.wydawca`), charakter (`session.charakter_formalny`),
rok (`session.normalized_data.get("year")`), dopasowanych autorów
(`session.authors`).

## 5. Kontrakt „Sugestia" (współdzielony value object)

Czysta, bezstanowa funkcja liczy sugestię i zwraca dataclass — bez zapisu, bez
efektów ubocznych. Obie ścieżki (ciągłe/zwarte) i oba wywołania (importer/komenda)
używają tego samego typu:

```python
class RodzajBraku(enum.Enum):
    BRAK_DANYCH_ZRODLA = "brak_danych_zrodla"        # ciągłe: brak Punktacja_Zrodla
    BRAK_ROKU = "brak_roku"                           # brak roku publikacji
    BRAK_WYDAWCY = "brak_wydawcy"                      # zwarte: brak wydawcy (anomalia danych)
    BRAK_AUTORSTWA = "brak_autorstwa"                  # zwarte: brak autorstwa/redakcji (anomalia danych)
    NIEOBSLUZONA_KOMBINACJA = "nieobsluzona_kombinacja"  # zwarte: nieobsłużony typ (luka logiki)

@dataclass
class SugestiaPunktacji:
    punkty: Decimal | None          # proponowane punkty_kbn; None gdy nie da się
    podstawa: str                   # np. "Punktacja źródła 2024", "Wydawca poziom II (monografia)"
    rodzaj_braku: RodzajBraku | None = None
    powod_braku: str | None = None  # człowiek-czytelny komunikat „dlaczego nie da się"
```

Dane do wyświetlenia (instancja `Punktacja_Zrodla`, poziom wydawcy) zbiera widok
bezpośrednio z sesji do kontekstu szablonu — **nie** przez snapshot w dataclassie
(F10). `rodzaj_braku` rozróżnia **anomalię danych** od **luki w logice** — to
pozwala komendzie zachować dotychczasową semantykę (§7, F5). Nie zjadamy błędów,
tylko je nazywamy (CLAUDE.md „no silent failures").

## 6. Ścieżka ciągłych (artykuł)

**Funkcja** `zaproponuj_punkty_ciagle(zrodlo, rok) -> SugestiaPunktacji`
(lokalizacja: nowy moduł `bpp/models/sugestia_punktacji.py` albo obok
`Punktacja_Zrodla` w `zrodlo.py`):

- `rok` puste → `punkty=None`, `rodzaj_braku=BRAK_ROKU`,
  `powod_braku="Brak roku publikacji — nie można dobrać punktacji źródła"`;
- jest `Punktacja_Zrodla` dla (źródło, rok) → `punkty = pz.punkty_kbn`,
  `podstawa=f"Punktacja źródła {rok}"`;
- brak → `punkty=None`, `rodzaj_braku=BRAK_DANYCH_ZRODLA`,
  `powod_braku=f"Brak punktacji źródła »{zrodlo}« za {rok}"`.

**Bez PBN-owego fallbacku „5 pkt"** (komenda `_ciaglych` ma go celowo; importer
pokazuje uczciwe „brak danych").

**Zapis przy tworzeniu (F3).** W `_create_publication` (`publikacja.py:269-274`)
dla ciągłych **zostaje** `uzupelnij_punktacje_z_zrodla(record, zrodlo, rok)` — on
kopiuje **cały** `POLA_PUNKTACJI` (`impact_factor, punkty_kbn, index_copernicus,
punktacja_wewnetrzna, punktacja_snip, kwartyl_w_scopus, kwartyl_w_wos`). **Po nim**
nadpisujemy `record.punkty_kbn` wartością operatora z `matched_data["punkty_kbn"]`
(o ile ustawiona) i zapisujemy. Dzięki temu IF/kwartyle/SNIP z źródła zostają,
a `punkty_kbn` ma finalne słowo operatora.

## 7. Ścieżka zwartych (monografia/rozdział) — ekstrakcja z komendy

Kanoniczna derywacja `punkty_kbn` dla zwartych istnieje inline w
`ustaw_zwrotnie_punkty_zwartych._przetworz`
(`src/pbn_api/management/commands/ustaw_zwrotnie_punkty_zwartych.py:84-134`):

- `poziom = wydawca.get_tier(rok)` (−1 gdy brak wiersza `Poziom_Wydawcy`),
- tabela progów `punkty_dct[poziom]` (indeks 0/1/2):
  - poziom 0 (spoza wykazu): `{KS: 20, RED: 5, ROZ: 5}`
  - poziom I: `{KS: 80, RED: 20, ROZ: 20}`
  - poziom II: `{KS: 200, RED: 100, ROZ: 50}`
- klasyfikacja: `warunek_ksiazka/rozdzial` (po `charakter_sloty`),
  `warunek_autorstwo/redakcja` (po rolach `autorzy_set`),
- mapowanie: książka+autorstwo→KS, książka+redakcja→RED, rozdział+autorstwo→ROZ.

**Funkcja** `zaproponuj_punkty_zwarte(*, poziom, ksiazka, rozdzial, autorstwo,
redakcja) -> SugestiaPunktacji` — na gołych prymitywach (F2), **nie** na rekordzie:

- normalizacja poziomu: `poziom in (-1, None) → 0` (F6 — `Poziom_Wydawcy.poziom`
  jest nullable; komenda ma tu utajony `punkty_dct[None]` TypeError, którego
  ekstrakcja się pozbywa);
- `not autorstwo and not redakcja` → `punkty=None`,
  `rodzaj_braku=BRAK_AUTORSTWA`;
- `ksiazka and rozdzial` (jednocześnie) → `punkty=None`,
  `rodzaj_braku=NIEOBSLUZONA_KOMBINACJA`;
- prawidłowa kombinacja → `punkty` wg tabeli, `podstawa=f"Wydawca poziom
  {opis_poziomu} ({typ})"`.

**Klasyfikacja w importerze (F1, F7):**

- `ksiazka = charakter_sloty == CHARAKTER_SLOTY_KSIAZKA`,
  `rozdzial = charakter_sloty == CHARAKTER_SLOTY_ROZDZIAL` — z
  `session.charakter_formalny` (parytet z komendą; **nie** `_is_chapter`, które
  patrzy na `charakter_ogolny`);
- `autorstwo = session.authors.exclude(matched_autor=None).exists()` (≥1
  dopasowany autor), `redakcja = False` — bo `_add_authors_to_record`
  (`publikacja.py:121`) tworzy **wszystkich** jako „aut."; `ImportedAuthor` nie ma
  pola roli. Sugestia jest więc spójna z tym, co realnie powstanie.
- **Caveat w UI:** „Sugestia zakłada autorstwo. Dla monografii/rozdziału
  redagowanego wpisz punktację ręcznie."
- **brak wydawcy** (`session.wydawca is None`) — widok nie woła funkcji, tylko
  pokazuje „brak danych, wpisz ręcznie" (`BRAK_WYDAWCY`).

**Refaktor komendy (F5).** `ustaw_zwrotnie_punkty_zwartych._przetworz`:

1. Zachowuje wczesny guard `elem.wydawca is None → RekordBezWydawcy`.
2. Liczy `ksiazka/rozdzial/autorstwo/redakcja` z rekordu (`warunek_*`).
3. Woła `zaproponuj_punkty_zwarte(...)`.
4. Tłumaczy wynik:
   - `sugestia.punkty is not None` → `elem.punkty_kbn = sugestia.punkty; save()`;
   - `rodzaj_braku == BRAK_AUTORSTWA` → `raise RekordBezPunktowalnegoAutorstwa`
     (skip+raport ZAWSZE, jak dziś);
   - `rodzaj_braku == NIEOBSLUZONA_KOMBINACJA` → `raise NotImplementedError`
     (**twardy crash bez `--ignore-errors`**, jak dziś).

Tabela progów staje się nazwaną stałą współdzieloną (jedno źródło prawdy).
Test regresyjny (§10) potwierdza identyczne wyniki i identyczne skip/raise.

**Zapis przy tworzeniu.** Dla zwartych `_create_publication` ustawia
`record.punkty_kbn = matched_data["punkty_kbn"]` (o ile ustawiona) — bez pól
źródłowych (zwarte nie mają `Punktacja_Zrodla`).

## 8. Zapis do sesji i brak flagi

- Wartość `punkty_kbn` wybrana w kroku żyje w `session.matched_data["punkty_kbn"]`
  (JSONField, string/decimal — bez migracji). Odczyt w `_create_publication`.
- **Migracja** potrzebna tylko dla nowej wartości `Status.PUNKTACJA` (AlterField
  choices — metadanowa, bez zmiany SQL). Nowa migracja (CLAUDE.md: nie edytować
  istniejących). Po niej `make baseline-update` (choices-only — baseline
  prawdopodobnie bez zmian, ale walidujemy).
- **Brak nowej flagi per-instytucja** (decyzja właściciela). Akcja „sugeruj
  punktację" zawsze dostępna. Ewentualny per-instytucja *default* (auto-proponuj)
  — poza zakresem v1.

## 9. Ryzyka i niuanse

**A. Progi HST — sugestia bazowa jest dla rekordów czysto-HST aktywnie błędna.**
Komenda `ustaw_zwrotnie_punkty_zwartych` używa progów **bazowych** (20/80/200),
a kalkulator slotów (`bpp/models/sloty/core.py:197-248`) dla rekordów HST
**wymaga** wartości augmentowanych (300/150/75, 120/40) w `punkty_kbn` — sugestia
200 dla monografii HST **zepsuje sloty**. v1: **nie** augmentujemy wartości
(dług), ale pokazujemy **ostrzeżenie**, gdy dopasowani autorzy mają dyscypliny
HST (sesja ma `matched_dyscyplina`). Predykat „dyscyplina jest HST" do ustalenia
w planie (dziedzina/`Dyscyplina_Naukowa`). Sugestia i tak edytowalna.

**B. Rekord nie istnieje w trakcie wizarda — ROZSTRZYGNIĘTE.** `warunek_*` czytają
`self.autorzy_set` (reverse-FK) i na instancji bez PK rzucają `ValueError`;
rekord powstaje dopiero w Celery po Review. Dlatego funkcja bierze **prymitywy**,
liczone z sesji (importer) albo z rekordu (komenda). Żadnego liczenia na
niezapisanym rekordzie.

**C. Braki danych do obsłużenia w kroku:** brak roku (`normalized_data["year"]`
puste aż do Create — `BRAK_ROKU`), brak źródła, brak wydawcy, brak poziomu
(→ spoza wykazu). Gdy nie ma z czego liczyć — krok pokazuje komunikat i pozwala
wpisać ręcznie / pominąć.

## 10. Testy (pytest, testcontainers)

- `zaproponuj_punkty_zwarte`: poziom 0/I/II × książka/rozdział × autorstwo/redakcja
  → oczekiwane progi; `poziom=None/-1 → 0`; brak autorstwa → `BRAK_AUTORSTWA`;
  książka+rozdział → `NIEOBSLUZONA_KOMBINACJA`.
- `zaproponuj_punkty_ciagle`: jest `Punktacja_Zrodla` → wartość; brak →
  `BRAK_DANYCH_ZRODLA` (bez fallbacku 5 pkt); `rok=None` → `BRAK_ROKU`.
- **Regresja komendy** `ustaw_zwrotnie_punkty_zwartych` po refaktorze: te same
  `punkty_kbn` co przed; `RekordBezPunktowalnegoAutorstwa` nadal skip+raport;
  nieobsłużona kombinacja nadal `NotImplementedError` bez `--ignore-errors`;
  `RekordBezWydawcy` nadal skip.
- Krok wizarda: ciągłe z `Punktacja_Zrodla` → proponuje wartość, edytowalną, POST
  zapisuje `matched_data["punkty_kbn"]` i przechodzi do Review; zwarte wg poziomu
  wydawcy; „brak danych" renderuje się dla braku źródła/wydawcy/poziomu/roku;
  `Status.PUNKTACJA` + `get_continue_url` prowadzi do właściwego kroku.
- `_create_publication`: ciągłe — IF/kwartyle z `Punktacja_Zrodla` zostają, a
  `punkty_kbn` = wartość operatora (nadpisanie po `uzupelnij_punktacje_z_zrodla`);
  zwarte — `punkty_kbn` = wartość operatora.

## 11. Poza zakresem

- Per-instytucja flaga / dosłowne „dla całej instytucji".
- HST-augmentowane progi w wartości sugestii (tylko warning).
- Rozróżnianie autorstwo/redakcja w imporcie (importer tworzy wszystkich jako
  autorów).
- Sugerowanie IF/kwartyli dla zwartych.
- Zmiany w adminie (admin ma własny „Uzupełnij punktację", zostaje).
