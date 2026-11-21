# Handoff: domknięcie fazy 03 (PR #742 wymaga poprawek)

> ## ✅ ZAMKNIĘTE 2026-08-08 — dokument HISTORYCZNY, nie lista zadań
>
> Wszystkie pięć pozycji (3.1–3.5) zostało zrobione. Nie działaj na podstawie
> tego pliku — aktualny stan i dług są w
> `docs/superpowers/HANDOFF-soft-delete-faza-04.md`.
>
> | Pozycja | Commit |
> |---|---|
> | 3.1 zaglądanie do kosza w gałęzi `None` | `b98aad5be` |
> | 3.2 warunkowy unique na habilitacji | `9c3ecb23e` |
> | 3.3 detekcja kolizji po `global_objects` | `369e6a5f6` |
> | 3.4 brak kolejkowania kosza do PBN | `369e6a5f6` |
> | 3.5 opis PR #742 | przepisany w GitHubie |
>
> Pozycje 9, 10, 13, 14 z §4 (niższy priorytet) NADAL otwarte — przeniesione
> do §6 handoffu fazy 04. Pułapki z §5 przeniesione do §7 tamże, wraz z trzema
> nowymi, które kosztowały tę sesję.
>
> ---

> Stan na 2026-08-08. Sesja przerwana w połowie naprawiania po self-review.
> **PR #742 NIE nadaje się do scalenia w obecnym stanie.**

---

## 1. Gdzie jesteś

| | |
|---|---|
| Worktree | `~/Programowanie/bpp-soft-delete-03` |
| Gałąź | `feat/soft-delete-03`, baza `feat/soft-delete` |
| PR | [#742](https://github.com/iplweb/bpp/pull/742), OPEN |
| Ostatni commit | `eb046897a` — cofnięcie akcesorów |
| Drzewo | czyste, wszystko wypchnięte |

Uruchom testy na start, żeby potwierdzić stan:
```bash
cd ~/Programowanie/bpp-soft-delete-03
uv run pytest src/bpp/tests/test_soft_delete/ src/pbn_api/ -q
```
Oczekiwane: zielono.

---

## 2. Co się wydarzyło (skrót)

Faza 03 miała sprawić, żeby re-import z PBN nie tworzył duplikatów rekordów
soft-skasowanych. Pierwsza implementacja poszła **złą drogą**: kazała
akcesorom (`rekord_w_bpp`, `get_bpp_publication`, `matchuj_publikacje`)
zaglądać do kosza i zwracać skasowane rekordy.

Self-review (osobny agent) znalazł 3 blokery i kilka rzeczy ważnych.
**Blokery 1 i 2 są już naprawione** commitem `eb046897a`.

### Decyzja właściciela, która ustawia resztę

> **Soft-delete znaczy, że rekordu NIE MA.** `Rekord` (widok
> `bpp_rekord_mat`) jest odfiltrowany po `deleted_at` i tak ma zostać.
> Akcesor zwraca `Rekord` albo `None` — nigdy rzeczy z kosza.
>
> Zaglądanie do kosza jest decyzją **IMPORTERA**, nie akcesora.

Oraz, na pytanie „co zrobić, gdy import trafi na rekord w koszu":

> **Wariant A: PRZYWRÓĆ + ODNOTUJ.** PBN jest źródłem prawdy — skoro rekord
> tam jest, ma wrócić do BPP. Ślad w rejestrze
> `pbn_integrator.RekordPrzywroconyPrzezImport`.

---

## 3. Do zrobienia — 5 pozycji, w tej kolejności

### 3.1. Przenieść zaglądanie do kosza w gałąź `None` (wariant A)

Dziś w `articles.py:70`, `books.py:68`, `chapters.py:113` jest:

```python
ret = pbn_publication.rekord_w_bpp
if ret is not None and not force:
    przywroc_jesli_w_koszu(ret, pbn_publication, "articles")
    return ret
```

Po cofnięciu akcesorów `ret` to `Rekord` albo `None` — **nigdy** obiekt
z kosza. Czyli `przywroc_jesli_w_koszu(ret, ...)` jest teraz **no-opem**
(`Rekord` nie ma pola `deleted_at`).

Docelowo: gdy `ret is None`, sprawdzić kosz JAWNIE po `pbn_uid`
(`Wydawnictwo_Ciagle.deleted_objects.filter(pbn_uid_id=...)` itd.),
przywrócić i wpisać do rejestru; dopiero potem tworzyć nowy rekord.

⚠️ `Patent` NIE ma pola `pbn_uid` — `.filter(pbn_uid_id=…)` na nim wywala
`FieldError` (Django resolwuje nazwy pól natychmiast).

`przywroc_jesli_w_koszu()` w `pbn_integrator/kosz.py` zostaje bez zmian —
jest dobry, ma testy, zweryfikowany mutacyjnie.

### 3.2. BLOKER 3 — warunkowy unique na habilitacji

`Praca_Habilitacyjna.autor` to `OneToOneField` → `UNIQUE (autor_id)`, które
**nie zna kosza**. Duplikat z habilitacją w koszu + główny autor z żywą →
`scal_autora` pada `IntegrityError` i **całe scalanie zwraca porażkę**.
Przed fazą 03 wiersz z kosza nie był przenoszony, więc scalanie się udawało.

Naprawa (decyzja właściciela): zdjąć `unique` z pola, dodać warunkowy
`UniqueConstraint(fields=["autor"], condition=Q(deleted_at__isnull=True))`
w `Meta`. Ten sam wzorzec, co faza 01 zastosowała do `*_Autor`.

Gdy OBIE habilitacje są żywe — to prawdziwy konflikt. Jawny komunikat:
„Nie można scalić autorów: obaj mają pracę habilitacyjną", zamiast
`IntegrityError`.

Test najpierw — musi być czerwony przed zmianą constraintu.

### 3.3. Detekcja kolizji w scalaniu — `merge.py:145`

`existing = model.objects.filter(rekord=…, autor=glowny, typ=…)` — na
menedżerze ŻYWYCH. Gdy publikacja jest w koszu, oba autorstwa też są
w koszu → kolizja niewykryta → powstają DWA wiersze
`(rekord, glowny, typ)` w koszu.

Skutek: `wc.restore()` wywala się `IntegrityError` na
`wc_autor_uniq_rekord_autor_typ`. **Kosz staje się drzwiami
jednokierunkowymi.** Dotyczy też `przywroc_jesli_w_koszu` w imporcie.

Naprawa: detekcja kolizji ma iść po `global_objects`.

### 3.4. Scalanie kolejkuje do PBN publikację z kosza

`merge.py:214-222` — `PBN_Export_Queue.objects.create(...)` dla
`record.rekord`, także gdy ten jest soft-skasowany. Sprzeczne z kierunkiem
fazy 05 (soft-delete ma **wycofywać** oświadczenia, nie wysyłać).

Naprawa: pominąć kolejkowanie, gdy `record.rekord.deleted_at` jest ustawione.

### 3.5. Poprawić opis PR #742

Obecny opis twierdzi, że blocker duplikatów jest domknięty. **Nie jest.**

- Ścieżka fuzzy (rekord BPP **bez** `pbn_uid`, czyli praca wprowadzona
  ręcznie) idzie przez `Rekord`, więc kosza nie widzi → duplikat nadal
  powstanie. Po cofnięciu akcesorów to zachowanie **zamierzone** (rekordu
  nie ma), ale opis PR-a sugeruje co innego.
- Ścieżka po `pbn_uid`: unique na `pbn_uid_id` **nie jest** partial, więc
  skasowany rekord i tak trzyma to pole. Przed fazą 03 dawało to
  *wywalenie importu*, nie cichy duplikat.

Zaktualizować też tabelkę „6 lookupów matchingu widzi kosz" — nieaktualna
po cofnięciu.

---

## 4. Ustalenia recenzji, które ZOSTAJĄ otwarte (niższy priorytet)

| # | Rzecz | Gdzie |
|---|---|---|
| 9 | Rejestr wskrzeszeń niewidoczny — `pbn_integrator/admin.py` to nadal `# Register your models here.` Brak też indeksu `(content_type, object_id)` pod pytanie „czy TEN rekord wrócił?" | `pbn_integrator/admin.py`, `models.py` |
| 10 | `force=True` omija wskrzeszenie (`if ret is not None and not force`), a `znajdz_ksiazke_nadrzedna` leży ZA tym guardem → książka-matka jest wskrzeszana przy `force`, sam rozdział nie. Niespójne | 3 importery |
| 12 | Brak newsfragmentu (CLAUDE.md wymaga) | `src/bpp/newsfragments/` |
| 13 | `Oswiadczenie_Instytucji.get_bpp_publication` iteruje po 4 modelach po `pbn_uid` przez `.objects` — nie ma go ani na liście zmienionych, ani „świadomie zostawionych" | `pbn_api/models/oswiadczenie_instytucji.py:51-74` |
| 14 | `hard_delete()` na querysecie NIE emituje `post_hard_delete` — najbardziej destrukcyjna operacja przejdzie niezauważona przez `SoftDeleteLog` z fazy 06 | do handoffu fazy 06 |

---

## 5. Pułapki, które już kosztowały (nie powtarzaj)

- **Lista wołaczy ≠ lista założeń wołaczy.** Sprawdziłem, kto woła
  `rekord_w_bpp`, ale nie co robi z wynikiem. Admin woła `.original` —
  atrybut istniejący WYŁĄCZNIE na `Rekord`. Efekt: `AttributeError` na całej
  changeliście, zero pokrycia testami. Naprawione + dołożony
  `src/pbn_api/tests/test_admin_rekord_w_bpp.py`.
- **Django połyka brak atrybutu w SZABLONACH.** Ten sam błąd w
  `change_form.html` dawał pusty `href` zamiast wyjątku — objaw gorszy niż
  crash.
- **`matchuj_publikacje` ma DWÓCH wołaczy o sprzecznych potrzebach**:
  `pbn_api` (przekazuje `Rekord`) i `deduplikator_publikacji`
  (`tasks.py:187`, przekazuje modele konkretne). Zmiana „na globalny
  menedżer widzący" sprawiła, że dedup zaczął podsuwać kosz — wbrew decyzji
  z Taska 8. Mój test tego nie złapał, bo pokrywał tylko połowę skanującą.
- **`make tests-without-playwright` zwraca EXIT 0 mimo porażek.** Czytaj
  podsumowanie pytest, nie kod wyjścia.
- **`ruff format` na całym katalogu zagarnia cudze pliki.** Formatuj tylko
  swoje.
- **Mutacja jest jedynym dowodem, że test coś pilnuje.** Czerwień z
  `ImportError` nie dowodzi, że asercje działają.

---

## 6. Poza tą gałęzią

- **PR upstream** [soynatan/django-easy-audit#348](https://github.com/soynatan/django-easy-audit/pull/348)
  — wystawiony z forka `mpasternak`. Po scaleniu skasować
  `src/bpp/easyaudit_shim.py`, wywołanie `zainstaluj()` w `BppConfig.ready()`
  i `test_easyaudit_shim.py`. Przypomni o tym
  `test_upstream_nadal_ma_blad_czyli_shim_jest_potrzebny`.
- **Bramka wydania przesunięta na fazę 07** (decyzja 2026-08-08) — patrz
  `HANDOFF-soft-delete-faza-04.md` §4b.
- **Nagrobki (OAI-PMH / CERIF / API) wciągnięte do fazy 05.**
