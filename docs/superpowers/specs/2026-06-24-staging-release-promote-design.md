# Spec: staging-release → promote (wydania dwufazowe, CLI)

Data: 2026-06-24
Status: **do akceptacji**
Autor: brainstorming (Claude) + Michał Pasternak

## 1. Problem

Dziś wydanie to jednofazowy `make release` (lokalnie) albo świeżo dodany
`release.yml` (CI). Oba **od razu** mintują wersję FINAL, mergują do `master`
i ruszają produkcyjny tag obrazu `:latest`. Serwer **staging pulluje `:latest`**
— czyli nie ma żadnej szczeliny między staging a produkcją: w momencie gdy na
stagingu okazuje się, że „jest kupa", `:latest` już się ruszył i produkcja może
pullnąć ten sam zepsuty obraz.

Cel: móc zbudować **kandydata** (release candidate), wdrożyć go na staging,
przetestować, a dopiero **na żądanie z CLI** podnieść go do statusu produkcyjnego
— **bez przebudowy obrazu** (te same bajty, które przeszły staging, lądują na
produkcji).

## 2. Zasady przewodnie

1. **Build once, promote the artifact.** Produkcja dostaje *dokładnie* ten digest,
   który przeszedł staging. Promocja = przepięcie metadanych tagu w rejestrze
   (`docker buildx imagetools create`), nigdy rebuild. To eliminuje całą klasę
   „na stagingu działało".
2. **Rozdzielenie kanałów deployu.** Staging i produkcja ciągną **różne ruchome
   tagi**: staging `:staging`, produkcja `:latest`. Bez tego nie ma czego
   promować.
3. **Wszystko z CLI (`gh`), zero przycisków.** Dwie komendy w cyklu życia:
   utnij RC, potem promuj.
4. **Jeden workflow = jedna rola.** Pełny refaktor klastra build/release zamiast
   doklejania nakładających się plików.

## 3. Cykl życia (UX docelowy)

```bash
# 1) Utnij kandydata → buduje 5 obrazów, przesuwa :staging, NIE rusza :latest
gh workflow run release-candidate.yml --ref dev
#    → wersja v202606.1392-rc1; obrazy :202606.1392rc1 (pep440) + :staging

# … staging pulluje :staging, testujesz …

# 2a) Staging OK → promuj: finalizacja + master + przepięcie :latest (imagetools)
gh workflow run promote.yml --ref dev
#    → v202606.1392 (final), merge→master, tag git, back-merge→dev,
#      :202606.1392rc1 → :latest + :202606.1392 (BEZ rebuildu)

# 2b) Staging = kupa → fix na dev, potem znów cut-RC (numer finalny niespalony):
gh workflow run release-candidate.yml --ref dev
#    → wersja v202606.1392-rc2; obraz :202606.1392rc2; :staging przesunięty
```

Podgląd: `gh run watch $(gh run list --workflow=<plik> -L1 --json databaseId --jq '.[0].databaseId')`.

## 4. Taksonomia tagów obrazów (WAŻNE — rozłączne pojęcia)

**Wszystkie docker-tagi wersyjne w formie pep440 bumpvera** (bez `v`, bez
myślnika przed `rc`): `202606.1392rc1`, `202606.1392`. To ta sama forma, którą
bumpver wpisuje do `DOCKER_VERSION` w Makefile / `version.py` / `package.json`,
więc build i promote zawsze nazywają obraz tak samo. Git-tagi natomiast mają
formę wersji-stringa (`v202606.1392`); RC nie dostaje git-tagu (tylko gałąź).

| Tag | Rodzaj | Kto pisze | Kto czyta |
|---|---|---|---|
| `sha-<commit>` | **build-staging** (izolacja builda + brama Trivy) | silnik build | tylko promocja wewnątrz builda |
| `:202606.1392rc1` | **immutable RC** (pep440) | silnik build (po Trivy) | promote (źródło) |
| `:staging` | **kanał deployu — staging** (ruchomy) | silnik build (przy cut-RC) | serwer staging |
| `:202606.1392` | **immutable final** (pep440) | promote (imagetools) | deploy po wersji |
| `:latest` | **kanał deployu — produkcja** (ruchomy) | promote (imagetools) | serwer produkcyjny |

Uwaga: dotychczasowy `sha-<commit>` to izolacja builda (żeby Trivy mógł
zablokować zanim powstanie kanoniczny tag), a NIE kanał deployu. Nowy `:staging`
to kanał deployu. To dwa różne byty — nie mylić.

## 5. Przepływ gita i wersji

```
dev ──┬─────────────────────────────────────────────► dev
      │ cut-RC (release-candidate.yml)                ▲
      └──► release/v202606.1392 ──[rc1]──[rc2]──┐     │ back-merge "Merge tag …"
                                                 │     │
                                          promote.yml  │
                                                 ▼     │
                                              master ──┴──► tag v202606.1392
```

- **Gałąź `release/v<BASE>`** żyje od pierwszego cut-RC do promote. Trzyma stan
  numeru RC (przez `current_version` bumpvera) i jest kontrolowaną powierzchnią
  wydania. Po promote jest kasowana.
- **Wersje (bumpver, wzorzec `vYYYY0M.BUILD[-TAGNUM]`):**
  > ⚠️ **`BUILD` auto-inkrementuje się przy KAŻDYM `bumpver update`** (zweryfikowane
  > empirycznie: `--tag rc --tag-num` z `1393` → `1394rc0`, kolejny `--tag-num` →
  > `1395rc0`, `--tag final` → `1397`). Dlatego `--tag rc/--tag-num/--tag final`
  > **NIE** nadaje się do iteracji RC — BASE by dryfował, a numer rc nie rósł.
  > Stąd liczymy BASE **raz** i sterujemy każdym krokiem przez `--set-version`:
  - pierwszy cut-RC: policz BASE raz — `BASE = bumpver test v<CUR> '...' | PEP440`
    (np. z `1393` → `1394`), potem `bumpver update --set-version "v<BASE>-rc1"`.
  - kolejny cut-RC (gałąź `release/*` istnieje): odczytaj bieżący pep440, wyłuskaj
    `BASE` (strip `rc\d+`) i `RCN`, `bumpver update --set-version "v<BASE>-rc<RCN+1>"`.
  - promote: `bumpver update --set-version "v<BASE>"` (BASE z nazwy gałęzi). BASE
    stały przez rc1→rc2→final; finalna wersja = testowany RC. **Nie re-datuje**
    (BASE policzony przy starcie cyklu), więc RC z czerwca promowany w lipcu
    pozostaje `202606.<BASE>`.

## 6. Workflowy — stan docelowy

### 6.1 `build-docker-images.yml` → silnik build (reusable)

Refaktor obecnego pliku. Staje się **`workflow_call`** (zachowuje też
`workflow_dispatch` dla ad-hoc i `pull_request` dla walidacji buildów).

- **USUWA** trigger `push: master` (i całą logikę „promote do `:latest` na push
  mastera"). Od teraz produkcyjny `:latest` rusza **wyłącznie** `promote.yml`
  przez imagetools — jedno źródło prawdy o produkcji.
- **Inputs** (`workflow_call`):
  - `ref` — git ref do zbudowania (gałąź `release/v…`).
  - `version_tag` — immutable tag do wypchnięcia (np. `202606.1392-rc1`).
  - `channel` (opcjonalny) — dodatkowy ruchomy tag (np. `staging`).
  - `run_trivy` (bool, default `true`) — brama CRITICAL.
- **Outputs:** mapa digestów per obraz (do pinowania przez wołającego).
- **Zachowuje** wewnętrzny wzorzec: build → `sha-<commit>` → Trivy gate (CRITICAL
  fail / HIGH report) → promote `sha-*` na `version_tag` (+ `channel` jeśli
  podany). **Nie dotyka** `:latest` ani kanonicznego final.

### 6.2 `release-candidate.yml` (przepisany `release.yml`)

`workflow_dispatch` (inputs: `skip_tests`, `skip_scan` jak dziś). Przebieg:

1. Ustal gałąź wydania (wersje przez `--set-version`, patrz §5):
   - brak otwartej `release/*` → policz BASE (`bumpver test`), `git switch -C
     release/v<BASE> origin/dev`, `bumpver update --set-version "v<BASE>-rc1"`.
   - istnieje otwarta `release/*` → checkout jej, `git merge --no-ff origin/dev`
     (podbiera fixy z dev — patrz §8 caveat o scope-creep), wylicz `BASE`/`RCN`
     z bieżącej wersji, `bumpver update --set-version "v<BASE>-rc<RCN+1>"`.
2. `uv lock` + commit (zamrożenie deps RC).
3. **Skan CVE** (`./bin/scan-deps.sh`, gate) — chyba że `skip_scan`. (Towncriera
   tu NIE ma — changelog składa się raz, przy promote; patrz §8.)
4. **Testy** — pełna suita pytest na obrazie test-runner (jak dziś) — chyba że
   `skip_tests`.
5. `git push origin release/v<BASE>`.
6. Wywołaj `build-docker-images.yml` (`workflow_call`) z `ref=release/v<BASE>`,
   `version_tag=<BASE>rcN` (pep440, np. `202606.1392rc1` — silnik i tak czyta
   `DOCKER_VERSION` z Makefile, który bumpver już ustawił na tę formę),
   `channel=staging`.

Master/dev/`:latest` **nietknięte**.

### 6.3 `promote.yml` (nowy — „druga komenda")

`workflow_dispatch`. Input opcjonalny `version` (np. `v202606.1392`) — bezpiecznik
gdy otwartych jest >1 gałęzi `release/*`. Przebieg:

1. Znajdź otwartą `release/*`:
   - 0 → błąd „brak otwartego wydania do promocji".
   - >1 i brak `version` → błąd „podaj -f version=…".
   - dokładnie 1 (lub wskazana) → checkout.
2. Odczytaj bieżącą wersję RC z gałęzi → docker-tag pep440 (np. `202606.1392rc2`)
   — to **immutable źródło** obrazów do promocji (istnieje od cut-RC; nie trzeba
   digestów, immutable tag wystarcza).
3. `bumpver update --set-version "v<BASE>"` (NIE `--tag final` — bumpnąłby BUILD,
   rozjeżdżając finalną wersję z testowanym RC) → `202606.1392`. Commit.
   Przed mutacją mastera: **pre-flight** `imagetools inspect` że obrazy `:<RC>`
   istnieją (inaczej half-applied release).
4. `towncrier build --yes` (konsumuje newsfragmenty, final changelog). Commit.
   `|| true` jak w Makefile (brak fragmentów ≠ błąd).
5. `git switch -C _master origin/master`; `git merge --no-ff release/v<BASE>
   -m "Release v<BASE>"`; `git tag -a v<BASE> -m "Release v<BASE>"`.
6. `git switch -C _dev origin/dev`; `git merge --no-ff v<BASE> -m "Merge tag
   'v<BASE>' into dev"` (komunikat, który `tests.yml` celowo pomija na dev).
7. `git push origin _master:master _dev:dev refs/tags/v<BASE>
   :refs/heads/release/v<BASE>` (push master+dev+tag, skasuj gałąź wydania).
8. **Promote obrazów (imagetools, bez rebuildu):** dla każdego z 5 obrazów
   `docker buildx imagetools create -t <repo>:<BASE> -t <repo>:latest
   <repo>:<BASE>rcN` (pep440, np. `202606.1392rc2`).
9. (Trivy NIE jest powtarzany — bramowano przy cut-RC; te same bajty.)

## 7. Mapa workflowów po zmianie

| Workflow | Trigger | Rola | Zmiana |
|---|---|---|---|
| `tests.yml` | push dev/master, PR dev | lint+testy+baseline+js | bez zmian (+ istniejący skip release-commita na master) |
| `dependency-audit.yml` | push/PR (deps), cron | CVE PR/scheduled | bez zmian |
| `docs.yml` | push/PR (docs) | MkDocs | bez zmian |
| `refresh-baseline.yml` | push dev (migrations) | baseline.sql | bez zmian |
| `sync-dockerhub.yml` | push master (DOCKERHUB.md) | opisy DH | bez zmian |
| `claude.yml` | komentarze | bot | bez zmian |
| `build-docker-images.yml` | **workflow_call**, dispatch, PR | **silnik build (reusable)** | refaktor: usuń push:master+promote-do-latest; dodaj inputs/outputs |
| `release-candidate.yml` | dispatch | **cut RC → staging** | przepisany z `release.yml` |
| `promote.yml` | dispatch | **RC → produkcja (imagetools)** | nowy |

Netto: liczba plików 8 → 9 (dochodzi `promote.yml`), ale tangiel build/release
znika — każdy plik ma jedną rolę.

## 8. Decyzje i caveaty

- **Towncrier przy promote, nie przy RC.** Inaczej rc1 zjadłby newsfragmenty i
  rc2 by się wywalił („already consumed") + rozjazd usunięć na gałęzi wydania.
  Changelog dotyczy wersji finalnej, więc składamy go raz, w promote.
- **rc2 = `release/* + merge dev`.** Podbiera fixy z dev. Ryzyko scope-creep
  (nowe, niezwiązane zmiany z dev wejdą do wydania) — akceptowane, bo dziś
  `make release` i tak wydaje „cokolwiek jest na dev". Alternatywa (cherry-pick
  fixów wprost na `release/*`) jest możliwa, ale poza zakresem v1.
- **Pliki wersji są własnością bumpvera — nie edytować ręcznie na dev.**
  `pyproject.toml` (`current_version`/`version`), `version.py`, `package.json`,
  `Makefile` (`DOCKER_VERSION`) zmieniają WYŁĄCZNIE candidate/promote przez
  bumpver. Dzięki temu `merge dev → release/*` (rc2) i back-merge `→ dev`
  (promote) nie konfliktują na linii wersji: tylko jedna strona kiedykolwiek
  zmienia te linie względem merge-base. Ręczna edycja wersji na dev złamałaby
  to założenie i wprowadziła konflikty — jest zabroniona.
- **`push: master` znika z buildu.** Każda zmiana produkcyjnego obrazu idzie
  przez promote (imagetools z gotowego RC). Hotfix „wprost na master" NIE
  przebuduje `:latest` — to świadome (build-once-promote). Awaryjny build:
  `gh workflow run build-docker-images.yml` ręcznie.
- **CVE-skan: warstwy zostają.** `release-candidate` używa `bin/scan-deps.sh`
  (komplet OSV/Grype/Trivy/pip-audit, gate — parytet z `make release`).
  `dependency-audit.yml` niezależnie pokrywa PR/cron. Overlap jest świadomym
  defense-in-depth (już udokumentowanym w repo). Opcja na przyszłość: zrobić
  `dependency-audit.yml` reusable i wołać go z RC zamiast `scan-deps.sh` — poza
  zakresem v1.
- **GITHUB_TOKEN / triggery.** Promote nie polega na auto-triggerze (push
  master tokenem i tak by nie wyzwolił), promocja obrazów jest inline (imagetools).
- **Branch protection na `master`.** Jeśli master odrzuca push z Actions —
  dodać fine-grained `RELEASE_PAT` (contents:write) i podmienić `token:` w
  checkout/push promote (opisane analogicznie jak w dzisiejszym `release.yml`).
- **Concurrency.** `release-candidate` i `promote` współdzielą grupę `release`
  (cancel-in-progress: false) — nie przeplatają się.

## 9. Co MUSI zrobić user (poza CI)

**Przed pierwszym promote:** zmienić deploy stagingu, żeby pullował `:staging`
(wszystkie 5 obrazów: appserver, workerserver, beatserver, authserver,
denorm-queue) zamiast `:latest`. Produkcja zostaje na `:latest`.

## 10. Plan wdrożenia

1. Zmerge'uj nowe/zmienione workflowy na `dev` (rejestracja `workflow_dispatch`).
2. Przełącz staging na `:staging`.
3. `gh workflow run release-candidate.yml` → zweryfikuj obrazy `:staging` + RC.
4. Test na stagingu.
5. `gh workflow run promote.yml` → zweryfikuj, że `:latest` ma **ten sam digest**
   co `:202606.1392rc1` (dowód build-once-promote):
   `docker buildx imagetools inspect <repo>:latest` vs `…:<BASE>rcN` (pep440).

## 11. Poza zakresem (YAGNI)

- GitHub Environments / bramka approval (user odrzucił — chce CLI).
- Blue-green / canary na produkcji, automatyczny rollback.
- Wiele równoległych środowisk staging.
- Changelog per-RC (tylko final).
- Cherry-pick fixów na `release/*` (v1: merge dev).
