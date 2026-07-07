# Sugerowanie punktacji ministerialnej w importerze publikacji

**Zgłoszenie:** Freshdesk #384 (pod-zgłoszenie #379, uwaga #5 z „importowanie bpp.docx")
**Data:** 2026-07-07
**Gałąź:** `fd-384-sugeruj-punktacje-importer` (baza: `dev`)
**Zastępuje:** zamknięty PR #404 (`fd-384-sugeruj-punktacje`)

## 1. Kontekst i problem

Operator wprowadzający dane w importerze publikacji nie ma skąd wiedzieć, ile
punktów MNiSW (20/40/80/140/200…) przypisać publikacji. Klient sformułował to
jako „przełącznik »sugeruj punktację« dla całej instytucji", i pierwotny PR #404
wziął to **dosłownie**: dodał `Uczelnia.sugeruj_punktacje` (BooleanField) i za tą
flagą zagatował cichy, automatyczny auto-fill punktacji ze źródła.

Po weryfikacji ze zgłaszającym ustalono, że to **nie** jest realna potrzeba.
Realnie chodzi o **jawną podpowiedź w toku importu**: operator ma zobaczyć, na
jakiej podstawie i ile punktów system proponuje, i móc to zaakceptować, zmienić
albo pominąć. Cichy globalny auto-fill jest nieprzejrzysty i myli operatora
(dlatego w ogóle powstała uwaga).

Ustalenia weryfikacyjne:

- `Uczelnia.sugeruj_punktacje` **nie istnieje** na `dev` — było wprowadzone
  wyłącznie przez zamknięty PR #404 i zniknęło wraz z gałęzią. Nie ma czego
  chronić przy migracjach.
- Pre-istniejąca, podobnie brzmiąca flaga to `podpowiadaj_dyscypliny`
  (`bpp/models/uczelnia.py:435`) — dotyczy **dyscyplin, nie punktacji**, jest
  w aktywnym użyciu i **pozostaje nietknięta**.

## 2. Cel

Dodać w importerze publikacji **dedykowany krok „Punktacja"**, który po
ustaleniu źródła / wydawcy i typu publikacji pokazuje **czarno na białym**:

1. **Źródło** (dla wyd. ciągłego) i jego punktacja za dany rok — albo wyraźną
   informację, że **brak danych** dla tego źródła/roku.
2. **Wydawca** (dla wyd. zwartego) i jego **poziom** za dany rok — albo
   informację, że **brak danych** (brak wydawcy / brak poziomu dla roku).
3. **Sugestię punktów** `punkty_kbn` (ile dać) — albo informację, że **nie da
   się zaproponować, z wytłumaczeniem dlaczego** (np. brak wydawcy, brak
   punktowalnego autorstwa, brak punktacji źródła).

Sugestia jest **wyłącznie podpowiedzią** — pole „punkty MNiSW" jest zawsze
edytowalne; operator może przyjąć proponowaną wartość, wpisać własną albo
zostawić puste.

## 3. Zakres

**W zakresie (v1):**

- Nowy krok wizarda „Punktacja" dla obu typów: wyd. ciągłe (artykuł) i wyd.
  zwarte (monografia / rozdział / redakcja).
- Ścieżka ciągłych: punktacja z `Punktacja_Zrodla` dla (źródło, rok).
- Ścieżka zwartych: derywacja `punkty_kbn` z poziomu wydawcy dla roku +
  klasyfikacji rekordu (książka/rozdział × autorstwo/redakcja), na bazie
  progów już zdefiniowanych w komendzie `ustaw_zwrotnie_punkty_zwartych`.
- Wyświetlanie źródła/wydawcy i ich danych punktacyjnych z jawnym „brak danych".
- Zapis wybranej wartości do rekordu przy tworzeniu.

**Poza zakresem (v1):**

- Nowa flaga per-instytucja (świadoma decyzja — patrz §8).
- Augmentacja HST progów (patrz §9, ryzyko A).
- Sugerowanie pól pochodnych innych niż `punkty_kbn` w ścieżce zwartych
  (IF/kwartyle nie dotyczą zwartych).

## 4. Architektura — nowy krok wizarda

Importer to sekwencja widoków HTMX w `src/importer_publikacji/views/wizard.py`,
każdy renderujący partial `templates/importer_publikacji/partials/step_*.html`.
Kolejność: Fetch → Verify → **Source** → Authors → **Review** → Create → Done.

Dodajemy krok **Punktacja** po `Authors`, przed `Review` (po Authors, bo
klasyfikacja zwartych zależy od ról autorów — patrz §7 i §9-B):

- **Widok** `PunktacjaView` (wzorzec z pozostałych kroków wizarda), URL name
  `punktacja`, partial `step_punktacja.html`.
- Renderer `_render_punktacja_step` w `views/steps.py` (spójnie z
  `_render_source_step` itd.).
- Krok już zna z sesji importu:
  - typ publikacji: `VerifyForm.jest_wydawnictwem_zwartym` +
    `_is_chapter()` (`steps.py`, po `charakter_ogolny`),
  - źródło / wydawcę: z `SourceForm` (`zrodlo` / `wydawca`),
  - rok publikacji.
- Formularz kroku ma jedno pole edytowalne: `punkty_kbn` („punkty MNiSW"),
  wypełnione proponowaną wartością (jeśli jest), plus akcja „ustaw
  automatycznie / sugeruj punktację" (re-oblicza sugestię). Nawigacja
  Wstecz/Dalej jak w pozostałych krokach.

## 5. Kontrakt „Sugestia" (współdzielony value object)

Obie ścieżki zwracają jednolity, mały obiekt wartości, który wprost napędza
„czarno na białym" UI oraz zapis:

```
Sugestia:
    punkty: Decimal | None        # proponowane punkty_kbn, None gdy nie da się
    podstawa: str                 # np. "Punktacja źródła 2024", "Wydawca poziom II"
    powod_braku: str | None       # człowiek-czytelne „dlaczego nie da się"
    dane_zrodla: dict | None      # snapshot Punktacja_Zrodla (ciągłe) do wyświetlenia
    poziom_wydawcy: int | None    # 1/2/None (zwarte) do wyświetlenia
```

`powod_braku` i `podstawa` są komunikatami dla operatora — nie zjadamy błędów,
tylko je nazywamy (zgodnie z CLAUDE.md „no silent failures").

## 6. Ścieżka ciągłych (artykuł) — reuse istniejącego

Mechanizm punktacji źródła już istnieje i jest przetestowany:

- `uzupelnij_punktacje_z_zrodla(rekord, zrodlo, rok)` (`bpp/models/zrodlo.py:25`)
  kopiuje pola `POLA_PUNKTACJI` z `Punktacja_Zrodla` na rekord.
- `Punktacja_Zrodla` (`bpp/models/zrodlo.py:92`) — per-rok punktacja źródła.
- API `PunktacjaZrodlaView` (`bpp/views/api/__init__.py:41`) — JSON punktacji.
- Komenda `ustaw_zwrotnie_punkty_ciaglych._przetworz` robi de facto to samo
  (`Punktacja_Zrodla.get(rok).punkty_kbn`).

**Nowa czysta funkcja** `zaproponuj_punkty_ciagle(zrodlo, rok) -> Sugestia`
(lokalizacja: przy `Punktacja_Zrodla` w `bpp/models/zrodlo.py` lub w module
sugestii importera):

- jest `Punktacja_Zrodla` dla (źródło, rok) → `punkty = punkty_kbn`,
  `podstawa = "Punktacja źródła {rok}"`, `dane_zrodla = {…}`;
- brak → `punkty = None`, `powod_braku = "Brak punktacji źródła »{zrodlo}« za
  {rok}"`.

**Uwaga (rozbieżność polityki):** komenda PBN ma fallback „brak danych → 5 pkt".
W importerze **nie** stosujemy tego fallbacku — pokazujemy „brak danych", żeby
operator zdecydował świadomie. Ekstrakcja czystej funkcji pozwala komendzie
zachować swój fallback, a importerowi pokazać uczciwe „brak danych".

## 7. Ścieżka zwartych (monografia/rozdział) — ekstrakcja z komendy

Kanoniczna derywacja `punkty_kbn` dla zwartych **już istnieje**, ale inline w
`ustaw_zwrotnie_punkty_zwartych._przetworz`
(`src/pbn_api/management/commands/ustaw_zwrotnie_punkty_zwartych.py:84`):

- `poziom = wydawca.get_tier(rok)` (−1 → 0),
- tabela progów `punkty_dct[poziom]`:
  - poziom 0 (spoza wykazu): `{KS: 20, RED: 5, ROZ: 5}`
  - poziom I: `{KS: 80, RED: 20, ROZ: 20}`
  - poziom II: `{KS: 200, RED: 100, ROZ: 50}`
- klasyfikacja: `warunek_ksiazka()`, `warunek_rozdzial()`, `warunek_autorstwo()`,
  `warunek_redakcja()` (`bpp/models/wydawnictwo_zwarte.py`),
- mapowanie: książka+autorstwo→KS, książka+redakcja→RED, rozdział+autorstwo→ROZ.

Komenda już definiuje **nazwane wyjątki na braki danych**, które mapują się 1:1
na `powod_braku`:

- `RekordBezWydawcy` → „Brak wydawcy — nie ma podstawy do poziomu punktacji"
- `RekordBezPunktowalnegoAutorstwa` → „Brak punktowalnego autorstwa/redakcji"
- kombinacja nieobsłużona → „Nieobsłużony typ publikacji ({…})"

**Plan:**

1. Wyekstrahować `_przetworz` do czystej funkcji
   `zaproponuj_punkty_zwarte(rekord_lub_dane, wydawca, rok) -> Sugestia`
   (zwraca `Sugestia`, nie zapisuje, nie rzuca — braki danych zamienia na
   `powod_braku`). Tabela progów staje się nazwaną stałą.
2. `ustaw_zwrotnie_punkty_zwartych` **przepisać na tę funkcję** (zachowując
   swoją politykę: pomiń/raportuj przy `powod_braku`), żeby nie było dwóch
   źródeł prawdy dla progów.
3. Nowy krok importera używa tej samej funkcji.

Na etapie importu klasyfikacja opiera się na `charakter_formalny` / `typ_kbn`
oraz rolach autorów zebranych w krokach wcześniejszych — do potwierdzenia, że
`warunek_*` da się policzyć na jeszcze-niezapisanym rekordzie (patrz §9,
ryzyko B).

## 8. Zapis do rekordu i brak flagi

- Wybrana wartość `punkty_kbn` trafia do rekordu **przy tworzeniu**
  (`common_fields` w `importer_publikacji/views/publikacja.py::_create_publication`),
  zamiast dzisiejszego cichego post-hoc `uzupelnij_punktacje_z_zrodla`
  (ciągłe) i braku jakiejkolwiek punktacji (zwarte).
- **Brak nowej flagi w ścieżce krytycznej** (decyzja właściciela). Akcja
  „sugeruj punktację" jest zawsze dostępna w kroku. Ewentualny per-instytucja
  *default* (auto-proponuj po wejściu w krok) można dodać później, gdyby klient
  nalegał na dosłowne „dla całej instytucji" — poza zakresem v1.

## 9. Ryzyka i niuanse

**A. Progi HST.** Komenda `ustaw_zwrotnie_punkty_zwartych` używa progów
**bazowych** (20/80/200…), bez augmentacji HST (kalkulator slotów
`bpp/models/sloty/core.py` HST uwzględnia: 120/300 itd.). v1 sugestii idzie za
komendą — progi bazowe. Ponieważ sugestia jest edytowalna, to akceptowalny
kompromis; augmentację HST oznaczamy jako znany, udokumentowany dług.

**B. `warunek_*` na niezapisanym rekordzie.** Klasyfikacja zwartych
(`warunek_ksiazka/rozdzial/autorstwo/redakcja`) zależy od ról autorów i
charakteru. Do potwierdzenia w implementacji, czy da się ją policzyć na danych
sesji importu przed zapisem rekordu; jeśli nie — krok liczy sugestię po
skompletowaniu danych (już po kroku Authors, co porządkuje kolejność:
Punktacja po Authors, przed Review).

**C. Kiedy pokazywać krok.** Krok pokazujemy zawsze (spójna nawigacja), ale
treść adaptuje się do dostępnych danych: gdy nie ma ani źródła, ani wydawcy →
komunikat „brak danych do zaproponowania punktów, wpisz ręcznie lub pomiń".

## 10. Testy (pytest, testcontainers)

- `zaproponuj_punkty_zwarte`: poziom I/II/spoza wykazu × książka/rozdział ×
  autorstwo/redakcja → oczekiwane progi; brak wydawcy → `powod_braku`; brak
  autorstwa → `powod_braku`.
- `zaproponuj_punkty_ciagle`: jest `Punktacja_Zrodla` → wartość; brak → `None`
  + `powod_braku` (bez fallbacku 5 pkt).
- `ustaw_zwrotnie_punkty_zwartych` po refaktorze: te same wyniki co przed
  (regresja — komenda nie zmienia zachowania, w tym pomijania/raportowania).
- Krok wizarda: dla ciągłego z `Punktacja_Zrodla` proponuje wartość, edytowalną;
  dla zwartego wg poziomu wydawcy; zapis `punkty_kbn` do rekordu; „brak danych"
  renderuje się gdy brak źródła/wydawcy/poziomu.

## 11. Poza zakresem

- Per-instytucja flaga / dosłowne „dla całej instytucji".
- HST-augmentowane progi w sugestii.
- Sugerowanie IF/kwartyli dla zwartych (nie dotyczy).
- Zmiany w adminie (to jest ścieżka importera; admin ma własny przycisk
  „Uzupełnij punktację", który zostaje).
