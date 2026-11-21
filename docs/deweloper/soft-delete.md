# Soft-delete (kosz): co jest kasowane miękko, a co nie

!!! info "Dla kogo"
    Strona dla dewelopera i agenta AI. Opisuje stan po skonsolidowanym PR
    „Soft delete (kosz)" (zastępuje stos #312 → #745 → #755 → #767 → #792)
    i decyzje właściciela projektu z listopada 2026. Historia faz (plany,
    handoffy, recenzje) została na gałęzi `feat/soft-delete-06` — tutaj jest
    stan docelowy, nie kronika.

## Zasady (w skrócie)

1. **Kosz jest zamrożony w bazie.** Trigger `bpp_kosz_straznik`
   (`BEFORE UPDATE OR DELETE`, migracja `0523`; zgłoszenia publikacji —
   `zglos_publikacje/0031`) na każdej tabeli z koszem:
   zmiana `deleted_at`, jakikolwiek `UPDATE` wiersza w koszu i fizyczny
   `DELETE` wiersza w koszu są odrzucane, chyba że transakcja ustawiła
   `bpp.kosz_operacja = 'on'` — robi to wyłącznie `operacja_kosza()`
   w `delete()`/`restore()`/`hard_delete()`. Nieaktualna instancja nie
   „wskrzesi" rekordu, `deleted_objects.update()` ani surowy SQL nic nie
   zmienią. Błąd ma prefiks `BPP_KOSZ:`; admin tłumaczy go na komunikat.
   Wyjątek: zmiany robione przez inne triggery (dane wyliczane).
2. **Worker PBN sprawdza stan w chwili wysyłki.** Pod blokadą tuż przed
   rozmową z PBN czyta rekord od nowa: wysyłka rekordu z kosza i wycofanie
   rekordu żywego kończą się bez wysyłania („rekord w koszu" / „rekord
   przywrócony").
3. **Jedna reguła kolejki PBN, bez wyjątków.** Rekord z JAKIMKOLWIEK
   niezakończonym wpisem kolejki (czeka, podjęty, czeka na ponowienie;
   wysyłka czy wycofanie) **nie trafia do kosza i nie wraca z niego**:
   „Rekord jest w kolejce PBN — poczekaj, aż kolejka zakończy jego
   przetwarzanie." Wiszącą wysyłkę operator może usunąć z kolejki ręcznie
   (wpisy wysyłki są usuwalne; wpisy wycofania — nie). Kolejkowanie (każda
   ścieżka: admin, „Wyślij do PBN w tle", sygnały, przywrócenie, „wyślij
   ponownie") i kosz/przywrócenie biorą tę samą transakcyjną blokadę
   rekordu (`PBN_Export_Queue.objects.zablokuj_rekord`,
   `pg_advisory_xact_lock`) i pod nią sprawdzają stan: kolejkowanie odmawia
   rekordowi z kosza (`RekordWKoszuPBN`), kosz — rekordowi z wpisem; kosz
   czyta `pbn_uid` z bazy (o wycofaniu nie decyduje nieaktualna instancja).
   Worker osobno trzyma sesyjną blokadę rekordu (`klucz_blokady_rekordu`),
   żeby dwa workery nie wysłały go naraz.
4. **Konta z wpisami kolejki nie da się usunąć** (`zamowil` =
   `PROTECT`) — kto zlecił wysyłkę/wycofanie, to ślad audytu; konto się
   dezaktywuje. Admin pokazuje stronę „chronione obiekty".
5. **Wszystkie migracje tego PR-a są nieodwracalne** (poza
   `pbn_import/0013`, która zmienia tylko `choices`) — przed wdrożeniem
   kopia bazy, powrót tylko z kopii (patrz „Wdrożenie").
6. **Bez trwałego usuwania z kosza w adminie** (wyłączone; w przyszłości
   — patrz „Etap 2"). `hard_delete()` zostaje dla kodu (np. czyszczenie
   przed pełnym re-importem z PBN).
7. **Akcje masowe admina** (`zmien_hurtowo_z_historia`) pomijają rekordy
   z kosza (są zamrożone).

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
`obj.hard_delete()` naprawdę kasuje wiersz (tylko z kodu — w adminie
wyłączone). **Kaskady pakietu nie używamy** — kasowałaby twardo dzieci
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

Guardy (`sprawdz_czy_mozna_do_kosza`):

- rekord, na który wskazuje inny rekord (żywy albo z kosza), nie trafia do
  kosza — np. książka z rozdziałami, książka wskazana w zgłoszeniu jako
  nadrzędna. Lista relacji jest wyprowadzana **generycznie** z `_meta`
  (`relacje_przychodzace`) — pomijane są wyłącznie jawnie wymienione dzieci
  publikacji (`POMIJANE_RELACJE_KOSZA`);
- **praca z autorami z kilku uczelni nie trafia do kosza** — kosz jest per
  instalacja, więc jedna uczelnia wyrzuciłaby rekord drugiej (i wycofała go
  z jej PBN). Komunikat każe usunąć z rekordu autorów swojej uczelni
  i zapisać rekord;
- habilitacja ma warunkowe unique „jedna żywa habilitacja na autora" —
  przywrócenie drugiej kończy się komunikatem „Nie można przywrócić —
  autor ma już habilitację" (`KonfliktPrzywracania`, nie 500).

`delete()` rekordu już w koszu i `restore()` żywego **rzucają**
`NiedozwolonaZmianaKosza` — taki stan nie może zajść (przesunięty
`deleted_at`, drugi `SoftDeleteLog`, drugie wycofanie z PBN). Stan jest
sprawdzany w bazie pod blokadą wiersza (`SELECT … FOR UPDATE`,
`sprawdz_stan_kosza`). Admin pomija takie rekordy z komunikatem.

### Tabele łączące i dzieci publikacji — NIE (decyzja właściciela)

| Model | Dlaczego bez kosza | Jak znika |
|---|---|---|
| `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor` | Są częścią publikacji. Własny kosz oznaczał wiersze-śmieci po każdej edycji inline'a, warunkowe constrainty (`ExclusionConstraint`) i migracje największych tabel. | `BppDzieckoPublikacjiMixin`: domyślny `objects` filtruje `rekord__deleted_at IS NULL`; `all_objects` widzi wszystko. W SQL widoki `bpp_*_autorzy` mają `EXISTS` na żywą publikację (migracja `0513`). Usunięcie autora z inline'a to zwykłe, twarde kasowanie wiersza (jak przed soft-delete). |
| `*_Streszczenie`, `*_Zewnetrzna_Baza_Danych` | jw. | jw. — pod-zasoby API i „ostatnie streszczenia" ich nie pokazują. |
| `Nagroda`, `WybranaPublikacjaAutora`, `Publikacja_Habilitacyjna` (GenericFK) | jw. | GenericFK rozwiązuje się przez `_base_manager` (widzi kosz), więc filtrujemy jawnie: API nagród i profil autora (wyróżnione prace) pomijają obiekty z kosza. |

Skutek uboczny (świadomy): `publikacja.autorzy_set` na publikacji z kosza
jest pusty, a rekord z kosza w adminie jest **tylko do odczytu** — najpierw
„Przywróć". Kod, który musi zajrzeć do autorstw skasowanej publikacji (PBN,
atrybucja tenanta, guardy), używa `all_objects`/`_base_manager`
(`manager_z_koszem()`).

Odpięcie OSTATNIEGO autora uczelni od publikacji (twarde kasowanie wiersza
`*_Autor` w wydawnictwie ciągłym, zwartym albo patencie) daje nagrobek
OAI-PMH/CERIF: receiver `cerif_export.signals` zakłada wiersz
`cerif_export.OdpietaPrzynaleznosc` (publikacja × uczelnia), który trzyma
rekord w nadzbiorze `przynaleznosc`, i podbija `ostatnio_zmieniony`
publikacji (datestamp nagrobka). Gdy autor tej uczelni wróci, wiersz jest
kasowany — rekord jest znów w secie zwykłą drogą. Przepięcie istniejącego
autorstwa do jednostki innej uczelni (edycja, nie kasowanie) nagrobka nie
daje.

### Autorzy — TAK, tylko „pusty" autor

| Model | Zasady |
|---|---|
| `Autor` | Liczba N: autor w koszu nie liczy się do N przy **przeliczeniu** — kosz/przywrócenie autora wymaga ręcznego przeliczenia N (jak ewaluacji). Guard: wskazuje na niego jakikolwiek rekord — autorstwo (także publikacji z kosza), doktorat (także jako **promotor**), habilitacja, projekt, **redakcja źródła**, **autor zgłoszenia**, konto użytkownika — → `ProtectedError`. Lista generyczna z `_meta`; pomijane jawnie (`POMIJANE_RELACJE_KOSZA_AUTORA`) tylko dane kadrowe, dane wyliczane, logi i wiersze importów/deduplikacji. Do kosza trafiają duplikaty, literówki, puste rekordy po scaleniu.  |
| `Autor_Jednostka`, `Autor_Dyscyplina`, `Autor_Absencja`, `Projekt_Autor` | **NIE** — dane kadrowe żyją z autorem: zostają przy nim w koszu i wracają z nim. Domyślny menedżer `Autor_Dyscyplina.objects` ukrywa wiersze autorów z kosza (raport zerowy, dwudyscyplinowcy, liczba N, optymalizacja, metryki — autor z kosza w nich nie występuje); `all_objects` widzi wszystko. Metryki pomijają też wiersze udziałów autora z kosza do czasu przeliczenia N. |

### Uczelnia i słowniki — TAK, tylko rekord nieużywany

`BppSoftDeleteSlownikMixin`. Guard bierze **wszystkie** przychodzące FK
(`relacje_przychodzace`) poza jawnie pominiętymi (`pomijane_relacje_kosza`)
i liczy powiązania przez `_base_manager` (czyli także te w koszu).

**`Jednostka` — NIE ma kosza i nie kasuje się jej wcale** (decyzja
właściciela): zamrożony rekord w drzewie MPTT blokowałby przeliczanie
`lft`/`rght`/`tree_id` sąsiadów. `delete()` i `QuerySet.delete()` rzucają
`JednostkaNieDoUsuniecia` („ukryj jednostkę — odznacz »Widoczna«"), admin
nie ma uprawnienia ani akcji usuwania.

| Model | Blokuje kosz | Zostaje przy rekordzie w koszu |
|---|---|---|
| `Uczelnia` | jednostki (także w koszu), użytkownicy z dostępem do uczelni | konfiguracja; **`site` (domena)** — uczelnia w koszu nie obsługuje domeny (`get_for_site`), ale trzyma `Site` (OneToOne NOT NULL); żeby podpiąć domenę pod inną uczelnię, usuń ją trwale z kosza |
| `Zrodlo` | wydawnictwa ciągłe | punktacja, dyscypliny, redakcja |
| `Wydawca` | wydawnictwa zwarte, doktoraty, habilitacje, aliasy, zgłoszenia | poziomy wydawcy |
| `Konferencja` | wydawnictwa ciągłe i zwarte | — |
| `Seria_Wydawnicza` | wydawnictwa zwarte | — |

`Wydzial` nie istnieje (usunięty w #438 — wydział to korzeń drzewa
`Jednostka`). FK publikacji do `Konferencja` i `Seria_Wydawnicza` zmieniły
się z `CASCADE` na `PROTECT`: skasowanie konferencji/serii **nie kaskaduje
już twardo na publikacje** (migracja `0510_slowniki_protect`; bez zmian w bazie —
`on_delete` żyje tylko w ORM). Import (np. dopasowanie źródła po ISSN)
kosza słowników nie widzi przy dopasowaniu, ale **nie tworzy duplikatu
wartości unikalnej trzymanej przez rekord z kosza**: import PBN (wydawcy,
autorzy), importer autorów PBN i komendy `import_wydawca_*` sprawdzają kosz
(`pbn_integrator.kosz.pomin_jesli_koliduje`) — trafienie w kosz = pomiń
i zgłoś (`RekordWKoszuPominietyPrzezImport`), nigdy nie wskrzeszaj.

### Zgłoszenia publikacji — TAK

`Zgloszenie_Publikacji` jest w tym samym koszu co reszta
(`BppSoftDeleteSlownikMixin`, trigger `zglos_publikacje/0031`). Wcześniej
(od 2024, #1468) miało własny, starszy soft-delete pakietu — z jego kaskadą,
która przy kasowaniu **twardo** usuwała autorów i załączniki zgłoszenia,
a w adminie nie dało się skasowanych zgłoszeń ani zobaczyć, ani przywrócić.

| Model | Zasady |
|---|---|
| `Zgloszenie_Publikacji` | Nic nie blokuje kosza (autorzy, załączniki i sesje importu są pominięte w guardzie). Admin jak wszędzie: filtr „♻️ Kosz" (ostatni; „🗑️ Tylko skasowane" wyłącza domyślne zawężenie „stan obsługi → Do obsługi", więc pokazuje też spam i odrzucone), „Usuń do kosza" z powodem, „♻️ Przywróć" (akcja i przycisk). Formularz zgłoszenia w adminie nigdy nie jest edytowalny, więc przywracanie sprawdza uprawnienie `change` użytkownika wprost (`moze_przywracac`). Zgłoszenie z kosza nie ma przycisków „Użyj importera", „Zwróć do autora", „Dodaj wyd. …"; `zwroc/` daje 404. Strona publiczna: link „edycja zgłoszenia" (kod z e-maila) daje 404; `numer_zgloszenia` w formularzu publikacji go nie widzi; importer nie domyka zgłoszenia z kosza i nie bierze z niego dyscyplin ani opłat. Ślad: `SoftDeleteLog` + `LogEntry` (model spoza reversion). `/api/v1/` zgłoszeń nie wystawia — nie ma ich w `/api/v1/usuniete/`. |
| `Zgloszenie_Publikacji_Autor`, `Zgloszenie_Publikacji_Zalacznik` | **NIE** — jak `*_Autor` publikacji: domyślny `objects` ukrywa wiersze zgłoszeń z kosza, `all_objects` widzi wszystko; wracają przy przywróceniu. |

Zgłoszenia skasowane starym mechanizmem mają te same kolumny
(`deleted_at`, `restored_at`, `transaction_id`, migracja `0016`), więc
**od razu są w koszu** — migracja danych nie jest potrzebna. Ich autorów
i załączników nie da się odzyskać (stara kaskada skasowała je twardo);
przywrócone takie zgłoszenie wraca bez nich.

### Poza koszem

| Model | Dlaczego |
|---|---|
| słowniki systemowe (`Charakter_Formalny`, `Jezyk`, `Typ_KBN`, …) | twarde kasowanie jak dotąd |
| `bpp_rekord_mat`, `bpp_autorzy_mat` | tabele cache — trigger usuwa i odtwarza wiersze |
| `Cache_Punktacja_*` | kasowane receiverem przy koszu, przeliczane przy restore |
| `PBN_Export_Queue`, `SentData`, `pbn_api.*` | kolejka i lustro PBN |
| `SoftDeleteLog` | audyt kosza |
| `Element_Repozytorium` | ma własny, starszy soft-delete |

## Unikalne pola w koszu (slug, nazwa, ORCID, PBN UID, …)

Rekord w koszu **zachowuje wszystkie swoje wartości unikalne** (decyzja
właściciela): link `/jan-kowalski/` zostaje na zawsze, nazwa, skrót, ORCID,
PBN UID, `pbn_id`, `expertus_id`, `system_kadrowy_id` — też.

- **slug:** autoslug sprawdza unikalność razem z koszem
  (`AutoSlugField(manager_name="global_objects")` dla `Autor`,
  `Uczelnia`, `Zrodlo`, `Wydawca`), więc nowy „Jan Kowalski" dostaje po
  prostu kolejny slug (`jan-kowalski-2`). To naprawia `IntegrityError` na
  `bpp_autor_slug_key`;
- **pozostałe pola unikalne:** wpisanie w formularzu wartości trzymanej
  przez rekord z kosza kończy się **błędem walidacji** z linkiem do tamtego
  rekordu: „Ta wartość należy do rekordu w koszu: … Zamiast wpisywać ją
  tutaj, przywróć tamten rekord z kosza" (`BppUnikalnoscZKoszemMixin.
  validate_unique` — Django sprawdza unikalność przez domyślny menedżer,
  który kosza nie widzi, więc bez tego był `IntegrityError`/500). To samo
  dotyczy deduplikacji (PBN UID trzymany przez duplikat w koszu) —
  integracja PBN (`ustaw_pbn_uid_jesli_brak`) pomija taki rekord
  i raportuje go jak import;
- **przywrócenie** niczego nie odzyskuje; jeśli mimo to łamie ograniczenie
  (np. warunkowe „jedna żywa habilitacja"), kończy się
  `KonfliktPrzywracania` z czytelnym komunikatem.

## PBN a kosz

Egzekwowane w warstwie modelu (nie tylko w adminie): reguła z punktu 3
„Zasad" — niezakończony wpis kolejki blokuje kosz i przywrócenie
(`RekordWKolejcePBN`), sprawdzana pod wspólną blokadą rekordu w tej samej
transakcji co zapis kosza/przywrócenia (`pbn_export_queue/operacje.py`).
Aktywnego zlecenia WYCOFANIA nie da się usunąć z kolejki ani wysłać
ponownie ręcznie (`WycofanieZablokowane`); wpis wysyłki — można usunąć.

**Ręczne operacje na kolejce.** Na zleceniach wycofania nie ma ŻADNYCH
ręcznych operacji (usuń, wyślij ponownie, „spróbuj wysłać") — także po
zakończeniu: to historia. Wpisu wysyłki, który worker właśnie wysyła (trzyma
blokadę rekordu), nie da się usunąć (`WpisWTrakcieWysylki`). Sprzątaczka
(`kolejka_wyczysc_wpisy_bez_rekordow`) usuwa wyłącznie wpisy wysyłki rekordów
fizycznie nieistniejących — historia wysyłek rekordów z kosza zostaje.

**Wycofanie nigdy nie kończy się błędem — zostaje w kolejce, aż się uda.**
Wygasły token albo konto bez tokenu (np. techniczne `bpp-system`) → wpis
czeka na zalogowanie do PBN (`retry_after_user_authorised`); każdy inny
błąd → ponowienie z rosnącym odstępem (do 6 h,
`PBN_Export_Queue.odstep_ponowienia`). Do tego czasu rekord stoi w koszu,
jego oświadczenia w PBN, a przywrócić go nie można (jedna reguła kolejki).
„Nie ma czego wycofać" (PBN nie ma oświadczeń albo nie zna publikacji —
HTTP 404) jest sukcesem. Dla wpisów `bpp-system` ustaw temu kontu
`przedstawiaj_w_pbn_jako` na konto z ważnym tokenem — logowanie tamtego
konta ponowi oczekujące wycofania. Wyjątek: rekord skasowany FIZYCZNIE
(nie ma skąd odczytać PBN UID) kończy wpis błędem.

| Sytuacja | Co się dzieje |
|---|---|
| Kosz publikacji z PBN UID | Receiver zleca `WYCOFANIE` — usuwa **oświadczenia naszej instytucji** (profil instytucji). Obiektu publikacji w repozytorium PBN nie da się usunąć (jest współdzielony). Strona potwierdzenia mówi o tym wprost. |
| Kosz, gdy rekord ma **jakikolwiek niezakończony wpis** kolejki (czeka, podjęty, czeka na ponowienie, wysyłka po przywróceniu, wycofanie) | Odmowa: „Rekord jest w kolejce PBN — poczekaj, aż kolejka zakończy jego przetwarzanie." Wiszącą wysyłkę można usunąć z kolejki ręcznie. |
| Kolejkowanie rekordu z kosza (dowolna ścieżka, także „wyślij ponownie") | Odmowa (`RekordWKoszuPBN`). Wycofanie zleca sam kosz. |
| Przywrócenie, gdy wycofanie **jeszcze się nie zakończyło** | Odmowa (ta sama reguła). |
| Przywrócenie po **zakończonym** wycofaniu | Od razu zlecana wysyłka — **tylko gdy rekord ma PBN UID**. Do jej końca rekord znów nie trafi do kosza (ta sama reguła). |
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
  z kosza"). Dziś: `Autor` i `Uczelnia` (jawnie, `bpp/wersjonowanie.py`,
  BEZ pól kosza `deleted_at`/`restored_at`/`transaction_id` — przywrócenie
  wersji nie może ominąć `delete()`/`restore()`);
- w przeciwnym razie → wpis admina `LogEntry` (CHANGE) z tym samym
  komunikatem (publikacje, słowniki). Bez usera (operacja
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

- Lista nad `global_objects` z filtrem „♻️ Kosz" (domyślnie: tylko żywe),
  zawsze **ostatnim** w panelu filtrów.
- „Usuń" na rekordzie → strona potwierdzenia kosza (powód, PBN, pytanie
  o kolejkę); guard daje komunikat zamiast 500.
- Strona „Nie można przenieść do kosza" **wylicza blokujące rekordy**:
  guard rzuca `BlokadaKosza` (podklasa `ProtectedError`) z listą
  `GrupaBlokady` per relacja (`grupa_blokady` — jedno zapytanie na relację:
  próbka `LIMIT_POZYCJI_BLOKADY` = 15 wierszy, najpierw te w koszu, plus
  `COUNT(*) OVER ()` całości i rekordów w koszu). Pozycje linkują do strony
  rekordu w adminie (wiersze `*_Autor` — do publikacji), rekordy z kosza są
  oznaczone „🗑️ w koszu"; reszta to „…i jeszcze N". Etykiety grup:
  `ETYKIETY_RELACJI_KOSZA`, poza nimi — z `_meta`. Tak samo pokazywane są
  autorzy per uczelnia (praca wielouczelniana), habilitacje wskazujące
  publikację i wpis kolejki PBN (`grupa_blokady_kolejki`).
- Strony kosza (potwierdzenie, blokada, akcja z powodem) używają markupu
  Grappelli (`grp-module`, `grp-row`, `grp-submit-row`), bez własnego CSS.
- Rekord z kosza ma na dole przycisk „♻️ Przywróć" (`<pk>/przywroc/`,
  tylko POST; te same uprawnienia `delete` + `change` i reguły co akcja
  „Przywróć zaznaczone", w tym blokada kolejki PBN).
- Akcje: „🗑️ Usuń do kosza (z powodem)" (uprawnienie `delete`),
  „♻️ Przywróć zaznaczone" (`delete` + `change`). Uprawnienie sprawdzane
  per rekord. Trwałego usuwania z kosza w adminie nie ma.
- Lista i szczegóły kolejki eksportu PBN dla rekordu z kosza pokazują
  „rekord w koszu" zamiast opisu.
- Rekord z kosza: tylko do odczytu, z komunikatem.
- `/api/v1/usuniete/` pokazuje wyłącznie kosz **bieżącej uczelni**
  (instalacja wielouczelniana; brak uczelni z domeny → pusto);
  `/api/v1/autor_jednostka/` i `/api/v1/poziom_wydawcy/` pomijają wiersze
  rodziców z kosza.
- Autocomplete admina nie podsuwa rekordów z kosza; przekierowanie
  `global-nav-redir` dla rekordu z kosza daje 404 (nie zdradza sluga).
- Publikacja wskazana w habilitacji (`Publikacja_Habilitacyjna`, GenericFK)
  nie trafi do kosza — GenericFK sprawdzamy jawnie.
- Scalanie autorów przepina pracę dyplomową z kosza wyłącznie w kolumnie
  autora (`update`), bez pełnego `save()` nieaktualnej instancji.

## Wdrożenie: okno serwisowe

Migracje `bpp/0511`–`0523` (oraz `pbn_export_queue/0011`–`0012`,
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

### Migracje nieodwracalne — przed wdrożeniem zrób kopię bazy; powrót tylko z kopii

Wszystkie migracje tego PR-a — `bpp/0511`–`0523`, `cerif_export/0001`,
`pbn_api/0080`, `pbn_export_queue/0011`–`0012`, `pbn_integrator/0001`,
`rozbieznosci_dyscyplin/0022`, `zglos_publikacje/0029`, `0031` — **nie mają
kroku wstecz** (decyzja właściciela). Wyjątek: `pbn_import/0013` zmienia tylko
`choices` (cofnięcie nic nie gubi). `migrate` w tył przez którąkolwiek
z nich rzuca `IrreversibleError`, zanim cokolwiek zmieni w bazie.
Migracje z kodem (`RunPython`/`RunSQL`) po prostu nie mają
`reverse_code`/`reverse_sql`; czysto schematowe kończą się operacją
`bpp.migration_util.nieodwracalna()`. Powód: cofnięcie zgubiłoby dane,
których stary kod nie umie odtworzyć — rekordy w koszu wróciłyby jako
żywe, wpisy „wycofanie" w kolejce PBN zamieniłyby się w wysyłki, a
sprzątnięte wiersze `_mat`, skasowane widoki `bpp_kronika_*` i trigger
zamrożenia kosza musiałyby być odtwarzane ręcznie.

**Przed wdrożeniem zrób kopię bazy; powrót do wersji sprzed kosza — tylko
z tej kopii** (razem z obrazem aplikacji sprzed wdrożenia). Pilnuje tego
`bpp/tests/test_soft_delete/test_migracje_nieodwracalne.py`. Testy e2e
migracji `pbn_api` cofają i ponownie stosują wyłącznie własne migracje
(`pbn_api/tests/migracje_e2e_utils.py`: `cofnij_tylko`/`zastosuj_tylko`),
nie cały graf — „`migrate pbn_api 0077`" pociągnęłoby za sobą ten łańcuch.

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
6. Nowy model z koszem: `AutoSlugField(..., manager_name="global_objects")`
   dla sluga; `BppUnikalnoscZKoszemMixin` daje walidację pól unikalnych;
   nowa relacja do modelu z koszem jest chroniona przez guard domyślnie —
   jeśli to dane „przy rekordzie", dopisz ją do listy pomijanych.

## Świadomie zaakceptowane

- **Wyścig guard ↔ zapis**: między sprawdzeniem „nic nie wskazuje na ten
  słownik/publikację" a zapisem kosza równoległy zapis może dodać
  odwołanie (milisekundy). Nie blokujemy tego dodatkowo.
- **Migracje nieodwracalne**: zamiast utrzymywać kroki wstecz (widoki,
  funkcje triggerów, sidecar `bpp_kronika_*`), których nikt nie użyje
  produkcyjnie — powrót wyłącznie z kopii bazy (patrz „Wdrożenie").
- **Przyszłe migracje danych** na tabelach z koszem, które mają objąć
  rekordy z kosza, muszą ustawić `bpp.kosz_operacja` (trigger).
- **Zmiany słowników „przez" rekord z kosza** (np. skasowanie słownika
  z `SET_NULL`/`CASCADE` do rekordu w koszu) są odrzucane — rekord
  w koszu jest zamrożony.

## Etap 2 (poza tym PR)

- **Trwałe usuwanie z kosza w adminie** (opróżnianie kosza) — wymaga
  decyzji co do niezakończonych wycofań z PBN.

- **Rejestracja modeli w reversion** (publikacje, struktura, słowniki) —
  kosz automatycznie przejdzie z `LogEntry` na rewizje.
- **reversion dla relacji:** autorstwa (`*_Autor`) jako obiekty powiązane
  rewizji publikacji (`follow`) — razem z rejestracją publikacji; pozwoli
  też odtworzyć atrybucję po odpięciu autora.
- **Kolejka usuwania z PBN** (FD#539) — patrz ramka wyżej.
