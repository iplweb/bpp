# Historia zmian rekordów (django-reversion) — spec i kontrakty z koszem

!!! info "Status"
    Spec przeniesiony z PR #310 („spec wersjonowania zmian django-reversion +
    kontrakty z soft-delete", 2026-06-04) i dostosowany do stanu po
    skonsolidowanym PR kosza ([Soft-delete (kosz)](soft-delete.md)).
    **Kontrakty z koszem (sekcja 5) są już zaimplementowane.** Rejestracja
    kolejnych modeli w reversion (sekcja 4) to **następny, osobny PR**.

**Cel:** rozliczalność edycji ludzkich. Operator otwiera rekord w adminie,
klika „Historia" i widzi ciągłą oś: kto utworzył, kto co zmienił, kto
przeniósł do kosza i kto przywrócił — z możliwością cofnięcia do
wcześniejszej wersji. To narzędzie do **diagnozy błędów ludzi**, nie
total-audyt bazy (bulk-importy, surowy SQL, triggery zostają poza nim).

## 1. Decyzja o narzędziu

| Narzędzie | Werdykt | Dlaczego |
|---|---|---|
| **django-reversion** (+ `reversion-compare`) | ✅ wybrane | Już w repo; oś wersji + revert + „kto/kiedy/komentarz"; zakres selektywny (per model); rejestracja kolejnego modelu nie wymaga migracji (tabele `Revision`/`Version` już są). Diff pól: `CompareVersionAdmin` z `reversion-compare` (zainstalowany, jeszcze niewpięty). |
| django-pghistory | ❌ | Triggerowy total-audyt bazy — inny problem niż historia edycji w adminie. |
| django-simple-history | ❌ | Duplikuje każdą tabelę (`_historical`) — zła kombinacja z dużymi tabelami publikacji; dubluje paradygmat reversion. |

## 2. Stan obecny (dev + PR kosza)

- **`LogEntry`** (wbudowany w admin) — warstwa 0: każda akcja z admina,
  bez wartości pól i bez revertu. Filtry w `src/bpp/admin/filters.py`.
- **reversion — zarejestrowane modele:** `Autor` (jawnie,
  `src/bpp/wersjonowanie.py`: `exclude=("search", "deleted_at",
  "restored_at", "transaction_id")`, `follow=("wybrane_publikacje",)`)
  i `WybranaPublikacjaAutora`; `Uczelnia` przez `VersionAdmin`. Zatrudnienie,
  dyscypliny i absencje autora celowo **nieśledzone** (revert z
  `delete=True` ruszałby wiersze innych uczelni / przypisania dyscyplin).
- **Edycje spoza admina:** profil autora (`zmiana_ze_strony` — rewizja +
  `LogEntry`), importer publikacji (#1043, `importer_publikacji/historia.py`
  — `LogEntry` ADDITION dla publikacji, `LogEntry` + rewizja dla `Autor`).
- **Strona „Historia" autora** (`HistoriaWersjiMixin`,
  `src/bpp/admin/helpers/wersje.py`) łączy rewizje reversion ze starszymi
  wpisami `LogEntry`; wersja początkowa sprzed pierwszej zmiany
  (`zapewnij_wersje_poczatkowa`), kontrola typu i uczelni w
  `revision_view`, recover tylko dla superusera. Rekord z kosza: „przywróć
  wersję" zablokowane (najpierw „Przywróć" z kosza).
- **Publikacje, struktura (`Jednostka`), słowniki NIE są w reversion.**

## 3. Relacja do `SoftDeleteLog`

Komplementarne, nie duplikaty:

| | `SoftDeleteLog` | reversion / `LogEntry` |
|---|---|---|
| Co | zdarzenia: kosz / przywrócenie / trwałe usunięcie + status PBN | historia rekordu (reversion: migawki pól) |
| Pytanie | „co, kto, dlaczego zniknęło; co z PBN" | „jak rekord wyglądał i kto go zmieniał" |
| UX | log operacji kosza | zakładka „Historia" rekordu |

## 4. Następny krok: rejestracja modeli w reversion (osobny PR)

Decyzja właściciela (listopad 2026): w osobnym PR do reversion trafi
**praktycznie każdy model edytowany w adminie** — publikacje
(`Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte`, `Patent`, `Praca_Doktorska`,
`Praca_Habilitacyjna`), zgłoszenia (`Zgloszenie_Publikacji`), struktura
(`Jednostka`), słowniki (`Zrodlo`, `Wydawca`, `Konferencja`,
`Seria_Wydawnicza`, …). Do ustalenia przy tamtym PR:

- `CompareVersionAdmin` (diff pól) jako domyślna baza adminów; szablon
  historii (`src/django_bpp/templates/reversion/object_history.html`)
  potrzebuje selektora pary wersji;
- **`follow` dla relacji:** autorstwa `*_Autor` jako część rewizji
  publikacji (inline'y `VersionAdmin` follow-uje sam; relacje spoza
  inline'ów — ręcznie). Pola kosza (`deleted_at`, `restored_at`,
  `transaction_id`) zawsze w `exclude`;
- `Jednostka` (MPTT): czy zmiany `lft/rght/level` mają trafiać do historii;
  przetestować MRO `VersionAdmin` + `DraggableMPTTAdmin`;
- backfill (`createinitialrevisions`) na dużych tabelach czy „historia od
  teraz"; retencja (`deleterevisions`).

**Kod kosza nie wymaga przy tym zmian** — patrz sekcja 5.1.

## 5. Kontrakty z koszem (zaimplementowane)

### 5.1 Kosz i przywrócenie zostawiają ślad w historii — generycznie

Receiver kosza (`_zapisz_wersje`, `src/bpp/receivers/soft_delete.py`):

- `reversion.is_registered(model)` → rewizja reversion z `set_user`
  i `set_comment` („Przeniesiono do kosza (powód: …)" / „Przywrócono
  z kosza");
- w przeciwnym razie → `LogEntry` (CHANGE) z tym samym komunikatem.

Zarejestrowanie modelu w reversion (sekcja 4) automatycznie przełącza go
z `LogEntry` na rewizje. Admin nie pisze przy koszu wpisu `DELETION`.

Warunek poprawności: `delete()`/`restore()` modeli z koszem zapisują przez
`save(update_fields=[...])` (nie `queryset.update()` — ten blokuje gate
`BppSoftDeleteQuerySet.update`), więc sygnały i reversion działają.

### 5.2 Jeden punkt atrybucji „kto"

`request.user` i powód wchodzą raz — przez `soft_delete_context` (thread-
local) w `BppSoftDeleteAdminMixin._soft_delete_user_context`. Czytają go
receivery `SoftDeleteLog` i historii (reversion/`LogEntry`).

### 5.3 Admin: MRO, widoczność kosza, „recover deleted"

- `BppSoftDeleteAdminMixin` stoi OSTATNI przed terminalną klasą admina
  (u `Autor`/`Uczelnia`: przed `HistoriaWersjiMixin`, `VersionAdmin`);
  `get_queryset → global_objects`, więc rekord z kosza da się otworzyć
  (tylko do odczytu) i przeczytać jego historię.
- reversion „recover deleted" dotyczy wyłącznie rekordów skasowanych
  TWARDO (wiersza nie ma) — wskrzeszenie z wersji ominęłoby kosz
  (`SoftDeleteLog`, PBN, punktację, unikalne slugi). Recover zostaje
  wyłącznie dla superusera; docelowo ukryć albo przekierować na
  przywracanie z kosza.

## 6. Otwarte decyzje

1. Backfill `createinitialrevisions` na dużych tabelach: tak / „od teraz".
2. Retencja rewizji (`deleterevisions`) — czy i po ilu dniach.
3. Czy zmiany pozycji w drzewie `Jednostka` (MPTT) wersjonować.
4. Czy recover reversion całkiem ukryć dla modeli z koszem.
