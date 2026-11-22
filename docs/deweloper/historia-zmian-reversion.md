# Historia zmian rekordów (django-reversion) — spec i kontrakty z koszem

!!! info "Status"
    Spec przeniesiony z PR #310 („spec wersjonowania zmian django-reversion +
    kontrakty z soft-delete", 2026-06-04) i dostosowany do stanu po
    skonsolidowanym PR kosza ([Soft-delete (kosz)](soft-delete.md)).
    **Kontrakty z koszem (sekcja 5) są zaimplementowane.** Rejestracja
    modeli edytowanych w adminie (sekcja 4) — zaimplementowana w FD#587.

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
  i `WybranaPublikacjaAutora`; `Uczelnia` przez `VersionAdmin`; od FD#587
  publikacje, zgłoszenia, słowniki i `Jednostka` (sekcja 4). Zatrudnienie,
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
- Przed FD#587 publikacje, struktura i słowniki miały tylko `LogEntry`.

## 3. Relacja do `SoftDeleteLog`

Komplementarne, nie duplikaty:

| | `SoftDeleteLog` | reversion / `LogEntry` |
|---|---|---|
| Co | zdarzenia: kosz / przywrócenie / trwałe usunięcie + status PBN | historia rekordu (reversion: migawki pól) |
| Pytanie | „co, kto, dlaczego zniknęło; co z PBN" | „jak rekord wyglądał i kto go zmieniał" |
| UX | log operacji kosza | zakładka „Historia" rekordu |

## 4. Rejestracja modeli w reversion (FD#587, zaimplementowane)

**Co jest wersjonowane** (`zarejestruj_wersjonowanie` w
`src/bpp/wersjonowanie.py`; zgłoszenia w `zglos_publikacje/wersjonowanie.py`;
import w `AppConfig.ready`, więc rejestracja działa też w Celery
i poleceniach):

| Model | `follow` | `exclude` (poza `POLA_KOSZA`) |
|---|---|---|
| `Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte` | `autorzy_set`, `streszczenia`, `dodatkowe_tytuly`, `zewnetrzna_baza_danych` + relacje generyczne (niżej) | `search_index`, `tytul_oryginalny_sort`, cache opisu i `cached_punkty_dyscyplin` |
| `Patent` | `autorzy_set` | jw. |
| `Praca_Doktorska` | — | jw. |
| `Praca_Habilitacyjna` | `publikacja_habilitacyjna_set` | jw. |
| `Zgloszenie_Publikacji` | `zgloszenie_publikacji_autor_set`, `zalaczniki` | — |
| `Zrodlo` | punktacja, redakcja, dyscypliny źródła | `search` |
| `Wydawca` | `poziom_wydawcy_set` | `lista_poziomow`, `ile_aliasow` |
| `Konferencja`, `Seria_Wydawnicza` | — | — |
| `Jednostka` | — (zatrudnienie nieśledzone, jak u `Autor`) | `search` |

Relacje generyczne każdej publikacji, która je ma (`GenericRelation`,
bez kolumn i migracji): `granty_rekordu`, `nagrody` (dodane też do
`Wydawnictwo_Ciagle`), `elementy_repozytorium`, `slowa_kluczowe_powiazania`
(wiersze `taggit.TaggedItem` — sam `slowa_kluczowe` zwraca wspólne tagi).
Treść plików repozytorium nie jest wersjonowana.

**Pozostałe modele admina** (słowniki, konfiguracja, użytkownicy, grupy,
modele z pakietów zewnętrznych): lista `MODELE_Z_HISTORIA`
w `src/bpp/admin/helpers/wersje_modele.py`. `BppAdminConfig.ready()` po
autodiscover woła `podepnij_historie_wersji`, które podmienia klasę admina
na `klasa + HistoriaWersjiMixin + CompareVersionAdmin`; `VersionAdmin`
rejestruje model z inline'ami (`follow`). `MODELE_BEZ_HISTORII` — świadome
wyjątki z powodem (logi, wyniki zadań, sesje importów, kopie danych z PBN,
tokeny). Test-strażnik `test_fd587_wszystkie_modele_admina.py` wymaga, by
każdy model w adminie był na jednej z list.

**Pola wrażliwe** (`POLA_WRAZLIWE`: hasło, `last_login`, token PBN
użytkownika, `client_secret` aplikacji OAuth) są poza wersjami, a przy
przywracaniu wersji receiver `zachowaj_pola_wrazliwe` (`pre_save`
z `raw=True`, tylko w `revision_view`) wpisuje ich bieżące wartości —
inaczej przywrócenie danych użytkownika wyzerowałoby mu hasło.

**`exclude` — pułapka.** Przywrócenie wersji zapisuje obiekt surowo
(`save_base(raw=True)`), a pole spoza wersji dostaje WARTOŚĆ DOMYŚLNĄ
modelu. Wolno wyłączać tylko pola liczone przez trigger `BEFORE` albo
denorm (przeliczane przy zapisie formularza po przywróceniu) lub mogące
być puste. Dlatego `slug`, `ostatnio_zmieniony` i pola MPTT `Jednostka`
(`lft`/`rght`/`tree_id`/`level`, NOT NULL) SĄ w wersji. Rejestr
`POLA_POZA_WERSJA` + parametryzowany test przywracania każdego modelu
(`test_fd587_historia_wersji.py`).

**Admin.** Wszystkie adminy z zakresu: `HistoriaWersjiMixin` +
`CompareVersionAdmin` (tuż przed terminalną klasą; `BppSoftDeleteAdminMixin`
zostaje przed nimi). Mixin dodatkowo:

- `compare_view` z kontrolą zakresu uczelni i uprawnień
  (reversion-compare sam ich nie sprawdza),
- `compare_exclude` — pomija pola techniczne, relacje nieśledzone
  i m2m przez własne tabele (inaczej diff źródła przeglądałby wszystkie
  jego publikacje); `REVERSION_COMPARE_FOREIGN_OBJECTS_AS_ID = True`,
  bo domyślnie biblioteka pokazuje KAŻDE pole FK jako zmienione,
- `po_przywroceniu_wersji` — hook; `JednostkaAdmin` przebudowuje drzewo
  MPTT (zapis surowy omija MPTT),
- `compare` — własne porównanie (`porownanie_wersji.py`) zamiast diffu
  reversion-compare: tabela „pole | wersja A | wersja B”, wartości po
  ludzku (nazwy ze słowników, tak/nie, daty), diff słów w tekstach, listy
  śledzone jako dodane/usunięte/zmienione z polami,
- `revision_view` (GET) — `zmiany_powiazanych`: formularz przywracania
  wypisuje pozycje list, które zostaną usunięte/przywrócone,
- szablony pod Grappelli: `reversion/object_history.html` (kolumny A/B,
  źródło zmiany), `reversion-compare/compare.html`,
  `reversion/revision_form.html`, wspólne style
  `reversion/_style_historii.html`; bez przycisku „Odzyskaj usunięte” na
  liście (decyzja 4 niżej).

**Źródło zmiany.** Aplikacja `historia_zmian` (osobna, bo `auth_server`
ładuje `bpp` bez reversion): model `ZrodloZmiany` (1:1 z `Revision`:
`zrodlo`, `aplikacja_client_id`, `aplikacja_nazwa` — bez FK do
`oauth2_provider`), receiver `post_revision_commit` + sygnał
`wersje_zapisane_hurtowo` dla zapisu hurtowego. Wartość z kontekstu
`bpp.zrodlo_zmian.zrodlo_zmian(...)`: middleware
`UzytkownikHistoriiMiddleware` ustawia „moduł redagowania” / „API” /
„strona” po ścieżce żądania; pomocniki importów (`zmiana_rekordu`,
`zarejestruj_utworzenie`, `zmiany_rekordow`) — „import lub narzędzie”;
poza żądaniem — „system”. Serwer MCP ma owijać zmiany w
`zrodlo_zmian(ZRODLO_API, aplikacja=<Application>)`. Lista wszystkich
rewizji z filtrami: admin „Historia zmian (rewizje)”.

**Jedna rewizja = jeden rekord.** `revision.revert()` odwraca CAŁĄ
rewizję. Dlatego:

- akcje masowe w ogóle nie dostają wspólnej rewizji z `changelist_view`
  (`HistoriaWersjiMixin.create_revision`),
- hurtowe zapisy wersji (`zapewnij_wersje_poczatkowe`,
  `zmien_hurtowo_z_historia`, `zapisz_wersje_utworzenia`) idą przez
  `zapisz_wersje_osobno`: rewizja na rekord, dwa `bulk_create` (stała
  liczba zapytań). Wersje są budowane po stronie BPP (pola jak
  w `reversion.register`), bo reversion nie ma publicznego API hurtowego,
  a prywatnego nie używamy (test-strażnik).

Limit akcji masowej dla publikacji: 5000 rekordów
(`MAKS_REKORDOW_AKCJI_MASOWEJ_PUBLIKACJI`, zmierzone ~4 ms/rekord z
autorem — wersja „przed” i „po”).

### Pierwotny plan (archiwum)

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

## 6. Decyzje

1. Backfill `createinitialrevisions` — **nie**: historia „od teraz”;
   wersję początkową zapisuje `zapewnij_wersje_poczatkowa` przy pierwszej
   zmianie rekordu.
2. Retencja rewizji — **bez limitu** (decyzja właściciela, 22.11.2026):
   `deleterevisions` nie jest uruchamiane.
3. Pozycja w drzewie `Jednostka` — rodzic i pola MPTT są w wersji (NOT
   NULL), po przywróceniu drzewo jest przebudowywane; w porównaniu wersji
   pola MPTT są ukryte.
4. Recover reversion — przycisk ukryty na listach; widok zostaje tylko dla
   superużytkownika (dotyczy wyłącznie rekordów skasowanych twardo).
5. Źródło zmiany na każdej rewizji — **tak** (`historia_zmian`, wyżej).
6. Zakres — **wszystkie** modele edytowane w adminie, łącznie z grantami,
   nagrodami, plikami repozytorium, słowami kluczowymi i załącznikami
   zgłoszeń.
7. Przywrócenie wersji publikacji usuwa pozycje list dopisane później —
   **tak**, ale formularz przywracania wypisuje je przed zapisem.
