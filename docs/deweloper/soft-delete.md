# Soft-delete (kosz): co jest kasowane miękko, a co nie

!!! info "Dla kogo"
    Strona dla dewelopera i agenta AI. Opisuje stan po skonsolidowanym PR
    „Soft delete (kosz)" (zastępuje stos #312 → #745 → #755 → #767 → #792)
    i decyzje właściciela projektu z listopada 2026. Historia faz (plany,
    handoffy, recenzje) została na gałęzi `feat/soft-delete-06` — tutaj jest
    stan docelowy, nie kronika.

## Mechanizm w jednym akapicie

Modele z koszem dziedziczą `SoftDeleteModel` z pakietu
[`django-soft-delete`](https://pypi.org/project/django-soft-delete/)
(`django_softdelete`). Dostają pola `deleted_at`, `restored_at`,
`transaction_id` i trzy menedżery:

| Menedżer | Co widzi | Kiedy używać |
|---|---|---|
| `objects` (domyślny) | tylko żywe wiersze | wyświetlanie, eksport, liczenie, ewaluacja |
| `global_objects` | żywe + kosz | import, deduplikacja, scalanie, admin (z filtrem „Kosz") |
| `deleted_objects` | tylko kosz | kosz w adminie, nagrobki, `/api/v1/usuniete/` |

`obj.delete()` to `UPDATE ... SET deleted_at = now()` (przez
`save(update_fields=...)`), `obj.restore()` czyści znacznik,
`obj.hard_delete()` naprawdę kasuje wiersz (w adminie: tylko z kosza, tylko
superuser). **Kaskady pakietu nie używamy** — kasowałaby twardo dzieci
spoza kosza; każdy model ma własne `delete()`/`restore()`. Kod wspólny:
`src/bpp/models/soft_delete.py`; receivery (`SoftDeleteLog`, punktacja, PBN,
historia): `src/bpp/receivers/soft_delete.py`; audyt:
`src/bpp/models/soft_delete_log.py`; user/powód:
`src/bpp/models/soft_delete_context.py`; admin:
`BppSoftDeleteAdminMixin` w `src/bpp/admin/helpers/mixins.py`.

**Zasada ogólna:** kosz dostają rekordy, które operator świadomie „wyrzuca"
i może chcieć odzyskać. Rekordy pomocnicze, które żyją i umierają z
rodzicem, **nie mają własnego kosza** — znikają razem z rodzicem (domyślny
menedżer je ukrywa) i wracają przy jego przywróceniu. Słowniki i struktura
trafiają do kosza **tylko jako rekordy nieużywane** (guard), więc żaden żywy
rekord nie wskazuje na coś z kosza.

## Tabela: model → kosz?

### Publikacje — TAK

| Model | `delete()` | `restore()` |
|---|---|---|
| `Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte`, `Patent`, `Praca_Doktorska`, `Praca_Habilitacyjna` | Znika z `objects`, z `bpp_rekord_mat` i `bpp_autorzy_mat` (trigger), z ewaluacji (`Cache_Punktacja_*` kasowane receiverem), z API/OAI (nagrobek), z rankingu i raportów (widoki SQL filtrują `deleted_at` publikacji). Dzieci zostają nietknięte. Wpis `SoftDeleteLog`, ślad w historii, zlecenie wycofania z PBN (patrz niżej). | Wszystko wraca: wiersz `_mat` i autorstwa w `bpp_autorzy_mat` (gałąź triggera dla `OLD.deleted_at IS NOT NULL`), punktacja przeliczana od nowa, zlecenie ponownej wysyłki do PBN. |

Guardy: książka z rozdziałami (także w koszu) nie trafia do kosza
(`Wydawnictwo_Zwarte.sprawdz_czy_mozna_do_kosza`); habilitacja ma
warunkowe unique „jedna żywa habilitacja na autora".

### Tabele łączące i dzieci publikacji — NIE (decyzja właściciela)

| Model | Dlaczego bez kosza | Jak znika |
|---|---|---|
| `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor` | Są częścią publikacji. Własny kosz oznaczał wiersze-śmieci po każdej edycji inline'a, warunkowe constrainty (`ExclusionConstraint`) i migracje największych tabel. | `BppDzieckoPublikacjiMixin`: domyślny `objects` filtruje `rekord__deleted_at IS NULL`; `all_objects` widzi wszystko. W SQL widoki `bpp_*_autorzy` mają `EXISTS` na żywą publikację (migracja `0511`). Usunięcie autora z inline'a to zwykłe, twarde kasowanie wiersza (jak przed soft-delete). |
| `*_Streszczenie`, `*_Zewnetrzna_Baza_Danych` | jw. | jw. — pod-zasoby API i „ostatnie streszczenia" ich nie pokazują. |
| `Nagroda`, `WybranaPublikacjaAutora`, `Publikacja_Habilitacyjna` (GenericFK) | jw. | GenericFK rozwiązuje się przez `_base_manager` (widzi kosz), więc filtrujemy jawnie: API nagród i profil autora (wyróżnione prace) pomijają obiekty z kosza. |

Skutek uboczny (świadomy): `publikacja.autorzy_set` na publikacji z kosza
jest pusty, a rekord z kosza w adminie jest **tylko do odczytu** — najpierw
„Przywróć". Kod, który musi zajrzeć do autorstw skasowanej publikacji (PBN,
atrybucja tenanta, guardy), używa `all_objects`/`_base_manager`
(`manager_z_koszem()`).

Znane ograniczenie: odpięcie OSTATNIEGO autora uczelni od publikacji
(twarde kasowanie wiersza `*_Autor`) nie daje nagrobka OAI — atrybucja
znika razem z wierszem. Docelowo pomoże etap 2 (historia relacji
w reversion).

### Autorzy — TAK, tylko „pusty" autor

| Model | Zasady |
|---|---|
| `Autor` | Guard: jakiekolwiek autorstwo (także publikacji z kosza), doktorat, habilitacja albo projekt → `ProtectedError`. Do kosza trafiają duplikaty, literówki, puste rekordy po scaleniu. Slug zwalniany (patrz niżej). Udziały autora z kosza **nie liczą się do liczby N** ani kalkulatora (`IloscUdzialowDlaAutora*` mają menedżer z filtrem, przeliczenie pomija autora). |
| `Autor_Jednostka`, `Autor_Dyscyplina`, `Autor_Absencja`, `Projekt_Autor` | **NIE** — dane kadrowe żyją z autorem: zostają przy nim w koszu i wracają z nim. |

### Struktura i słowniki — TAK, tylko rekord nieużywany

`BppSoftDeleteSlownikMixin`. Guard liczy powiązania przez `_base_manager`
(czyli także te w koszu).

| Model | Blokuje kosz | Zostaje przy rekordzie w koszu |
|---|---|---|
| `Uczelnia` | jednostki (także w koszu) | konfiguracja; **`site` (domena)** — uczelnia w koszu nie obsługuje domeny (`get_for_site`), ale trzyma `Site` (OneToOne NOT NULL); żeby podpiąć domenę pod inną uczelnię, usuń ją trwale z kosza |
| `Jednostka` | wszystko, co na nią wskazuje (reguła „ściśle zero" — `przeszkody_w_kasowaniu`) | — |
| `Zrodlo` | wydawnictwa ciągłe | punktacja, dyscypliny, redakcja |
| `Wydawca` | wydawnictwa zwarte, aliasy | poziomy wydawcy |
| `Konferencja` | wydawnictwa ciągłe i zwarte | — |
| `Seria_Wydawnicza` | wydawnictwa zwarte | — |

`Wydzial` nie istnieje (usunięty w #438 — wydział to korzeń drzewa
`Jednostka`). FK publikacji do `Konferencja` i `Seria_Wydawnicza` zmieniły
się z `CASCADE` na `PROTECT`: skasowanie konferencji/serii **nie kaskaduje
już twardo na publikacje** (migracja `0518`; bez zmian w bazie —
`on_delete` żyje tylko w ORM). Import (np. dopasowanie źródła po ISSN)
kosza słowników nie widzi — może utworzyć nowy rekord obok tego z kosza.

### Poza koszem

| Model | Dlaczego |
|---|---|
| słowniki systemowe (`Charakter_Formalny`, `Jezyk`, `Typ_KBN`, …) | twarde kasowanie jak dotąd |
| `bpp_rekord_mat`, `bpp_autorzy_mat` | tabele cache — trigger usuwa i odtwarza wiersze |
| `Cache_Punktacja_*` | kasowane receiverem przy koszu, przeliczane przy restore |
| `PBN_Export_Queue`, `SentData`, `pbn_api.*` | kolejka i lustro PBN |
| `SoftDeleteLog` | audyt kosza |
| `Element_Repozytorium`, `Zgloszenie_Publikacji` | mają własny, starszy soft-delete |

## Unikalne pola w koszu (slug, nazwa)

Wiersz w koszu fizycznie zostaje, a `slug`/`nazwa`/`skrot` mają
bezwarunkowe `UNIQUE`. Dlatego przy przenoszeniu do kosza
(`zwolnij_pola_unikalne`):

- slug → pierwszy wolny wariant `jan-kowalski-unexistent-1`, `-2`, …;
- nazwa/skrót → `Nazwa [kosz-1]`, `[kosz-2]`, … (przycięte do `max_length`).

Przy przywróceniu (`odzyskaj_pola_unikalne`) oryginał wraca, jeśli jest
wolny; slug zajęty → autoslug generuje nowy; nazwa zajęta →
`KonfliktPrzywracania` (komunikat w adminie — operator zmienia nazwę jednego
z rekordów). To naprawia `IntegrityError` przy tworzeniu nowego „Jana
Kowalskiego" po wyrzuceniu starego do kosza (`bpp_autor_slug_key` —
autoslug sprawdza unikalność przez domyślny menedżer, który kosza nie
widzi).

## PBN a kosz

| Sytuacja | Co się dzieje |
|---|---|
| Kosz publikacji z PBN UID | Receiver zleca `WYCOFANIE` — usuwa **oświadczenia naszej instytucji** (profil instytucji). Obiektu publikacji w repozytorium PBN nie da się usunąć (jest współdzielony). Strona potwierdzenia w adminie mówi o tym wprost. |
| Kosz publikacji, która czeka w kolejce `WYSYLKA` | Admin pyta: „rekord jest w kolejce wysyłki do PBN — trzeba go wycofać. Wycofać? Tak / Nie". **Nie** → rekord NIE trafia do kosza. **Tak** (`anuluj_wysylke_pbn=True`) → wpis zamknięty jako anulowany, zlecone wycofanie, rekord w koszu. W kodzie: `RekordWKolejcePBN` z `delete()` bez zgody. |
| Wysyłka już w toku (worker ją podjął) | Kosz zablokowany także ze zgodą — trzeba poczekać na koniec wysyłki. |
| Przywrócenie, gdy wycofanie się zakończyło | Zwykłe zlecenie `WYSYLKA` (ponowna wysyłka). |
| Przywrócenie, gdy wycofanie jeszcze czeka | Wycofanie idzie dalej; wpis dostaje `wyslij_ponownie_po_zakonczeniu=True` i po jego zakończeniu system sam zleca świeżą wysyłkę (`wyslij_ponownie_po_wycofaniu`, po commicie). Żadna operacja nie ginie po cichu. |
| Import z PBN trafia na rekord, który u nas jest w koszu | **Pomija i raportuje** (decyzja właściciela): „W PBN jest rekord X, ale u nas jest usunięty (w koszu)". Raport: admin `RekordWKoszuPominietyPrzezImport` (jeden wpis na rekord i ścieżkę, z licznikiem), log (`WARNING`), nieścisłość `record_in_trash` w raporcie sesji `pbn_import`. Rekordów z kosza import **nie wskrzesza**. Rozdział książki z kosza też jest pomijany. |
| Rekord z PBN UID w adminie (FD#539) | Usuwanie zablokowane (`RestrictDeletionWhenPBNUIDSetMixin`), ale przycisk „Usuń" jest **wyszarzony z wyjaśnieniem** zamiast znikać. Akcje masowe sprawdzają to uprawnienie per rekord. |

!!! note "Kolejka usuwania z PBN (poza tym PR)"
    Docelowo: kolejka „usuń z PBN" — wycofanie rekordu z profilu
    instytucji (sam rekord w repozytorium PBN zostaje). Gdy powstanie,
    blokada FD#539 może zniknąć: kasowanie rekordu z odpowiednikiem w PBN
    pójdzie do kosza z automatycznym wycofaniem (przepływ z tabeli wyżej
    jest na to gotowy — `stan_pbn_przed_koszem`, `zakolejkuj_wycofanie`).

## Historia zmian (reversion / LogEntry)

Kosz i przywrócenie **zawsze** zostawiają ślad w historii rekordu
(`_zapisz_wersje` w `receivers/soft_delete.py`), generycznie:

- `reversion.is_registered(model)` → **rewizja** reversion z `set_user`
  i `set_comment` („Przeniesiono do kosza (powód: …)" / „Przywrócono
  z kosza"). Dziś: `Autor` (jawnie, `bpp/wersjonowanie.py`) i `Uczelnia`
  (przez `VersionAdmin`);
- w przeciwnym razie → wpis admina `LogEntry` (CHANGE) z tym samym
  komunikatem (publikacje, słowniki, jednostki). Bez usera (operacja
  systemowa) `LogEntry` nie powstaje — śladem zostaje `SoftDeleteLog`.

Rejestracja modelu w reversion w przyszłości **automatycznie** przełącza go
na rewizje — kod kosza się nie zmienia. To planowany następny krok
(osobny PR): rejestracja praktycznie każdego modelu edytowanego w adminie
(publikacje, struktura, słowniki) — patrz
[Historia zmian (reversion)](historia-zmian-reversion.md).

Admin nie zapisuje przy koszu wpisu `DELETION` (rekord nie został usunięty).
Pola kosza są **wykluczone z treści wersji** — przywrócenie starej wersji
nie może po cichu wyjąć rekordu z kosza; dla rekordu z kosza „przywróć
wersję" jest zablokowane (najpierw „Przywróć" z kosza).

## Admin

- Lista nad `global_objects` z filtrem „Kosz" (domyślnie: tylko żywe).
- „Usuń" na rekordzie → strona potwierdzenia kosza (powód, PBN, pytanie
  o kolejkę); guard daje komunikat zamiast 500.
- Akcje: „🗑️ Usuń do kosza (z powodem)" (uprawnienie `delete`),
  „♻️ Przywróć zaznaczone" (`delete` + `change`), „❌ Usuń TRWALE"
  (superuser, tylko z kosza). Uprawnienie sprawdzane per rekord.
- Rekord z kosza: tylko do odczytu, z komunikatem.
- `/api/v1/usuniete/` pokazuje wyłącznie kosz **bieżącej uczelni**
  (instalacja wielouczelniana; brak uczelni z domeny → pusto).

## Wdrożenie: okno serwisowe

Migracje `bpp/0509`–`0518` (oraz `pbn_export_queue/0011`–`0012`,
`pbn_api/0080`, `rozbieznosci_dyscyplin/0022`, `zglos_publikacje/0029`,
`pbn_integrator/0001`, `pbn_import/0013`) dodają kolumny
`deleted_at`/`restored_at`/`transaction_id` (bez wartości domyślnej —
szybkie), **częściowe indeksy budowane bez `CONCURRENTLY`** na tabelach
publikacji i autorów (`WHERE deleted_at IS NOT NULL` — na starcie puste,
ale `CREATE INDEX` blokuje zapisy na czas skanu tabeli), przebudowują
widoki SQL i funkcje triggerów `bpp_rekord_mat`/`bpp_autorzy_mat`.
**Wdrażać w oknie serwisowym** — migracje muszą się domknąć, zanim nowy kod
zacznie obsługiwać ruch. Tabele łączące `*_autor` (największe w systemie)
nie są migrowane wcale.

## Zasady dla kodu, który dopisujesz

1. Czytasz publikacje/autorów do wyświetlenia, eksportu, liczenia →
   `objects` / `Rekord`.
2. Dopasowujesz rekordy przy imporcie, deduplikacji, scalaniu →
   `manager_z_koszem(model)` i zdecyduj jawnie, co zrobić z trafieniem
   w kosz (import PBN: pomiń i zgłoś).
3. Czytasz dziecko publikacji bez przechodzenia przez rodzica →
   `objects` dziecka już filtruje; ale lookup przez relację z innego modelu
   (`Autor.objects.filter(wydawnictwo_ciagle_autor__…)`) NIE pyta
   menedżera — dołóż `…__rekord__deleted_at__isnull=True`. GenericFK
   (nagrody, wyróżnione prace) — sprawdź `deleted_at` obiektu.
4. Nowy widok SQL czytający tabele publikacji albo `*_autor` → warunek na
   `deleted_at` **publikacji**; `test_kanarek_katalogowy.py` padnie, jeśli
   zapomnisz.
5. **Nigdy** `queryset.update(deleted_at=...)` — tylko `.delete()` /
   `.restore()` per instancja (inaczej omijasz sygnały, `SoftDeleteLog`,
   PBN i historię).
6. Nowy model z koszem i unikalnym slugiem/nazwą → `pola_unikalne_kosza`.

## Etap 2 (poza tym PR)

- **Rejestracja modeli w reversion** (publikacje, struktura, słowniki) —
  kosz automatycznie przejdzie z `LogEntry` na rewizje.
- **reversion dla relacji:** autorstwa (`*_Autor`) jako obiekty powiązane
  rewizji publikacji (`follow`) — razem z rejestracją publikacji; pozwoli
  też odtworzyć atrybucję po odpięciu autora.
- **Kolejka usuwania z PBN** (FD#539) — patrz ramka wyżej.
