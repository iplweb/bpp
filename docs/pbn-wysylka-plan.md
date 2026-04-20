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
   przepuszczony przez `convert_js_with_statements_to_no_statements()`).
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
   (wymusza JSON bez oświadczeń przez `convert_js_with_statements_to_no_statements`).
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

### CLI argumenty

```
uv run python src/manage.py pbn_test_wysylka_interaktywna \
    --wydawnictwo-zwarte <PK>       # albo --wydawnictwo-ciagle <PK>
    --user <USERNAME>               # użytkownik z tokenem PBN
    [--dry-run]                     # nic nie wysyłaj
```

## Faza 2 — refaktoryzacja `sync_publication` (osobna gałąź)

Po ręcznych testach narzędziem z Fazy 1 i udokumentowaniu wyników
(osobny dokument `docs/pbn-wysylka-eksperymenty.md` w kolejnym PR)
implementujemy docelowy flow w `src/pbn_api/client/publication_sync.py`.
Plan dla Fazy 2 — szczegóły po zebraniu obserwacji z eksperymentów.

## Testowanie (Faza 1)

```bash
# Testy narzędzia (unit):
UV_NO_SYNC=1 uv run --all-extras pytest \
    src/pbn_api/tests/test_pbn_test_wysylka_interaktywna.py -n auto

# Smoke test na preprod PBN (ręczny):
uv run python src/manage.py pbn_test_wysylka_interaktywna \
    --wydawnictwo-zwarte <PK> --user <USERNAME> --dry-run
# a potem bez --dry-run, na rzeczywistej publikacji w preprod
```

## Wymagania CI

- `.docker-build` w root repo ⇒ CI buduje obraz Docker dla tej gałęzi,
  tak by user mógł uruchomić narzędzie w środowisku testowym.
- Pełny pipeline (`tests.yml`): lint + testy (non-playwright, serial,
  playwright) muszą przejść.
