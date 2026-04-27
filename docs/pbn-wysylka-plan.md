# Plan: bezpieczna wysyłka publikacji i oświadczeń do PBN

Dokument opisuje plan zmian w mechanizmie wysyłki publikacji z BPP do PBN.
Celem długofalowym jest **rozdzielenie** wysyłki samego dzieła od wysyłki
oświadczeń instytucji, tak aby nieudana wysyłka publikacji nie kasowała
wcześniej istniejących oświadczeń w PBN.

Plan jest **dwufazowy**. Ta gałąź (`feature/pbn-test-wysylka-interaktywna`)
realizuje wyłącznie **Fazę 1** — interaktywne narzędzie CLI służące do
empirycznego zbadania, jak PBN reaguje na poszczególne kroki, zanim
zdecydujemy o kształcie docelowej refaktoryzacji w Fazie 2.

## Kontekst problemu

Gdy w panelu uczelni włączona jest opcja
`uczelnia.pbn_api_kasuj_przed_wysylka=True`, obecny flow w
`PBNClient.sync_publication()`
(`src/pbn_api/client/publication_sync.py:467-539`) wygląda tak:

1. **DELETE** oświadczeń publikacji w PBN
   (`DELETE /api/v1/institutionProfile/publications/{id}` z `all: True`).
2. **POST** publikacji razem z oświadczeniami
   (`POST /api/v1/publications`, JSON zawiera klucz `statements`).
3. **DOWNLOAD** publikacji (`GET /api/v1/publications/id/{id}`).
4. **DOWNLOAD** oświadczeń z PBN i synchronizacja lokalnej tabeli
   `OswiadczenieInstytucji`.

Problem: krok 2 bywa zawodny (HTTP 423 Locked, błąd walidacji, status
PBN „LOGED" itp.). Wtedy DELETE z kroku 1 już się wykonał, a POST z kroku
2 nie wszedł — w PBN zostaje publikacja **bez oświadczeń**, a lokalne dane
też już nie wrócą na profil instytucji bez ręcznego ponownego wysyłu
oświadczeń. User zgłasza utratę oświadczeń w tym scenariuszu.

## Docelowy flow (Faza 2, do zaprojektowania po Fazie 1)

Wstępny zamysł — do weryfikacji przez Fazę 1:

1. POST publikacji przez endpoint **repozytoryjny**
   `POST /api/v1/repositorium/publications` (JSON bez klucza `statements`,
   przepuszczony przez `convert_json_with_statements_to_no_statements()`).
   - FAIL ⇒ zwróć błąd, nie ruszamy oświadczeń. Stan w PBN nietknięty.
   - OK ⇒ mamy `objectId`.
2. GET oświadczeń publikacji w PBN
   (`GET /api/v1/institutionProfile/publications/page/statements?publicationId={objectId}`).
3. Porównanie tego, co jest w PBN, z tym, co wygenerował
   `WydawnictwoPBNAdapter.pbn_get_api_statements()`.
   - identyczne ⇒ koniec, nic nie robimy z oświadczeniami.
   - różne ⇒ DELETE oświadczeń
     (`DELETE /api/v1/institutionProfile/publications/{objectId}` z `all: True`)
     + POST nowych przez
     `POST /api/v2/institution-profile/statements`.
4. DOWNLOAD oświadczeń lokalnie (synchronizacja BPP z PBN,
   reużywa `download_statements_of_publication()`).

Gdy flaga `delete_statements_before_upload=False` — **zachowanie bez zmian**,
stary flow z `/api/v1/publications` pozostaje.

**Niewiadome, które musimy zbadać zanim wdrożymy Fazę 2:**
- Jak PBN zachowuje się po wysyłce do endpointu repozytoryjnego
  w przypadkach, gdy publikacja już istnieje (różne statusy: ACTIVE,
  LOGED itp.).
- Czy `POST /api/v2/institution-profile/statements` wymaga uprzedniego
  DELETE, czy sam potrafi nadpisać istniejący zestaw oświadczeń.
- Czy kolejność GET → porównanie → DELETE+POST jest wystarczająca, czy
  trzeba obsłużyć dodatkowe stany pośrednie.

## Faza 1 — narzędzie CLI (ta gałąź)

### Co powstaje

- `src/pbn_api/management/commands/pbn_test_wysylka_interaktywna.py` —
  interaktywny REPL, który dla wybranej publikacji prowadzi użytkownika
  krok po kroku przez pełen flow wysyłki. Po każdym kroku czeka na
  `Enter` (lub `q` żeby przerwać). Dla każdego żądania HTTP pokazuje
  metodę, URL, body; dla odpowiedzi — status, body (skrócone lub pełne).
- `src/pbn_api/tests/test_pbn_test_wysylka_interaktywna.py` — testy
  jednostkowe z mockiem `input()` i `MockTransport`.
- `src/bpp/newsfragments/+pbn-test-wysylka-interaktywna.feature.rst` —
  changelog towncrier.
- `.docker-build` — pusty plik w root repo, włącza build obrazu
  Docker w CI (patrz `.github/workflows/build-docker-images.yml`).

### Zakres narzędzia

Narzędzie realizuje **tylko operacje zgodne ze specyfikacją PBN API** —
nie podejmuje prób wysyłania JSON-a z kluczem `statements` do endpointu
repozytoryjnego ani innych eksperymentów niezgodnych z API. Zakres
dostępnych kroków:

1. **Pokaż publikację** — wybrany rekord (pk, tytuł, obecny PBN UID,
   liczba oświadczeń lokalnych).
2. **Wygeneruj JSON publikacji** — wywołaj `WydawnictwoPBNAdapter`,
   pokaż czy JSON zawiera klucz `statements`.
3. **Wybierz endpoint publikacji** — `/api/v1/publications` (all-in-one,
   z oświadczeniami jeśli są w JSON) albo `/api/v1/repositorium/publications`
   (wymusza JSON bez oświadczeń przez `convert_json_with_statements_to_no_statements`).
4. **Wyślij POST publikacji** — pokaż URL, body, po wysyłce status i JSON
   odpowiedzi; wyciągnij `objectId`.
5. **Pobierz aktualne oświadczenia z PBN** —
   `GET /api/v1/institutionProfile/publications/page/statements?publicationId={objectId}`.
6. **Porównaj z lokalnymi** — które identyczne, które w PBN nie ma, które
   lokalnie nie ma. Decyzja użytkownika: czy kasować i nadpisywać.
7. **DELETE oświadczeń w PBN** (opcjonalnie) —
   `DELETE /api/v1/institutionProfile/publications/{objectId}` z `all: True`.
8. **POST nowych oświadczeń** (opcjonalnie) —
   `POST /api/v2/institution-profile/statements` z payloadem z
   `WydawnictwoPBNAdapter.pbn_get_api_statements()`.
9. **Podsumowanie** — co poszło, jakie statusy, ile zajęło.

Tryb `--dry-run` pokazuje wszystkie żądania, ale nic nie wysyła.

### Wymagania niefunkcjonalne

- **Nie modyfikuje lokalnej bazy BPP.** Nie tworzy, nie kasuje, nie
  aktualizuje żadnych rekordów BPP (w tym `OswiadczenieInstytucji`,
  `SentData`, `Publication`). Służy wyłącznie do audytu zachowania PBN.
- Reużywa istniejący `PBNClient` i `WydawnictwoPBNAdapter` — nie duplikuje
  logiki budowania JSON ani wysyłki HTTP.
- Obsługa błędów: łapie `HttpException`, `PraceSerwisoweException`,
  `NeedsPBNAuthorisationException`; pokazuje czytelny komunikat i
  pozwala wrócić do menu wyboru (albo wyjść).
- Identyfikacja użytkownika PBN — wzorzec z
  `pbn_wysylka_oswiadczen/tasks.py::get_pbn_client()`.

## Jak testować narzędzie — krok po kroku

Ta sekcja to konkretna instrukcja uruchomienia narzędzia
`pbn_test_wysylka_interaktywna` — zarówno lokalnie, jak i w kontenerze
pre-prod zbudowanym przez CI.

### 1. Testy jednostkowe (bez PBN)

Szybka weryfikacja że narzędzie działa na poziomie kodu — używa
mockowanego transportu, nie wymaga tokena PBN ani dostępu do sieci.

```bash
cd /sciezka/do/worktree
UV_NO_SYNC=1 uv run --all-extras pytest \
    src/pbn_api/tests/test_pbn_test_wysylka_interaktywna.py -n auto
```

Powinieneś zobaczyć `13 passed`.

### 2. Smoke test na preprod PBN (tryb dry-run)

Dry-run pokazuje wszystkie żądania HTTP które *zostałyby* wysłane do
PBN, ale nic nie wysyła. Idealne do weryfikacji że narzędzie widzi
Twoją publikację i poprawnie generuje JSON.

```bash
# Lokalnie (worktree ma własne .venv i testcontainers):
UV_NO_SYNC=1 uv run --all-extras python src/manage.py \
    pbn_test_wysylka_interaktywna \
    --wydawnictwo-zwarte 12345 \
    --dry-run
```

W tym trybie żaden token PBN nie jest wymagany — narzędzie nie wysyła
niczego. Naciskasz Enter między krokami, narzędzie wypisze każde
żądanie (METODA, URL, body).

### 3. Rzeczywisty test na preprod PBN

Gdy upewniłeś się że dry-run wygląda OK, puść bez `--dry-run`. Wymaga
tokena PBN — można go podać przez `--user-token` albo skonfigurować
uczelnię (`Uczelnia.pbn_api_user`) w adminie.

```bash
# Wariant A: token z parametru
UV_NO_SYNC=1 uv run --all-extras python src/manage.py \
    pbn_test_wysylka_interaktywna \
    --wydawnictwo-zwarte 12345 \
    --user-token <TOKEN_PBN>

# Wariant B: token zaciągnięty z Uczelnia.pbn_api_user (automatycznie,
# bez --user-token, jeśli uczelnia ma skonfigurowany pbn_api_user_id)
UV_NO_SYNC=1 uv run --all-extras python src/manage.py \
    pbn_test_wysylka_interaktywna \
    --wydawnictwo-ciagle 67890
```

### 4. Uruchomienie w obrazie Docker zbudowanym przez CI

Po tym jak w tej gałęzi jest plik `.docker-build`, CI buduje obrazy
`iplweb/bpp_appserver:feature-pbn-test-wysylka-interaktywna` (tag =
nazwa brancha, tylko małe litery / kreski). Po zakończeniu buildu:

```bash
# Pobierz obraz:
docker pull iplweb/bpp_appserver:feature-pbn-test-wysylka-interaktywna

# Uruchom narzędzie w kontenerze (zakładam że bpp-deploy już stoi):
docker exec -it <nazwa-kontenera-appserver> \
    python src/manage.py pbn_test_wysylka_interaktywna \
    --wydawnictwo-zwarte 12345 --dry-run
```

### 5. Co robi narzędzie (flow, 8 kroków)

Między każdym krokiem naciskasz **Enter** aby kontynuować albo **q**
żeby przerwać (narzędzie zawsze wypisze podsumowanie na końcu, nawet
po q).

1. **KROK 1/8** — info o publikacji (PK, tytuł, rok, aktualny PBN UID,
   liczba lokalnych `OswiadczenieInstytucji`).
2. **KROK 2/8** — generowanie JSON przez `WydawnictwoPBNAdapter`.
   Narzędzie pokaże czy JSON zawiera klucz `statements` i zapyta czy
   pokazać pełną treść (default: `n`, tylko preview do 600 znaków).
3. **KROK 3/8** — wybór endpointa: `[1]` `/api/v1/publications`
   (all-in-one, wysyła razem z oświadczeniami jeśli są w JSON) albo
   `[2]` `/api/v1/repositorium/publications` (narzędzie usuwa klucz
   `statements` i przepuszcza JSON przez
   `convert_json_with_statements_to_no_statements` — zgodnie ze
   specyfikacją PBN endpoint repozytoryjny nie przyjmuje oświadczeń).
4. **KROK 4/8** — POST publikacji. Narzędzie wypisze URL, body i prosi
   o potwierdzenie. Po sukcesie wyciąga `objectId` z odpowiedzi PBN.
5. **KROK 5/8** — GET aktualnych oświadczeń z PBN dla tego objectId
   (`/api/v1/institutionProfile/publications/page/statements
   ?publicationId={id}`).
6. **KROK 6/8** — porównanie: **intencja BPP na żywo** vs **aktualnie
   w PBN**. „Intencja BPP" to wynik
   `WydawnictwoPBNAdapter.pbn_get_api_statements()` — generowany z
   aktualnych `Wydawnictwo_*_Autor` + dyscyplin, czyli to co BPP
   **wysłałby teraz**. **Nie** używamy lokalnego cache'a
   `OswiadczenieInstytucji` (to snapshot poprzedniej synchronizacji
   *PBN*, nie aktualnej intencji BPP — po skasowaniu autora cache
   zostałby nieaktualny). Narzędzie pokazuje:
   - ile oświadczeń jest identycznych (intencja ∩ PBN),
   - ile jest tylko w intencji (intencja \ PBN, „do dodania"),
   - ile jest tylko w PBN (PBN \ intencja, „do usunięcia").
   Następnie przechodzi do pytań o DELETE i POST (punkty 7-8).
7. **KROK 7/8** — DELETE oświadczeń w PBN
   (`DELETE /api/v1/institutionProfile/publications/{objectId}` z
   `{"all": true, "statementsOfPersons": []}`). Narzędzie **zawsze
   pyta** czy wykonać DELETE, nawet gdy porównanie zwróciło
   identyczność. Domyślna wartość zależy od wyniku KROK 6/8:
   „identyczne" → default `n`, „różnice" → default `t`. Pozwala to
   wymusić DELETE dla testowania reakcji PBN.
8. **KROK 8/8** — POST nowych oświadczeń
   (`POST /api/v2/institution-profile/statements` z payloadem z
   `WydawnictwoPBNAdapter.pbn_get_api_statements()`). Retry ×3 dla
   HTTP 500/423 z exponential backoff. **Zawsze pyta** — jak w
   KROK 7/8 — z domyślną wartością zależną od identyczności.

Narzędzie wypisuje **PODSUMOWANIE** z wynikami każdego kroku (OK /
dry-run / pominięty / BŁĄD HTTP XXX).

### 6. Co sprawdzać ręcznie w preprod (checklist)

Cel Fazy 1: zebrać empiryczne obserwacje zachowania PBN przed
decyzjami projektowymi Fazy 2.

- [ ] **Publikacja z PBN UID + oświadczeniami lokalnymi**, wysłana
  opcją `[1]` (`/api/v1/publications`) — potwierdzenie że PBN
  zaakceptuje JSON z `statements` (znany case, weryfikacja baseline).
- [ ] **Ta sama publikacja** wysłana opcją `[2]`
  (`/api/v1/repositorium/publications` bez `statements` w JSON) —
  czy PBN zaakceptuje? Jaki jest `status` publikacji po wysyłce?
  Czy oświadczenia wcześniej skojarzone z publikacją pozostają
  nietknięte?
- [ ] **Sekwencja** opcja `[2]` → GET oświadczeń → jeśli się różnią,
  `t` na DELETE → POST `/v2/statements`. Ma to być docelowy flow
  Fazy 2 — chcemy wiedzieć że PBN jest z tym OK.
- [ ] **Edge case** — publikacja ze statusem "LOGED" (jeśli
  napotkamy): co zwraca GET? Czy DELETE działa? Co zwraca POST
  `/v2/statements`?
- [ ] **Publikacja bez PBN UID (nowa)** — opcja `[1]` powinna
  zwrócić nowy `objectId`. Opcja `[2]` też (`.../repositorium`).
- [ ] **Publikacja bez oświadczeń lokalnych** — porównanie w KROK 6/8
  ma pokazać że lokalne są puste, a więc nie ma o czym rozmawiać.

Obserwacje notujemy w osobnym pliku `docs/pbn-wysylka-eksperymenty.md`
(tworzony w osobnym PR), żeby były bazą do decyzji w Fazie 2.

### 7. Rozwiązywanie problemów

- **`NeedsPBNAuthorisationException`** — brak tokena PBN. Podaj
  `--user-token <TOKEN>` albo skonfiguruj `Uczelnia.pbn_api_user_id`
  (Django admin → Redagowanie → Uczelnia).
- **`BrakZdefiniowanegoObiektuUczelniaWSystemieError`** — stwórz
  obiekt Uczelnia w adminie (tylko raz na instalację).
- **`DaneLokalneWymagajaAktualizacjiException`** w KROK 8/8 — brak
  lokalnego `PublikacjaInstytucji_V2` dla tego PBN UID. Pobierz
  ręcznie przez
  `python src/manage.py pbn_pobierz_publikacje_z_instytucji_v2
  --user-token <TOKEN>` albo wyślij publikację najpierw opcją `[1]`
  (PBN wtedy zwróci PublikacjaInstytucji_V2, a my ją pobierzemy).
- **`HttpException 423 Locked`** przy POST — publikacja lub zasób
  zablokowany w PBN. Poczekaj chwilę i spróbuj ponownie (dla POST
  `/v2/statements` narzędzie ma wbudowany retry ×3).
- **Pliki migracji** — jeśli podczas pytest widzisz konflikt leaf
  nodes w `importer_publikacji`, zrób
  `uv run python src/manage.py makemigrations --merge --noinput`
  (nie modyfikuje istniejących migracji, dodaje nową merge-ową).

## Faza 2 — refaktoryzacja `sync_publication` (**zaimplementowana, PR #164**)

Refaktoryzacja została wykonana na tej samej gałęzi
`feature/pbn-test-wysylka-interaktywna` (8 commitów, cała seria w PR #164).
Narzędzie CLI `pbn_test_wysylka_interaktywna` zostaje jako diagnostyka —
aktualna `sync_publication` ma tą samą logikę wewnętrznie.

### Flow docelowy (zaimplementowany)

1. `upload_publication(rec, ...)` → ZAWSZE `POST /api/v1/repositorium/publications`
   (`post_publication_no_statements`), niezależnie od obecności oświadczeń
   w JSON. Konwersja przez `convert_json_with_statements_to_no_statements()`.
2. `download_publication(objectId)` + update `SentData.pbn_uid`.
3. Obsługa zmiany/konfliktu PBN UID (`_handle_uid_change`/`_conflict`).
4. `_download_statements_with_retry()` — best effort odświeżenie lokalnego
   cache `OswiadczenieInstytucji` + pobranie `PublikacjaInstytucji_V2`
   (potrzebne dla `pbn_get_api_statements`). Błąd tutaj = warning log,
   flow kontynuuje.
5. `_sync_statements_with_pbn(rec, objectId, kasuj_selektywnie)`:
   - GET aktualnych oświadczeń z PBN (retry x3 + rollbar + raise
     `StatementsResendFailedException` po wyczerpaniu).
   - Diff z `pbn_get_json_statements()` — klucz `(person mongoId, dyscyplina numerek)`.
   - Selektywny DELETE per-osoba (`delete_publication_statement(pub_id, personId, role)`)
     gdy `Uczelnia.pbn_kasuj_dyscypliny_selektywnie=True` (default),
     batch `delete_all_publication_statements` gdy `False`.
   - POST batch `/api/v2/institution-profile/statements` dla brakujących.
   - Każdy krok z retry x3 + rollbar level=warning + `StatementsResendFailedException`.

### Zmiany modelu

- Usunięto `Uczelnia.pbn_api_kasuj_przed_wysylka` (migracja 0414).
- Dodano `Uczelnia.pbn_kasuj_dyscypliny_selektywnie` BooleanField default=True.
- Zachowano `Uczelnia.pbn_wysylaj_bez_oswiadczen` (semantyka: odmawia
  wysyłki publikacji bez oświadczeń — walidacja w adapterze `pbn_get_json`).

### Nowy wyjątek

`pbn_api.exceptions.StatementsResendFailedException(publication_pk, pbn_uid, last_error)`
— podnoszony po wyczerpaniu retry dla GET/DELETE/POST oświadczeń.
Klasyfikowany w `pbn_export_queue._handle_retry_exception` jako
`RETRY_LATER`.

### Historia commitów (PR #164)

1. Exception class + model Uczelnia + migracja + admin
2. Dead code removal (`post_publication`, `_should_retry_validation_error`,
   `_retry_download_publication`) + bug fix `_delete_statements_with_retry`
   (`< 0` → `<= 0`)
3. Helpery: `_diff_statements`, `_get_pbn_statements_with_retry`,
   `_delete_statements_selective`, `_delete_statements_batch`,
   `_post_statements_with_retry`, `_sync_statements_with_pbn`
4. Refaktoryzacja `sync_publication` (nowy split flow)
5. Aktualizacja callerów (usunięcie `delete_statements_before_upload`)
6. Aktualizacja 5 plików testowych (37 testów, nowe scenariusze)
7. Handling `StatementsResendFailedException` w `pbn_export_queue` + test
8. Changelog + docs

## Wymagania CI

- `.docker-build` w root repo ⇒ CI buduje obraz Docker dla tej gałęzi,
  tak by user mógł uruchomić narzędzie w środowisku testowym.
- Pełny pipeline (`tests.yml`): lint + testy (non-playwright, serial,
  playwright) muszą przejść.
- Build Docker odpala się **raz** na commit (push do master lub
  event pull_request) — od zmiany z 2026-04-21 push do
  feature/fix/hotfix nie triggeruje już buildu (tylko PR events),
  żeby uniknąć duplikatów.
