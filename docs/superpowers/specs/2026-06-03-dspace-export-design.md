# Eksport publikacji BPP → DSpace (REST API)

Data: 2026-06-03
Status: projekt zaakceptowany w brainstormingu, do review przed planem implementacji

## 1. Cel

Umożliwić wysyłanie rekordów publikacji z BPP do zewnętrznych instalacji
DSpace (cel: **DSpace 9.x**) przez REST API. Operator wybiera rekordy w
adminie i wyzwala wysyłkę akcją (jak przy integracji PBN).

Model jest **wielouczelniany (multi-hosted)**: jeden rekord może być
afiliowany do wielu uczelni (przez autorów: `autor → jednostka →
uczelnia`). Każda uczelnia ma **własną** instalację DSpace, własną
konfigurację i własne kolekcje. Eksport rekordu to **wachlarz**: rekord
leci do DSpace każdej uczelni, do której jest afiliowany **i** która ma
skonfigurowany DSpace; dla afiliowanych uczelni bez konfiguracji →
ostrzeżenie na UI.

W obrębie jednej uczelni: rekord trafia do kolekcji dobranej po
`Charakter_Formalny`. Pliki jawne są dołączane jako bitstreamy; przy ich
braku powstaje item metadanowy ze streszczeniem.

## 2. Decyzje (ustalone)

- **Wyzwalanie:** akcja w adminie (sync + w tle), wzorzec `pbn_api`.
  Brak nowego pola na modelach publikacji — stan żyje w `SentToDSpace`.
- **Wielouczelnianość:** uczelnie rekordu wyprowadzane z afiliacji:
  `{ powiazanie.jednostka.uczelnia for powiazanie in rec.autorzy_set }`
  (`Wydawnictwo_X_Autor.jednostka` → `Jednostka.uczelnia`). Eksport to
  wachlarz po tych uczelniach.
- **Konfiguracja jako pola wprost na `Uczelnia`** (spójnie z istniejącymi
  integracjami: `clarivate_password`, `orcid_client_secret`,
  `pbn_app_token` są już polami `Uczelnia`). Endpoint + poświadczenia w DB
  (self-service), edytowane w adminie Uczelni. **Hasło szyfrowane**
  współdzielonym `EncryptedTextField` (Fernet).
  - Uwaga faktograficzna: `baseline.sql` **nie** zrzuca tego hasła —
    dumpuje schemat wszystkich tabel, ale dane tylko ze słowników
    (~34 tabele); `bpp_uczelnia` idzie z 0 wierszy. Szyfrowanie jest dla
    realnych wektorów: pełne backupy bazy, `dbshell`/`psql`, ad-hoc
    exporty — defense-in-depth, nie ochrona przed CI-dumpem.
- **Routing (per uczelnia):** mapa `(Uczelnia, Charakter_Formalny) →
  collection UUID`. Charakter bez wpisu dla danej uczelni → rekord do tej
  uczelni **NIE jest wysyłany**, operator dostaje ostrzeżenie na UI z
  konkretną przyczyną. Edycja mapy w sekcji **„Dane systemowe"**.
- **Pliki:** dołączamy wyłącznie `Element_Repozytorium` z
  `tryb_dostepu == jawny`. Brak jawnego pliku → item metadanowy (DSpace
  pozwala na item bez bitstreamu). `streszczenie` zawsze ląduje w
  `dc.description.abstract` (jeśli niepuste).
- **Zakres MVP typów:** `Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte`,
  `Patent`, `Praca_Doktorska`, `Praca_Habilitacyjna`.
- **Biblioteka:** `dspace-rest-client` (PyPI, BSD-3, the-library-code).
  Obsługuje XSRF+Bearer auth, item-w-kolekcji, bundle+bitstream. REST
  Contract jest wspólny dla DSpace 7–9, więc 9.x jest pokryte; weryfikacja
  na testowej instalacji early.

## 3. Architektura — nowa app `src/dspace_api/`

Lustro `src/pbn_api/`:

```
src/dspace_api/
├── client.py                     # otoczka na dspace-rest-client:
│                                 #   auth, retry, logging, mapowanie wyjątków
├── conf/settings.py              # ewentualne defaulty/feature-flag
├── selectors.py                  # uczelnie_rekordu(rec) -> set[Uczelnia]
├── adapters/
│   ├── base.py                   # wspólne DC (tytuł, autorzy, rok,
│   │                             #   streszczenie, słowa kluczowe, jezyk, doi)
│   ├── wydawnictwo_ciagle.py
│   ├── wydawnictwo_zwarte.py
│   ├── patent.py
│   ├── praca_doktorska.py
│   └── praca_habilitacyjna.py
├── models/
│   ├── mapowanie.py              # Mapowanie_DSpace (scope per Uczelnia)
│   └── sentdata.py               # SentToDSpace (scope per Uczelnia)
├── admin.py                      # Mapowanie w „Dane systemowe”
├── tasks.py                      # celery batch
├── management/commands/
│   └── dspace_wyslij.py          # bulk/cron
└── tests/

src/bpp/fields.py                 # EncryptedTextField (Fernet) — WSPÓŁDZIELONY,
                                  #   używany przez pola dspace_* na Uczelni,
                                  #   docelowo też retrofit clarivate/orcid/pbn
```

Konfiguracja DSpace = nowe pola na `src/bpp/models/uczelnia.py` (patrz 4.1).

**Zależność:** `dspace-rest-client`, `cryptography` (Fernet) → `pyproject.toml`.

## 4. Modele

### 4.1 Pola DSpace na `Uczelnia`

Nowe pola na `src/bpp/models/uczelnia.py` (spójnie z istniejącymi
`clarivate_*`, `orcid_*`, `pbn_app_token`). Edytowalne w adminie Uczelni.

| pole | typ | uwagi |
|---|---|---|
| `dspace_aktywny` | Boolean | feature-flag wysyłki dla tej uczelni |
| `dspace_api_endpoint` | URLField | np. `https://repo.uczelnia.pl/server/api` |
| `dspace_api_username` | CharField | jawne |
| `dspace_api_password` | `EncryptedTextField` | **szyfrowane Fernet** |
| `dspace_domyslny_jezyk_dc` | CharField | fallback dla `dc.language.iso` |

`EncryptedTextField` (`src/bpp/fields.py`, współdzielony):
- Klucz Fernet z env (`DSPACE_CREDENTIALS_KEY`, fallback dedykowany — NIE
  cichy fallback do plaintextu; brak klucza = błąd przy zapisie/odczycie).
- Szyfruje w `get_prep_value`, deszyfruje w `from_db_value`. W DB leży
  base64 szyfrogramu.
- **Utrata klucza = nieodwracalna utrata sekretu** (trzeba wpisać hasło
  ponownie). Świadomy trade-off: dump bazy bez klucza jest bezużyteczny.

### 4.2 `Mapowanie_DSpace` (scope per uczelnia)

| pole | typ | uwagi |
|---|---|---|
| `uczelnia` | FK(`Uczelnia`) | której instalacji dotyczy mapa |
| `charakter_formalny` | FK(`Charakter_Formalny`) | |
| `collection_uuid` | UUIDField | docelowa kolekcja w DSpace tej uczelni |
| `opis` | CharField | dla operatora |

`unique_together = (uczelnia, charakter_formalny)`.

### 4.3 `SentToDSpace` (scope per uczelnia; wzorzec `pbn_api.SentData`)

| pole | typ |
|---|---|
| `content_type` + `object_id` | GenericForeignKey → dowolny rekord |
| `uczelnia` | FK(`Uczelnia`) — do której instalacji wysłano |
| `dspace_uuid` | UUIDField, null — UUID utworzonego itemu |
| `bitstreams` | JSONField, default dict — mapa `Element_Repozytorium.id → bitstream UUID` (do reconciliation) |
| `data_sent` | JSONField — wysłany dict DC (do diff/skip) |
| `data_hash` | CharField — hash do szybkiego „czy się zmieniło" |
| `submitted_successfully` | Boolean |
| `submitted_at` | DateTimeField, null |
| `exception` | TextField — błąd, jeśli był |
| `api_response_status` | TextField |
| `last_updated_on` | DateTimeField, auto_now |

`unique_together = (content_type, object_id, uczelnia)` — jeden wpis na
parę (rekord, uczelnia). Manager: `get_for_rec_uczelnia`,
`check_if_upload_needed`, `mark_as_successful`, `mark_as_failed`.

## 5. Przepływ wysyłki jednego rekordu (wachlarz)

```
rec
 ├─ uczelnie = selectors.uczelnie_rekordu(rec)        # przez afiliacje autorów
 │     (distinct po jednostka.uczelnia; select_related("jednostka__uczelnia"))
 └─ for uczelnia in uczelnie:
      ├─ brak uczelnia.dspace_api_endpoint / !uczelnia.dspace_aktywny → WARNING
      │     „rekord afiliowany do {uczelnia}: brak/nieaktywny DSpace → pominięto” ; continue
      ├─ collection = Mapowanie_DSpace[uczelnia, rec.charakter_formalny]
      │     └─ brak → WARNING „charakter {x} bez mapowania DSpace dla {uczelnia}” ; continue
      ├─ dc_dict = adapter_for(rec).to_dspace_dict(domyslny_jezyk=uczelnia.dspace_domyslny_jezyk_dc)
      ├─ sent = SentToDSpace.get_for_rec_uczelnia(rec, uczelnia)
      │     └─ check_if_upload_needed(sent, dc_dict): bez zmian → SKIP (info)
      ├─ client = DSpaceClient(uczelnia)    # auth per uczelnia (endpoint/login/hasło z Uczelni)
      ├─ nowy:    item = client.create_item(collection, dc_dict)
      │  istnieje: client.patch_item(sent.dspace_uuid, dc_dict)
      ├─ RECONCILE bitstreamów (jawne pliki Element_Repozytorium):
      │     aktualne = {el.id: el for el in jawne_pliki_rekordu(rec)}  # żywe, jawny, ma plik
      │     poprzednie = sent.bitstreams                               # {element_id: bitstream_uuid}
      │     bundle = client.ensure_bundle(item, 'ORIGINAL')
      │     for el_id in aktualne - poprzednie:                        # nowe → upload
      │         poprzednie[el_id] = client.create_bitstream(bundle, aktualne[el_id])
      │     for el_id in poprzednie - aktualne:                        # usunięte/soft-del/nie-jawne → kasuj w DSpace
      │         client.delete_bitstream(poprzednie.pop(el_id))
      └─ SentToDSpace.mark_as_successful(rec, uczelnia, dspace_uuid, bitstreams=poprzednie)
```

- Item tworzony **bezpośrednio w kolekcji** (POST `items?owningCollection=`),
  z pominięciem workflow submission → konto API każdej uczelni musi mieć
  prawa collection-admin/admin w swoim DSpace.
- **Re-wysyłka:** zmienione metadane → PATCH istniejącego itemu (per
  uczelnia, po `SentToDSpace.dspace_uuid`).
- **Reconciliation bitstreamów (w zakresie):** `Element_Repozytorium`
  zyskuje `plik` (FileField) i dziedziczy `SoftDeleteModel` (paczka
  `django-soft-delete`). Mapa `Element_Repozytorium.id → bitstream UUID`
  żyje w `SentToDSpace.bitstreams` (JSONField). Przy każdej udanej wysyłce
  (create i patch) liczymy różnicę: nowe pliki wgrywamy, a pliki usunięte
  (hard- lub soft-delete) albo już-nie-jawne **kasujemy też po stronie
  DSpace** (`delete_bitstream`). Soft-delete sprawia, że usunięty plik
  automatycznie wypada z `jawne_pliki_rekordu` (domyślny manager `objects`
  pomija `is_deleted`), więc trafia do zbioru „do skasowania".

## 6. Mapowanie metadanych (Dublin Core)

Wspólne (`base.py`):

| BPP | DSpace |
|---|---|
| `tytul_oryginalny` | `dc.title` |
| autorzy `Nazwisko, Imię` | `dc.contributor.author` (po jednym) |
| redaktorzy | `dc.contributor.editor` |
| `rok` | `dc.date.issued` |
| `streszczenie` (+ `jezyk_streszczenia`) | `dc.description.abstract` (z `language`) |
| `slowa_kluczowe`, `slowa_kluczowe_eng` | `dc.subject` |
| `doi` | `dc.identifier.doi` |
| `jezyk` | `dc.language.iso` |
| `charakter_formalny` | `dc.type` |

Per-typ (`dc.type` wg słownika COAR/DRIVER):

| model | `dc.type` | dodatkowe |
|---|---|---|
| `Wydawnictwo_Ciagle` | `article` | `zrodlo`→`dc.relation.ispartof`, `issn`→`dc.identifier.issn`, `tom`/`strony` |
| `Wydawnictwo_Zwarte` | `book` / `bookPart` | `wydawca`→`dc.publisher`, `isbn`→`dc.identifier.isbn`, `miejsce_wydania` |
| `Patent` | `patent` | numer/data zgłoszenia → `dc.identifier` / `dc.date` |
| `Praca_Doktorska` | `doctoralThesis` | promotor → `dc.contributor.advisor` |
| `Praca_Habilitacyjna` | `Thesis` (lub custom) | — |

Dokładny zestaw pól per-typ doprecyzowany przy implementacji adaptera
(TDD: najpierw test z oczekiwanym dict).

## 7. Wyzwalanie (admin)

Dwie akcje na adminie publikacji (jak `wyslij_do_pbn` / `…_w_tle`):

- `wyslij_do_dspace` — synchronicznie, limit ~10, komunikaty od ręki.
- `wyslij_do_dspace_w_tle` — celery batch, limit ~2000.

Każda akcja robi wachlarz po uczelniach rekordu. Wynik raportowany
zbiorczo przez `message_user`: ile wysłano/zaktualizowano/pominięto, z
rozbiciem przyczyn pominięć per uczelnia (brak konfiguracji / brak
mapowania charakteru).

Konfiguracja DSpace: inline na adminie `Uczelnia`. Mapowania: osobny
admin w „Dane systemowe". Management command `dspace_wyslij` do cron/bulk.

## 8. Bezpieczeństwo

- Hasło API: `EncryptedTextField` (Fernet, klucz z env). W DB tylko
  szyfrogram → backupy bazy / `dbshell` / exporty nie ujawniają hasła.
  (Baseline `baseline.sql` i tak nie zawiera danych `bpp_uczelnia` — to
  ochrona przed innymi wektorami, nie przed CI-dumpem.)
- Pliki: tylko `tryb_dostepu == jawny`; niejawne / „tylko w sieci"
  **nigdy** nie opuszczają BPP.
- Izolacja uczelni: wysyłka do uczelni X używa wyłącznie konfiguracji i
  mapowań uczelni X — brak ryzyka wysłania do cudzego DSpace.
- Brak `except: pass` — wyjątki z API logowane do `SentToDSpace.exception`
  + Rollbar w tasku tła, i re-raise/zwrot błędu zgodnie z regułami repo.

## 9. Testy

- `selectors.uczelnie_rekordu`: rekord z autorami z różnych uczelni →
  poprawny zbiór; autor bez jednostki/uczelni → obsłużony.
- `adapters/*`: czyste testy jednostkowe — rekord (model_bakery) → dict;
  asercja na strukturę DC. Bez sieci.
- wachlarz: rekord afiliowany do 2 uczelni, jedna skonfigurowana, druga
  nie → 1 wysyłka + 1 warning.
- `client.py`: mock `dspace-rest-client` (bez realnego DSpace w CI).
- `EncryptedTextField`: round-trip + brak plaintextu w surowej kolumnie.
- Smoke-test end-to-end na testowej instalacji DSpace 9.x — manualnie /
  poza CI (wymaga sekretów i żywego serwera).

## 10. Poza MVP (v2)

- Kopiowanie plików `zglos_publikacje` → `Element_Repozytorium` przy
  akceptacji zgłoszenia (osobny PR — patrz §10b). Bez tego `Element_Repozytorium`
  zapełnia operator ręcznie (upload w inline adminie).
- Streszczenie jako pobieralny załącznik (`.txt`/`.pdf`), jeśli zajdzie potrzeba.
- Mapowanie do schematów custom DSpace-CRIS (autorytety autorów, afiliacje).
- Pozostałe typy rekordów, jeśli się pojawią.

### 10a. Follow-up (osobny PR): szyfrowanie istniejących sekretów

`EncryptedTextField` powstaje w `src/bpp/fields.py` jako współdzielony.
Po wdrożeniu DSpace można nim owinąć istniejące, dziś-plaintextowe pola:

- `Uczelnia.clarivate_password`, `Uczelnia.orcid_client_secret`,
  `Uczelnia.pbn_app_token`,
- `BppUser.pbn_token` (per-user).

Wymaga **data-migracji** (odczyt plaintext → zapis szyfrogram, w środowisku
z dostępnym kluczem) i dotyka żywych ścieżek auth PBN/ORCID/Clarivate →
**robione osobnym PR-em**, nie wmieszane w feature DSpace (izolacja ryzyka
regresji). Ten sam field, dwa rozłączne wdrożenia.

### 10b. Follow-up (osobny PR): kopiowanie zgłoszeń → Element_Repozytorium

Wynik spike'u Task 20: realne bajty plików **nie** są w `Element_Repozytorium`
(to był metadanowy wskaźnik dla OAI/Primo), lecz w module `zglos_publikacje`
(`Zgloszenie_Publikacji.plik` + `Zgloszenie_Publikacji_Zalacznik.plik`,
Django FileField w `protected/`), spięte z rekordem przez `odpowiednik_w_bpp`
(GenericFK) / `wydawnictwo_nadrzedne` (FK `related_name="zgloszenia_publikacji"`).

Decyzja architektoniczna: **`Element_Repozytorium` staje się kanonicznym
magazynem plików** (zyskuje `plik` FileField + soft-delete) — DSpace czyta
z jednego miejsca. Workflow kopiowania zaakceptowanego `zglos_publikacje` →
`Element_Repozytorium` (z mapowaniem `forma_dostepu`/`zgoda_na_publikacje_pelnego_tekstu`
→ `tryb_dostepu`) to **osobny PR**, bo dotyka ścieżki akceptacji zgłoszeń.
Do tego czasu `Element_Repozytorium` zapełnia operator ręcznie.

## 11. Otwarte / do potwierdzenia przy implementacji

- **Reconciliation a wersje plików:** identyfikacja bitstreamu jest po
  `Element_Repozytorium.id` (nie po treści). Podmiana *zawartości* tego
  samego pliku (ten sam wiersz, nowy upload) nie jest wykrywana jako zmiana
  — w razie potrzeby dołożyć hash treści do `bitstreams` i porównywać.
  Usunięcie/dodanie/zmiana `tryb_dostepu` — wykrywane (zmiana zbioru id).

- **Jednostki obce / afiliacje zewnętrzne:** autorzy mogą afiliować do
  jednostek spoza „własnych" uczelni (np. „Obca jednostka"). Jeśli taka
  jednostka wskazuje uczelnię bez konfiguracji, domyślnie wygeneruje
  warning. Do ustalenia: czy ostrzegać dla każdej afiliowanej uczelni bez
  configu (zgodnie z dzisiejszą decyzją), czy ograniczyć wachlarz tylko do
  uczelni oznaczonych jako „tenant/własna" (mniej szumu). Domyślnie: wg
  dzisiejszej decyzji — warning dla każdej afiliowanej-a-nieskonfigurowanej.
- Dokładny schemat metadanych docelowego DSpace (czy `dc` wystarcza, czy
  są pola custom) — ustalić z administratorem repozytorium.
- Dokładny endpoint i poziom uprawnień konta API na testowej 9.x.
